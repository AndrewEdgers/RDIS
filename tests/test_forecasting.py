from datetime import date
from pathlib import Path

import pytest

from app.forecasting.jobs import build_latest_holdout_comparison, generate_and_store_forecasts
from app.forecasting.models import LastValueModel, LinearRegressionModel
from app.forecasting.selection import select_forecast_model
from app.forecasting.series import IndicatorRegionSeries, SeriesPoint
from app.storage.database import (
    NormalizedIndicatorRow,
    connect_database,
    initialize_database,
    upsert_indicator_values,
)


def test_select_forecast_model_uses_last_value_for_single_point():
    series = build_series([("2025-05-01", 2.0)])

    model = select_forecast_model(series)

    assert model.name == "last_value"


def test_select_forecast_model_uses_last_value_for_two_points():
    series = build_series([("2024-05-01", 1.0), ("2025-05-01", 2.0)])

    model = select_forecast_model(series)

    assert model.name == "last_value"


def test_select_forecast_model_uses_linear_regression_for_three_points():
    series = build_series(
        [("2023-05-01", 1.0), ("2024-05-01", 2.0), ("2025-05-01", 3.0)]
    )

    model = select_forecast_model(series)

    assert model.name == "linear_regression"


def test_last_value_forecasts_next_years_with_latest_value():
    series = build_series([("2025-05-01", 7.0)])

    forecasts = LastValueModel().forecast(series, horizon=2)

    assert forecasts[0].forecast_date == date(2026, 5, 1)
    assert forecasts[0].predicted_value == 7.0
    assert forecasts[1].forecast_date == date(2027, 5, 1)
    assert forecasts[1].predicted_value == 7.0


def test_last_value_forecasts_explicit_target_dates_with_latest_value():
    series = build_series([("2025-05-01", 7.0)])

    forecasts = LastValueModel().forecast_dates(series, [date(2025, 12, 31)])

    assert forecasts[0].forecast_date == date(2025, 12, 31)
    assert forecasts[0].predicted_value == 7.0


def test_linear_regression_forecasts_next_year_from_trend():
    series = build_series(
        [("2023-05-01", 1.0), ("2024-05-01", 3.0), ("2025-05-01", 5.0)]
    )

    forecasts = LinearRegressionModel().forecast(series, horizon=1)

    assert forecasts[0].forecast_date == date(2026, 5, 1)
    assert forecasts[0].predicted_value == pytest.approx(
        expected_linear_prediction(series, date(2026, 5, 1))
    )


def test_linear_regression_forecasts_explicit_target_date_from_trend():
    series = build_series(
        [("2023-05-01", 1.0), ("2024-05-01", 3.0), ("2025-05-01", 5.0)]
    )

    forecasts = LinearRegressionModel().forecast_dates(series, [date(2025, 10, 30)])

    assert forecasts[0].forecast_date == date(2025, 10, 30)
    assert forecasts[0].predicted_value == pytest.approx(
        expected_linear_prediction(series, date(2025, 10, 30))
    )


def test_generate_and_store_forecasts_is_idempotent(tmp_path: Path):
    database_path = tmp_path / "rdis.sqlite3"
    with connect_database(database_path) as connection:
        initialize_database(connection)
        upsert_indicator_values(
            connection,
            [
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code="industrial_parks_count",
                    period_date="2024-05-01",
                    value=1.0,
                ),
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code="industrial_parks_count",
                    period_date="2025-05-01",
                    value=3.0,
                ),
            ],
            tmp_path / "normalized.csv",
        )

        first_count = generate_and_store_forecasts(connection, horizon=1)
        second_count = generate_and_store_forecasts(connection, horizon=1)

        stored_count = connection.execute(
            "SELECT COUNT(*) FROM indicator_forecasts"
        ).fetchone()[0]
        forecast = connection.execute(
            """
            SELECT forecast_date, predicted_value, model_name
            FROM indicator_forecasts
            """
        ).fetchone()

    assert first_count == 1
    assert second_count == 1
    assert stored_count == 1
    assert forecast["forecast_date"] == "2026-05-01"
    assert forecast["predicted_value"] == pytest.approx(3.0)
    assert forecast["model_name"] == "last_value"


def test_generate_and_store_forecasts_replaces_stale_model_rows(tmp_path: Path):
    database_path = tmp_path / "rdis.sqlite3"
    with connect_database(database_path) as connection:
        initialize_database(connection)
        upsert_indicator_values(
            connection,
            [
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code="industrial_parks_count",
                    period_date="2024-05-01",
                    value=1.0,
                ),
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code="industrial_parks_count",
                    period_date="2025-05-01",
                    value=3.0,
                ),
            ],
            tmp_path / "normalized.csv",
        )

        series = build_series([("2024-05-01", 1.0), ("2025-05-01", 3.0)])
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
            """,
            (series.indicator_id, series.region_id, "2026-05-01", 5.0, "linear_regression"),
        )
        generate_and_store_forecasts(connection, horizon=1)

        forecasts = connection.execute(
            """
            SELECT predicted_value, model_name
            FROM indicator_forecasts
            ORDER BY model_name
            """
        ).fetchall()

    assert [dict(row) for row in forecasts] == [
        {"predicted_value": 3.0, "model_name": "last_value"}
    ]


def test_latest_holdout_comparison_trains_without_latest_actual(tmp_path: Path):
    database_path = tmp_path / "rdis.sqlite3"
    with connect_database(database_path) as connection:
        initialize_database(connection)
        upsert_indicator_values(
            connection,
            [
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code="industrial_parks_count",
                    period_date="2023-05-01",
                    value=1.0,
                ),
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code="industrial_parks_count",
                    period_date="2024-05-01",
                    value=3.0,
                ),
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code="industrial_parks_count",
                    period_date="2025-05-01",
                    value=50.0,
                ),
            ],
            tmp_path / "normalized.csv",
        )

        result = build_latest_holdout_comparison(connection)

    assert result.target_date == date(2025, 5, 1)
    assert result.skipped_regions == ()
    assert len(result.comparisons) == 1
    comparison = result.comparisons[0]
    assert comparison.actual_value == 50.0
    assert comparison.predicted_value == pytest.approx(3.0)
    assert comparison.difference == pytest.approx(47.0)
    assert comparison.model_name == "last_value"
    assert comparison.training_points == 2


def build_series(values: list[tuple[str, float]]) -> IndicatorRegionSeries:
    return IndicatorRegionSeries(
        indicator_id=1,
        region_id=1,
        indicator_code="industrial_parks_count",
        region_name="Test Region",
        points=tuple(
            SeriesPoint(period_date=date.fromisoformat(period_date), value=value)
            for period_date, value in values
        ),
    )


def expected_linear_prediction(series: IndicatorRegionSeries, target_date: date) -> float:
    xs = [float(point.period_date.toordinal()) for point in series.points]
    ys = [point.value for point in series.points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    slope = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys)
    ) / sum((x_value - mean_x) ** 2 for x_value in xs)
    intercept = mean_y - slope * mean_x
    return slope * float(target_date.toordinal()) + intercept
