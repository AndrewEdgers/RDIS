from __future__ import annotations

import csv
import json
from datetime import datetime, UTC
from pathlib import Path

from app.config import SourceConfig, get_source
from app.ingestion.data_gov_client import download_resource, fetch_dataset_metadata, select_resource
from app.ingestion.parsers import get_parser


def run_industrial_parks_ingestion() -> Path:
    return run_source_ingestion("industrial_parks")


def run_source_ingestion(source_id: str) -> Path:
    source = get_source(source_id)
    dataset_metadata = discover_resource(source)
    selected_resource = select_resource(
        dataset_metadata,
        strategy=source.resource_strategy,
        preferred_formats=source.preferred_formats,
    )
    download_selected_resource(source, selected_resource)
    parsed_rows = parse_source(source, selected_resource)
    write_clean_csv(source.clean_output_path, parsed_rows)
    write_manifest(source, selected_resource, parsed_rows)
    print(f"[{source.source_id}] wrote {len(parsed_rows)} rows to {source.clean_output_path}")
    return source.clean_output_path


def discover_resource(source: SourceConfig) -> dict:
    dataset_metadata = fetch_dataset_metadata(source.base_url, source.dataset_id)
    write_json(source.raw_metadata_path, dataset_metadata)
    return dataset_metadata


def download_selected_resource(source: SourceConfig, resource: dict) -> None:
    download_resource(resource["url"], source.raw_binary_path)


def parse_source(source: SourceConfig, resource: dict) -> list[dict[str, object]]:
    parser = get_parser(source.parser)
    context = {
        "dataset_id": source.dataset_id,
        "resource_id": resource.get("id"),
        "resource_url": resource.get("url"),
        "resource_last_modified": resource.get("last_modified"),
        "ingested_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    return parser(source.raw_binary_path, source.parser_options, context)


def write_clean_csv(output_path: Path, rows: list[dict[str, object]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("No parsed rows were produced")

    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(source: SourceConfig, resource: dict, rows: list[dict[str, object]]) -> None:
    manifest = {
        "source_id": source.source_id,
        "dataset_id": source.dataset_id,
        "parser": source.parser,
        "schema_version": source.parser_options.get("schema_version"),
        "resource_id": resource.get("id"),
        "resource_name": resource.get("name"),
        "resource_url": resource.get("url"),
        "resource_last_modified": resource.get("last_modified"),
        "raw_metadata_path": str(source.raw_metadata_path),
        "raw_binary_path": str(source.raw_binary_path),
        "clean_output_path": str(source.clean_output_path),
        "row_count": len(rows),
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    write_json(source.manifest_path, manifest)


def write_json(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)
