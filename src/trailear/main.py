"""CLI entry points for TrailEar."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _get_classifier():
    """Get the appropriate classifier based on config."""
    from trailear.config import config

    if config.classifier.backend == "mock":
        from trailear.classify.mock import MockClassifier

        return MockClassifier()

    # Try BirdNET, fall back to mock
    try:
        from trailear.classify.birdnet import BirdNETClassifier, is_available

        if not is_available():
            print("[INFO] birdnetlib not installed, falling back to MockClassifier")
            from trailear.classify.mock import MockClassifier

            return MockClassifier()
        return BirdNETClassifier()
    except (ImportError, ModuleNotFoundError):
        print("[INFO] birdnetlib not installed, falling back to MockClassifier")
        from trailear.classify.mock import MockClassifier

        return MockClassifier()
    except Exception as exc:  # noqa: BLE001
        print(f"[INFO] BirdNET unavailable ({exc}), falling back to MockClassifier")
        from trailear.classify.mock import MockClassifier

        return MockClassifier()


def cmd_file(path: str) -> None:
    """Run the classifier over a WAV file and print detections."""
    wav_path = Path(path)
    if not wav_path.exists():
        print(f"Error: file not found: {wav_path}")
        sys.exit(1)

    from trailear.audio.capture import FileSource
    from trailear.config import config
    from trailear.detect.manager import DetectionManager
    from trailear.pipeline import Pipeline, make_storage_sink
    from trailear.storage.db import end_walk, start_walk

    classifier = _get_classifier()
    source = FileSource(wav_path)

    # Create a walk record
    walk_id = start_walk(lat=config.location.lat, lon=config.location.lon)
    storage_sink = make_storage_sink(walk_id)

    manager = DetectionManager()
    pipeline = Pipeline(
        source=source,
        classifier=classifier,
        manager=manager,
        sinks=[storage_sink],
    )

    announced = pipeline.run()
    end_walk(walk_id)

    if not announced:
        print(f"\nNo qualifying detections announced. (Walk #{walk_id} recorded)")
        return

    print(f"\n{'Species':<35} {'Confidence':>10}  {'Time (s)':>8}")
    print("-" * 58)
    for d in announced:
        print(f"{d.common_name:<35} {d.confidence:>10.2f}  {d.t:>8.1f}")

    unique_count = len({d.scientific_name for d in announced})
    print(
        f"\nWalk #{walk_id} recorded: {len(announced)} sightings announced, "
        f"{unique_count} unique species."
    )


def cmd_walk(pocket: bool = False, file_path: str | None = None) -> None:
    """Start a walk session in live mic mode or simulated file mode."""
    from trailear.config import config
    from trailear.detect.manager import DetectionManager
    from trailear.pipeline import Pipeline, make_storage_sink, make_tts_sink
    from trailear.storage.db import end_walk, get_walk, start_walk
    from trailear.voice.tts import get_tts

    if file_path is not None:
        p = Path(file_path)
        if not p.exists():
            print(f"Error: file not found: {file_path}")
            sys.exit(1)
        from trailear.audio.capture import FileSource

        source = FileSource(p)
        is_live = False
    else:
        from trailear.audio.capture import MicSource

        try:
            source = MicSource()
        except RuntimeError as err:
            print(f"Error: {err}")
            sys.exit(1)
        is_live = True

    classifier = _get_classifier()
    tts = get_tts()

    walk_id = start_walk(lat=config.location.lat, lon=config.location.lon)

    # Voice cue: "Walk started"
    tts.speak("Walk started")

    mode_label = "Pocket Mode" if pocket else "Walk Mode"
    print(f"\n=== TrailEar {mode_label} (Walk #{walk_id}) ===")
    if is_live:
        print("Listening via microphone... (Press Ctrl+C to stop)")
    else:
        print(f"Processing audio from {file_path}... (Press Ctrl+C to stop)")

    storage_sink = make_storage_sink(walk_id)
    tts_sink = make_tts_sink(
        tts,
        speak_only_new_species=config.pocket_mode.speak_only_new_species,
        chime_on_rare=config.pocket_mode.chime_on_rare,
    )

    def console_sink(d):
        print(f"  [HEARD] {d.common_name} ({d.confidence:.2f}) at {d.t:.1f}s")

    sinks = [storage_sink, tts_sink, console_sink]

    pipeline = Pipeline(
        source=source,
        classifier=classifier,
        manager=DetectionManager(),
        sinks=sinks,
    )

    pipeline.start()
    try:
        if is_live:
            while True:
                time.sleep(0.5)
        else:
            pipeline.join()
    except KeyboardInterrupt:
        print("\nStopping walk...")
    finally:
        pipeline.stop()
        end_walk(walk_id)

    # Post-walk spoken announcement
    walk = get_walk(walk_id)
    species_seen = {s.common_name for s in walk.sightings} if walk else set()
    n_species = len(species_seen)

    if n_species == 1:
        tts.speak("Walk ended. One species heard.")
    else:
        tts.speak(f"Walk ended. {n_species} species heard.")

    # Brief delay for TTS thread to queue final speech
    time.sleep(0.5)

    print("\n" + "=" * 50)
    print(f"Walk #{walk_id} Summary")
    if walk:
        print(f"Started: {walk.started_at}")
        print(f"Ended:   {walk.ended_at}")
        print(f"Total Sightings: {len(walk.sightings)}")
        print(f"Species Heard ({n_species}):")
        for sp in sorted(species_seen):
            print(f"  * {sp}")
    print("=" * 50 + "\n")

    # Generate journal automatically after walk (quiet skip if LLM unavailable)
    try:
        from trailear.llm.journal import generate_and_save_journal

        journal = generate_and_save_journal(walk_id)
        if journal:
            print("--- Field Journal ---")
            print(journal)
            print("-" * 50 + "\n")
    except Exception as err:  # noqa: BLE001
        print(f"[INFO] LLM unavailable ({err}). Journal generation skipped.")
        print(f"Run 'python -m trailear journal {walk_id}' to generate later.")


def cmd_journal(walk_id: int) -> None:
    """Generate and store a field journal for a completed walk."""
    from trailear.llm.journal import generate_and_save_journal
    from trailear.storage.db import get_walk

    walk = get_walk(walk_id)
    if walk is None:
        print(f"Error: walk #{walk_id} not found.")
        sys.exit(1)

    print(f"Generating journal for Walk #{walk_id} ({len(walk.sightings)} sightings)...")
    try:
        journal = generate_and_save_journal(walk_id)
        if journal:
            print("\n" + "=" * 50)
            print(f"Walk #{walk_id} Field Journal")
            print("=" * 50)
            print(journal)
            print("=" * 50 + "\n")
            print(f"Journal successfully stored in walks #{walk_id}.")
    except Exception as err:  # noqa: BLE001
        print(f"Error generating journal: {err}")
        sys.exit(1)


def cmd_species(query: str) -> None:
    """Search the species database for matching common or scientific names."""
    from trailear.storage.db import lookup_species

    results = lookup_species(query)
    if not results:
        print(f"No species found matching '{query}'.")
        return

    print(f"\nFound {len(results)} matching species for '{query}':\n")
    for sp in results:
        rarity_str = f" [{sp['rarity'].upper()}]" if sp.get("rarity") else ""
        print(f"* {sp['common_name']} ({sp['scientific_name']}){rarity_str}")
        if sp.get("family"):
            print(f"    Family:   {sp['family']}")
        if sp.get("habitat"):
            print(f"    Habitat:  {sp['habitat']}")
        if sp.get("size_note"):
            print(f"    Size:     {sp['size_note']}")
        if sp.get("call_note"):
            print(f"    Call:     {sp['call_note']}")
        print()


def cmd_devices() -> None:
    """List available audio input devices."""
    from trailear.audio.capture import list_devices

    devices = list_devices()
    if not devices:
        print("No audio input devices found.")
        return

    print(f"\n{'Index':<8} {'Name':<45} {'Channels':>8}  {'Rate':>8}")
    print("-" * 72)
    for dev in devices:
        print(
            f"{dev['index']:<8} {dev['name']:<45} {dev['channels']:>8}  {dev['sample_rate']:>8.0f}"
        )


def cmd_serve(host: str | None = None, port: int | None = None) -> None:
    """Start API server and serve web interface."""
    from trailear.api.server import run_server

    run_server(host=host, port=port)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="trailear",
        description="TrailEar: offline bird-call companion",
    )
    sub = parser.add_subparsers(dest="command")

    # file command
    file_parser = sub.add_parser("file", help="Classify a WAV file")
    file_parser.add_argument("path", help="Path to a WAV file")

    # walk command
    walk_parser = sub.add_parser("walk", help="Start a walk session")
    walk_parser.add_argument(
        "--pocket", action="store_true", help="Run in pocket mode (audio cues, no UI)"
    )
    walk_parser.add_argument(
        "--file", type=str, default=None, help="Process a WAV file instead of live microphone"
    )

    # devices command
    sub.add_parser("devices", help="List audio input devices")

    # species command
    species_parser = sub.add_parser("species", help="Search species database")
    species_parser.add_argument("search", help="Search term (scientific or common name)")

    # serve command
    serve_parser = sub.add_parser("serve", help="Start the API server and web app")
    serve_parser.add_argument("--host", default=None, help="Host address to bind")
    serve_parser.add_argument("--port", type=int, default=None, help="Port to listen on")

    # journal command (Phase 4)
    journal_parser = sub.add_parser("journal", help="Generate a journal (Phase 4)")
    journal_parser.add_argument("walk_id", type=int, help="Walk ID")

    args = parser.parse_args()

    if args.command == "file":
        cmd_file(args.path)
    elif args.command == "walk":
        cmd_walk(pocket=args.pocket, file_path=args.file)
    elif args.command == "devices":
        cmd_devices()
    elif args.command == "species":
        cmd_species(args.search)
    elif args.command == "journal":
        cmd_journal(args.walk_id)
    elif args.command == "serve":
        cmd_serve(host=args.host, port=args.port)
    elif args.command is None:
        parser.print_help()
    else:
        print(f"Command '{args.command}' is not yet implemented.")
        sys.exit(0)


if __name__ == "__main__":
    main()
