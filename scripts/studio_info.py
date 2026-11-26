"""Derive display facts for a studio from its listing data. Stdlib only.

Everything returned here is computed from fields in data/studios.json (the
Outscraper export) and data/website-enrichment.json (each studio's own public
homepage). Nothing is invented: a specialty, amenity, or hours line appears
only when a field supports it, and each specialty records what supported it.
"""

from __future__ import annotations

import re

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_SHORT = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
             "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}
JS_DAY = {"Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5, "Saturday": 6}

# ---------------------------------------------------------------- hours


def _norm(text: str) -> str:
    text = text.replace("\u202f", " ").replace("\u2009", " ").replace("\u00a0", " ")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"\s+", " ", text).strip()


def _tok(token: str, meridiem: str | None):
    token = token.strip().upper().replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(AM|PM)?", token)
    if not m:
        return None
    hour, minute, mer = int(m.group(1)), int(m.group(2) or 0), m.group(3) or meridiem
    if hour < 1 or hour > 12 or minute > 59 or not mer:
        return None
    if mer == "AM":
        hour = 0 if hour == 12 else hour
    elif hour != 12:
        hour += 12
    return hour * 60 + minute


def parse_span(text: str):
    """Return ('closed'|'24h'|'span'|'raw', (open, close) or None). close may exceed 1440."""
    raw = _norm(str(text))
    low = raw.lower()
    if low == "closed":
        return "closed", None
    if low in {"open 24 hours", "24 hours", "open 24 hrs"}:
        return "24h", (0, 1440)
    if "-" not in raw:
        return "raw", None
    left, right = [part.strip() for part in raw.split("-", 1)]
    rm = re.search(r"(AM|PM)\s*$", right, re.I)
    right_mer = rm.group(1).upper() if rm else None
    close = _tok(right, None)
    if close is None:
        return "raw", None
    lm = re.search(r"(AM|PM)\s*$", left, re.I)
    if lm:
        opening = _tok(left, None)
    else:
        opening = None
        other = {"AM": "PM", "PM": "AM"}.get(right_mer or "")
        for mer in (right_mer, other):
            if not mer:
                continue
            candidate = _tok(left, mer)
            if candidate is not None and candidate < close:
                opening = candidate
                break
        if opening is None and right_mer:
            opening = _tok(left, right_mer)
    if opening is None:
        return "raw", None
    if close <= opening:
        close += 1440
    return "span", (opening, close)


def fmt_minutes(value: int) -> str:
    value %= 1440
    hour, minute = divmod(value, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12} {suffix}" if minute == 0 else f"{hour12}:{minute:02d} {suffix}"


def parse_week(hours: dict | None) -> dict:
    """day -> {'label': str, 'spans': [(o,c)], 'closed': bool, 'ok': bool}"""
    week = {}
    if not hours:
        return week
    for day, items in hours.items():
        spans, labels, ok, closed = [], [], True, False
        for item in items:
            kind, value = parse_span(item)
            if kind == "closed":
                closed = True
                labels.append("Closed")
            elif kind == "24h":
                spans.append(value)
                labels.append("Open 24 hours")
            elif kind == "span":
                spans.append(value)
                labels.append(f"{fmt_minutes(value[0])} – {fmt_minutes(value[1])}")
            else:
                ok = False
                labels.append(_norm(str(item)))
        week[day] = {"label": ", ".join(labels), "spans": spans, "closed": closed and not spans, "ok": ok}
    return week


def hours_attr(week: dict) -> str:
    """Compact string for client-side 'open now': 'dayIndex=open-close,open-close;...'."""
    if not week or any(not info["ok"] for info in week.values()):
        return ""
    parts = []
    for day, info in week.items():
        if day in JS_DAY and info["spans"]:
            spans = ",".join(f"{o}-{c}" for o, c in info["spans"])
            parts.append(f"{JS_DAY[day]}={spans}")
    return ";".join(parts)


def hours_summary(week: dict) -> str:
    """'Mon–Fri 10 AM – 6 PM; Sat 10 AM – 4 PM; closed Sun'"""
    if not week:
        return ""
    rows = [(day, week[day]["label"]) for day in DAY_ORDER if day in week]
    groups, current = [], None
    for day, label in rows:
        if current and current[1] == label:
            current[2] = day
        else:
            current = [day, label, day]
            groups.append(current)
    open_parts, closed_days = [], []
    for first, label, last in groups:
        span = DAY_SHORT[first] if first == last else f"{DAY_SHORT[first]}–{DAY_SHORT[last]}"
        if (first, last) == ("Monday", "Sunday"):
            span = "Every day"
        if label == "Closed":
            closed_days.append(span)
        else:
            open_parts.append(f"{span} {label}")
    text = "; ".join(open_parts)
    if closed_days:
        text += ("; " if text else "") + "closed " + ", ".join(closed_days)
    return text


def schema_hours(week: dict) -> list[dict]:
    out = []
    for day, info in week.items():
        if day not in JS_DAY or not info["ok"]:
            continue
        for opening, close in info["spans"]:
            if (opening, close) == (0, 1440):
                opens, closes = "00:00", "23:59"
            else:
                opens = f"{opening // 60:02d}:{opening % 60:02d}"
                closes = f"{(close % 1440) // 60:02d}:{(close % 1440) % 60:02d}"
            out.append({
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": f"https://schema.org/{day}",
                "opens": opens,
                "closes": closes,
            })
    return out


# ---------------------------------------------------------------- specialties

# id, label, slug, plural phrase for sub-page headings, subtype matches, regex
SPECIALTIES = [
    ("portraits", "Portraits", "portraits", "Portrait photographers",
     {"portrait studio"}, r"\bportrait"),
    ("headshots", "Headshots", "headshots", "Headshot photographers",
     set(), r"head\s?-?shot|professional (profile )?photos?\b|linkedin photo"),
    ("weddings", "Weddings", "weddings", "Wedding photographers",
     {"wedding photographer"}, r"\bwedding|\bbridal\b|\bbrides?\b|elopement|engagement (photo|session|shoot)"),
    ("newborn", "Newborn & baby", "newborn", "Newborn and baby photographers",
     set(), r"newborn|\bbab(y|ies)\b|cake smash|\binfants?\b|milestone"),
    ("maternity", "Maternity", "maternity", "Maternity photographers",
     set(), r"maternity|pregnancy (photo|session|portrait|shoot)"),
    ("prom", "Prom", "prom", "Prom photographers",
     set(), r"$^"),
    ("christmas", "Christmas", "christmas", "Christmas photographers",
     set(), r"$^"),
    ("graduation", "Graduation", "graduation", "Graduation photographers",
     set(), r"$^"),
    ("natural-light", "Natural light", "natural-light", "Natural light photo studios",
     set(), r"$^"),
    ("prop-rental", "Photo prop rental", "photo-prop-rentals", "Photo prop rentals",
     set(), r"$^"),
    ("family", "Family", "family", "Family photographers",
     set(), r"\bfamil(y|ies)\b(?![- ](owned|run|operated|business|friendly))"),
    ("seniors", "Senior & graduation", "senior-photos", "Senior and graduation photographers",
     set(), r"\bseniors?\b(?! (living|care|center|citizens?|discount))|graduat|\bgrad\b|class of 20\d\d"),
    ("quinceanera", "Quinceañera", "quinceanera", "Quinceañera photographers",
     set(), r"quincea|\bquince\b|\bxv\b|15 a[nñ]os"),
    ("boudoir", "Boudoir", "boudoir", "Boudoir photographers", set(), r"boudoir"),
    ("commercial", "Commercial & product", "commercial", "Commercial and product photographers",
     {"commercial photographer"}, r"commercial|product photo|e-?commerce|brand(ing)? (photo|shoot|session)|corporate|advertis"),
    ("real-estate", "Real estate & architecture", "real-estate", "Real estate photographers",
     set(), r"real estate|realtors?\b|\brealty\b|property photo|listing photo|architectur"),
    ("events", "Events", "events", "Event photographers",
     set(), r"events?[ -](photo|coverage|photograph)|(photograph\w*|photo\w*|video\w*) (of |for )?(your |all )?(events?|parties)|\bparty\b|\bparties\b|\bevents\b"),
    ("pets", "Pets", "pet-photography", "Pet photographers",
     set(), r"\bpets?\b|\bdogs?\b|\bcanine|\bcats?\b|\banimals?\b"),
    ("passport", "Passport & ID photos", "passport-photos", "Passport and ID photo studios",
     {"passport photo processor"}, r"passport|visa photo|\bid photos?\b|immigration photo"),
    ("rental", "Studio rental", "studio-rental", "Photo studios for rent",
     set(), r"studio rentals?|rental studio|studio for rent|rent (our|the|a) (photo |photography )?(studio|space)|space rentals?|rentable|hourly (studio )?rental|book (our|the) studio|rent by the hour"),
    ("video", "Video production", "video-production", "Video production studios",
     {"video production service", "film production company", "videographer", "movie studio"},
     r"\bvideo|videograph|cinematograph|film production|\bfilms?\b(?! photograph)"),
    ("drone", "Aerial & drone", "aerial-drone", "Aerial and drone photographers",
     {"aerial photographer", "drone service"}, r"\bdrone|\baerial|\buav\b"),
    ("photo-booth", "Photo booths", "photo-booths", "Photo booth providers",
     {"photo booth"}, r"photo ?booth|selfie booth|360 booth"),
    ("restoration", "Photo restoration", "photo-restoration", "Photo restoration services",
     {"photo restoration service"}, r"photo restoration|\brestor(e|ation)|photo repair"),
    ("classes", "Classes & workshops", "photography-classes", "Photography classes and workshops",
     {"photography class", "photography school"}, r"\bclasses\b|workshops?|photography (class|school|course|lessons?)|\bmentor"),
    ("models", "Model portfolios", "model-portfolios", "Model portfolio photographers",
     {"model portfolio studio"}, r"model portfolio|\bmodeling\b|comp card|model photo"),
]
SPEC_BY_ID = {item[0]: item for item in SPECIALTIES}
_SPEC_RE = {item[0]: re.compile(item[5], re.I) for item in SPECIALTIES}

# feature chips: id, label
FEATURES = [
    ("booking", "Online booking"),
    ("wheelchair", "Wheelchair accessible"),
    ("women-owned", "Women-owned"),
    ("latino-owned", "Latino-owned"),
    ("black-owned", "Black-owned"),
    ("veteran-owned", "Veteran-owned"),
    ("lgbtq", "LGBTQ+ friendly"),
]
FEATURE_LABEL = dict(FEATURES)

BAD_PAGE = re.compile(
    r"just a moment|access denied|attention required|forbidden|\b40[0-9]\b|\b50[0-9]\b|not found|"
    r"error|domain (is )?(for sale|expired)|this domain|parked|godaddy|sedo|coming soon|"
    r"under construction|account suspended|default web site|index of /|captcha|are you human|"
    r"security check|checking your browser|site can.t be reached|page isn.t working|fiverr",
    re.I,
)


def clean_site_info(info: dict | None) -> dict:
    """Keep website enrichment only when the fetched page is a real page."""
    if not info or str(info.get("status")) not in {"200", "skipped-social"}:
        return {}
    probe = f"{info.get('title') or ''} {info.get('description') or ''}"
    if BAD_PAGE.search(probe):
        return {"social": info.get("social") or {}} if info.get("social") else {}
    return info


# Specialties that are also statewide category pages. Their evidence comes only from
# data/category-evidence.json (see scripts/categories.py): strict, word-bounded, per-source.
STRICT_IDS = ("portraits", "family", "headshots", "weddings", "prom", "maternity", "christmas", "graduation", "natural-light", "prop-rental", "newborn", "seniors", "quinceanera", "boudoir", "commercial", "real-estate", "events", "pets", "passport", "rental", "video", "drone", "photo-booth", "restoration", "classes", "models")
STRICT_SOURCE = {
    "listing categories": "listing categories", "business name": "business name",
    "listing description": "listing description", "booking page": "booking page",
    "manual review": "manual review",
}


def detect_specialties(studio: dict, site: dict, strict: dict | None = None) -> dict[str, list[str]]:
    """specialty id -> ordered unique list of evidence sources.

    strict: this studio's entry from data/category-evidence.json ({category id: [{"source", "text"}]}).
    When given (even empty), it alone decides the statewide-category specialties.
    """
    found: dict[str, list[str]] = {}

    def add(spec_id: str, source: str) -> None:
        sources = found.setdefault(spec_id, [])
        if source not in sources:
            sources.append(source)

    subtypes = {item.lower() for item in studio.get("subtypes") or []}
    for spec_id, _label, _slug, _plural, wanted, _rx in SPECIALTIES:
        if strict is not None and spec_id in STRICT_IDS:
            continue
        if wanted & subtypes:
            add(spec_id, "listing categories")
    texts = [
        ("business name", studio.get("name") or ""),
        ("listing description", studio.get("description") or ""),
        ("customer review topics", ", ".join(studio.get("review_topics") or [])),
        ("booking page", re.sub(r"[-_/]+", " ", (studio.get("booking_link") or "").split("//", 1)[-1])),
        ("website", " | ".join(filter(None, [site.get("title"), site.get("description"), " | ".join(site.get("topics") or [])]))),
    ]
    for source, text in texts:
        if not text:
            continue
        for spec_id, rx in _SPEC_RE.items():
            if strict is not None and spec_id in STRICT_IDS:
                continue
            if rx.search(text):
                add(spec_id, source)
    if strict is not None:
        for spec_id in STRICT_IDS:
            for item in strict.get(spec_id) or []:
                add(spec_id, STRICT_SOURCE.get(item["source"], "website"))
    # "Pregnancy care center" style non-photo listings must not read as maternity photography.
    if strict is None and "maternity" in found and found["maternity"] == ["business name"] and re.search(r"pregnancy (care|resource|help|center)", studio.get("name") or "", re.I):
        del found["maternity"]
    order = {item[0]: index for index, item in enumerate(SPECIALTIES)}
    return dict(sorted(found.items(), key=lambda kv: (0 if "listing categories" in kv[1] else 1, -len(kv[1]), order[kv[0]])))


def detect_features(studio: dict) -> list[str]:
    about = studio.get("about") or {}
    flat = {item.lower() for items in about.values() for item in items}
    out = []
    if studio.get("booking_link"):
        out.append("booking")
    if "wheelchair accessible entrance" in flat:
        out.append("wheelchair")
    if "identifies as women-owned" in flat:
        out.append("women-owned")
    if "identifies as latino-owned" in flat:
        out.append("latino-owned")
    if "identifies as black-owned" in flat:
        out.append("black-owned")
    if "identifies as veteran-owned" in flat:
        out.append("veteran-owned")
    if "lgbtq+ friendly" in flat:
        out.append("lgbtq")
    return out


def amenity_groups(studio: dict) -> list[tuple[str, list[str]]]:
    """Group the positive 'about' attributes for display."""
    about = studio.get("about") or {}
    groups = []
    owner = []
    for group in ("From the business", "Other"):
        for item in about.get(group, []):
            if item.lower().startswith("identifies as"):
                owner.append(item.replace("Identifies as ", "").replace("identifies as ", "").capitalize().replace("lgbtq+", "LGBTQ+"))
    friendly = [item for item in about.get("Other", []) if not item.lower().startswith("identifies as")]
    friendly += about.get("Crowd", [])
    mapping = [("Accessibility", about.get("Accessibility", [])), ("Parking", about.get("Parking", [])),
               ("Amenities", about.get("Amenities", []) + about.get("Children", [])),
               ("Planning", about.get("Planning", [])), ("Payments", about.get("Payments", [])),
               ("Service options", about.get("Service options", [])),
               ("Business identity", sorted(set(owner))), ("Atmosphere", friendly)]
    for label, items in mapping:
        if items:
            groups.append((label, items))
    return groups


def humanize(label: str) -> str:
    return label.replace("_", " ").strip().capitalize()


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text and not text[:2].isupper() else text


def join_list(items: list[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def summary(studio: dict, specialties: dict[str, list[str]], week: dict, features: list[str]) -> str:
    """Short factual paragraph from the studio's own fields."""
    name, city = studio["name"], studio["city"]
    category = (studio.get("category") or "photo studio").lower()
    place = f"{city}, Texas"
    where = ""
    if studio.get("neighborhood") and studio["neighborhood"].lower() not in {city.lower()}:
        where = f" in the {studio['neighborhood']} area of {place}"
    else:
        where = f" in {place}"
    bits = [f"{name} is listed as a {category}{where}"]
    if studio.get("street"):
        bits[0] += f", at {studio['street']}"
    bits[0] += "."
    rating, count = studio.get("rating"), studio.get("review_count")
    if rating is not None and count:
        noun = "review" if count == 1 else "reviews"
        bits.append(f"It has a {float(rating):.1f}-star rating from {count:,} Google {noun}.")
    elif rating is not None:
        bits.append(f"It has a {float(rating):.1f}-star rating on Google.")
    labels = [SPEC_BY_ID[key][1].lower() for key in list(specialties)[:4]]
    if labels:
        bits.append(f"Its listing details point to {join_list(labels)}.")
    others = [s for s in (studio.get("subtypes") or []) if s.lower() != (studio.get("category") or "").lower()]
    if others and not labels:
        bits.append(f"Also listed as {join_list([lower_first(x) for x in others[:3]])}.")
    summary_hours = hours_summary(week) if week else ""
    if studio.get("business_status") == "CLOSED_TEMPORARILY":
        bits.append("Google lists it as temporarily closed, so check before you visit.")
    elif summary_hours and len(summary_hours) < 120:
        bits.append(f"Hours: {summary_hours}.")
    if "booking" in features:
        bits.append("It links to an online booking page.")
    if "wheelchair" in features:
        bits.append("Google lists a wheelchair accessible entrance.")
    if studio.get("verified") and rating is not None:
        bits.append("The business profile is verified on Google.")
    return " ".join(bits)
