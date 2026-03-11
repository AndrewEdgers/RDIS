import requests
import json
from pathlib import Path

API_URL = "https://data.gov.ua/api/3/action/package_show"
DATASET_ID = "8206ed0c-5911-4b88-9c7f-56c6fcd08660"


def fetch_dataset():
    response = requests.get(API_URL, params={"id": DATASET_ID}, timeout=30)
    response.raise_for_status()
    return response.json()


def save_json(data):
    Path("../data").mkdir(exist_ok=True)

    with open("../data/industrial_parks.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("RDIS: pulling dataset")

    data = fetch_dataset()

    print("API success:", data["success"])

    save_json(data)

    print("Saved JSON to ../data")


if __name__ == "__main__":
    main()