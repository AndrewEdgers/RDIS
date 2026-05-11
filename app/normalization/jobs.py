from __future__ import annotations

import csv
from pathlib import Path

from app.config import NORMALIZED_INDICATORS_PATH, get_source
from app.normalization.industrial_parks import (
    build_industrial_parks_count_by_region,
    validate_normalized_rows,
)


def run_industrial_parks_normalization() -> Path:
    source = get_source("industrial_parks")
    clean_rows = read_clean_rows(source.clean_output_path)
    normalized_rows = build_industrial_parks_count_by_region(clean_rows)
    validate_normalized_rows(normalized_rows)
    write_normalized_rows(NORMALIZED_INDICATORS_PATH, normalized_rows)
    print(f"[industrial_parks] wrote {len(normalized_rows)} rows to {NORMALIZED_INDICATORS_PATH}")
    return NORMALIZED_INDICATORS_PATH


def run_industrial_parks_history_normalization(clean_output_paths: list[Path] | None = None) -> Path:
    source = get_source("industrial_parks")
    normalized_rows: list[dict[str, str | int]] = []
    paths = clean_output_paths or sorted(source.historical_clean_dir.glob("*.csv"))
    if not paths:
        raise ValueError(f"No historical clean snapshots found in {source.historical_clean_dir}")

    for clean_output_path in sorted(paths):
        clean_rows = read_clean_rows(clean_output_path)
        normalized_rows.extend(build_industrial_parks_count_by_region(clean_rows))

    validate_normalized_rows(normalized_rows)
    write_normalized_rows(NORMALIZED_INDICATORS_PATH, normalized_rows)
    print(f"[industrial_parks] wrote {len(normalized_rows)} rows to {NORMALIZED_INDICATORS_PATH}")
    return NORMALIZED_INDICATORS_PATH


def read_clean_rows(clean_output_path: Path) -> list[dict[str, str]]:
    with clean_output_path.open("r", encoding="utf-8", newline="") as file_handle:
        return list(csv.DictReader(file_handle))


def write_normalized_rows(
    output_path: Path,
    rows: list[dict[str, str | int]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["region", "indicator_name", "value", "date"]
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
