from pathlib import Path

import pandas as pd

from app.dashboard import (
    INDICATOR_CODE,
    build_actual_forecast_color_range,
    build_grouped_bar_chart,
    build_series_line_chart,
    load_actual_values,
    load_future_forecasts,
)
from app.forecasting.jobs import generate_and_store_forecasts, build_latest_holdout_comparison
from app.storage.database import (
    NormalizedIndicatorRow,
    connect_database,
    initialize_database,
    upsert_indicator_values,
)


def test_dashboard_loaders_and_holdout_use_project_database_connection(tmp_path: Path):
    database_path = tmp_path / "rdis.sqlite3"
    with connect_database(database_path) as connection:
        initialize_database(connection)
        upsert_indicator_values(
            connection,
            [
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code=INDICATOR_CODE,
                    period_date="2024-05-01",
                    value=1.0,
                ),
                NormalizedIndicatorRow(
                    region="Test Region",
                    indicator_code=INDICATOR_CODE,
                    period_date="2025-05-01",
                    value=3.0,
                ),
            ],
            tmp_path / "normalized.csv",
        )
        generate_and_store_forecasts(connection)

        actuals = load_actual_values(connection, INDICATOR_CODE)
        forecasts = load_future_forecasts(connection, INDICATOR_CODE)
        holdout = build_latest_holdout_comparison(connection, INDICATOR_CODE)

    assert len(actuals) == 2
    assert len(forecasts) == 1
    assert len(holdout.comparisons) == 1


def test_dashboard_chart_legends_use_only_requested_series():
    frame = pd.DataFrame(
        {
            "region": ["A", "A"],
            "period_date": pd.to_datetime(["2025-01-01", "2026-01-01"]),
            "value": [1.0, 2.0],
            "series_type": ["Actual", "Forecast"],
        }
    )

    line_spec = build_series_line_chart(
        frame,
        "Date",
        color_domain=["Actual", "Forecast"],
        color_range=["#2563eb", "#f97316"],
    ).to_dict()
    bar_domain = ["Actual latest", "Forecast 2026-01-01"]
    bar_spec = build_grouped_bar_chart(
        frame,
        color_domain=bar_domain,
        color_range=build_actual_forecast_color_range(bar_domain),
    ).to_dict()

    assert line_spec["encoding"]["color"]["scale"]["domain"] == ["Actual", "Forecast"]
    assert bar_spec["encoding"]["color"]["scale"]["domain"] == bar_domain
