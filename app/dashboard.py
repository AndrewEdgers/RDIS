from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import DATABASE_PATH
from app.forecasting.jobs import build_latest_holdout_comparison
from app.storage.database import connect_database


INDICATOR_CODE = "industrial_parks_count"
INDICATOR_LABEL = "Number of industrial parks"


def main() -> None:
    st.set_page_config(
        page_title="Industrial Parks Dashboard",
        layout="wide",
    )
    st.title("Industrial Parks Indicator Demo")

    if not DATABASE_PATH.exists():
        st.error(f"Database not found: {DATABASE_PATH}")
        st.stop()

    with connect_database(DATABASE_PATH) as connection:
        actuals = load_actual_values(connection, INDICATOR_CODE)
        forecasts = load_future_forecasts(connection, INDICATOR_CODE)
        holdout = build_latest_holdout_comparison(connection, INDICATOR_CODE)

    if actuals.empty:
        st.error(f"No values found for indicator '{INDICATOR_CODE}'.")
        st.stop()

    regions = sorted(actuals["region"].unique())
    selected_regions = st.sidebar.multiselect(
        "Regions",
        options=regions,
        default=regions,
    )
    if not selected_regions:
        st.warning("Select at least one region.")
        st.stop()

    actuals = actuals[actuals["region"].isin(selected_regions)]
    forecasts = forecasts[forecasts["region"].isin(selected_regions)]
    holdout_df = holdout_to_dataframe(holdout)
    if not holdout_df.empty:
        holdout_df = holdout_df[holdout_df["region"].isin(selected_regions)]

    render_summary(actuals, forecasts, holdout)
    render_historical_chart(actuals)
    render_forecast_views(actuals, forecasts)
    render_holdout_comparison(actuals, holdout_df, holdout.skipped_regions, selected_regions)


def load_actual_values(connection, indicator_code: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT
            r.name AS region,
            i.code AS indicator,
            iv.period_date AS period_date,
            iv.value AS value
        FROM indicator_values iv
        JOIN indicators i ON i.id = iv.indicator_id
        JOIN regions r ON r.id = iv.region_id
        WHERE i.code = ?
        ORDER BY iv.period_date, r.name
        """,
        connection,
        params=(indicator_code,),
    )
    return normalize_date_column(frame, "period_date")


def load_future_forecasts(connection, indicator_code: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT
            r.name AS region,
            i.code AS indicator,
            f.forecast_date AS period_date,
            f.predicted_value AS value,
            f.model_name AS model
        FROM indicator_forecasts f
        JOIN indicators i ON i.id = f.indicator_id
        JOIN regions r ON r.id = f.region_id
        WHERE i.code = ?
        ORDER BY f.forecast_date, r.name
        """,
        connection,
        params=(indicator_code,),
    )
    return normalize_date_column(frame, "period_date")


def normalize_date_column(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if not frame.empty:
        frame[column] = pd.to_datetime(frame[column])
    return frame


def holdout_to_dataframe(holdout) -> pd.DataFrame:
    rows = [asdict(comparison) for comparison in holdout.comparisons]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame.rename(
        columns={
            "region_name": "region",
            "target_date": "period_date",
        }
    )
    frame["period_date"] = pd.to_datetime(frame["period_date"])
    return frame


def render_summary(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
    holdout,
) -> None:
    latest_date = actuals["period_date"].max()
    latest_actuals = actuals[actuals["period_date"] == latest_date]

    columns = st.columns(4)
    columns[0].metric("Latest snapshot", latest_date.date().isoformat())
    columns[1].metric("Regions shown", str(actuals["region"].nunique()))
    columns[2].metric("Latest total", f"{latest_actuals['value'].sum():.0f}")
    columns[3].metric("Future forecasts", str(len(forecasts)))

    if holdout.target_date is not None:
        st.caption(
            "Holdout comparison trains on snapshots before "
            f"{holdout.target_date.isoformat()} and predicts that latest date."
        )


def render_historical_chart(actuals: pd.DataFrame) -> None:
    st.subheader("Historical Indicator Values")
    chart = (
        alt.Chart(actuals)
        .mark_line(point=True)
        .encode(
            x=alt.X("period_date:T", title="Snapshot date"),
            y=alt.Y("value:Q", title=INDICATOR_LABEL),
            color=alt.Color("region:N", title="Region"),
            tooltip=[
                alt.Tooltip("region:N", title="Region"),
                alt.Tooltip("period_date:T", title="Date"),
                alt.Tooltip("value:Q", title=INDICATOR_LABEL, format=".0f"),
            ],
        )
        .properties(height=420)
    )
    st.altair_chart(chart, use_container_width=True)


def render_forecast_views(actuals: pd.DataFrame, forecasts: pd.DataFrame) -> None:
    st.subheader("Actual Values and Future Forecast")
    if forecasts.empty:
        st.info("No future forecast rows found. Run `python -m app.main` to populate forecasts.")
        return

    line_data = build_future_forecast_line_data(actuals, forecasts)
    bar_data = build_future_forecast_bar_data(actuals, forecasts)
    line_column, bar_column = st.columns(2)
    with line_column:
        st.altair_chart(
            build_series_line_chart(
                line_data,
                "Date",
                color_domain=["Actual", "Forecast"],
                color_range=["#2563eb", "#f97316"],
            ),
            use_container_width=True,
        )
    with bar_column:
        bar_domain = list(dict.fromkeys(bar_data["series_type"]))
        st.altair_chart(
            build_grouped_bar_chart(
                bar_data,
                color_domain=bar_domain,
                color_range=build_actual_forecast_color_range(bar_domain),
            ),
            use_container_width=True,
        )


def build_future_forecast_line_data(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
) -> pd.DataFrame:
    actual_plot = actuals.assign(series_type="Actual")
    latest_actuals = (
        actuals.sort_values("period_date")
        .groupby("region", as_index=False)
        .tail(1)
        .assign(series_type="Forecast")
    )
    forecast_plot = forecasts.assign(series_type="Forecast")
    return pd.concat(
        [
            actual_plot[["region", "period_date", "value", "series_type"]],
            latest_actuals[["region", "period_date", "value", "series_type"]],
            forecast_plot[["region", "period_date", "value", "series_type"]],
        ],
        ignore_index=True,
    )


def build_future_forecast_bar_data(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
) -> pd.DataFrame:
    latest_actuals = (
        actuals.sort_values("period_date")
        .groupby("region", as_index=False)
        .tail(1)
        .assign(series_type="Actual latest")
    )
    forecast_plot = forecasts.copy()
    forecast_plot["series_type"] = forecast_plot["period_date"].dt.strftime("Forecast %Y-%m-%d")
    return pd.concat(
        [
            latest_actuals[["region", "period_date", "value", "series_type"]],
            forecast_plot[["region", "period_date", "value", "series_type"]],
        ],
        ignore_index=True,
    )


def build_series_line_chart(
    data: pd.DataFrame,
    x_title: str,
    color_domain: list[str],
    color_range: list[str],
) -> alt.Chart:
    chart = (
        alt.Chart(data)
        .mark_line(point=True)
        .encode(
            x=alt.X("period_date:T", title=x_title),
            y=alt.Y("value:Q", title=INDICATOR_LABEL),
            color=alt.Color(
                "series_type:N",
                title="Series",
                scale=alt.Scale(
                    domain=color_domain,
                    range=color_range,
                ),
            ),
            detail="region:N",
            tooltip=[
                alt.Tooltip("region:N", title="Region"),
                alt.Tooltip("series_type:N", title="Series"),
                alt.Tooltip("period_date:T", title="Date"),
                alt.Tooltip("value:Q", title=INDICATOR_LABEL, format=".2f"),
            ],
        )
        .properties(height=420)
    )
    return chart


def build_grouped_bar_chart(
    data: pd.DataFrame,
    color_domain: list[str],
    color_range: list[str],
) -> alt.Chart:
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("region:N", title="Region", sort="-y"),
            xOffset=alt.XOffset("series_type:N"),
            y=alt.Y("value:Q", title=INDICATOR_LABEL),
            color=alt.Color(
                "series_type:N",
                title="Series",
                scale=alt.Scale(domain=color_domain, range=color_range),
            ),
            tooltip=[
                alt.Tooltip("region:N", title="Region"),
                alt.Tooltip("series_type:N", title="Series"),
                alt.Tooltip("period_date:T", title="Date"),
                alt.Tooltip("value:Q", title=INDICATOR_LABEL, format=".2f"),
            ],
        )
        .properties(height=420)
    )


def render_holdout_comparison(
    actuals: pd.DataFrame,
    holdout_df: pd.DataFrame,
    skipped_regions: tuple[str, ...],
    selected_regions: list[str],
) -> None:
    st.subheader("Latest Actual vs Holdout Forecast")
    visible_skipped = sorted(set(skipped_regions).intersection(set(selected_regions)))
    if holdout_df.empty:
        st.info("No holdout comparison rows are available for the selected regions.")
        if visible_skipped:
            st.caption(f"Skipped regions without enough holdout data: {', '.join(visible_skipped)}")
        return

    line_data = build_holdout_line_data(actuals, holdout_df)
    bar_data = build_holdout_bar_data(holdout_df)

    line_column, bar_column = st.columns(2)
    with line_column:
        st.altair_chart(
            build_series_line_chart(
                line_data,
                "Snapshot date",
                color_domain=["Actual", "Holdout forecast"],
                color_range=["#2563eb", "#f97316"],
            ),
            use_container_width=True,
        )
    with bar_column:
        st.altair_chart(
            build_grouped_bar_chart(
                bar_data,
                color_domain=["Actual latest", "Forecasted latest"],
                color_range=["#2563eb", "#f97316"],
            ),
            use_container_width=True,
        )

    table = holdout_df[
        [
            "region",
            "period_date",
            "actual_value",
            "predicted_value",
            "difference",
            "model_name",
            "training_points",
        ]
    ].sort_values("difference", key=lambda column: column.abs(), ascending=False)
    st.dataframe(table, use_container_width=True, hide_index=True)

    if visible_skipped:
        st.caption(f"Skipped regions without enough holdout data: {', '.join(visible_skipped)}")


def build_holdout_bar_data(holdout_df: pd.DataFrame) -> pd.DataFrame:
    comparison = holdout_df.melt(
        id_vars=["region", "period_date", "model_name"],
        value_vars=["actual_value", "predicted_value"],
        var_name="series_type",
        value_name="value",
    )
    comparison["series_type"] = comparison["series_type"].map(
        {
            "actual_value": "Actual latest",
            "predicted_value": "Forecasted latest",
        }
    )
    return comparison[["region", "period_date", "value", "series_type"]]


def build_actual_forecast_color_range(color_domain: list[str]) -> list[str]:
    return [
        "#2563eb" if series_name.startswith("Actual") else "#f97316"
        for series_name in color_domain
    ]


def build_holdout_line_data(actuals: pd.DataFrame, holdout_df: pd.DataFrame) -> pd.DataFrame:
    target_date = holdout_df["period_date"].max()
    regions = set(holdout_df["region"])
    actual_plot = actuals[actuals["region"].isin(regions)].assign(series_type="Actual")
    training_anchors = (
        actual_plot[actual_plot["period_date"] < target_date]
        .sort_values("period_date")
        .groupby("region", as_index=False)
        .tail(1)
        .assign(series_type="Holdout forecast")
    )
    forecast_points = holdout_df.rename(columns={"predicted_value": "value"}).assign(
        series_type="Holdout forecast"
    )
    return pd.concat(
        [
            actual_plot[["region", "period_date", "value", "series_type"]],
            training_anchors[["region", "period_date", "value", "series_type"]],
            forecast_points[["region", "period_date", "value", "series_type"]],
        ],
        ignore_index=True,
    )


if __name__ == "__main__":
    main()
