"""Strict statewide category evidence for PhotoStudiosTexas.com. Stdlib only.

A studio qualifies for a category only when something it (or its Google
listing) published says so: its Google listing categories, its business name,
its listing description, or text on its own website (title, descriptions,
headings, menu links, and sentences on the homepage). A generic "photographer"
with no mention of the service never counts. Matching is word-bounded and has
explicit exclusions (for example "family-owned", "wedding venue", "promo").

generate_category_evidence() is run by scripts/generate_category_evidence.py,
which writes data/category-evidence.json. The site build reads that file; it
never guesses.
"""

from __future__ import annotations

import re

# id, slug, singular label (chip), page h1, short plural noun, spec id used for filter chips
CATEGORIES = [
    ("portraits", "portrait-studios", "Portraits", "Portrait Studios in Texas", "portrait studios"),
    ("family", "family-photo-studios", "Family", "Family Photo Studios in Texas", "family photo studios"),
    ("headshots", "headshot-studios", "Headshots", "Headshot Studios in Texas", "headshot studios"),
    ("weddings", "wedding-photo-studios", "Weddings", "Wedding Photo Studios in Texas", "wedding photo studios"),
    ("prom", "prom-photo-studios", "Prom", "Prom Photo Studios in Texas", "prom photo studios"),
    ("maternity", "maternity-photo-studios", "Maternity", "Maternity Photo Studios in Texas", "maternity photo studios"),
]
CAT_BY_ID = {c[0]: c for c in CATEGORIES}
CAT_IDS = [c[0] for c in CATEGORIES]

# A homepage/subpage sentence only counts as evidence when it reads like the studio describing what it offers.
OFFER = re.compile(
    r"special|\boffer|services?\b|packages?|\bwe (?:photograph|capture|shoot|provide|do|love to)\b|\bi (?:photograph|capture|shoot|provide|do|love to)\b"
    r"|(?:starts?|starting)\s+(?:at|from)|\$\s?\d|\bbook\b|galler(?:y|ies)|collections?\b|including|include|such as|focus|available|"
    r"photographer\b(?!s)|photography\b|portfolio",
    re.I,
)
NOT_OFFER = re.compile(
    r"worked with|hired|recommend|thank you|thanks|amazing|loved|highly|took me under|assist(?:ed|ing)?\b|second photographer|"
    r"\bmy (?:husband|wife|daughter|son|mom|dad|sister|brother|friend|fianc)|\bwas (?:so|very|such|absolutely|the best)|had the (?:pleasure|opportunity)|"
    r"experience with|restor(?:e|ation|ing)|repair|damaged|scan(?:ning)?\b|digiti[sz]|heirloom|prom dress|bridesmaid|"
    r"picking out|\bour (?:daughter|son)\b|let me know|reviews?\b|testimonial|rating|lessons? learned|my (?:own )?wedding|tips|how to|why you|workshops?|mentor|educat|\bteach|courses?\b|\bperfect for\b|\bideal for\b|\bgreat for\b|\bour (?:boy|girl|baby|little)|\bsessions? (?:with|was|were)\b|have used|used this studio|i am a photographer with",
    re.I,
)
SERVICE_WORDS = re.compile(r"wedding|bridal|famil(?:y|ies)|portrait|headshot|newborn|maternity|senior|graduat|engagement|branding|birthday|prom|couples|children|kids|baby|babies|boudoir|event|quincea", re.I)
RENTAL_NAME = re.compile(r"\b(?:rentals?|rent|self[- ]?(?:service|portrait|photo|shoot|studio)|selfie|photo ?booth|cyc|loft|space|spaces|rooms?|hourly|venue|sets?)\b", re.I)
RENTAL_SITE = re.compile(
    r"studio\s+(?:rentals?|for\s+rent)|hourly\s+bookings?|rent(?:al)?\s+(?:the|our|a)\s+(?:\w+\s+){0,2}(?:studio|space)|(?:hourly|daily)\s+(?:rental|rate)|"
    r"self[- ]?(?:serve|service|shoot|portrait|photo)|selfie\s+(?:studio|museum)|photographers?\s+(?:can|may|to)\s+(?:rent|book)|rentable|"
    r"book\s+(?:our|the)\s+(?:studio|space)|space\s+rentals?",
    re.I,
)

PHOTO_CTX = r"photo|portrait|session|shoot|picture|studio|camera|image|capture|gown|album|print"

# Short texts: name, titles, descriptions, headings, menu labels, URL paths.
SHORT = {
    "portraits": re.compile(r"\bportrait(?:s|ure)?\b(?!\s*(?:mode|orientation|lens|format|layout|size|view|style\s+print))", re.I),
    "headshots": re.compile(r"\bhead\s?-?shots?\b|\bacting\s+(?:photos|portraits)\b|\blinkedin\s+(?:profile\s+)?(?:photos?|portraits?)\b", re.I),
    "weddings": re.compile(r"\bwedding(?:s)?\b|\bbridal\b|\belopement(?:s)?\b", re.I),
    "prom": re.compile(r"\bproms?\b", re.I),
    "maternity": re.compile(r"\bmaternity\b|\bpregnancy\s+(?:photo\w*|portrait\w*|session\w*|shoot\w*)\b|\bexpecting\s+(?:mother|mom|mama)s?\s+(?:photo|portrait|session)", re.I),
    "family": re.compile(
        r"\bfamil(?:y|ies)\s*(?:&|and)?\s*(?:photo\w*|portrait\w*|session\w*|picture\w*|shoot\w*|mini[- ]?session\w*|headshot\w*|photographer\w*|kids|children|couples)\b"
        r"|(?:photo\w*|portrait\w*|session\w*|picture\w*|shoot\w*|photographer\w*)\s+(?:of|for|with)\s+(?:your\s+|the\s+|a\s+|our\s+)?famil(?:y|ies)\b"
        r"|^\s*(?:families|family)(?:\s*(?:&|and|\+)\s*\w+)?\s*$"
        r"|\b(?:couples|seniors?|newborns?|maternity|children|kids|babies|weddings?|portraits?)\s*(?:,|&|and|\||/)\s*(?:and\s+)?famil(?:y|ies)\b(?!\s+(?:reunions?|gatherings?|events?|members?|business|owned))"
        r"|\bfamil(?:y|ies)\s*(?:,|&|and|\||/)\s*(?:couples|seniors?|newborns?|maternity|children|kids|babies|weddings?|portraits?|pets?)\b",
        re.I),
}

# Sentences from a website body (weaker source: require a service context in the sentence).
BODY = {
    "portraits": re.compile(r"\bportrait(?:s|ure)?\b", re.I),
    "headshots": SHORT["headshots"],
    "weddings": re.compile(r"\bwedding(?:s)?\b|\bbridal\b|\belopement(?:s)?\b", re.I),
    "prom": SHORT["prom"],
    "maternity": re.compile(r"\bmaternity\b|\bpregnancy\s+(?:photo\w*|portrait\w*|session\w*|shoot\w*)", re.I),
    "family": SHORT["family"],
}
BODY_CTX = {
    "portraits": re.compile(r"photograph|photos?\b|session|studio|specializ|offer|capture|shoot|book|packages?|sittings?", re.I),
    "headshots": re.compile(r".", re.I),
    "weddings": re.compile(r"photograph|photos?\b|photography|cinematograph|videograph|film\b|session|capture|coverage|packages?|shoot", re.I),
    "prom": re.compile(r"photo|portrait|picture|session|studio|dance|homecoming|formal|senior", re.I),
    "maternity": re.compile(PHOTO_CTX + r"|bump|expecting", re.I),
    "family": re.compile(r".", re.I),
}

# Exclusions applied to any matched text.
EXCLUDE = {
    "weddings": re.compile(
        r"wedding\s+(?:venue|planner|planning|dress|gown|cake|invitation|favors?|florist|flowers?|dj|band|chapel|hall|reception|rental|decor|coordinator|catering|caterer|officiant|jewelry|rings?|registry|shop|boutique|barn|ceremony space)s?\b"
        r"|(?:venue|chapel|hall|barn)\s+for\s+weddings?|weddings?\s+and\s+events?\s+venue|bridal\s+(?:shop|boutique|salon|gown|boudoir|beauty|makeup|hair)s?\b",
        re.I),
    "maternity": re.compile(r"maternity\s+(?:clothing|clothes|wear|leave|care|ward|hospital|store|boutique|shop|bra|insurance|nurse|center|centre|medical|health|services?)\b|pregnancy\s+(?:care|resource|help|center|centre|test|clinic|support)", re.I),
    "family": re.compile(r"\bfamil(?:y|ies)[- ](?:owned|run|operated|business|friendly|oriented|centered|style|first|tradition|company|farm|legacy)\b|\b(?:our|my|a|the|your|their)\s+family\s+(?:business|owned|is|of|has|and\s+I)\b", re.I),
    "portraits": re.compile(r"\bportrait\s+(?:mode|orientation|lens|format|layout|view|painting|artist|drawing)s?\b|\b(?:painted|drawn|charcoal|pencil|oil)\s+portraits?\b", re.I),
    "headshots": re.compile(r"$^"),
    "prom": re.compile(r"$^"),
}

NONPHOTO_SUBTYPES = {
    "wedding venue", "wedding chapel", "banquet hall", "event venue", "event planner", "wedding planner",
    "party planner", "bridal shop", "maternity store", "baby store", "baby clothing store", "pregnancy care center",
    "medical clinic", "hair salon", "hairdresser", "beauty salon", "clothing store", "boutique", "dance school",
    "dance hall", "music school", "church", "coworking space", "recording studio", "wedding service",
    "full dress rental service", "party equipment rental service", "dj service", "catering food and drink supplier",
    "winery", "garden", "event management company", "conference center", "festival hall", "live music venue",
    "art school", "senior high school", "meeting planning service", "party store", "women's clothing store",
    "children's party service", "farm", "retreat center", "makerspace",
}
PHOTOGRAPHER_SUBTYPES = {
    "photographer", "portrait studio", "wedding photographer", "commercial photographer", "photography service",
    "aerial photographer", "model portfolio studio", "photo agency",
}
PHOTO_NAME = re.compile(r"photo|portrait|image|picture|camera|lens|foto|film|video|cinema|studio|capture|moments|memories|shutter|pixel|click|snap", re.I)

SOURCE_LABEL = {
    "listing categories": "its Google listing categories",
    "business name": "its business name",
    "listing description": "its Google listing description",
    "booking page": "its booking page link",
    "website title": "its website title",
    "website description": "its website description",
    "website heading": "a heading on its website",
    "website menu": "a menu link on its website",
    "website text": "text on its website",
}
STRONG_ORDER = ["listing categories", "business name", "listing description", "website title", "website description",
                "website heading", "website menu", "booking page", "website text"]


def _short_hit(cat: str, text: str) -> str | None:
    if not text:
        return None
    if EXCLUDE[cat].search(text):
        return None
    m = SHORT[cat].search(text)
    return m.group(0) if m else None


def _body_hit(cat: str, text: str) -> str | None:
    if not text or EXCLUDE[cat].search(text):
        return None
    if NOT_OFFER.search(text) or not OFFER.search(text):
        return None
    words = {w.lower() for w in SERVICE_WORDS.findall(text)}
    if len(words) < 1:
        return None
    if not BODY[cat].search(text) or not BODY_CTX[cat].search(text):
        return None
    return BODY[cat].search(text).group(0)


def photographer_like(studio: dict) -> bool:
    subtypes = {s.lower() for s in studio.get("subtypes") or []}
    if subtypes & PHOTOGRAPHER_SUBTYPES:
        return True
    if not (subtypes & NONPHOTO_SUBTYPES):
        return True
    return bool(re.search(r"photo|portrait|image|picture|camera|lens|foto|capture|shutter", studio.get("name") or "", re.I))


def rental_like(studio: dict, enrich: dict, evidence: dict) -> bool:
    """Space-rental and self-service studios provide a room, not the photography."""
    subtypes = {s.lower() for s in studio.get("subtypes") or []}
    if subtypes & PHOTOGRAPHER_SUBTYPES:
        return False
    if RENTAL_NAME.search(studio.get("name") or ""):
        return True
    probe = " | ".join(filter(None, [
        (evidence or {}).get("title"), *((evidence or {}).get("meta") or []),
        (enrich or {}).get("title"), (enrich or {}).get("description"), studio.get("description"),
    ]))
    return bool(RENTAL_SITE.search(probe))


def _path_text(path: str) -> str | None:
    path = (path or "").strip()
    segs = [p for p in path.strip("/").split("/") if p]
    if not segs or len(segs) > 2:
        return None
    if re.match(r"^(blog|news|post|posts|20\d\d|tag|category|author|page|wp-)", segs[0], re.I):
        return None
    return re.sub(r"[-_.]+", " ", " ".join(segs))


def generate_category_evidence(studio: dict, enrich: dict | None, evidence: dict | None) -> dict[str, list[dict]]:
    """category id -> ordered evidence list [{'source', 'text'}]. Empty when nothing qualifies."""
    enrich = enrich or {}
    evidence = evidence or {}
    found: dict[str, list[dict]] = {}

    def add(cat: str, source: str, text: str, page: str = "", hit: str = "") -> None:
        items = found.setdefault(cat, [])
        if any(i["source"] == source for i in items):
            return
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean) > 200 and hit and hit.lower() in clean.lower():
            at = clean.lower().index(hit.lower())
            start = max(0, min(at - 80, len(clean) - 200))
            clean = ("\u2026" if start else "") + clean[start:start + 200] + ("\u2026" if start + 200 < len(clean) else "")
        elif len(clean) > 200:
            clean = clean[:200]
        item = {"source": source, "text": clean}
        if page:
            item["page"] = page
        items.append(item)

    subtypes = {s.lower() for s in studio.get("subtypes") or []}
    if "portrait studio" in subtypes:
        add("portraits", "listing categories", "Google category: Portrait studio")
    if "wedding photographer" in subtypes:
        add("weddings", "listing categories", "Google category: Wedding photographer")

    shorts = [("business name", studio.get("name") or ""),
              ("listing description", studio.get("description") or ""),
              ("booking page", re.sub(r"[-_/.]+", " ", (studio.get("booking_link") or "").split("//", 1)[-1]))]
    ok_enrich = str(enrich.get("status")) in {"200"}
    ok_evid = str(evidence.get("status")) == "200"
    if ok_enrich or ok_evid:
        titles = [evidence.get("title") if ok_evid else None, enrich.get("title") if ok_enrich else None]
        for t in titles:
            if t:
                shorts.append(("website title", t))
        metas = (evidence.get("meta") if ok_evid else []) or []
        if ok_enrich and enrich.get("description"):
            metas = list(metas) + [enrich["description"]]
        for m in metas:
            shorts.append(("website description", m))
        heads = list((evidence.get("headings") if ok_evid else []) or [])
        topics = list(enrich.get("topics") or []) if ok_enrich else []
        for h in heads:
            shorts.append(("website heading", h))
        links = list((evidence.get("links") if ok_evid else []) or [])
        for label, path in links:
            if label:
                shorts.append(("website menu", label))
            pt = _path_text(path)
            if pt:
                shorts.append(("website menu", pt))
        for t in topics:
            # enrichment topics mix menu labels (<=40 chars) and headings
            shorts.append(("website menu" if len(t) <= 40 else "website heading", t))
    for source, text in shorts:
        for cat in CAT_IDS:
            hit = _short_hit(cat, text)
            if hit:
                add(cat, source, text, hit=hit)
    if ok_evid:
        for sentence in evidence.get("snippets") or []:
            for cat in CAT_IDS:
                hit = _body_hit(cat, sentence)
                if hit:
                    add(cat, "website text", sentence, hit=hit)
        for sub in evidence.get("pages") or []:
            page = sub.get("path") or ""
            sub_shorts = [("website title", sub.get("title") or "")]
            sub_shorts += [("website description", m) for m in sub.get("meta") or []]
            sub_shorts += [("website heading", h) for h in sub.get("headings") or []]
            for source, text in sub_shorts:
                for cat in CAT_IDS:
                    hit = _short_hit(cat, text)
                    if hit:
                        add(cat, source, text, page, hit)
            for sentence in sub.get("snippets") or []:
                for cat in CAT_IDS:
                    hit = _body_hit(cat, sentence)
                    if hit:
                        add(cat, "website text", sentence, page, hit)

    if rental_like(studio, enrich, evidence):
        for cat in list(found):
            kept = [i for i in found[cat] if i["source"] in {"listing categories", "business name"}]
            if kept:
                found[cat] = kept
            else:
                del found[cat]
    # A venue, planner, boutique or clinic is not a photographer: keep only explicit photo-service evidence.
    if not photographer_like(studio):
        for cat in list(found):
            kept = [i for i in found[cat]
                    if i["source"] == "listing categories"
                    or (re.search(r"photo|portrait|session|shoot|cinemato|videograph|film", i["text"], re.I)
                        and i["source"] in {"business name", "website title", "website description", "website heading", "website text"})]
            if kept:
                found[cat] = kept
            else:
                del found[cat]
    for cat, items in found.items():
        items.sort(key=lambda i: STRONG_ORDER.index(i["source"]))
        found[cat] = items[:3]
    return found
