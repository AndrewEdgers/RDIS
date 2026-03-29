from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    source_type: str
    base_url: str
    dataset_id: str
    resource_strategy: str
    parser: str
    raw_metadata_path: Path
    raw_binary_path: Path
    clean_output_path: Path
    manifest_path: Path
    preferred_formats: tuple[str, ...] = ("XLSX",)
    parser_options: dict[str, object] = field(default_factory=dict)


SOURCES: dict[str, SourceConfig] = {
    "industrial_parks": SourceConfig(
        source_id="industrial_parks",
        source_type="ckan",
        base_url="https://data.gov.ua/api/3/action",
        dataset_id="69d235d7-cbbb-4650-964b-df3c68ddc478",
        resource_strategy="latest",
        parser="industrial_parks_summary",
        raw_metadata_path=DATA_DIR / "industrial_parks.json",
        raw_binary_path=DATA_DIR / "industrial_parks_latest.xlsx",
        clean_output_path=DATA_DIR / "industrial_parks_register_clean.csv",
        manifest_path=DATA_DIR / "industrial_parks_register_clean.manifest.json",
        parser_options={
            "schema_version": "industrial_parks_summary.v1",
            "sheet_index": 0,
            "header_row": 3,
            "data_start_row": 6,
            "minimum_rows": 50,
            "column_map": {
                "B": "registration_no",
                "C": "park_name",
                "D": "included_at",
                "E": "excluded_at_raw",
                "F": "location_raw",
                "G": "created_for_years",
                "H": "area_ha_raw",
                "I": "concept_reference",
                "J": "register_entry_reference",
                "K": "government_decision_reference",
            },
            "header_expectations": {
                "B": "реєстраційний номер",
                "C": "назва індустріального",
                "D": "дата включення",
                "E": "дата виключення",
                "F": "місцезнаходження",
                "G": "строк",
                "H": "загальна площа",
                "I": "концепція",
                "J": "примітки",
            },
        },
    ),
}


def get_source(source_id: str) -> SourceConfig:
    try:
        return SOURCES[source_id]
    except KeyError as exc:
        known_sources = ", ".join(sorted(SOURCES))
        raise KeyError(f"Unknown source '{source_id}'. Known sources: {known_sources}") from exc
