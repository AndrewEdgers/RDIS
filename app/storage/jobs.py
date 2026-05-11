from __future__ import annotations

from pathlib import Path

from app.config import DATABASE_PATH, NORMALIZED_INDICATORS_PATH
from app.storage.database import load_normalized_indicators_to_database


def run_indicator_storage(
    normalized_indicators_path: Path = NORMALIZED_INDICATORS_PATH,
    database_path: Path = DATABASE_PATH,
) -> Path:
    row_count = load_normalized_indicators_to_database(
        normalized_indicators_path=normalized_indicators_path,
        database_path=database_path,
    )
    print(f"[storage] wrote {row_count} indicator rows to {database_path}")
    return database_path
