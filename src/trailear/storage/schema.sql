-- species.sqlite
CREATE TABLE species (
  scientific_name TEXT PRIMARY KEY,
  common_name     TEXT NOT NULL,
  family          TEXT,
  habitat         TEXT,
  size_note       TEXT,
  call_note       TEXT,
  rarity          TEXT
);

-- walks.sqlite
CREATE TABLE walks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL, ended_at TEXT,
  lat REAL, lon REAL, journal TEXT
);
CREATE TABLE sightings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  walk_id INTEGER NOT NULL REFERENCES walks(id),
  scientific_name TEXT NOT NULL, common_name TEXT NOT NULL,
  confidence REAL NOT NULL, t_offset_s REAL NOT NULL
);
CREATE INDEX idx_sightings_walk ON sightings(walk_id);
