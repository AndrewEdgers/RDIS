from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import DATABASE_PATH
from app.forecasting.models import ForecastPoint
from app.forecasting.selection import select_forecast_model
from app.forecasting.series import IndicatorRegionSeries, load_indicator_region_series
from app.storage.database import connect_database, initialize_database


@dataclass(frozen=True)
class HoldoutForecastComparison:
    indicator_code: str
    region_name: str
    target_date: date
    actual_value: float
    predicted_value: float
    difference: float
    model_name: str
    training_points: int


@dataclass(frozen=True)
class HoldoutForecastResult:
    comparisons: tuple[HoldoutForecastComparison, ...]
    skipped_regions: tuple[str, ...]
    target_date: date | None


def run_indicator_forecasting(
    database_path: Path = DATABASE_PATH,
    horizon: int = 1,
) -> int:
    with connect_database(database_path) as connection:
        initialize_database(connection)
        forecast_count = generate_and_store_forecasts(connection, horizon)

    print(f"[forecasting] wrote {forecast_count} forecast rows to {database_path}")
    return forecast_count


def generate_and_store_forecasts(
    connection: sqlite3.Connection,
    horizon: int = 1,
) -> int:
    forecast_count = 0
    for series in load_indicator_region_series(connection):
        model = select_forecast_model(series)
        forecast_points = model.forecast(series, horizon)
        delete_indicator_forecasts(connection, series)
        forecast_count += upsert_indicator_forecasts(
            connection=connection,
            series=series,
            forecast_points=forecast_points,
            model_name=model.name,
        )

    connection.commit()
    return forecast_count


def delete_indicator_forecasts(
    connection: sqlite3.Connection,
    series: IndicatorRegionSeries,
) -> None:
    connection.execute(
        """
        DELETE FROM indicator_forecasts
        WHERE indicator_id = ?
          AND region_id = ?
        """,
        (series.indicator_id, series.region_id),
    )


def build_latest_holdout_comparison(
    connection: sqlite3.Connection,
    indicator_code: str = "industrial_parks_count",
) -> HoldoutForecastResult:
    series_list = [
        series
        for series in load_indicator_region_series(connection)
        if series.indicator_code == indicator_code
    ]
    all_dates = sorted(
        {point.period_date for series in series_list for point in series.points}
    )
    if len(all_dates) < 2:
        return HoldoutForecastResult(
            comparisons=(),
            skipped_regions=tuple(series.region_name for series in series_list),
            target_date=all_dates[-1] if all_dates else None,
        )

    target_date = all_dates[-1]
    comparisons: list[HoldoutForecastComparison] = []
    skipped_regions: list[str] = []
    for series in series_list:
        actual_point = next(
            (point for point in series.points if point.period_date == target_date),
            None,
        )
        training_points = tuple(
            point for point in series.points if point.period_date < target_date
        )
        if actual_point is None or not training_points:
            skipped_regions.append(series.region_name)
            continue

        training_series = IndicatorRegionSeries(
            indicator_id=series.indicator_id,
            region_id=series.region_id,
            indicator_code=series.indicator_code,
            region_name=series.region_name,
            points=training_points,
        )
        model = select_forecast_model(training_series)
        predicted_point = model.forecast_dates(training_series, [target_date])[0]
        comparisons.append(
            HoldoutForecastComparison(
                indicator_code=series.indicator_code,
                region_name=series.region_name,
                target_date=target_date,
                actual_value=actual_point.value,
                predicted_value=predicted_point.predicted_value,
                difference=actual_point.value - predicted_point.predicted_value,
                model_name=model.name,
                training_points=len(training_points),
            )
        )

    return HoldoutForecastResult(
        comparisons=tuple(sorted(comparisons, key=lambda comparison: comparison.region_name)),
        skipped_regions=tuple(sorted(skipped_regions)),
        target_date=target_date,
    )


def upsert_indicator_forecasts(
    connection: sqlite3.Connection,
    series: IndicatorRegionSeries,
    forecast_points: list[ForecastPoint],
    model_name: str,
) -> int:
    written = 0
    for forecast_point in forecast_points:
        connection.execute(
            """
            INSERT INTO indicator_forecasts (
                indicator_id,
                region_id,
                forecast_date,
                predicted_value,
                model_name
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(indicator_id, region_id, forecast_date, model_name)
            DO UPDATE SET
                predicted_value = excluded.predicted_value,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                series.indicator_id,
                series.region_id,
                forecast_point.forecast_date.isoformat(),
                forecast_point.predicted_value,
                model_name,
            ),
        )
        written += 1

    return written
