"""Data models for database records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Species:
    scientific_name: str
    common_name: str
    family: str | None = None
    habitat: str | None = None
    size_note: str | None = None
    call_note: str | None = None
    rarity: str | None = None  # common | uncommon | rare

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Sighting:
    id: int
    walk_id: int
    scientific_name: str
    common_name: str
    confidence: float
    t_offset_s: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Walk:
    id: int
    started_at: str
    ended_at: str | None = None
    lat: float | None = None
    lon: float | None = None
    journal: str | None = None
    sightings: list[Sighting] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LifeListEntry:
    scientific_name: str
    common_name: str
    first_seen: str
    count: int

    def to_dict(self) -> dict:
        return asdict(self)
