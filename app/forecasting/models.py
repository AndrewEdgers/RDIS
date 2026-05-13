from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Protocol

from app.forecasting.series import IndicatorRegionSeries, SeriesPoint


@dataclass(frozen=True)
class ForecastPoint:
    forecast_date: date
    predicted_value: float


class ForecastModel(Protocol):
    name: str

    def can_fit(self, series: IndicatorRegionSeries) -> bool:
        ...

    def forecast(self, series: IndicatorRegionSeries, horizon: int) -> list[ForecastPoint]:
        ...

    def forecast_dates(
        self,
        series: IndicatorRegionSeries,
        target_dates: list[date],
    ) -> list[ForecastPoint]:
        ...


class LastValueModel:
    name = "last_value"

    def can_fit(self, series: IndicatorRegionSeries) -> bool:
        return len(series.points) >= 1

    def forecast(self, series: IndicatorRegionSeries, horizon: int) -> list[ForecastPoint]:
        validate_horizon(horizon)
        if not self.can_fit(series):
            raise ValueError("last_value requires at least one data point")

        points = sort_points(series.points)
        return self.forecast_dates(series, build_forecast_dates(points, horizon))

    def forecast_dates(
        self,
        series: IndicatorRegionSeries,
        target_dates: list[date],
    ) -> list[ForecastPoint]:
        if not self.can_fit(series):
            raise ValueError("last_value requires at least one data point")

        points = sort_points(series.points)
        last_value = points[-1].value
        return [
            ForecastPoint(forecast_date=target_date, predicted_value=last_value)
            for target_date in target_dates
        ]


class LinearRegressionModel:
    name = "linear_regression"
    minimum_points = 3

    def can_fit(self, series: IndicatorRegionSeries) -> bool:
        unique_dates = {point.period_date for point in series.points}
        return len(unique_dates) >= self.minimum_points

    def forecast(self, series: IndicatorRegionSeries, horizon: int) -> list[ForecastPoint]:
        validate_horizon(horizon)
        if not self.can_fit(series):
            raise ValueError("linear_regression requires at least three dated points")

        points = sort_points(series.points)
        return self.forecast_dates(series, build_forecast_dates(points, horizon))

    def forecast_dates(
        self,
        series: IndicatorRegionSeries,
        target_dates: list[date],
    ) -> list[ForecastPoint]:
        if not self.can_fit(series):
            raise ValueError("linear_regression requires at least three dated points")

        points = sort_points(series.points)
        xs = [float(point.period_date.toordinal()) for point in points]
        ys = [point.value for point in points]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denominator = sum((x_value - mean_x) ** 2 for x_value in xs)
        if denominator == 0:
            raise ValueError("linear_regression requires at least two unique dates")

        numerator = sum(
            (x_value - mean_x) * (y_value - mean_y)
            for x_value, y_value in zip(xs, ys)
        )
        slope = numerator / denominator
        intercept = mean_y - slope * mean_x

        return [
            ForecastPoint(
                forecast_date=target_date,
                predicted_value=slope * float(target_date.toordinal()) + intercept,
            )
            for target_date in target_dates
        ]


class ArimaModel:
    name = "arima"
    minimum_regular_yearly_points = 8

    def can_fit(self, series: IndicatorRegionSeries) -> bool:
        return False

    def forecast(self, series: IndicatorRegionSeries, horizon: int) -> list[ForecastPoint]:
        raise NotImplementedError("ARIMA is reserved for regular yearly series with enough history")

    def forecast_dates(
        self,
        series: IndicatorRegionSeries,
        target_dates: list[date],
    ) -> list[ForecastPoint]:
        raise NotImplementedError("ARIMA is reserved for regular yearly series with enough history")


class ProphetModel:
    name = "prophet"
    minimum_regular_monthly_points = 24

    def can_fit(self, series: IndicatorRegionSeries) -> bool:
        return False

    def forecast(self, series: IndicatorRegionSeries, horizon: int) -> list[ForecastPoint]:
        raise NotImplementedError("Prophet is reserved for regular monthly series with enough history")

    def forecast_dates(
        self,
        series: IndicatorRegionSeries,
        target_dates: list[date],
    ) -> list[ForecastPoint]:
        raise NotImplementedError("Prophet is reserved for regular monthly series with enough history")


def validate_horizon(horizon: int) -> None:
    if horizon < 1:
        raise ValueError("Forecast horizon must be at least 1")


def sort_points(points: tuple[SeriesPoint, ...]) -> tuple[SeriesPoint, ...]:
    return tuple(sorted(points, key=lambda point: point.period_date))


def build_forecast_dates(points: tuple[SeriesPoint, ...], horizon: int) -> list[date]:
    validate_horizon(horizon)
    if not points:
        raise ValueError("Cannot build forecast dates without historical points")

    points = sort_points(points)
    last_date = points[-1].period_date
    frequency = infer_frequency(points)
    if frequency == "monthly":
        return [add_months(last_date, step) for step in range(1, horizon + 1)]
    return [add_years(last_date, step) for step in range(1, horizon + 1)]


def infer_frequency(points: tuple[SeriesPoint, ...]) -> str:
    if len(points) < 2:
        return "yearly"

    intervals = [
        (current.period_date - previous.period_date).days
        for previous, current in zip(points, points[1:])
    ]
    median_interval = median(intervals)
    if 24 <= median_interval <= 45:
        return "monthly"
    return "yearly"


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
