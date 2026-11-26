#!/usr/bin/env python3
"""Clean an Outscraper Google Maps export into data/studios.json.

Only fields present in the export are kept. Nothing is invented.
Re-run when a new export arrives:

    python3 scripts/clean_data.py path/to/export.xlsx

With no argument, reads data/source/outscraper-photography-studio-tx.xlsx.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XLSX = ROOT / "data" / "source" / "outscraper-photography-studio-tx.xlsx"
STUDIOS_PATH = ROOT / "data" / "studios.json"
REPORT_PATH = ROOT / "data" / "cleaning-report.json"

# Official spellings for abbreviations that showed up in this export and that
# are likely to recur. The source city string is kept unless it matches.
CITY_ALIASES = {
    "mt pleasant": "Mount Pleasant",
    "mt. pleasant": "Mount Pleasant",
    "st jo": "Saint Jo",
    "st. jo": "Saint Jo",
    "ft worth": "Fort Worth",
    "ft. worth": "Fort Worth",
    "desoto": "DeSoto",
    "de soto": "DeSoto",
    "mckinney": "McKinney",
    "mcallen": "McAllen",
}

DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def load_rows(path: Path) -> list[dict]:
    try:
        import openpyxl
    except ImportError as exc:
        raise SystemExit(
            "openpyxl is required to read the xlsx export. "
            "Install it with: pip install -r requirements.txt"
        ) from exc

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        iterator = ws.iter_rows(values_only=True)
        header_row = next(iterator)
        headers = [str(cell).strip() if cell is not None else "" for cell in header_row]
        rows = []
        for raw in iterator:
            if raw is None or all(cell is None or cell == "" for cell in raw):
                continue
            record = {}
            for index, header in enumerate(headers):
                if not header:
                    continue
                value = raw[index] if index < len(raw) else None
                if isinstance(value, str):
                    value = value.strip()
                    if value == "":
                        value = None
                record[header] = value
            rows.append(record)
        return rows
    finally:
        wb.close()


def as_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value) -> int | None:
    number = as_float(value)
    if number is None:
        return None
    return int(number)


def postal_code(value) -> str | None:
    text = as_text(value)
    if text is None:
        return None
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 5:
        return digits[:5]
    if digits:
        return digits.zfill(5)
    return text


def normalize_city(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name).strip()
    alias = CITY_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    mount = re.fullmatch(r"Mt\.?\s+(.+)", cleaned)
    if mount:
        return "Mount " + mount.group(1).strip()
    saint = re.fullmatch(r"St\.?\s+(.+)", cleaned)
    if saint:
        return "Saint " + saint.group(1).strip()
    fort = re.fullmatch(r"Ft\.?\s+(.+)", cleaned)
    if fort:
        return "Fort " + fort.group(1).strip()
    return cleaned


def slugify(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if len(slug) > 80:
        slug = slug[:80].rstrip("-")
    return slug or fallback


TRACKING_PARAMS = re.compile(r"^(utm_[a-z]+|rwg_token|fbclid|gclid|y_source|ved|usg|opi|cd|ei)$", re.I)


def clean_url(value) -> str | None:
    """Drop tracking parameters (including %3F-encoded ones Google adds)."""
    text = as_text(value)
    if not text:
        return None
    text = re.split(r"%3[Ff]", text, maxsplit=1)[0] if re.search(r"%3[Ff](utm_|rwg_token)", text, re.I) else text
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return text
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not TRACKING_PARAMS.match(k) and not (k.lower() == "ref" and v.lower() in {"rwg_link", "gmb", "google"})
    ]
    path = parts.path
    if path == "/" and not query:
        path = "/"
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), ""))


def parse_json(value):
    text = as_text(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_about(value) -> dict | None:
    """Keep attributes Google marks true. Keeps language assistance text."""
    data = parse_json(value)
    if not isinstance(data, dict):
        return None
    out: dict[str, list[str]] = {}
    for group, attrs in data.items():
        if not isinstance(attrs, dict):
            continue
        items = []
        for name, flag in attrs.items():
            if flag is True:
                items.append(str(name))
            elif isinstance(flag, str) and flag.strip():
                items.append(f"{name}: {flag.strip()}")
        if items:
            out[str(group)] = items
    return out or None


def parse_other_hours(value) -> list[dict] | None:
    data = parse_json(value)
    if not isinstance(data, list):
        return None
    out = []
    for block in data:
        if not isinstance(block, dict):
            continue
        for label, days in block.items():
            if not isinstance(days, dict):
                continue
            cleaned = {
                day: str(text).replace("\u202f", " ").strip()
                for day, text in days.items()
                if str(text).strip()
            }
            if cleaned:
                out.append({"label": str(label), "hours": cleaned})
    return out or None


def parse_breakdown(value) -> dict | None:
    data = parse_json(value)
    if not isinstance(data, dict):
        return None
    try:
        counts = {str(k): int(float(v)) for k, v in data.items() if str(k) in {"1", "2", "3", "4", "5"}}
    except (TypeError, ValueError):
        return None
    return counts if len(counts) == 5 and sum(counts.values()) > 0 else None


def parse_tags(value) -> list[str]:
    text = as_text(value)
    if not text:
        return []
    seen, out = set(), []
    for part in text.split(","):
        item = part.strip()
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def parse_hours(value) -> dict | None:
    text = as_text(value)
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    ordered = {}
    for day in DAY_ORDER:
        if day in parsed and isinstance(parsed[day], list):
            spans = [str(span).strip() for span in parsed[day] if str(span).strip()]
            if spans:
                ordered[day] = spans
    for day, spans in parsed.items():
        if day in ordered or not isinstance(spans, list):
            continue
        cleaned = [str(span).strip() for span in spans if str(span).strip()]
        if cleaned:
            ordered[str(day)] = cleaned
    return ordered or None


def parse_subtypes(value) -> list[str]:
    text = as_text(value)
    if not text:
        return []
    parts = []
    seen = set()
    for part in text.split(","):
        item = part.strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            parts.append(item)
    return parts


def address_core(address: str | None, city: str, postal: str | None) -> str:
    text = address or ""
    text = re.sub(r"[^\x00-\x7f]+", " ", text).lower()
    if city:
        text = text.replace(city.lower(), " ")
    if postal:
        text = text.replace(postal.lower(), " ")
    text = re.sub(r"\b(united states of america|united states|usa|texas)\b", " ", text)
    text = re.sub(r"\btx\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_text)).strip()


def jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def same_place(left: dict, right: dict) -> bool:
    if left["postal_code"] and right["postal_code"] and left["postal_code"] != right["postal_code"]:
        return False
    core_left = left["_core"]
    core_right = right["_core"]
    if core_left and core_right and core_left == core_right:
        return True
    if not core_left or not core_right:
        return False
    digits_left = re.findall(r"\d+", core_left)
    digits_right = re.findall(r"\d+", core_right)
    if not digits_left or digits_left != digits_right:
        return False
    return jaccard(core_left, core_right) >= 0.8


def record_score(record: dict) -> tuple:
    photo = record.get("photo") or ""
    real_photo = bool(photo) and "streetview" not in photo
    ascii_address = bool(record["address"]) and all(ord(ch) < 128 for ch in record["address"])
    return (
        record["review_count"] or 0,
        record["rating"] or 0,
        1 if record["business_status"] == "OPERATIONAL" else 0,
        1 if real_photo else 0,
        1 if record["phone"] else 0,
        1 if record["website"] else 0,
        1 if ascii_address else 0,
    )


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            if left_root < right_root:
                self.parent[right_root] = left_root
            else:
                self.parent[left_root] = right_root


def dedupe(records: list[dict]) -> tuple[list[dict], list[dict]]:
    groups: dict[tuple, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        groups[(record["city"].lower(), record["_name_key"])].append(index)

    union = UnionFind(len(records))
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        for offset, left in enumerate(indexes):
            for right in indexes[offset + 1 :]:
                if same_place(records[left], records[right]):
                    union.union(left, right)

    clusters: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        clusters[union.find(index)].append(index)

    kept = []
    removed = []
    for indexes in clusters.values():
        # Highest score wins. Equal scores keep the smaller place_id.
        winner_index = min(
            indexes,
            key=lambda index: (
                tuple(-part for part in record_score(records[index]))
                + (records[index]["place_id"],)
            ),
        )
        winner = records[winner_index]
        kept.append(winner)
        if len(indexes) == 1:
            continue
        for index in indexes:
            if index == winner_index:
                continue
            other = records[index]
            removed.append(
                {
                    "name": other["name"],
                    "city": other["city"],
                    "address": other["address"],
                    "dropped_place_id": other["place_id"],
                    "kept_place_id": winner["place_id"],
                    "kept_address": winner["address"],
                    "dropped_reviews": other["review_count"],
                    "kept_reviews": winner["review_count"],
                }
            )
    return kept, removed


def build_record(raw: dict) -> dict | None:
    name = as_text(raw.get("name"))
    city_source = as_text(raw.get("city"))
    if not name or not city_source:
        return None
    city = normalize_city(city_source)
    latitude = as_float(raw.get("latitude"))
    longitude = as_float(raw.get("longitude"))
    if latitude is None or longitude is None:
        return None
    place_id = as_text(raw.get("place_id")) or as_text(raw.get("google_id"))
    if not place_id:
        return None
    postal = postal_code(raw.get("postal_code"))
    subtypes = parse_subtypes(raw.get("subtypes"))
    category = as_text(raw.get("type")) or (subtypes[0] if subtypes else None)
    status = as_text(raw.get("business_status")) or "UNKNOWN"
    record = {
        "place_id": place_id,
        "name": name,
        "address": as_text(raw.get("address")),
        "street": as_text(raw.get("street")),
        "city": city,
        "city_source": city_source,
        "postal_code": postal,
        "phone": as_text(raw.get("phone")),
        "website": clean_url(raw.get("website")),
        "rating": as_float(raw.get("rating")),
        "review_count": as_int(raw.get("reviews")),
        "hours": parse_hours(raw.get("working_hours")),
        "category": category,
        "subtypes": subtypes,
        "photo": as_text(raw.get("photo")),
        "logo": as_text(raw.get("logo")),
        "maps_url": as_text(raw.get("location_link")),
        "latitude": latitude,
        "longitude": longitude,
        "description": as_text(raw.get("description")),
        "business_status": status,
        "located_in": as_text(raw.get("located_in")),
        "neighborhood": (None if (as_text(raw.get("county")) or "").lower() in {"none", "nan", "n/a"} else as_text(raw.get("county"))),
        "time_zone": as_text(raw.get("time_zone")),
        "plus_code": as_text(raw.get("plus_code")),
        "verified": str(raw.get("verified")).strip().lower() == "true",
        "photos_count": as_int(raw.get("photos_count")),
        "street_view": as_text(raw.get("street_view")),
        "reviews_link": as_text(raw.get("reviews_link")),
        "rating_breakdown": parse_breakdown(raw.get("reviews_per_score")),
        "review_topics": parse_tags(raw.get("reviews_tags")),
        "booking_link": clean_url(raw.get("booking_appointment_link")) or clean_url(raw.get("order_links")),
        "about": parse_about(raw.get("about")),
        "other_hours": parse_other_hours(raw.get("other_hours")),
    }
    record["_core"] = address_core(record["address"], city, postal)
    record["_name_key"] = name_key(name) or name.lower()
    return record


def assign_slugs(records: list[dict]) -> list[dict]:
    city_slugs: dict[str, str] = {}
    used_city_slugs = set()
    for record in sorted(records, key=lambda item: (item["city"].lower(), item["place_id"])):
        city = record["city"]
        if city in city_slugs:
            continue
        base = slugify(city, "city")
        slug = base
        suffix = 2
        while slug in used_city_slugs:
            slug = f"{base}-{suffix}"
            suffix += 1
        used_city_slugs.add(slug)
        city_slugs[city] = slug

    by_city: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        record["city_slug"] = city_slugs[record["city"]]
        by_city[record["city_slug"]].append(record)

    for city_slug, group in by_city.items():
        used = set()
        for record in sorted(group, key=lambda item: (item["name"].lower(), item["place_id"])):
            base = slugify(record["name"], "studio")
            slug = base
            suffix = 2
            while slug in used:
                slug = f"{base}-{suffix}"
                suffix += 1
            used.add(slug)
            record["slug"] = slug
            record["url_path"] = f"/tx/{city_slug}/{slug}/"
    return records


def public_record(record: dict) -> dict:
    return {
        "place_id": record["place_id"],
        "name": record["name"],
        "slug": record["slug"],
        "url_path": record["url_path"],
        "address": record["address"],
        "street": record["street"],
        "city": record["city"],
        "city_slug": record["city_slug"],
        "postal_code": record["postal_code"],
        "phone": record["phone"],
        "website": record["website"],
        "rating": record["rating"],
        "review_count": record["review_count"],
        "hours": record["hours"],
        "category": record["category"],
        "subtypes": record["subtypes"],
        "photo": record["photo"],
        "logo": record["logo"],
        "maps_url": record["maps_url"],
        "latitude": record["latitude"],
        "longitude": record["longitude"],
        "description": record["description"],
        "business_status": record["business_status"],
        "located_in": record["located_in"],
        "neighborhood": record["neighborhood"],
        "time_zone": record["time_zone"],
        "plus_code": record["plus_code"],
        "verified": record["verified"],
        "photos_count": record["photos_count"],
        "street_view": record["street_view"],
        "reviews_link": record["reviews_link"],
        "rating_breakdown": record["rating_breakdown"],
        "review_topics": record["review_topics"],
        "booking_link": record["booking_link"],
        "about": record["about"],
        "other_hours": record["other_hours"],
    }


def main() -> None:
    source = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_XLSX
    if not source.is_file():
        raise SystemExit(f"Export not found: {source}")

    raw_rows = load_rows(source)
    state_counts = Counter()
    non_texas = Counter()
    dropped_closed = 0
    dropped_incomplete = 0
    city_renames = Counter()
    prepared = []

    for raw in raw_rows:
        state_code = (as_text(raw.get("state_code")) or "").upper()
        state_name = as_text(raw.get("state")) or ""
        state_counts[state_code or state_name or "UNKNOWN"] += 1
        is_texas = state_code == "TX" or state_name.lower() == "texas"
        if not is_texas:
            non_texas[state_code or state_name or "UNKNOWN"] += 1
            continue
        status = (as_text(raw.get("business_status")) or "").upper()
        if status == "CLOSED_PERMANENTLY":
            dropped_closed += 1
            continue
        record = build_record(raw)
        if record is None:
            dropped_incomplete += 1
            continue
        if record["city_source"] != record["city"]:
            city_renames[f"{record['city_source']} -> {record['city']}"] += 1
        prepared.append(record)

    deduped, removed = dedupe(prepared)
    assign_slugs(deduped)
    deduped.sort(key=lambda item: (item["city"].lower(), item["name"].lower(), item["place_id"]))
    studios = [public_record(record) for record in deduped]

    payload = {
        "source": source.name,
        "canonical_base": "https://photostudiostexas.com",
        "studio_count": len(studios),
        "city_count": len({studio["city_slug"] for studio in studios}),
        "studios": studios,
    }
    STUDIOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STUDIOS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    city_counts = Counter(studio["city"] for studio in studios)
    status_counts = Counter(studio["business_status"] for studio in studios)
    report = {
        "source_file": str(source.relative_to(ROOT) if source.is_relative_to(ROOT) else source),
        "source_rows": len(raw_rows),
        "rows_by_state_code": dict(state_counts.most_common()),
        "dropped_non_texas": sum(non_texas.values()),
        "dropped_non_texas_by_state": dict(non_texas.most_common()),
        "dropped_permanently_closed_in_texas": dropped_closed,
        "dropped_incomplete_texas_rows": dropped_incomplete,
        "duplicates_removed": len(removed),
        "duplicate_rows": removed,
        "city_name_normalizations": dict(city_renames),
        "kept_by_business_status": dict(status_counts),
        "studio_count": len(studios),
        "city_count": payload["city_count"],
        "cities_with_one_studio": sum(1 for count in city_counts.values() if count == 1),
        "top_cities": city_counts.most_common(15),
        "missing_fields": {
            "phone": sum(1 for studio in studios if not studio["phone"]),
            "website": sum(1 for studio in studios if not studio["website"]),
            "rating": sum(1 for studio in studios if studio["rating"] is None),
            "hours": sum(1 for studio in studios if not studio["hours"]),
            "photo": sum(1 for studio in studios if not studio["photo"]),
            "logo": sum(1 for studio in studios if not studio["logo"]),
            "description": sum(1 for studio in studios if not studio["description"]),
            "street": sum(1 for studio in studios if not studio["street"]),
            "maps_url": sum(1 for studio in studios if not studio["maps_url"]),
        },
        "decisions": [
            "Kept rows whose state_code is TX (or whose state name is Texas).",
            "Dropped every other state. The export query 'Photography studio in TX' also returned same-name matches such as Dallas, GA and New York studios.",
            "Dropped business_status CLOSED_PERMANENTLY. CLOSED_TEMPORARILY stays, and pages label it as temporarily closed.",
            "Did not merge cities that have few listings into a neighbor. Every studio stays on the city named in the listing. Nearby-city links are generated at build time from listing coordinates.",
            "City names are preserved except whitespace cleanup and a short alias list: Mt Pleasant -> Mount Pleasant, St Jo -> Saint Jo, plus Fort Worth / DeSoto / McKinney / McAllen variants for future exports.",
            "Deduped listings that share a normalized name, city, and street address (exact normalized address, or the same street numbers with very similar address text). Chain locations with different addresses are kept. The kept row is the one with more reviews, then rating, then operational status, photo, phone, and website.",
            "No descriptions, ratings, hours, phones, or photos were filled in when the export left them blank.",
            "The category shown is the export's type field (Photography studio, Photographer, and so on). The subtypes list is kept separately. The export's category column was empty for almost every row.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(studios)} studios in {payload['city_count']} cities to {STUDIOS_PATH.relative_to(ROOT)}"
    )
    print(
        f"Dropped {sum(non_texas.values())} non-Texas, {dropped_closed} permanently closed, "
        f"{len(removed)} duplicates."
    )


if __name__ == "__main__":
    main()
