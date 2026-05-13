from __future__ import annotations

from app.forecasting.models import ForecastModel, LastValueModel, LinearRegressionModel
from app.forecasting.series import IndicatorRegionSeries


IMPLEMENTED_MODELS: tuple[ForecastModel, ...] = (
    LinearRegressionModel(),
    LastValueModel(),
)


def select_forecast_model(
    series: IndicatorRegionSeries,
    candidate_models: tuple[ForecastModel, ...] = IMPLEMENTED_MODELS,
) -> ForecastModel:
    for model in candidate_models:
        if model.can_fit(series):
            return model

    raise ValueError(
        f"No forecast model can fit indicator_id={series.indicator_id}, region_id={series.region_id}"
    )

