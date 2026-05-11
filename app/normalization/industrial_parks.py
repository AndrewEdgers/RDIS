from __future__ import annotations

from collections import Counter
from datetime import datetime


OBLAST_PATTERNS: tuple[tuple[str, str], ...] = (
    ("вінницької області", "Вінницька область"),
    ("вінницька область", "Вінницька область"),
    ("волинської області", "Волинська область"),
    ("волинська область", "Волинська область"),
    ("дніпропетровської області", "Дніпропетровська область"),
    ("дніпропетровська область", "Дніпропетровська область"),
    ("дніпровської області", "Дніпропетровська область"),
    ("донецької області", "Донецька область"),
    ("донецька область", "Донецька область"),
    ("житомирської області", "Житомирська область"),
    ("житомирська область", "Житомирська область"),
    ("закарпатської області", "Закарпатська область"),
    ("закарпатська область", "Закарпатська область"),
    ("запорізької області", "Запорізька область"),
    ("запорізька область", "Запорізька область"),
    ("івано-франківської області", "Івано-Франківська область"),
    ("івано-франківська область", "Івано-Франківська область"),
    ("київської області", "Київська область"),
    ("київська область", "Київська область"),
    ("київська обл.", "Київська область"),
    ("кіровоградської області", "Кіровоградська область"),
    ("кіровоградська область", "Кіровоградська область"),
    ("львівської області", "Львівська область"),
    ("львівська область", "Львівська область"),
    ("луганської області", "Луганська область"),
    ("луганська область", "Луганська область"),
    ("миколаївської області", "Миколаївська область"),
    ("миколаївська область", "Миколаївська область"),
    ("одеської області", "Одеська область"),
    ("одеська область", "Одеська область"),
    ("полтавської області", "Полтавська область"),
    ("полтавська область", "Полтавська область"),
    ("рівненської області", "Рівненська область"),
    ("рівненська область", "Рівненська область"),
    ("сумської області", "Сумська область"),
    ("сумська область", "Сумська область"),
    ("тернопільської області", "Тернопільська область"),
    ("тернопільська область", "Тернопільська область"),
    ("харківської області", "Харківська область"),
    ("харківська область", "Харківська область"),
    ("херсонської області", "Херсонська область"),
    ("херсонська область", "Херсонська область"),
    ("хмельницької області", "Хмельницька область"),
    ("хмельницька область", "Хмельницька область"),
    ("черкаської області", "Черкаська область"),
    ("черкаська область", "Черкаська область"),
    ("чернівецької області", "Чернівецька область"),
    ("чернівецька область", "Чернівецька область"),
    ("чернігівської області", "Чернігівська область"),
    ("чернігівська область", "Чернігівська область"),
    ("вінницька обл.", "Вінницька область"),
    ("волинська обл.", "Волинська область"),
    ("дніпропетровська обл.", "Дніпропетровська область"),
    ("донецька обл.", "Донецька область"),
    ("житомирська обл.", "Житомирська область"),
    ("закарпатська обл.", "Закарпатська область"),
    ("запорізька обл.", "Запорізька область"),
    ("івано-франківська обл.", "Івано-Франківська область"),
    ("кіровоградська обл.", "Кіровоградська область"),
    ("львівська обл.", "Львівська область"),
    ("миколаївська обл.", "Миколаївська область"),
    ("одеська обл.", "Одеська область"),
    ("полтавська обл.", "Полтавська область"),
    ("рівненська обл.", "Рівненська область"),
    ("сумська обл.", "Сумська область"),
    ("тернопільська обл.", "Тернопільська область"),
    ("харківська обл.", "Харківська область"),
    ("херсонська обл.", "Херсонська область"),
    ("хмельницька обл.", "Хмельницька область"),
    ("черкаська обл.", "Черкаська область"),
    ("чернівецька обл.", "Чернівецька область"),
    ("чернігівська обл.", "Чернігівська область"),
)

CITY_REGION_FALLBACKS: tuple[tuple[str, str], ...] = (
    ("м. київ", "м. Київ"),
    ("м. львів", "Львівська область"),
    ("м. тростянець", "Сумська область"),
    ("м. вінниця", "Вінницька область"),
    ("м. житомир", "Житомирська область"),
    ("м. волочиськ", "Хмельницька область"),
)


def build_industrial_parks_count_by_region(
    clean_rows: list[dict[str, str]],
) -> list[dict[str, str | int]]:
    snapshot_date = derive_snapshot_date(clean_rows)
    active_counts: Counter[str] = Counter()
    unresolved_rows: list[str] = []

    for row in clean_rows:
        status = derive_status(row.get("excluded_from_register", ""))
        region = extract_region(row.get("location_raw", ""))
        if region is None:
            unresolved_rows.append(
                f"{row.get('registration_no', '?')}:{row.get('park_name', '')}:{row.get('location_raw', '')}"
            )
            continue

        if status == "active":
            active_counts[region] += 1

    if unresolved_rows:
        examples = "; ".join(unresolved_rows[:5])
        raise ValueError(f"Could not extract region for {len(unresolved_rows)} rows. Examples: {examples}")

    return [
        {
            "region": region,
            "indicator_name": "industrial_parks_count",
            "value": count,
            "date": snapshot_date,
        }
        for region, count in sorted(active_counts.items())
    ]


def derive_snapshot_date(clean_rows: list[dict[str, str]]) -> str:
    for row in clean_rows:
        source_snapshot_date = (row.get("source_snapshot_date") or "").strip()
        if source_snapshot_date:
            return source_snapshot_date[:10]

        source_last_modified = (row.get("source_last_modified") or "").strip()
        if source_last_modified:
            return source_last_modified[:10]
    raise ValueError("Could not derive snapshot date from source_snapshot_date or source_last_modified")


def derive_status(excluded_from_register: str | None) -> str:
    if normalize_text(excluded_from_register) is None:
        return "active"
    return "inactive"


def extract_region(location_raw: str | None) -> str | None:
    normalized_location = normalize_text(location_raw)
    if normalized_location is None:
        return None

    lowered = normalized_location.casefold()
    city_prefix_normalized = lowered.replace("м.", "м. ")

    for pattern, canonical_region in OBLAST_PATTERNS:
        if pattern in lowered:
            return canonical_region

    for prefix, canonical_region in CITY_REGION_FALLBACKS:
        if lowered.startswith(prefix) or city_prefix_normalized.startswith(prefix):
            return canonical_region

    return None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\xa0", " ").split())
    if cleaned in {"", "-", "—"}:
        return None
    return cleaned


def validate_normalized_rows(rows: list[dict[str, str | int]]) -> None:
    if not rows:
        raise ValueError("Normalization produced no indicator rows")

    seen_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (str(row["region"]), str(row["indicator_name"]), str(row["date"]))
        if key in seen_keys:
            raise ValueError(f"Duplicate normalized row detected for {key}")
        seen_keys.add(key)

        if not isinstance(row["value"], int):
            raise ValueError(f"Indicator value must be an integer: {row}")

        datetime.strptime(str(row["date"]), "%Y-%m-%d")
