import csv
import sqlite3
from pathlib import Path

from app.storage.database import (
    connect_database,
    initialize_database,
    load_normalized_indicators_to_database,
)


def test_initialize_database_creates_indicator_schema(tmp_path: Path):
    database_path = tmp_path / "rdis.sqlite3"

    with connect_database(database_path) as connection:
        initialize_database(connection)
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"regions", "indicators", "indicator_values", "indicator_forecasts"}.issubset(table_names)


def test_load_normalized_indicators_to_database_populates_lookup_tables(tmp_path: Path):
    csv_path = write_normalized_csv(
        tmp_path / "normalized_indicators.csv",
        [
            {
                "region": "Львівська область",
                "indicator_name": "industrial_parks_count",
                "value": "2",
                "date": "2025-05-01",
            },
            {
                "region": "м. Київ",
                "indicator_name": "industrial_parks_count",
                "value": "1",
                "date": "2025-05-01",
            },
        ],
    )
    database_path = tmp_path / "rdis.sqlite3"

    row_count = load_normalized_indicators_to_database(csv_path, database_path)

    assert row_count == 2
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        regions = connection.execute(
            "SELECT name, region_type FROM regions ORDER BY name"
        ).fetchall()
        indicators = connection.execute(
            "SELECT code, name, unit FROM indicators"
        ).fetchall()
        values = connection.execute(
            """
            SELECT i.code, r.name AS region, iv.period_date, iv.value
            FROM indicator_values iv
            JOIN indicators i ON i.id = iv.indicator_id
            JOIN regions r ON r.id = iv.region_id
            ORDER BY r.name
            """
        ).fetchall()

    assert [dict(row) for row in regions] == [
        {"name": "Львівська область", "region_type": "oblast"},
        {"name": "м. Київ", "region_type": "city"},
    ]
    assert [dict(row) for row in indicators] == [
        {
            "code": "industrial_parks_count",
            "name": "Number of industrial parks",
            "unit": "count",
        }
    ]
    assert [dict(row) for row in values] == [
        {
            "code": "industrial_parks_count",
            "region": "Львівська область",
            "period_date": "2025-05-01",
            "value": 2.0,
        },
        {
            "code": "industrial_parks_count",
            "region": "м. Київ",
            "period_date": "2025-05-01",
            "value": 1.0,
        },
    ]


def test_load_normalized_indicators_to_database_is_idempotent(tmp_path: Path):
    csv_path = write_normalized_csv(
        tmp_path / "normalized_indicators.csv",
        [
            {
                "region": "Львівська область",
                "indicator_name": "industrial_parks_count",
                "value": "2",
                "date": "2025-05-01",
            },
        ],
    )
    database_path = tmp_path / "rdis.sqlite3"

    load_normalized_indicators_to_database(csv_path, database_path)
    write_normalized_csv(
        csv_path,
        [
            {
                "region": "Львівська область",
                "indicator_name": "industrial_parks_count",
                "value": "3",
                "date": "2025-05-01",
            },
        ],
    )
    load_normalized_indicators_to_database(csv_path, database_path)

    with sqlite3.connect(database_path) as connection:
        count, value = connection.execute(
            "SELECT COUNT(*), value FROM indicator_values"
        ).fetchone()

    assert count == 1
    assert value == 3.0


def write_normalized_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=["region", "indicator_name", "value", "date"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path
