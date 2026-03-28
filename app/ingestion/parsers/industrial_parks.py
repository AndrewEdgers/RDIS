from __future__ import annotations

import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET


MAIN_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
EXCEL_EPOCH = datetime(1899, 12, 30)
NUMERIC_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_industrial_parks_summary_workbook(
    workbook_path: Path,
    parser_options: dict[str, object],
    source_context: dict[str, object],
) -> list[dict[str, object]]:
    workbook = XlsxWorkbook(workbook_path)
    sheet_index = int(parser_options["sheet_index"])
    header_row_number = int(parser_options["header_row"])
    data_start_row = int(parser_options["data_start_row"])
    minimum_rows = int(parser_options.get("minimum_rows", 1))
    column_map = {
        str(column).upper(): str(field_name)
        for column, field_name in dict(parser_options["column_map"]).items()
    }
    header_expectations = {
        str(column).upper(): str(expected_fragment)
        for column, expected_fragment in dict(parser_options["header_expectations"]).items()
    }

    sheet_name, rows = workbook.read_sheet_rows(sheet_index)
    validate_header_row(rows, header_row_number, header_expectations)

    parsed_rows: list[dict[str, object]] = []
    seen_registration_numbers: set[int] = set()

    for row_number in sorted(rows):
        if row_number < data_start_row:
            continue

        row_cells = rows[row_number]
        if should_skip_row(row_cells, column_map):
            continue

        parsed_row = parse_summary_row(row_cells, column_map, sheet_name, source_context)

        registration_no = parsed_row["registration_no"]
        if registration_no in seen_registration_numbers:
            raise ValueError(f"Duplicate registration number detected: {registration_no}")
        seen_registration_numbers.add(registration_no)
        parsed_rows.append(parsed_row)

    if len(parsed_rows) < minimum_rows:
        raise ValueError(
            f"Parsed {len(parsed_rows)} rows from '{sheet_name}', below minimum threshold {minimum_rows}"
        )

    return parsed_rows


def validate_header_row(
    rows: dict[int, dict[str, str]],
    header_row_number: int,
    header_expectations: dict[str, str],
) -> None:
    header_row = rows.get(header_row_number)
    if not header_row:
        raise ValueError(f"Header row {header_row_number} was not found in workbook")

    for column, expected_fragment in header_expectations.items():
        header_value = normalize_whitespace(header_row.get(column, "")).casefold()
        if expected_fragment.casefold() not in header_value:
            raise ValueError(
                f"Header validation failed for column {column}: expected fragment "
                f"'{expected_fragment}', got '{header_row.get(column, '')}'"
            )


def parse_summary_row(
    row_cells: dict[str, str],
    column_map: dict[str, str],
    sheet_name: str,
    source_context: dict[str, object],
) -> dict[str, object]:
    source_values = {
        field_name: normalize_whitespace(row_cells.get(column, ""))
        for column, field_name in column_map.items()
    }

    registration_no = parse_required_int(source_values["registration_no"], "registration_no")
    park_name = parse_required_text(source_values["park_name"], "park_name")
    included_at = parse_required_date(source_values["included_at"], "included_at")
    created_for_years = parse_optional_int(source_values["created_for_years"])
    area_ha_raw = source_values["area_ha_raw"]
    area_ha = parse_optional_float(area_ha_raw)

    row = {
        "registration_no": registration_no,
        "park_name": park_name,
        "included_at": included_at,
        "excluded_from_register": nullable_text(source_values["excluded_at_raw"]),
        "location_raw": nullable_text(source_values["location_raw"]),
        "created_for_years": created_for_years,
        "area_ha": area_ha,
        "area_ha_raw": nullable_text(area_ha_raw),
        "concept_reference": nullable_text(source_values["concept_reference"]),
        "register_entry_reference": nullable_text(source_values["register_entry_reference"]),
        "government_decision_reference": nullable_text(
            source_values["government_decision_reference"]
        ),
        "source_sheet_name": sheet_name,
        "source_dataset_id": source_context.get("dataset_id"),
        "source_resource_id": source_context.get("resource_id"),
        "source_resource_url": source_context.get("resource_url"),
        "source_last_modified": source_context.get("resource_last_modified"),
        "ingested_at_utc": source_context.get("ingested_at_utc"),
    }
    return row


def is_effectively_blank(row_cells: dict[str, str], column_map: dict[str, str]) -> bool:
    for column in column_map:
        if nullable_text(row_cells.get(column, "")) is not None:
            return False
    return True


def should_skip_row(row_cells: dict[str, str], column_map: dict[str, str]) -> bool:
    if is_effectively_blank(row_cells, column_map):
        return True

    registration_column = get_column_name(column_map, "registration_no")
    park_name_column = get_column_name(column_map, "park_name")
    included_at_column = get_column_name(column_map, "included_at")

    if parse_optional_int(row_cells.get(registration_column, "")) is None:
        return True
    if nullable_text(row_cells.get(park_name_column, "")) is None:
        return True
    if parse_optional_date(row_cells.get(included_at_column, "")) is None:
        return True
    return False


def get_column_name(column_map: dict[str, str], field_name: str) -> str:
    for column, mapped_field_name in column_map.items():
        if mapped_field_name == field_name:
            return column
    raise KeyError(f"Column map does not contain field '{field_name}'")


def parse_required_text(value: str, field_name: str) -> str:
    cleaned = nullable_text(value)
    if cleaned is None:
        raise ValueError(f"Required field '{field_name}' is blank")
    return cleaned


def parse_required_int(value: str, field_name: str) -> int:
    parsed = parse_optional_int(value)
    if parsed is None:
        raise ValueError(f"Required integer field '{field_name}' is blank or invalid: '{value}'")
    return parsed


def parse_required_date(value: str, field_name: str) -> str:
    parsed = parse_optional_date(value)
    if parsed is None:
        raise ValueError(f"Required date field '{field_name}' is blank or invalid: '{value}'")
    return parsed


def parse_optional_int(value: str) -> int | None:
    cleaned = nullable_text(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned.replace(",", ".")))
    except ValueError:
        return None


def parse_optional_float(value: str) -> float | None:
    cleaned = nullable_text(value)
    if cleaned is None:
        return None

    match = NUMERIC_RE.search(cleaned)
    if not match:
        return None

    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_optional_date(value: str) -> str | None:
    cleaned = nullable_text(value)
    if cleaned is None:
        return None

    if re.fullmatch(r"\d+(?:[.,]\d+)?", cleaned):
        serial = float(cleaned.replace(",", "."))
        return (EXCEL_EPOCH + timedelta(days=serial)).date().isoformat()

    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_whitespace(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split())


def nullable_text(value: str | None) -> str | None:
    cleaned = normalize_whitespace(value)
    if cleaned in {"", "-", "—"}:
        return None
    return cleaned


class XlsxWorkbook:
    def __init__(self, workbook_path: Path) -> None:
        self.workbook_path = workbook_path

    def read_sheet_rows(self, sheet_index: int) -> tuple[str, dict[int, dict[str, str]]]:
        with zipfile.ZipFile(self.workbook_path) as archive:
            shared_strings = load_shared_strings(archive)
            sheets = load_sheet_targets(archive)
            try:
                sheet_name, sheet_target = sheets[sheet_index]
            except IndexError as exc:
                raise ValueError(f"Sheet index {sheet_index} not found in workbook") from exc
            rows = load_sheet_rows(archive, sheet_target, shared_strings)
        return sheet_name, rows


def load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        xml_bytes = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ET.fromstring(xml_bytes)
    shared_strings: list[str] = []
    for string_item in root.findall("main:si", MAIN_NS):
        text = "".join(node.text or "" for node in string_item.iterfind(".//main:t", MAIN_NS))
        shared_strings.append(text)
    return shared_strings


def load_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))

    relationship_targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships_root.findall("rel:Relationship", REL_NS)
    }

    sheets: list[tuple[str, str]] = []
    for sheet in workbook_root.findall("main:sheets/main:sheet", MAIN_NS):
        relationship_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        sheets.append((sheet.attrib["name"], "xl/" + relationship_targets[relationship_id]))
    return sheets


def load_sheet_rows(
    archive: zipfile.ZipFile,
    sheet_target: str,
    shared_strings: list[str],
) -> dict[int, dict[str, str]]:
    sheet_root = ET.fromstring(archive.read(sheet_target))
    rows: dict[int, dict[str, str]] = {}

    for row in sheet_root.findall("main:sheetData/main:row", MAIN_NS):
        row_number = int(row.attrib["r"])
        cells: dict[str, str] = {}
        for cell in row.findall("main:c", MAIN_NS):
            cell_reference = cell.attrib["r"]
            column = extract_column_name(cell_reference)
            cells[column] = read_cell_value(cell, shared_strings)
        rows[row_number] = cells
    return rows


def read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iterfind(".//main:t", MAIN_NS))

    value_element = cell.find("main:v", MAIN_NS)
    if value_element is None or value_element.text is None:
        return ""

    value = value_element.text
    if cell_type == "s":
        return shared_strings[int(value)]
    return value


def extract_column_name(cell_reference: str) -> str:
    letters = "".join(character for character in cell_reference if character.isalpha())
    if not letters:
        raise ValueError(f"Could not extract column name from cell reference '{cell_reference}'")
    return letters

