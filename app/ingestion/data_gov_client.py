import requests


def fetch_dataset_metadata(base_url: str, dataset_id: str) -> dict:
    response = requests.get(
        f"{base_url}/package_show",
        params={"id": dataset_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def list_resources(data: dict) -> list[dict]:
    return data["result"]["resources"]


def get_latest_resource(data: dict) -> dict:
    resources = list_resources(data)
    return max(resources, key=lambda r: r.get("last_modified") or "")


def download_resource(url: str, output_path) -> None:
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)
