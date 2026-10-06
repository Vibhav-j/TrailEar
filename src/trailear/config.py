"""Pydantic settings loaded from config.yaml."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


class LocationConfig(BaseModel):
    lat: float = 0.0
    lon: float = 0.0


class AudioConfig(BaseModel):
    device: int | None = None
    sample_rate: int = 48000
    window_s: float = 3.0
    hop_s: float = 1.0


class ClassifierConfig(BaseModel):
    backend: str = "birdnet"
    min_confidence: float = 0.35
    use_location_filter: bool = True


class DetectConfig(BaseModel):
    announce_threshold: float = 0.60
    min_consecutive: int = 2
    cooldown_s: int = 120


class LLMConfig(BaseModel):
    backend: str = "ollama"
    model: str = "qwen2.5:3b"
    host: str = "http://127.0.0.1:11434"


class TTSConfig(BaseModel):
    enabled: bool = True
    voice: str = "en_US-lessac-medium"


class PocketModeConfig(BaseModel):
    speak_only_new_species: bool = True
    chime_on_rare: bool = True


class PrivacyConfig(BaseModel):
    save_clips: bool = False


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class AppConfig(BaseModel):
    location: LocationConfig = Field(default_factory=LocationConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    detect: DetectConfig = Field(default_factory=DetectConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    pocket_mode: PocketModeConfig = Field(default_factory=PocketModeConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from a YAML file, falling back to defaults."""
    path = path or _CONFIG_PATH
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return AppConfig(**raw)
    return AppConfig()


# Module-level singleton, loaded once on import.
config = load_config()


def save_config(app_config: AppConfig, path: Path | None = None) -> None:
    """Save configuration to a YAML file."""
    path = path or _CONFIG_PATH
    data = app_config.model_dump()
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False)


def get_settings() -> dict:
    """Return dictionary of current settings."""
    return {
        "use_location_filter": config.classifier.use_location_filter,
        "latitude": config.location.lat,
        "longitude": config.location.lon,
        "lat": config.location.lat,
        "lon": config.location.lon,
        "min_confidence": config.classifier.min_confidence,
    }


def update_settings(
    use_location_filter: bool | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    min_confidence: float | None = None,
    persist: bool = True,
) -> dict:
    """Update runtime configuration settings and persist to YAML."""
    if use_location_filter is not None:
        config.classifier.use_location_filter = bool(use_location_filter)
    if latitude is not None:
        config.location.lat = float(latitude)
    if longitude is not None:
        config.location.lon = float(longitude)
    if min_confidence is not None:
        config.classifier.min_confidence = float(min_confidence)

    if persist and _CONFIG_PATH.exists():
        try:
            save_config(config, _CONFIG_PATH)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not persist configuration to %s: %s", _CONFIG_PATH, exc)

    return get_settings()
