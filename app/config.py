from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

SOURCES = {
    "industrial_parks": {
        "source_type": "ckan",
        "base_url": "https://data.gov.ua/api/3/action",
        "dataset_id": "8206ed0c-5911-4b88-9c7f-56c6fcd08660",
        "resource_strategy": "latest",
        "raw_json_path": DATA_DIR / "industrial_parks.json",
        "raw_file_path": DATA_DIR / "industrial_parks_latest.xlsx",
        "summary_sheet_index": 0,
    }
}
