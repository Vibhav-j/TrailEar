"""Pipeline wiring: Audio Source -> Classifier -> Detection Manager -> Sinks."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from trailear.detect.manager import DetectionManager

if TYPE_CHECKING:
    from pathlib import Path

    from trailear.classify.base import Classifier
    from trailear.types import Detection, Window
    from trailear.voice.tts import TTS

logger = logging.getLogger(__name__)


def make_storage_sink(
    walk_id: int,
    db_path: Path | str | None = None,
) -> Callable[[Detection], None]:
    """Create a sink callable that records announced detections in SQLite."""
    from trailear.storage.db import add_sighting

    def _storage_sink(detection: Detection) -> None:
        try:
            add_sighting(
                walk_id=walk_id,
                scientific_name=detection.scientific_name,
                common_name=detection.common_name,
                confidence=detection.confidence,
                t_offset_s=detection.t,
                db_path=db_path,
            )
        except Exception:
            logger.exception("Failed to record sighting in database")

    return _storage_sink


def make_tts_sink(
    tts: TTS,
    speak_only_new_species: bool = True,
    chime_on_rare: bool = True,
) -> Callable[[Detection], None]:
    """Create a sink callable that speaks announced detections via TTS.

    - Speaks the common name only.
    - If speak_only_new_species is True, each species is only spoken once per walk session.
    - If chime_on_rare is True, plays a short chime before speaking if the species is rare.
    """
    from trailear.storage.db import lookup_species

    spoken_species: set[str] = set()

    def _tts_sink(detection: Detection) -> None:
        try:
            if speak_only_new_species and detection.scientific_name in spoken_species:
                return

            spoken_species.add(detection.scientific_name)

            if chime_on_rare:
                results = lookup_species(detection.scientific_name)
                if results and results[0].get("rarity") == "rare":
                    tts.play_chime()

            tts.speak(detection.common_name)
        except Exception:
            logger.exception("Error in TTS sink")

    return _tts_sink


class Pipeline:
    """Threaded audio processing pipeline.

    Spawns:
    - A capture thread that iterates through audio windows and enqueues them.
    - A classifier worker thread that dequeues windows, runs the classifier,
      passes results through the DetectionManager, and fans out announced
      detections to all registered sinks.
    """

    def __init__(
        self,
        source,
        classifier: Classifier,
        manager: DetectionManager | None = None,
        sinks: list[Callable[[Detection], None]] | None = None,
        max_queue_size: int = 50,
    ) -> None:
        self.source = source
        self.classifier = classifier
        self.manager = manager or DetectionManager()
        self.sinks: list[Callable[[Detection], None]] = sinks or []

        self._queue: queue.Queue[Window | None] = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._classifier_thread: threading.Thread | None = None
        self._announced: list[Detection] = []
        self._lock = threading.Lock()

    @property
    def announced(self) -> list[Detection]:
        """List of all announced detections emitted during this pipeline run."""
        with self._lock:
            return list(self._announced)

    def _capture_loop(self) -> None:
        """Capture audio windows and push them into the queue."""
        try:
            for window in self.source.windows():
                if self._stop_event.is_set():
                    break
                self._queue.put(window)
        except Exception:
            logger.exception("Error in capture thread")
        finally:
            self._queue.put(None)  # Sentinel to terminate classifier worker

    def _classifier_loop(self) -> None:
        """Consume audio windows, run classification, and notify sinks."""
        while not self._stop_event.is_set():
            try:
                window = self._queue.get()
                if window is None:
                    break

                try:
                    detections = self.classifier.classify(window)
                except Exception:
                    logger.exception("Classifier error on window at t=%.1f", window.t_start)
                    continue

                for d in detections:
                    announced_d = self.manager.process_detection(d, t=window.t_start)
                    if announced_d is not None:
                        with self._lock:
                            self._announced.append(announced_d)
                        for sink in self.sinks:
                            try:
                                sink(announced_d)
                            except Exception:
                                logger.exception("Error in sink execution")
            except Exception:
                logger.exception("Unexpected error in classifier worker loop")

    def start(self) -> None:
        """Start the capture and classifier threads."""
        self._stop_event.clear()
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="AudioCaptureThread",
            daemon=True,
        )
        self._classifier_thread = threading.Thread(
            target=self._classifier_loop,
            name="ClassifierWorkerThread",
            daemon=True,
        )
        self._capture_thread.start()
        self._classifier_thread.start()

    def stop(self) -> None:
        """Request pipeline stop and wait for threads to exit."""
        self._stop_event.set()
        # If source has a stop method (e.g. MicSource), invoke it
        if hasattr(self.source, "stop") and callable(self.source.stop):
            try:
                self.source.stop()
            except Exception:  # noqa: BLE001, S110
                pass

        # If classifier loop is waiting on queue, wake it up
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self.join()

    def join(self, timeout: float | None = None) -> None:
        """Wait for worker threads to finish."""
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=timeout)
        if self._classifier_thread and self._classifier_thread.is_alive():
            self._classifier_thread.join(timeout=timeout)

    def run(self) -> list[Detection]:
        """Run the pipeline synchronously until the audio source is exhausted."""
        self.start()
        self.join()
        return self.announced
