from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.config import DATABASE_PATH, NORMALIZED_INDICATORS_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS regions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    region_type TEXT NOT NULL DEFAULT 'region'
);

CREATE TABLE IF NOT EXISTS indicators (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS indicator_values (
    id INTEGER PRIMARY KEY,
    indicator_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    period_date TEXT NOT NULL,
    value REAL NOT NULL,
    source_file TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (indicator_id, region_id, period_date),
    FOREIGN KEY (indicator_id) REFERENCES indicators(id),
    FOREIGN KEY (region_id) REFERENCES regions(id)
);

CREATE INDEX IF NOT EXISTS idx_indicator_values_period
ON indicator_values (period_date);

CREATE INDEX IF NOT EXISTS idx_indicator_values_region_period
ON indicator_values (region_id, period_date);
"""


INDICATOR_METADATA: dict[str, dict[str, str | None]] = {
    "industrial_parks_count": {
        "name": "Number of industrial parks",
        "unit": "count",
        "description": "Count of active industrial parks by region.",
    },
}


@dataclass(frozen=True)
class NormalizedIndicatorRow:
    region: str
    indicator_code: str
    period_date: str
    value: float


def connect_database(database_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def load_normalized_indicators_to_database(
    normalized_indicators_path: Path = NORMALIZED_INDICATORS_PATH,
    database_path: Path = DATABASE_PATH,
) -> int:
    rows = read_normalized_indicator_rows(normalized_indicators_path)
    with connect_database(database_path) as connection:
        initialize_database(connection)
        return upsert_indicator_values(connection, rows, normalized_indicators_path)


def read_normalized_indicator_rows(path: Path) -> list[NormalizedIndicatorRow]:
    with path.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        rows = [parse_normalized_indicator_row(row) for row in reader]

    if not rows:
        raise ValueError(f"No normalized indicator rows found in {path}")
    return rows


def parse_normalized_indicator_row(row: dict[str, str]) -> NormalizedIndicatorRow:
    region = require_text(row.get("region"), "region")
    indicator_code = require_text(row.get("indicator_name"), "indicator_name")
    period_date = require_date(row.get("date"))
    value = require_float(row.get("value"))
    return NormalizedIndicatorRow(
        region=region,
        indicator_code=indicator_code,
        period_date=period_date,
        value=value,
    )


def upsert_indicator_values(
    connection: sqlite3.Connection,
    rows: Iterable[NormalizedIndicatorRow],
    source_file: Path,
) -> int:
    written = 0
    source_file_text = str(source_file)
    for row in rows:
        region_id = upsert_region(connection, row.region)
        indicator_id = upsert_indicator(connection, row.indicator_code)
        connection.execute(
            """
            INSERT INTO indicator_values (
                indicator_id,
                region_id,
                period_date,
                value,
                source_file
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(indicator_id, region_id, period_date)
            DO UPDATE SET
                value = excluded.value,
                source_file = excluded.source_file,
                updated_at = CURRENT_TIMESTAMP
            """,
            (indicator_id, region_id, row.period_date, row.value, source_file_text),
        )
        written += 1

    connection.commit()
    return written


def upsert_region(connection: sqlite3.Connection, name: str) -> int:
    connection.execute(
        """
        INSERT INTO regions (name, region_type)
        VALUES (?, ?)
        ON CONFLICT(name) DO NOTHING
        """,
        (name, derive_region_type(name)),
    )
    return int(
        connection.execute(
            "SELECT id FROM regions WHERE name = ?",
            (name,),
        ).fetchone()["id"]
    )


def upsert_indicator(connection: sqlite3.Connection, code: str) -> int:
    metadata = INDICATOR_METADATA.get(code, {})
    connection.execute(
        """
        INSERT INTO indicators (code, name, unit, description)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name = excluded.name,
            unit = excluded.unit,
            description = excluded.description
        """,
        (
            code,
            str(metadata.get("name") or code),
            str(metadata.get("unit") or "unknown"),
            metadata.get("description"),
        ),
    )
    return int(
        connection.execute(
            "SELECT id FROM indicators WHERE code = ?",
            (code,),
        ).fetchone()["id"]
    )


def derive_region_type(region_name: str) -> str:
    if region_name.startswith("м. "):
        return "city"
    return "oblast"


def require_text(value: str | None, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"Missing required field '{field_name}'")
    return cleaned


def require_date(value: str | None) -> str:
    cleaned = require_text(value, "date")
    datetime.strptime(cleaned, "%Y-%m-%d")
    return cleaned


def require_float(value: str | None) -> float:
    cleaned = require_text(value, "value")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value '{cleaned}'") from exc
