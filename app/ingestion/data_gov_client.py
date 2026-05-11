from __future__ import annotations

from pathlib import Path

import requests


def fetch_dataset_metadata(base_url: str, dataset_id: str) -> dict:
    response = requests.get(
        f"{base_url}/package_show",
        params={"id": dataset_id},
        headers={"User-Agent": "RDIS-ingestion/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError(f"Dataset request for '{dataset_id}' did not succeed")
    return payload


def list_resources(data: dict) -> list[dict]:
    return list(data.get("result", {}).get("resources", []))


def select_resource(
    data: dict,
    strategy: str = "latest",
    preferred_formats: tuple[str, ...] = (),
) -> dict:
    return select_resources(data, strategy=strategy, preferred_formats=preferred_formats)[-1]


def select_resources(
    data: dict,
    strategy: str = "latest",
    preferred_formats: tuple[str, ...] = (),
) -> list[dict]:
    resources = [
        resource
        for resource in list_resources(data)
        if resource.get("state") == "active" and resource.get("url")
    ]
    if preferred_formats:
        normalized_formats = {fmt.upper() for fmt in preferred_formats}
        matching_resources = [
            resource
            for resource in resources
            if str(resource.get("format", "")).upper() in normalized_formats
        ]
        if matching_resources:
            resources = matching_resources

    if not resources:
        raise ValueError("No active resources were found for dataset")

    sorted_resources = sorted(
        resources,
        key=lambda resource: (
            resource.get("last_modified") or "",
            resource.get("created") or "",
            resource.get("id") or "",
        ),
    )

    if strategy == "all":
        return sorted_resources

    if strategy != "latest":
        raise ValueError(f"Unsupported resource strategy '{strategy}'")

    return [sorted_resources[-1]]


def download_resource(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        url,
        headers={"User-Agent": "RDIS-ingestion/1.0"},
        timeout=60,
        stream=True,
    )
    response.raise_for_status()

    with output_path.open("wb") as file_handle:
        for chunk in response.iter_content(chunk_size=1024 * 128):
            if chunk:
                file_handle.write(chunk)
