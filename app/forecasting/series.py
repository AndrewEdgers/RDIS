from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SeriesPoint:
    period_date: date
    value: float


@dataclass(frozen=True)
class IndicatorRegionSeries:
    indicator_id: int
    region_id: int
    indicator_code: str
    region_name: str
    points: tuple[SeriesPoint, ...]


def load_indicator_region_series(
    connection: sqlite3.Connection,
) -> list[IndicatorRegionSeries]:
    rows = connection.execute(
        """
        SELECT
            iv.indicator_id,
            i.code AS indicator_code,
            iv.region_id,
            r.name AS region_name,
            iv.period_date,
            iv.value
        FROM indicator_values iv
        JOIN indicators i ON i.id = iv.indicator_id
        JOIN regions r ON r.id = iv.region_id
        ORDER BY iv.indicator_id, iv.region_id, iv.period_date
        """
    ).fetchall()

    grouped_points: dict[tuple[int, int, str, str], list[SeriesPoint]] = {}
    for row in rows:
        key = (
            int(row["indicator_id"]),
            int(row["region_id"]),
            str(row["indicator_code"]),
            str(row["region_name"]),
        )
        grouped_points.setdefault(key, []).append(
            SeriesPoint(
                period_date=date.fromisoformat(str(row["period_date"])),
                value=float(row["value"]),
            )
        )

    return [
        IndicatorRegionSeries(
            indicator_id=indicator_id,
            region_id=region_id,
            indicator_code=indicator_code,
            region_name=region_name,
            points=tuple(points),
        )
        for (indicator_id, region_id, indicator_code, region_name), points in grouped_points.items()
    ]

