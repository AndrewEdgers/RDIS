from app.ingestion.parsers.industrial_parks import (
    normalize_workbook_relationship_target,
    parse_detail_sheet,
    parse_optional_date,
    parse_optional_float,
    parse_optional_int,
    parse_summary_row,
    validate_header_row,
)


def test_validate_header_row_accepts_expected_summary_layout():
    rows = {
        3: {
            "B": "Реєстраційний номер",
            "C": "Назва індустріального (промислового) парку",
            "D": "Дата включення до Реєстру",
            "E": "Дата виключення з Реєстру",
            "F": "Місцезнаходження",
            "G": "Строк, на який створено",
            "H": "Загальна площа",
            "I": "Концепція",
            "J": "Примітки",
        }
    }
    validate_header_row(
        rows,
        3,
        {
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
    )


def test_normalize_workbook_relationship_target_accepts_relative_and_absolute_targets():
    assert normalize_workbook_relationship_target("worksheets/sheet1.xml") == "xl/worksheets/sheet1.xml"
    assert normalize_workbook_relationship_target("/xl/worksheets/sheet1.xml") == "xl/worksheets/sheet1.xml"
    assert normalize_workbook_relationship_target("xl/worksheets/sheet1.xml") == "xl/worksheets/sheet1.xml"


def test_parse_detail_sheet_handles_legacy_per_park_layout():
    row = parse_detail_sheet(
        "5. ЛІКВІДОВАНО Центральний",
        {
            1: {"A": 'Індустріальний парк "Центральний"'},
            2: {
                "A": "Реєстраційний номер:",
                "K": "5",
                "L": "Дата включення:",
                "M": "0",
                "N": "1",
                "O": ".",
                "P": "0",
                "Q": "4",
                "R": ".",
                "S": "2",
                "T": "0",
                "U": "1",
                "V": "4",
            },
            3: {"A": "Місцезнаходження:", "B": "м. Кременчук Полтавська область"},
            4: {"A": "Строк, на який створено:", "B": "50 років"},
            5: {"A": "Площа індустріального парку:", "B": "168,55"},
        },
        {
            "dataset_id": "dataset",
            "resource_id": "resource",
            "resource_url": "https://example.com/workbook.xls",
            "resource_last_modified": "2022-02-17T00:00:00",
            "source_snapshot_date": "2022-02-15",
            "ingested_at_utc": "2026-05-11T00:00:00+00:00",
        },
    )

    assert row is not None
    assert row["registration_no"] == 5
    assert row["included_at"] == "2014-04-01"
    assert row["excluded_from_register"] == "ЛІКВІДОВАНО"
    assert row["location_raw"] == "м. Кременчук Полтавська область"
    assert row["created_for_years"] == 50
    assert row["area_ha"] == 168.55


def test_parse_detail_sheet_combines_split_registration_digits():
    row = parse_detail_sheet(
        "53. Kalush Industrial HUB",
        {
            1: {"A": 'Індустріальний парк "Kalush Industrial HUB"'},
            2: {
                "A": "Реєстраційний номер:",
                "J": "5",
                "K": "3",
                "L": "Дата включення:",
                "M": "3",
                "N": "0",
                "O": ".",
                "P": "0",
                "Q": "9",
                "R": ".",
                "S": "2",
                "T": "0",
                "U": "2",
                "V": "1",
            },
            3: {"A": "Місцезнаходження:", "B": "м. Калуш, Івано-Франківська область"},
        },
        {"source_snapshot_date": "2022-02-15"},
    )

    assert row is not None
    assert row["registration_no"] == 53
    assert row["included_at"] == "2021-09-30"


def test_parse_optional_date_handles_excel_serial_and_text_formats():
    assert parse_optional_date("41673") == "2014-02-03"
    assert parse_optional_date("03/02/2014") == "2014-02-03"
    assert parse_optional_date("-") is None


def test_parse_optional_float_extracts_numeric_prefix_from_area_notes():
    assert parse_optional_float("27,14 дані не актуальні") == 27.14
    assert parse_optional_float("23.49") == 23.49
    assert parse_optional_float("-") is None


def test_parse_optional_int_extracts_numeric_prefix_from_text_notes():
    assert parse_optional_int("50 років") == 50
    assert parse_optional_int("30") == 30
    assert parse_optional_int("-") is None


def test_parse_summary_row_keeps_exclusion_field_as_source_value():
    row = parse_summary_row(
        {
            "B": "1",
            "C": "\"Перший еко ІП\" (Долина)",
            "D": "41673",
            "E": "Розпорядження КМУ від 21.02.2025 № 151-р",
            "F": "м. Долина, Івано-Франківської області",
            "G": "30",
            "H": "27,14 дані не актуальні",
            "I": "Концепція",
            "J": "Витяг з Реєстру",
            "K": "Розпорядження КМУ від 21.02.2025 № 151-р",
        },
        {
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
        "Загальний перелік ІП",
        {
            "dataset_id": "dataset",
            "resource_id": "resource",
            "resource_url": "https://example.com/workbook.xlsx",
            "resource_last_modified": "2025-03-27T00:00:00",
            "ingested_at_utc": "2026-03-27T00:00:00+00:00",
        },
    )

    assert row["registration_no"] == 1
    assert row["included_at"] == "2014-02-03"
    assert row["excluded_from_register"] == "Розпорядження КМУ від 21.02.2025 № 151-р"
    assert row["area_ha"] == 27.14
