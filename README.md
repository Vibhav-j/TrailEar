# TrailEar

An offline bird-call companion. Walk with earbuds in and the laptop in your bag: it identifies birds locally, whispers their names, and writes a field journal when you get home. Built for the HackOctober "Touch Grass" challenge.

---

## 1. Why Open Matters

| Open advantage | How TrailEar shows it |
|---|---|
| **Works with no signal** | Birds live where there is no coverage. Everything runs offline; the demo is recorded in airplane mode. |
| **Data stays yours** | Raw audio is processed in memory and never uploaded. Optional clip saving is off by default. |
| **Swap models freely** | Classifier, LLM and TTS voice are config values. Use a bigger LLM at home and a smaller one on the trail. |
| **Zero running cost** | No keys, no per-call fees, no subscription. |

### Licence Note
BirdNET model weights are licensed for non-commercial use. Google's Perch is a more permissive alternative and is planned as a second `Classifier` backend.

---

## 2. Quick Start

Requirements: Windows 10/11, Python 3.11+, and PowerShell.

### Step 1: Automated Setup
Run the setup script from PowerShell to create the virtual environment, install dependencies, fetch models, and seed the species database:

```powershell
.\scripts\setup_windows.ps1
```

### Step 2: Run the Offline Demo
Execute the full offline pipeline on a sample audio file with network disconnected:

```powershell
.\scripts\demo_offline.ps1
```

### Step 3: Run Modes
* **Pocket Mode (Live Mic):**
  Put the laptop in your bag and earbuds in. Speaks announcements directly:
  ```powershell
  python -m trailear walk --pocket
  ```

* **Simulated Walk from WAV:**
  Test pocket mode without microphone access:
  ```powershell
  python -m trailear walk --file data/samples/sample.wav --pocket
  ```

* **Offline Web PWA Dashboard:**
  Start the local server and open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the live detection feed, walk log, and life list:
  ```powershell
  python -m trailear serve
  ```

* **Generate Field Journal:**
  Synthesize a field journal for any past walk:
  ```powershell
  python -m trailear journal 1
  ```

---

## 3. Swapping Models via `config.yaml`

All external models sit behind abstract interfaces (`Classifier`, `LLM`, `TTS`). You can reconfigure them in `config.yaml` without changing application code:

```yaml
location:
  lat: 42.3601          # Your local coordinates for species priors
  lon: -71.0589

classifier:
  backend: birdnet      # "birdnet" (TFLite) or "mock" (deterministic)
  min_confidence: 0.35
  use_location_filter: true

detect:
  announce_threshold: 0.60
  min_consecutive: 2    # Require hits across consecutive hops
  cooldown_s: 120       # Suppress duplicate announcements for 2 minutes

llm:
  backend: ollama       # "ollama" (local) or "mock" (template fallback)
  model: qwen2.5:3b     # Any Ollama model: qwen2.5:3b, llama3.2:3b, etc.
  host: http://127.0.0.1:11434

tts:
  enabled: true         # Set false or leave empty for NullTTS
  voice: en_US-lessac-medium  # Piper voice in models/ directory
```

---

## 4. Known Limitations

* **BirdNET License:** BirdNET model weights are restricted to non-commercial and academic usage. Commercial deployments should wait for the planned Google Perch backend.
* **Backpack Hardware:** Running 3.0s neural audio inference continuously alongside a 3B LLM requires a laptop in a backpack. Fan noise and battery consumption must be planned for on long treks.
* **Microphone Physics:** Built-in laptop microphones pick up fabric friction inside a backpack as well as wind buffeting. An external clip-on lavalier mic with a windscreen pinned to your collar provides significantly cleaner audio.
* **Overlapping Vocalizations:** In dense morning bird choruses where multiple species vocalize simultaneously, single-window TFLite classification may occasionally miss quieter secondary birds.
* **Initial Service Worker Cache:** The offline PWA must be opened once while the local server is running so the Service Worker can cache all static assets for subsequent airplane-mode walks.

---

## 5. Folder Structure

```
trailear/
|-- README.md                    # This document
|-- README.html                  # Source of truth specification
|-- pyproject.toml               # Build metadata & dependencies
|-- config.yaml                  # Runtime configuration
|-- .env.example
|-- .gitignore
|-- scripts/
|   |-- setup_windows.ps1        # PowerShell automated installer
|   |-- fetch_models.py          # Downloads BirdNET & Piper models
|   |-- seed_species_db.py       # Seeds species facts database
|   `-- demo_offline.ps1         # Runs sample WAV end-to-end in airplane mode
|-- models/                      # Gitignored: Piper voices, cached weights
|-- data/
|   |-- species.sqlite           # Species taxonomy, habitat, call notes
|   |-- walks.sqlite             # Walk records & sightings (runtime)
|   |-- species_facts.json       # Curated species facts
|   `-- samples/                 # Sample & test audio WAVs
|-- src/trailear/
|   |-- __init__.py
|   |-- __main__.py              # Entrypoint (python -m trailear)
|   |-- main.py                  # CLI commands
|   |-- config.py                # Pydantic settings
|   |-- types.py                 # Window, Detection, WalkSummary models
|   |-- pipeline.py              # Capture -> Classify -> Detect -> Sinks
|   |-- audio/
|   |   |-- capture.py           # MicSource, FileSource
|   |   `-- preprocess.py        # Mono downmix, 48kHz resample, normalize
|   |-- classify/
|   |   |-- base.py              # Classifier ABC
|   |   |-- birdnet.py           # BirdNET TFLite wrapper
|   |   |-- mock.py              # Deterministic MockClassifier
|   |   `-- location_filter.py   # Lat/lon & 48-week geographic priors
|   |-- detect/
|   |   `-- manager.py           # Debounce & announcement manager
|   |-- storage/
|   |   |-- db.py                # SQLite repository
|   |   |-- models.py            # SQLite data models
|   |   `-- schema.sql           # Schema DDL
|   |-- llm/
|   |   |-- base.py              # LLM ABC
|   |   |-- ollama_client.py     # Local Ollama client
|   |   |-- mock.py              # MockLLM
|   |   |-- prompts.py           # Grounded field journal prompts
|   |   |-- grounding.py         # Anti-hallucination verification
|   |   `-- journal.py           # Journal generation & persistence
|   |-- voice/
|   |   `-- tts.py               # Piper TTS & NullTTS fallback
|   `-- api/
|       |-- server.py            # FastAPI application
|       |-- routes.py            # REST endpoints
|       `-- ws.py                # WebSocket live feed broadcaster
|-- web/
|   |-- index.html               # High-contrast sunlight UI
|   |-- app.js                   # State & WebSocket client
|   |-- style.css                # Sunlight-readable CSS
|   |-- sw.js                    # Offline Service Worker cache
|   `-- manifest.json            # PWA manifest
|-- tests/
|   |-- test_classifier.py
|   |-- test_manager.py
|   |-- test_storage.py
|   |-- test_journal_prompt.py
|   `-- test_api.py
|-- docs/
|   |-- architecture.md          # System design & runtime model
|   |-- devrelay-session.md      # DevRelay walkthrough recording link
|   |-- field-test-log.md        # Real outdoor field test template
|   `-- post-draft.md            # HackOctober blog post skeleton
`-- assets/                      # Screenshots, demo gifs
```
