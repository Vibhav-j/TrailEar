"""Downloads the BirdNET model and the Piper voice into models/.

This script requires network access and is meant to be run during setup only.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Piper voice: en_US-lessac-medium
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
PIPER_FILES = [
    "en_US-lessac-medium.onnx",
    "en_US-lessac-medium.onnx.json",
]


def download_file(url: str, dest: Path) -> None:
    """Download a file with progress indication."""
    if dest.exists():
        print(f"  [SKIP] {dest.name} already exists")
        return
    print(f"  Downloading {dest.name} ...")
    try:
        urllib.request.urlretrieve(url, str(dest))
        print(f"  [OK] {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] Failed to download {dest.name}: {e}")


def fetch_piper_voice() -> None:
    """Download the Piper TTS voice files."""
    print("\nFetching Piper voice (en_US-lessac-medium)...")
    piper_dir = MODELS_DIR / "piper"
    piper_dir.mkdir(parents=True, exist_ok=True)
    for fname in PIPER_FILES:
        download_file(PIPER_BASE + fname, piper_dir / fname)


def fetch_birdnet() -> None:
    """BirdNET model is bundled with birdnetlib; just verify the package."""
    print("\nChecking BirdNET model...")
    try:
        from birdnetlib.analyzer import Analyzer  # noqa

        print("  [OK] birdnetlib is installed; model will be loaded on first use.")
    except ImportError:
        print("  [WARN] birdnetlib is not installed.")
        print("         Install with: pip install birdnetlib")
        print("         The MockClassifier will be used in the meantime.")


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    fetch_birdnet()
    fetch_piper_voice()
    print("\nModel fetch complete.")


if __name__ == "__main__":
    main()
