# TrailEar Architecture

TrailEar is an offline, edge-native acoustic companion designed for birders and outdoor enthusiasts. It operates completely disconnected from the internet, performing real-time audio capture, acoustic classification, announcement deduplication, non-blocking text-to-speech, local database persistence, and offline LLM journal generation.

## System Diagram

```
 Mic / WAV file
      |
      v
+--------------+  3 s windows, 1 s hop  +----------------------+
| audio/       | ---------------------> | classify/            |
| capture.py   |                        | Classifier (BirdNET) |
| preprocess   |                        | + location_filter    |
+--------------+                        +----------+-----------+
                                                   | Detection(species, conf, t)
                                                   v
                                        +----------------------+
                                        | detect/manager.py    |
                                        | threshold, debounce, |
                                        | dedupe per species   |
                                        +-----+----------+-----+
                                              |          |
                               +--------------v--+   +---v-----------------+
                               | storage/        |   | voice/tts.py        |
                               | SQLite: walks,  |   | Piper speaks the    |
                               | sightings,      |   | common name         |
                               | species facts   |   +---------------------+
                               +--------+--------+
                                        | structured facts only
                                        v
                               +----------------------+
                               | llm/ (Ollama)        |
                               | journal + grounding  |
                               +--------+-------------+
                                        v
                               +----------------------+
                               | api/ FastAPI + WS    |
                               | web/ PWA (offline)   |
                               +----------------------+
```

---

## Runtime Model & Dataflow

### 1. Audio Ingestion (`trailear.audio`)
* **Capture Sources:**
  * `MicSource`: Uses `sounddevice.InputStream` to capture live microphone input in the background. It buffers audio chunks into fixed 3.0-second sliding windows with a 1.0-second hop.
  * `FileSource`: Ingests standard WAV files (or loops them) for deterministic testing, offline replays, or verification in airplane mode.
* **Preprocessing (`audio.preprocess`):**
  * Multi-channel streams are downmixed to mono `(ch0 + ch1)/2`.
  * Audio is resampled to BirdNET's native rate of 48,000 Hz using linear interpolation.
  * Float samples are normalized to $[-1.0, 1.0]$.
* **Queue Decoupling:** Windows are pushed to a bounded `queue.Queue` so audio capture is never bottlenecked by neural network inference.

---

### 2. Classification & Geographic Prior (`trailear.classify`)
* **Classifier Interface (`classify.base.Classifier`):** Abstract class defining `classify(window: Window) -> list[Detection]`.
* **BirdNET Backend (`classify.birdnet.BirdNETClassifier`):**
  * Loads TFLite weights lazily from `models/` or the `birdnetlib` package.
  * Incorporates latitude, longitude, and week-of-year (BirdNET 48-week scheme via `classify.location_filter.get_birdnet_week`) priors to suppress ecologically impossible false positives.
  * Filters raw candidate outputs against `config.classifier.min_confidence`.
* **Mock Backend (`classify.mock.MockClassifier`):**
  * Deterministic test engine returning pre-defined bird calls based on audio energy and spectral peaks. Ensures zero-dependency testing without machine learning libraries.

---

### 3. Detection Management & Debouncing (`trailear.detect`)
Raw neural network predictions are noisy. `DetectionManager` provides deterministic temporal filtering:
* **Confidence Gate:** Only candidate detections meeting or exceeding `config.detect.announce_threshold` (e.g. $\ge 0.60$) are considered.
* **Consecutive Hit Verification:** Requires at least `min_consecutive` hits within a temporal sliding window ($3 \times \text{hop\_s}$) to filter transient noise spikes or wind gusts.
* **Species Cooldown:** Once a species is announced, further announcements for that species are suppressed for `cooldown_s` (e.g. 120 seconds) to prevent repetitive vocal spam.
* **Event Dispatch:** Dispatches `Detection` events only when an announcement criteria is met.

---

### 4. Sinks & Fan-Out (`trailear.pipeline`)
The detection pipeline fans out each announcement to multiple concurrent sinks:
* **Storage Sink (`storage.db`):** Inserts sightings into `data/walks.sqlite`.
* **Voice Sink (`voice.tts`):** Formats audio announcements (e.g. common name whisper, chime for rare species) and queues them for playback.
* **WebSocket Sink (`api.ws`):** Broadcasts real-time JSON payloads to all connected browser clients.
* **Console Sink (`main.py`):** Prints timestamped detections to `stdout`.

---

### 5. Non-Blocking Text-to-Speech (`trailear.voice`)
* **Piper TTS (`PiperTTS`):** Synthesizes high-quality speech offline using an ONNX model from `models/` without internet access.
* **Dedicated Audio Thread:** Speech synthesis and playback run on a dedicated worker thread via `sounddevice.play`.
* **Queue Dropping Policy:** If the TTS queue exceeds 3 pending items (e.g. sudden chorus of birds), stale items are automatically dropped to keep latency low.
* **NullTTS Fallback:** If TTS is disabled or dependencies fail to load, `NullTTS` is used seamlessly with a single diagnostic warning.
* **Rare Species Chime:** Pure NumPy sine-wave chime synthesized programmatically at runtime without external audio assets.

---

### 6. Storage & Knowledge Base (`trailear.storage`)
* **Species Facts (`data/species.sqlite`):** Read-only database built once via `scripts/seed_species_db.py`. Contains taxonomic information, habitat notes, size indicators, call traits, and rarity rankings merged from `data/species_facts.json`.
* **Walk History (`data/walks.sqlite`):** Runtime walk ledger tracking walk duration, coordinates, sightings history, and field journal narratives.

---

### 7. Grounded LLM Journal Generation (`trailear.llm`)
* **Ollama Client (`OllamaClient`):** Interacts with local Ollama daemon (`http://127.0.0.1:11434`) running small open models like `qwen2.5:3b`.
* **Pure Fact Injection:** The LLM does *not* identify birds. It receives a JSON payload containing only the verified SQLite sightings and species facts.
* **Hallucination Grounding Check (`llm.grounding`):**
  * Scans generated output against all known species in `species.sqlite`.
  * If the model hallucinates an unobserved bird species, it regenerates once with a strict anti-hallucination prompt.
  * If hallucination persists, it falls back to a deterministic, structured template built solely from database facts.

---

### 8. Web PWA & API (`trailear.api` & `web/`)
* **FastAPI Server:** Exposes endpoints for walk lifecycle management (`/api/walks/start`, `/api/walks/{id}/stop`, `/api/walks`, `/api/lifelist`, `/api/health`).
* **WebSocket `/ws/live`:** Real-time push stream for in-browser detection updates.
* **Vanilla Offline PWA:**
  * Zero external CDNs, fonts, or JS libraries.
  * High-contrast, sunlight-readable UI optimized for outdoor mobile/tablet screens.
  * Service worker (`sw.js`) caches all assets locally for 100% offline access when walking in airplane mode.
