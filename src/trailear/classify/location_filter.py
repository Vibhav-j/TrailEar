"""Lat/lon + week-of-year species prior filter using BirdNET's 48-week scheme."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trailear.types import Detection


def date_to_birdnet_week(dt: datetime.date | datetime.datetime | None = None) -> int:
    """Convert a date to BirdNET's 48-week scheme (4 weeks per month, 1-48).

    BirdNET partitions each calendar month into 4 weeks:
    - Days 1-7: week 1 of the month
    - Days 8-14: week 2 of the month
    - Days 15-21: week 3 of the month
    - Days 22-end: week 4 of the month
    Returns an integer in the range [1, 48].
    """
    if dt is None:
        dt = datetime.datetime.now(datetime.UTC)
    week_in_month = min(4, (dt.day - 1) // 7 + 1)
    return (dt.month - 1) * 4 + week_in_month


def get_location_species_list(
    lat: float,
    lon: float,
    week: int | None = None,
) -> list[str] | None:
    """Query birdnetlib for species expected at the given coordinates and week.

    Returns a list of species names if birdnetlib is available and the query
    succeeds; returns None otherwise.
    """
    try:
        from birdnetlib.species import SpeciesList  # lazy import

        species_helper = SpeciesList()
        # Query species for coordinates and week
        return species_helper.return_list(lat=lat, lon=lon, week=week)
    except (ImportError, Exception):  # noqa: BLE001
        return None


def filter_detections_by_species(
    detections: list[Detection],
    allowed_species: set[str] | None,
) -> list[Detection]:
    """Filter detections against a set of allowed species names (scientific or common)."""
    if allowed_species is None:
        return detections
    return [
        d
        for d in detections
        if d.scientific_name in allowed_species or d.common_name in allowed_species
    ]
