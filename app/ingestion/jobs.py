from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urlparse

from requests import RequestException

from app.config import SourceConfig, get_source
from app.ingestion.data_gov_client import (
    download_resource,
    fetch_dataset_metadata,
    select_resource,
    select_resources,
)
from app.ingestion.parsers import get_parser
from app.ingestion.workbook_conversion import convert_xls_to_xlsx


SUPPORTED_WORKBOOK_SUFFIXES = {".xlsx"}
CONVERTIBLE_WORKBOOK_SUFFIXES = {".xls"}


@dataclass(frozen=True)
class ResourceDownload:
    resource: dict
    url: str
    snapshot_date: str
    raw_binary_path: Path
    clean_output_path: Path


def run_industrial_parks_ingestion() -> Path:
    return run_source_ingestion("industrial_parks")


def run_industrial_parks_history_ingestion() -> list[Path]:
    return run_source_history_ingestion("industrial_parks")


def run_source_ingestion(source_id: str) -> Path:
    source = get_source(source_id)
    dataset_metadata = discover_resource(source)
    selected_resource = select_resource(
        dataset_metadata,
        strategy=source.resource_strategy,
        preferred_formats=source.preferred_formats,
    )
    download_selected_resource(source, selected_resource)
    snapshot_date = derive_snapshot_date(selected_resource, selected_resource["url"])
    parsed_rows = parse_source(source, selected_resource, source.raw_binary_path, snapshot_date)
    write_clean_csv(source.clean_output_path, parsed_rows)
    write_manifest(source, selected_resource, parsed_rows)
    print(f"[{source.source_id}] wrote {len(parsed_rows)} rows to {source.clean_output_path}")
    return source.clean_output_path


def run_source_history_ingestion(source_id: str) -> list[Path]:
    source = get_source(source_id)
    dataset_metadata = discover_resource(source)
    resources = select_resources(
        dataset_metadata,
        strategy="all",
        preferred_formats=source.preferred_formats,
    )

    clean_output_paths: list[Path] = []
    manifest_entries: list[dict[str, object]] = []
    for download in build_resource_downloads(source, resources):
        manifest_entry = build_download_manifest_entry(download)
        try:
            ensure_resource_downloaded(download, manifest_entry)
        except RequestException as exc:
            manifest_entry["status"] = "download_failed"
            manifest_entry["error"] = str(exc)
            manifest_entries.append(manifest_entry)
            print(
                f"[{source.source_id}] failed to download snapshot {download.snapshot_date}: {exc}"
            )
            continue

        parseable_workbook_path = prepare_workbook_for_parsing(source, download, manifest_entry)
        if parseable_workbook_path is not None:
            parsed_rows = parse_source(
                source,
                download.resource,
                parseable_workbook_path,
                download.snapshot_date,
            )
            write_clean_csv(download.clean_output_path, parsed_rows)
            clean_output_paths.append(download.clean_output_path)
            manifest_entry["status"] = "parsed"
            manifest_entry["clean_output_path"] = str(download.clean_output_path)
            manifest_entry["row_count"] = len(parsed_rows)
            print(
                f"[{source.source_id}] wrote {len(parsed_rows)} rows "
                f"to {download.clean_output_path}"
            )
        else:
            manifest_entry["status"] = "raw_downloaded"
            manifest_entry["skip_reason"] = (
                f"Parser supports {sorted(SUPPORTED_WORKBOOK_SUFFIXES)} "
                f"and converts {sorted(CONVERTIBLE_WORKBOOK_SUFFIXES)}, "
                f"got '{download.raw_binary_path.suffix.lower()}'"
            )
            print(
                f"[{source.source_id}] downloaded raw snapshot {download.snapshot_date} "
                f"to {download.raw_binary_path}"
            )

        manifest_entries.append(manifest_entry)

    write_history_manifest(source, manifest_entries)
    return clean_output_paths


def discover_resource(source: SourceConfig) -> dict:
    dataset_metadata = fetch_dataset_metadata(source.base_url, source.dataset_id)
    write_json(source.raw_metadata_path, dataset_metadata)
    return dataset_metadata


def download_selected_resource(source: SourceConfig, resource: dict) -> None:
    download_resource(resource["url"], source.raw_binary_path)


def parse_source(
    source: SourceConfig,
    resource: dict,
    workbook_path: Path | None = None,
    snapshot_date: str | None = None,
) -> list[dict[str, object]]:
    parser = get_parser(source.parser)
    context = {
        "dataset_id": source.dataset_id,
        "resource_id": resource.get("id"),
        "resource_url": resource.get("url"),
        "resource_last_modified": resource.get("last_modified"),
        "source_snapshot_date": snapshot_date,
        "ingested_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    return parser(workbook_path or source.raw_binary_path, source.parser_options, context)


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


def write_history_manifest(source: SourceConfig, entries: list[dict[str, object]]) -> None:
    manifest = {
        "source_id": source.source_id,
        "dataset_id": source.dataset_id,
        "parser": source.parser,
        "schema_version": source.parser_options.get("schema_version"),
        "resource_count": len(entries),
        "parsed_resource_count": sum(1 for entry in entries if entry["status"] == "parsed"),
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "resources": entries,
    }
    write_json(source.historical_manifest_path, manifest)


def write_json(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)


def build_resource_downloads(
    source: SourceConfig,
    resources: list[dict],
) -> list[ResourceDownload]:
    downloads: list[ResourceDownload] = []
    seen_urls: set[str] = set()
    for resource in resources:
        for url in resource_download_urls(resource):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            snapshot_date = derive_snapshot_date(resource, url)
            downloads.append(
                ResourceDownload(
                    resource=resource,
                    url=url,
                    snapshot_date=snapshot_date,
                    raw_binary_path=build_raw_history_path(source, resource, url, snapshot_date),
                    clean_output_path=build_clean_history_path(source, resource, snapshot_date),
                )
            )
    return sorted(downloads, key=lambda download: (download.snapshot_date, download.url))


def resource_download_urls(resource: dict) -> list[str]:
    urls = [str(resource["url"])]
    archiver = resource.get("archiver") or {}
    for key in ("url_redirected_to", "cache_url"):
        url = archiver.get(key)
        if url and url not in urls:
            urls.append(str(url))
    return urls


def derive_snapshot_date(resource: dict, url: str) -> str:
    date_from_url = extract_date_from_url(url)
    if date_from_url is not None:
        return date_from_url

    archiver = resource.get("archiver") or {}
    for value in (
        resource.get("last_modified"),
        archiver.get("resource_timestamp"),
        archiver.get("updated"),
        resource.get("created"),
    ):
        if value:
            return str(value)[:10]

    raise ValueError(f"Could not derive snapshot date for resource {resource.get('id')}")


def extract_date_from_url(url: str) -> str | None:
    day_first_match = re.search(r"(?<!\d)(\d{2})-(\d{2})-(\d{2}|\d{4})(?!\d)", url)
    if day_first_match:
        day, month, year = day_first_match.groups()
        if len(year) == 2:
            year = f"20{year}"
        return f"{year}-{month}-{day}"

    iso_match = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", url)
    if iso_match:
        return "-".join(iso_match.groups())

    return None


def build_raw_history_path(
    source: SourceConfig,
    resource: dict,
    url: str,
    snapshot_date: str,
) -> Path:
    extension = Path(urlparse(url).path).suffix.lower() or ".bin"
    return source.historical_raw_dir / f"{build_history_stem(source, resource, snapshot_date)}{extension}"


def build_clean_history_path(source: SourceConfig, resource: dict, snapshot_date: str) -> Path:
    return source.historical_clean_dir / f"{build_history_stem(source, resource, snapshot_date)}.csv"


def build_history_stem(source: SourceConfig, resource: dict, snapshot_date: str) -> str:
    resource_id = str(resource.get("id") or "unknown")[:8]
    return f"{source.source_id}_{snapshot_date}_{resource_id}"


def is_supported_workbook_path(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_WORKBOOK_SUFFIXES


def is_convertible_workbook_path(path: Path) -> bool:
    return path.suffix.lower() in CONVERTIBLE_WORKBOOK_SUFFIXES


def prepare_workbook_for_parsing(
    source: SourceConfig,
    download: ResourceDownload,
    manifest_entry: dict[str, object],
) -> Path | None:
    if is_supported_workbook_path(download.raw_binary_path):
        return download.raw_binary_path

    if is_convertible_workbook_path(download.raw_binary_path):
        converted_path = build_converted_history_path(
            source,
            download.resource,
            download.snapshot_date,
        )
        convert_xls_to_xlsx(download.raw_binary_path, converted_path)
        manifest_entry["converted_workbook_path"] = str(converted_path)
        return converted_path

    return None


def build_converted_history_path(
    source: SourceConfig,
    resource: dict,
    snapshot_date: str,
) -> Path:
    return source.historical_converted_dir / f"{build_history_stem(source, resource, snapshot_date)}.xlsx"


def build_download_manifest_entry(download: ResourceDownload) -> dict[str, object]:
    return {
        "resource_id": download.resource.get("id"),
        "resource_name": download.resource.get("name"),
        "resource_url": download.url,
        "resource_last_modified": download.resource.get("last_modified"),
        "snapshot_date": download.snapshot_date,
        "raw_binary_path": str(download.raw_binary_path),
    }


def ensure_resource_downloaded(
    download: ResourceDownload,
    manifest_entry: dict[str, object],
) -> None:
    if download.raw_binary_path.exists() and download.raw_binary_path.stat().st_size > 0:
        manifest_entry["download_status"] = "cached"
        return

    download_resource(download.url, download.raw_binary_path)
    manifest_entry["download_status"] = "downloaded"
