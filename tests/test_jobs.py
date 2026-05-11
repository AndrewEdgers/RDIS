from pathlib import Path

from app.config import SourceConfig, get_source
from app.ingestion import jobs


def test_write_clean_csv_writes_header_and_rows(tmp_path: Path):
    output_path = tmp_path / "industrial_parks_register_clean.csv"
    rows = [
        {"registration_no": 1, "park_name": "Alpha"},
        {"registration_no": 2, "park_name": "Beta"},
    ]

    jobs.write_clean_csv(output_path, rows)

    content = output_path.read_text(encoding="utf-8")
    assert "registration_no,park_name" in content
    assert "1,Alpha" in content


def test_write_manifest_includes_row_count(tmp_path: Path):
    source = get_source("industrial_parks")
    overridden_source = SourceConfig(
        source_id=source.source_id,
        source_type=source.source_type,
        base_url=source.base_url,
        dataset_id=source.dataset_id,
        resource_strategy=source.resource_strategy,
        parser=source.parser,
        raw_metadata_path=tmp_path / "raw.json",
        raw_binary_path=tmp_path / "raw.xlsx",
        clean_output_path=tmp_path / "clean.csv",
        manifest_path=tmp_path / "manifest.json",
        preferred_formats=source.preferred_formats,
        parser_options=source.parser_options,
    )

    jobs.write_manifest(
        overridden_source,
        {
            "id": "resource-id",
            "name": "Industrial parks",
            "url": "https://example.com",
            "last_modified": "2025-01-01",
        },
        [{"registration_no": 1}],
    )

    manifest = overridden_source.manifest_path.read_text(encoding="utf-8")
    assert '"row_count": 1' in manifest


def test_extract_date_from_url_handles_industrial_parks_filenames():
    assert (
        jobs.extract_date_from_url(
            "https://example.com/reiestr-industrialnikh-parkiv_01-05-2025.xlsx"
        )
        == "2025-05-01"
    )
    assert jobs.extract_date_from_url("https://example.com/reiestr_ip_st_na_15-02-22.xls") == "2022-02-15"


def test_build_resource_downloads_includes_archived_resource_url(tmp_path: Path):
    source = get_source("industrial_parks")
    overridden_source = SourceConfig(
        source_id=source.source_id,
        source_type=source.source_type,
        base_url=source.base_url,
        dataset_id=source.dataset_id,
        resource_strategy=source.resource_strategy,
        parser=source.parser,
        raw_metadata_path=tmp_path / "raw.json",
        raw_binary_path=tmp_path / "raw.xlsx",
        clean_output_path=tmp_path / "clean.csv",
        manifest_path=tmp_path / "manifest.json",
        preferred_formats=source.preferred_formats,
        parser_options=source.parser_options,
    )
    resource = {
        "id": "7c91f8d0-f153-4197-b47b-da8f65c6e800",
        "name": "Industrial parks",
        "url": "https://example.com/reiestr-industrialnikh-parkiv_01-05-2025.xlsx",
        "last_modified": "2025-05-01T09:28:21.204634",
        "archiver": {
            "url_redirected_to": "https://example.com/reiestr-industrialnikh-parkiv_06-05-2023.xlsx",
            "resource_timestamp": "2023-05-06T19:31:43.730177",
        },
    }

    downloads = jobs.build_resource_downloads(overridden_source, [resource])

    assert [download.snapshot_date for download in downloads] == ["2023-05-06", "2025-05-01"]
    assert downloads[0].raw_binary_path == (
        tmp_path / "industrial_parks" / "raw" / "industrial_parks_2023-05-06_7c91f8d0.xlsx"
    )
    assert downloads[1].clean_output_path == (
        tmp_path / "industrial_parks" / "clean" / "industrial_parks_2025-05-01_7c91f8d0.csv"
    )


def test_prepare_workbook_for_parsing_converts_xls(tmp_path: Path, monkeypatch):
    source = get_source("industrial_parks")
    overridden_source = SourceConfig(
        source_id=source.source_id,
        source_type=source.source_type,
        base_url=source.base_url,
        dataset_id=source.dataset_id,
        resource_strategy=source.resource_strategy,
        parser=source.parser,
        raw_metadata_path=tmp_path / "raw.json",
        raw_binary_path=tmp_path / "raw.xlsx",
        clean_output_path=tmp_path / "clean.csv",
        manifest_path=tmp_path / "manifest.json",
        preferred_formats=source.preferred_formats,
        parser_options=source.parser_options,
    )
    download = jobs.ResourceDownload(
        resource={"id": "2e670248-f3e2-49c8-a202-3595955af87a"},
        url="https://example.com/reiestr_ip_st_na_15-02-22.xls",
        snapshot_date="2022-02-15",
        raw_binary_path=tmp_path / "raw" / "industrial_parks_2022-02-15_2e670248.xls",
        clean_output_path=tmp_path / "clean.csv",
    )
    manifest_entry = {}

    def fake_convert_xls_to_xlsx(source_path: Path, output_path: Path) -> Path:
        assert source_path == download.raw_binary_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("converted", encoding="utf-8")
        return output_path

    monkeypatch.setattr(jobs, "convert_xls_to_xlsx", fake_convert_xls_to_xlsx)

    parseable_path = jobs.prepare_workbook_for_parsing(
        overridden_source,
        download,
        manifest_entry,
    )

    assert parseable_path == (
        tmp_path / "industrial_parks" / "converted" / "industrial_parks_2022-02-15_2e670248.xlsx"
    )
    assert manifest_entry["converted_workbook_path"] == str(parseable_path)


def test_ensure_resource_downloaded_reuses_existing_raw_file(tmp_path: Path, monkeypatch):
    raw_path = tmp_path / "raw" / "snapshot.xlsx"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("existing", encoding="utf-8")
    download = jobs.ResourceDownload(
        resource={"id": "resource-id"},
        url="https://example.com/snapshot.xlsx",
        snapshot_date="2025-05-01",
        raw_binary_path=raw_path,
        clean_output_path=tmp_path / "clean.csv",
    )
    manifest_entry = {}

    def fail_download_resource(url: str, output_path: Path) -> None:
        raise AssertionError("download should not run for cached files")

    monkeypatch.setattr(jobs, "download_resource", fail_download_resource)

    jobs.ensure_resource_downloaded(download, manifest_entry)

    assert manifest_entry["download_status"] == "cached"
