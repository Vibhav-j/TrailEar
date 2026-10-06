"""CLI entry points for TrailEar."""

from __future__ import annotations

import argparse
import sys
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

    classifier = _get_classifier()
    source = FileSource(wav_path)

    seen: set[str] = set()
    all_detections = []

    for window in source.windows():
        detections = classifier.classify(window)
        for d in detections:
            all_detections.append(d)
            if d.scientific_name not in seen:
                seen.add(d.scientific_name)

    if not all_detections:
        print("No detections.")
        return

    print(f"\n{'Species':<35} {'Confidence':>10}  {'Time (s)':>8}")
    print("-" * 58)
    for d in all_detections:
        print(f"{d.common_name:<35} {d.confidence:>10.2f}  {d.t:>8.1f}")
    print(f"\nTotal: {len(all_detections)} detections, {len(seen)} unique species.")


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

    # devices command
    sub.add_parser("devices", help="List audio input devices")

    # walk command (Phase 3 stub)
    sub.add_parser("walk", help="Start a live walk (Phase 3)")

    # serve command (Phase 5 stub)
    sub.add_parser("serve", help="Start the API server (Phase 5)")

    # journal command (Phase 4 stub)
    journal_parser = sub.add_parser("journal", help="Generate a journal (Phase 4)")
    journal_parser.add_argument("walk_id", type=int, help="Walk ID")

    # species command (stub)
    species_parser = sub.add_parser("species", help="Search species database")
    species_parser.add_argument("search", help="Search term")

    args = parser.parse_args()

    if args.command == "file":
        cmd_file(args.path)
    elif args.command == "devices":
        cmd_devices()
    elif args.command is None:
        parser.print_help()
    else:
        print(f"Command '{args.command}' is not yet implemented.")
        sys.exit(0)


if __name__ == "__main__":
    main()
