# TrailEar

An offline bird-call companion. Walk with earbuds in and the laptop in your bag:
it identifies birds locally, whispers their names, and writes a field journal
when you get home. Built for the HackOctober "Touch Grass" challenge.

## Why Open?

| Open advantage | How TrailEar shows it |
|---|---|
| Works with no signal | Birds live where there is no coverage. Everything runs offline; the demo is recorded in airplane mode. |
| Data stays yours | Raw audio is processed in memory and never uploaded. Optional clip saving is off by default. |
| Swap models freely | Classifier, LLM and TTS voice are config values. Use a bigger LLM at home and a smaller one on the trail. |
| Zero running cost | No keys, no per-call fees, no subscription. |

## Quick Start

```powershell
.\scripts\setup_windows.ps1
python -m trailear file data/samples/sample.wav
python -m trailear devices
```

## Licence Note

BirdNET model weights are licensed for non-commercial use. Google's Perch is a
more permissive alternative and is planned as a second `Classifier` backend.

## Known Limitations

- Phase 1: Only `file` and `devices` CLI commands are functional.
- Live microphone capture (Phase 3), LLM journal generation (Phase 4),
  and the web UI (Phase 5) are not yet implemented.
- BirdNET classification requires `birdnetlib` to be installed separately.
  When missing, a `MockClassifier` is used.
