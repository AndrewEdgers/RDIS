import json

from app.config import SOURCES
from app.ingestion.data_gov_client import (
    fetch_dataset_metadata,
    get_latest_resource,
    list_resources,
    download_resource,
)


def run_industrial_parks_ingestion() -> None:
    source = SOURCES["industrial_parks"]

    data = fetch_dataset_metadata(
        base_url=source["base_url"],
        dataset_id=source["dataset_id"],
    )

    with open(source["raw_json_path"], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    resources = list_resources(data)

    print(f"Dataset: {data['result']['title']}")
    print(f"Resources found: {len(resources)}")

    for i, resource in enumerate(resources):
        print(f"\n[{i}] {resource.get('name')}")
        print(f"    Format: {resource.get('format')}")
        print(f"    Last modified: {resource.get('last_modified')}")
        print(f"    URL: {resource.get('url')}")

    latest_resource = get_latest_resource(data)

    print("\nSelected latest resource:")
    print(f"Name: {latest_resource.get('name')}")
    print(f"Last modified: {latest_resource.get('last_modified')}")
    print(f"URL: {latest_resource.get('url')}")

    download_resource(
        url=latest_resource["url"],
        output_path=source["raw_file_path"],
    )

    print(f"\nSaved JSON to {source['raw_json_path']}")
    print(f"Downloaded file to {source['raw_file_path']}")
