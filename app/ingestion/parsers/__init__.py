from collections.abc import Callable
from pathlib import Path

from app.ingestion.parsers.industrial_parks import parse_industrial_parks_summary_workbook


ParserFn = Callable[[Path, dict[str, object], dict[str, object]], list[dict[str, object]]]


PARSERS: dict[str, ParserFn] = {
    "industrial_parks_summary": parse_industrial_parks_summary_workbook,
}


def get_parser(name: str) -> ParserFn:
    try:
        return PARSERS[name]
    except KeyError as exc:
        known_parsers = ", ".join(sorted(PARSERS))
        raise KeyError(f"Unknown parser '{name}'. Known parsers: {known_parsers}") from exc
