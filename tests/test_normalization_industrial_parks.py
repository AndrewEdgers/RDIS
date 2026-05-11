from app.normalization.industrial_parks import (
    build_industrial_parks_count_by_region,
    derive_status,
    extract_region,
    validate_normalized_rows,
)


def test_extract_region_from_oblast_phrase():
    assert (
        extract_region("м. Долина, Івано-Франківської області")
        == "Івано-Франківська область"
    )


def test_extract_region_from_city_fallback():
    assert extract_region('м. Львів у межах промвузла "Рясне-2"') == "Львівська область"
    assert extract_region('м.Львів у межах промвузла "Рясне-2"') == "Львівська область"
    assert extract_region("м. Київ") == "м. Київ"


def test_derive_status_from_exclusion_field():
    assert derive_status("") == "active"
    assert derive_status("Розпорядження КМУ від 21.02.2025 № 151-р") == "inactive"


def test_build_industrial_parks_count_by_region_counts_only_active_rows():
    rows = [
        {
            "registration_no": "1",
            "park_name": "Alpha",
            "excluded_from_register": "",
            "location_raw": "м. Львів",
            "source_last_modified": "2025-05-01T09:28:21.204634",
        },
        {
            "registration_no": "2",
            "park_name": "Beta",
            "excluded_from_register": "",
            "location_raw": "м. Львів",
            "source_last_modified": "2025-05-01T09:28:21.204634",
        },
        {
            "registration_no": "3",
            "park_name": "Gamma",
            "excluded_from_register": "Наказ про виключення",
            "location_raw": "м. Львів",
            "source_last_modified": "2025-05-01T09:28:21.204634",
        },
        {
            "registration_no": "4",
            "park_name": "Delta",
            "excluded_from_register": "",
            "location_raw": "м. Київ",
            "source_last_modified": "2025-05-01T09:28:21.204634",
        },
    ]

    normalized = build_industrial_parks_count_by_region(rows)
    validate_normalized_rows(normalized)

    assert normalized == [
        {
            "region": "Львівська область",
            "indicator_name": "industrial_parks_count",
            "value": 2,
            "date": "2025-05-01",
        },
        {
            "region": "м. Київ",
            "indicator_name": "industrial_parks_count",
            "value": 1,
            "date": "2025-05-01",
        },
    ]
