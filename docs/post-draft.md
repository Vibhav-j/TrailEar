# TrailEar: Building an Offline Bird-Call Companion for the "Touch Grass" Challenge

*A HackOctober submission exploring local acoustics, edge intelligence, and the freedom of open models.*

---

## The Pitch: Why Walk with an AI in Your Ear?

Most AI demos happen in front of a glowing monitor or rely on a cloud API with millisecond round-trips over 5G. But when you're actually outside on a trail—deep in a state forest, along a riverbank, or under a dense deciduous canopy—cell towers vanish.

For HackOctober's **Touch Grass** challenge, I built **TrailEar**: a private, offline bird-call companion. You put on your earbuds, leave your laptop in your backpack, and walk. As you explore, TrailEar listens through your mic, runs an open-weight acoustic classifier locally every second, debounces the detections, and whispers the common names of birds directly into your ears. When you reach the trailhead and stop the walk, a local small language model synthesizes your verified sightings and regional ecological facts into a quiet, grounded field journal.

No cloud. No telemetry. No subscriptions. No cell reception required.

---

## What I Built

TrailEar is an end-to-end edge pipeline written in Python:

1. **Acoustic Streaming (`trailear.audio`):** Streams 3-second audio windows with a 1-second hop (at 48 kHz mono) over a non-blocking background queue via `sounddevice`.
2. **Local Bioacoustic Classification (`trailear.classify`):** Integrates Cornell's BirdNET (TFLite) with a custom 48-week-of-year and latitude/longitude geographic prior filter (`location_filter.py`) to silence ecologically implausible species.
3. **Temporal Debounce Manager (`trailear.detect`):** Requires consecutive hits within a narrow window to suppress transient noise, and applies a per-species cooldown (default 120s) so your ears aren't spammed by a chatty robin.
4. **Non-Blocking TTS Whispers (`trailear.voice`):** Uses Piper TTS with local ONNX voice models. An asynchronous audio queue drops stale items if speech queues up, and synthesizes pure NumPy chimes for rare species.
5. **Grounded Field Journaling (`trailear.llm`):** Runs Ollama locally with `qwen2.5:3b`. The LLM never identifies birds; it only reflects on rows in `walks.sqlite`. A strict grounding validator checks every output against known species and falls back to a deterministic template if any hallucination is detected.
6. **Sunlight-Ready Offline PWA (`trailear.api` & `web/`):** A zero-dependency, high-contrast web dashboard with WebSockets for real-time live feeds and an offline Service Worker.

---

## Why Open Worked Better Than Closed

Building this project underscored why open weights and local software are superior for field computing:

| Open Advantage | How TrailEar Demonstrates It |
|---|---|
| **Works with No Signal** | True biodiversity lives where cellular networks don't. Closed cloud APIs (OpenAI, Claude, cloud Merlin) fail entirely in remote ravines or mountains. TrailEar runs 100% in airplane mode. |
| **Data Stays Yours** | Bioacoustic audio recorded in the wild stays strictly on local storage. Ambient audio is processed entirely in memory; no audio recordings or location traces are uploaded. |
| **Swap Models Freely** | All components (classifier, LLM, TTS voice) sit behind abstract base interfaces. You can run lightweight models on a low-power laptop on trail, and switch to a larger LLM or alternative classifier (like Google Perch) via `config.yaml`. |
| **Zero Running Cost** | No API keys, no per-minute transcription billing, and no recurring monthly fees to enjoy nature. |

---

## Field Test Results

> *Fill this section with data from `docs/field-test-log.md` after outdoor testing.*

* **Test Date & Location:** `[Fill in: e.g. Oct 8, 2026 - Pine Ridge Trail]`
* **Weather & Habitat:** `[Fill in: 16°C, Light wind, mixed oak/conifer woodland]`
* **Hardware Used:** `[Fill in: Laptop in backpack, wired lavalier mic, Bluetooth earbuds]`
* **Species Encountered:** `[Fill in list of species heard/seen]`
* **Verification & Accuracy:**
  * True Positives: `[X]`
  * False Positives: `[Y]`
  * Missed Detections: `[Z]`
* **Battery & Performance:** `[Battery % consumed over X minutes walk]`

### Honest Failure Notes
`[Describe what failed during real-world testing: wind rustling on microphone, overlapping bird songs confusing single-window classifier, battery drain, or earbud latency.]`

---

## Sample Generated Journal

*(Generated offline on device at walk conclusion)*

```text
[Paste sample generated journal entry from a real or simulated walk here]
```

---

## Watch the Walkthrough & Demo

* **DevRelay Walkthrough:** [Watch the DevRelay Session](docs/devrelay-session.md) `[Insert Link Here]`
* **Airplane Mode Demo:** Screen recording showing `demo_offline.ps1` executing cleanly with Wi-Fi disabled.

---

## Try It Yourself

Clone the repo and run the Windows setup script:

```powershell
git clone https://github.com/Vibhav-j/TrailEar.git
cd TrailEar
.\scripts\setup_windows.ps1

# Test with offline sample audio
python -m trailear file data/samples/sample.wav

# Or take it outside in pocket mode
python -m trailear walk --pocket
```

*Built with Python 3.11, BirdNET, Piper TTS, Ollama, and SQLite.*
