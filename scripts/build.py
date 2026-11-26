#!/usr/bin/env python3
"""Generate the PhotoStudiosTexas static site into dist/.

Stdlib only. Run after data/studios.json exists:

    python3 scripts/build.py
"""

from __future__ import annotations

import html
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DATA_PATH = ROOT / "data" / "studios.json"
CONFIG_PATH = ROOT / "config" / "site.json"
SERVICES_PATH = ROOT / "config" / "services.json"
BRAND = ROOT / "assets" / "brand"

EXAMPLES_DIR = ROOT / "assets" / "examples"
EXAMPLE_URL = "/images/retouching"
HERO_DIR = ROOT / "assets" / "hero"
HERO_URL = "/images/hero"


def example_picture(item: dict, *, loading: str = "lazy") -> str:
    name = item["file"]
    webp = f"{EXAMPLE_URL}/{name}.webp"
    jpg = f"{EXAMPLE_URL}/{name}.jpg"
    return (
        f'<picture>'
        f'<source type="image/webp" srcset="{esc(webp)}">'
        f'<img src="{esc(jpg)}" alt="{esc(item["alt"])}" '
        f'width="{int(item["width"])}" height="{int(item["height"])}" '
        f'loading="{esc(loading)}" decoding="async">'
        f'</picture>'
    )



DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ROOT_ASSETS = [
    "favicon.svg",
    "favicon.ico",
    "apple-touch-icon.png",
    "icon-192.png",
    "icon-512.png",
    "og-image.png",
    "site.webmanifest",
]


def esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def comma(value: int) -> str:
    return f"{value:,}"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.7613
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1, a)))


def miles_label(miles: float) -> str:
    if miles < 1:
        return "< 1 mi"
    return f"{round(miles)} mi"


def initials(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    if not parts:
        return "PS"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def meta_text(text: str, limit: int = 158) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def http_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.lower().startswith(("https://", "http://")):
        return cleaned
    return None


def safe_email(value: str | None) -> str:
    cleaned = (value or "").strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned):
        return cleaned
    return ""


def tel_href(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if phone.strip().startswith("+"):
        return "tel:+" + digits
    return "tel:" + digits


def to_24(token: str) -> str | None:
    cleaned = re.sub(r"\s+", "", token.strip().upper())
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(AM|PM)", cleaned)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    if hour < 1 or hour > 12 or minute > 59:
        return None
    if cleaned.endswith("AM"):
        hour = 0 if hour == 12 else hour
    elif hour != 12:
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def opening_hours(hours: dict | None) -> list[dict]:
    specs = []
    if not hours:
        return specs
    for day, spans in hours.items():
        if not isinstance(spans, list):
            continue
        for span in spans:
            text = str(span).strip()
            if text.lower() == "closed":
                continue
            if text.lower() in {"open 24 hours", "24 hours"}:
                specs.append({
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": f"https://schema.org/{day}",
                    "opens": "00:00",
                    "closes": "23:59",
                })
                continue
            match = re.match(r"^(.+?)\s*[-–]\s*(.+)$", text)
            if not match:
                continue
            opens = to_24(match.group(1))
            closes = to_24(match.group(2))
            if not opens or not closes:
                continue
            specs.append({
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": f"https://schema.org/{day}",
                "opens": opens,
                "closes": closes,
            })
    return specs


def json_script(data) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{payload}</script>'


def rating_html(studio: dict) -> str:
    if studio.get("rating") is None:
        return ""
    reviews = studio.get("review_count")
    review_html = ""
    if reviews is not None:
        noun = "review" if int(reviews) == 1 else "reviews"
        review_html = f' <span class="muted">({comma(int(reviews))} {noun})</span>'
    return (
        f'<p class="rating"><span aria-hidden="true">★</span> {float(studio["rating"]):.1f}'
        f"{review_html}</p>"
    )


def photo_block(studio: dict, class_name: str) -> str:
    mark = f'<span aria-hidden="true">{esc(initials(studio["name"]))}</span>'
    photo = http_url(studio.get("photo"))
    image = ""
    if photo:
        alt = f'{studio["name"]} in {studio["city"]}, Texas'
        image = (
            f'<img src="{esc(photo)}" alt="{esc(alt)}" loading="lazy" decoding="async" '
            f'onerror="this.remove()">'
        )
    return f'<div class="photo {class_name}">{mark}{image}</div>'


def badge(studio: dict) -> str:
    if studio.get("business_status") == "CLOSED_TEMPORARILY":
        return '<p class="badge">Temporarily closed</p>'
    return ""


class City:
    def __init__(self, name: str, slug: str, studios: list[dict]):
        self.name = name
        self.slug = slug
        self.studios = studios
        self.latitude = sum(studio["latitude"] for studio in studios) / len(studios)
        self.longitude = sum(studio["longitude"] for studio in studios) / len(studios)
        self.path = f"/tx/{slug}/"

    @property
    def count(self) -> int:
        return len(self.studios)


class Site:
    def __init__(self):
        payload = load_json(DATA_PATH)
        self.config = load_json(CONFIG_PATH)
        self.services = load_json(SERVICES_PATH)
        self.studios = payload["studios"]
        self.base = self.config["canonicalBase"].rstrip("/")
        self.email = safe_email(self.config.get("CONTACT_EMAIL"))
        grouped: dict[str, list[dict]] = defaultdict(list)
        names: dict[str, str] = {}
        for studio in self.studios:
            grouped[studio["city_slug"]].append(studio)
            names[studio["city_slug"]] = studio["city"]
        self.cities = [City(names[slug], slug, studios) for slug, studios in grouped.items()]
        self.by_count = sorted(self.cities, key=lambda city: (-city.count, city.name.lower()))
        self.by_name = sorted(self.cities, key=lambda city: city.name.lower())
        self.city_by_slug = {city.slug: city for city in self.cities}
        self.nearby = self._nearby(int(self.config.get("nearbyCityCount", 8)))
        self.footer_cities = self.by_count[: int(self.config.get("footerCityCount", 12))]
        self.featured = self._featured()
        self.primary_service = self.services[0]
        self.pages: list[tuple[str, str]] = []

    def _nearby(self, limit: int) -> dict[str, list[tuple[float, City]]]:
        found = {}
        for city in self.cities:
            ranked = []
            for other in self.cities:
                if other.slug == city.slug:
                    continue
                miles = haversine_miles(city.latitude, city.longitude, other.latitude, other.longitude)
                ranked.append((miles, other))
            ranked.sort(key=lambda item: (item[0], item[1].name.lower()))
            found[city.slug] = ranked[:limit]
        return found

    def _featured(self) -> list[dict]:
        minimum = int(self.config.get("featuredMinReviews", 15))
        cap = int(self.config.get("featuredPerCityCap", 2))
        wanted = int(self.config.get("featuredCount", 12))
        eligible = [
            studio for studio in self.studios
            if studio.get("business_status") == "OPERATIONAL"
            and studio.get("rating") is not None
            and (studio.get("review_count") or 0) >= minimum
        ]
        eligible.sort(key=lambda studio: (
            -float(studio["rating"]),
            -(studio.get("review_count") or 0),
            studio["name"].lower(),
            studio["place_id"],
        ))
        picked = []
        per_city: Counter = Counter()
        seen = set()
        for studio in eligible:
            if per_city[studio["city_slug"]] >= cap:
                continue
            picked.append(studio)
            seen.add(studio["place_id"])
            per_city[studio["city_slug"]] += 1
            if len(picked) >= wanted:
                return picked
        for studio in eligible:
            if studio["place_id"] in seen:
                continue
            picked.append(studio)
            if len(picked) >= wanted:
                break
        return picked

    def abs_url(self, path: str) -> str:
        if path == "/":
            return self.base + "/"
        return self.base + path

    def payment_link(self, service: dict) -> str:
        raw = str(self.config.get(service.get("paymentLinkKey", "STRIPE_PAYMENT_LINK")) or "").strip()
        if raw.startswith("https://"):
            return raw
        return ""

    def head_links(self) -> str:
        image = self.abs_url("/og-image.png")
        return f"""
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#111111">
<meta property="og:image" content="{esc(image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="PhotoStudiosTexas.com — photo studios across Texas">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{esc(image)}">"""

    def header(self, active: str) -> str:
        items = [
            ("home", "/", "Home"),
            ("cities", "/cities/", "Cities"),
            ("service", f"/services/{self.primary_service['slug']}/", self.primary_service["navLabel"]),
            ("about", "/about/", "About / Contact"),
        ]
        links = []
        for key, href, label in items:
            current = ' aria-current="page"' if key == active else ""
            links.append(f'<a href="{href}"{current}>{esc(label)}</a>')
        return f"""<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="/"><img src="/assets/logo-light.svg" alt="PhotoStudiosTexas" width="276" height="48"></a>
    <input class="nav-toggle" id="nav-toggle" type="checkbox">
    <label class="nav-burger" for="nav-toggle" aria-label="Menu"><span></span></label>
    <nav class="nav" aria-label="Primary">{''.join(links)}</nav>
  </div>
</header>"""

    def footer(self) -> str:
        explore = [
            ("/", "Home"),
            ("/tx/", "Texas"),
            ("/cities/", "All cities"),
            ("/services/", "Services"),
            ("/about/", "About / Contact"),
            ("/sitemap/", "HTML sitemap"),
            ("/sitemap.xml", "XML sitemap"),
        ]
        explore_html = "".join(f'<li><a href="{href}">{esc(label)}</a></li>' for href, label in explore)
        service_html = "".join(
            f'<li><a href="/services/{esc(service["slug"])}/">{esc(service["name"])}</a></li>'
            for service in self.services
        )
        city_html = "".join(
            f'<li><a href="{city.path}">{esc(city.name)}</a> <span class="muted">({city.count})</span></li>'
            for city in self.footer_cities
        )
        return f"""<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <a class="footer-logo" href="/"><img src="/assets/logo-dark.svg" alt="PhotoStudiosTexas" width="276" height="48"></a>
      <p>A directory of photo studios in Texas, plus photo editing when you need the pictures finished.</p>
    </div>
    <div>
      <h2>Explore</h2>
      <ul>{explore_html}</ul>
    </div>
    <div>
      <h2>Services</h2>
      <ul>{service_html}</ul>
    </div>
    <div>
      <h2>Top cities</h2>
      <ul>{city_html}</ul>
    </div>
  </div>
  <div class="wrap legal">
    <p>Listing details come from public business listings and may be out of date. PhotoStudiosTexas.com is not the studio and is not affiliated with Google.</p>
  </div>
</footer>"""

    def crumbs(self, items: list[tuple[str, str | None]]) -> str:
        parts = []
        for label, href in items:
            if href:
                parts.append(f'<li><a href="{href}">{esc(label)}</a></li>')
            else:
                parts.append(f'<li aria-current="page">{esc(label)}</li>')
        return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(parts)}</ol></nav>'

    def breadcrumb_schema(self, items: list[tuple[str, str | None]], current_path: str) -> dict:
        elements = []
        for index, (label, href) in enumerate(items, start=1):
            path = href or current_path
            elements.append({
                "@type": "ListItem",
                "position": index,
                "name": label,
                "item": self.abs_url(path),
            })
        return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": elements}

    def cta(self) -> str:
        service = self.primary_service
        teaser = ""
        examples = service.get("beforeAfter") or []
        if examples:
            item = examples[0]
            teaser = f"""
    <a class="cta-teaser" href="/services/{esc(service["slug"])}/#before-after">
      {example_picture(item)}
      <span class="cta-teaser-label">See before &amp; after</span>
    </a>"""
        return f"""<aside class="cta">
  <div class="cta-inner">
    <div class="cta-copy">
      <p class="eyebrow">Photo editing</p>
      <h2>{esc(service["name"])}</h2>
      <p>{esc(service["priceDisplay"])} {esc(service["priceNote"])} · {esc(service["delivery"])} · {esc(service["revisions"])}</p>
      <a class="btn" href="/services/{esc(service["slug"])}/">Order photo editing</a>
    </div>{teaser}
  </div>
</aside>"""

    def nearby_html(self, city: City) -> str:
        chips = []
        for miles, other in self.nearby[city.slug]:
            chips.append(
                f'<a class="chip" href="{other.path}">{esc(other.name)}'
                f' <span class="muted">{miles_label(miles)}</span></a>'
            )
        if not chips:
            return ""
        return f"""<section class="section">
  <h2>Nearby cities</h2>
  <div class="chips">{"".join(chips)}</div>
</section>"""

    def layout(self, title: str, description: str, path: str, body: str, active: str, schemas: list, robots: str = "index,follow", extra_head: str = "") -> str:
        canonical = self.abs_url(path)
        description = meta_text(description)
        schema_html = "\n".join(json_script(item) for item in schemas)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="robots" content="{esc(robots)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="PhotoStudiosTexas.com">
{self.head_links()}
<link rel="stylesheet" href="/assets/site.css">
{extra_head}{schema_html}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{self.header(active)}
<main id="main">{body}</main>
{self.footer()}
<script src="/assets/site-config.js"></script>
<script src="/assets/site.js"></script>
</body>
</html>
"""

    def write_page(self, path: str, document: str) -> None:
        relative = "index.html" if path == "/" else path.strip("/") + "/index.html"
        target = DIST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding="utf-8")
        self.pages.append((path, relative))

    def city_card(self, city: City) -> str:
        noun = "studio" if city.count == 1 else "studios"
        return (
            f'<a class="city-card" data-city="{esc(city.name)}" href="{city.path}">'
            f'<span>{esc(city.name)}</span><strong>{city.count} <span class="visually-hidden">{noun}</span></strong></a>'
        )

    def studio_card(self, studio: dict, show_city: bool = True) -> str:
        city_line = f'<p class="muted">{esc(studio["city"])}, TX</p>' if show_city else ""
        category = f'<p class="muted">{esc(studio["category"])}</p>' if studio.get("category") else ""
        return f"""<a class="studio-card" href="{esc(studio["url_path"])}">
  {photo_block(studio, "")}
  <div class="card-body">
    {badge(studio)}
    <h3>{esc(studio["name"])}</h3>
    {rating_html(studio)}
    {city_line}
    {category}
  </div>
</a>"""

    def order_form(self, service: dict | None, subject: str, submit_label: str) -> str:
        endpoint = str(self.config.get("ORDER_FORM_ENDPOINT") or "").strip()
        if endpoint.startswith("https://"):
            action = endpoint
            enctype = "application/x-www-form-urlencoded"
        elif self.email:
            action = f"mailto:{self.email}"
            enctype = "text/plain"
        else:
            action = "#order"
            enctype = "text/plain"
        hidden = ""
        if service:
            hidden = f'<input type="hidden" name="service" value="{esc(service["slug"])}">'
        return f"""<form id="order-form" class="form-card" action="{esc(action)}" method="post" enctype="{enctype}" data-subject="{esc(subject)}">
  {hidden}
  <label for="order-name">Name</label>
  <input id="order-name" name="name" type="text" autocomplete="name" required>
  <label for="order-email">Email</label>
  <input id="order-email" name="email" type="email" autocomplete="email" required>
  <label for="order-instructions">Instructions</label>
  <textarea id="order-instructions" name="instructions" required placeholder="What should change in the photos?"></textarea>
  <p class="note">Image upload: this form does not receive files. Paste a share link to your images in the instructions. If your email app opens, attach the files there.</p>
  <button class="btn" type="submit">{esc(submit_label)}</button>
</form>"""

    def build_home(self) -> None:
        studio_count = len(self.studios)
        city_count = len(self.cities)
        service = self.primary_service
        preferred = ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth"]
        by_name = {city.name: city for city in self.cities}
        chip_cities = [by_name[name] for name in preferred if name in by_name]
        seen = {city.slug for city in chip_cities}
        for city in self.by_count:
            if len(chip_cities) >= 5:
                break
            if city.slug not in seen:
                chip_cities.append(city)
                seen.add(city.slug)
        chips = "".join(
            f'<a class="hero-chip" href="{city.path}">{esc(city.name)}</a>'
            for city in chip_cities
        )
        datalist = "".join(
            f'<option value="{esc(city.name)}"></option>'
            for city in self.by_name
        )
        city_paths = {city.name.lower(): city.path for city in self.cities}
        featured = "".join(self.studio_card(studio) for studio in self.featured)
        cities = "".join(self.city_card(city) for city in self.by_count)
        extra_head = (
            f'<link rel="preload" as="image" href="{HERO_URL}/studio-desktop.webp" '
            'type="image/webp" media="(min-width: 701px)" fetchpriority="high">\n'
            f'<link rel="preload" as="image" href="{HERO_URL}/studio-mobile.webp" '
            'type="image/webp" media="(max-width: 700px)" fetchpriority="high">\n'
        )
        body = f"""<!-- Hero photo: Alexander Dummer, "Photographic studio", Unsplash (https://unsplash.com/photos/aS4Duj2j7r4). Published 16 August 2016. License: CC0 1.0 Public Domain. -->
<section class="home-hero">
  <div class="home-hero-media" aria-hidden="true">
    <picture>
      <source media="(max-width: 700px)" type="image/webp" srcset="{HERO_URL}/studio-mobile.webp">
      <source type="image/webp" srcset="{HERO_URL}/studio-desktop.webp">
      <img src="{HERO_URL}/studio-desktop.jpg" alt="" width="1920" height="1080" fetchpriority="high" decoding="async">
    </picture>
  </div>
  <div class="home-hero-overlay" aria-hidden="true"></div>
  <div class="wrap home-hero-content">
    <p class="eyebrow"><a href="/tx/">Texas directory</a></p>
    <h1>Find the Best Photo Studios in Texas</h1>
    <hr class="rule">
    <p class="lede">{comma(studio_count)} photography studios across {comma(city_count)} cities. Search a city to open its hub, or browse every listing below.</p>
    <form class="hero-city-search" id="hero-city-search" role="search" action="/cities/" method="get">
      <label class="visually-hidden" for="city-search">Search a Texas city</label>
      <input id="city-search" name="q" type="search" list="city-list" placeholder="Search a Texas city" autocomplete="off">
      <datalist id="city-list">{datalist}</datalist>
      <button class="btn btn-orange" type="submit">Go</button>
    </form>
    <script type="application/json" id="city-paths">{json.dumps(city_paths, ensure_ascii=False, separators=(",", ":"))}</script>
    <div class="hero-actions">
      <a class="btn btn-orange" href="#cities">Browse Cities</a>
      <a class="btn btn-ghost" href="/services/{esc(service["slug"])}/">Photo Editing - {esc(service["priceDisplay"])}</a>
    </div>
    <p class="hero-chip-label">Popular cities</p>
    <div class="hero-chips">{chips}</div>
  </div>
  <p class="home-hero-credit">Photo: <a href="https://unsplash.com/photos/aS4Duj2j7r4" rel="noopener noreferrer">Alexander Dummer / Unsplash</a> (CC0)</p>
</section>
<section class="section section-search"><div class="wrap">
  <div class="search-bar" role="search">
    <div>
      <label class="visually-hidden" for="studio-search">Search studios or cities</label>
      <input id="studio-search" type="search" placeholder="Search by studio or city" autocomplete="off">
    </div>
  </div>
  <div id="search-results" class="search-results" aria-live="polite"></div>
  <noscript><p>Every city is listed below. The search box runs in the browser.</p></noscript>
</div></section>
<section class="section section-sand"><div class="wrap">
  <div class="section-head"><h2>Featured studios</h2><a href="/cities/">All cities</a></div>
  <div class="card-grid">{featured}</div>
</div></section>
<section class="section" id="cities"><div class="wrap">
  <div class="section-head"><h2>Cities</h2><a href="/cities/">Alphabetical index</a></div>
  <div class="city-grid">{cities}</div>
</div></section>
<div class="wrap">{self.cta()}</div>"""
        schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "PhotoStudiosTexas.com",
            "url": self.abs_url("/"),
            "description": f"Directory of {studio_count} photo studios in {city_count} Texas cities.",
        }
        title = "Photo Studios in Texas | PhotoStudiosTexas.com"
        description = (
            f"Browse {comma(studio_count)} photo studios across {comma(city_count)} Texas cities. "
            "Compare ratings, hours, and contact details, and order professional photo editing for $39.88."
        )
        self.write_page("/", self.layout(title, description, "/", body, "home", [schema], extra_head=extra_head))

    def build_texas(self) -> None:
        path = "/tx/"
        cities = "".join(self.city_card(city) for city in self.by_count)
        with_phone = sum(1 for studio in self.studios if studio.get("phone"))
        with_site = sum(1 for studio in self.studios if http_url(studio.get("website")))
        temporary = sum(1 for studio in self.studios if studio.get("business_status") == "CLOSED_TEMPORARILY")
        crumbs = [("Home", "/"), ("Texas", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <p class="eyebrow">State hub</p>
  <h1>Photo studios in Texas</h1>
  <hr class="rule">
  <p class="lede">Every studio in this directory sits on a city page. This Texas hub links all {comma(len(self.cities))} city pages.</p>
  <div class="stat-row">
    <div class="stat"><b>{comma(len(self.studios))}</b> studios</div>
    <div class="stat"><b>{comma(len(self.cities))}</b> cities</div>
    <div class="stat"><b>{comma(temporary)}</b> temporarily closed</div>
  </div>
  <p class="muted">{comma(with_phone)} listings include a phone number and {comma(with_site)} include a website. {comma(temporary)} are marked temporarily closed in the source data and stay in the directory.</p>
</div>
<section class="section"><div class="wrap">
  <div class="section-head"><h2>All cities by number of studios</h2><a href="/cities/">View A–Z</a></div>
  <div class="city-grid">{cities}</div>
</div></section>
<div class="wrap">{self.cta()}</div>"""
        title = "Texas Photo Studio Directory | PhotoStudiosTexas.com"
        description = (
            f"Texas hub for {comma(len(self.studios))} photo studios in {comma(len(self.cities))} cities, "
            "with links to every city page."
        )
        self.write_page(path, self.layout(
            title, description, path, body, "",
            [self.breadcrumb_schema(crumbs, path)],
        ))

    def build_cities_index(self) -> None:
        path = "/cities/"
        letters = []
        groups = []
        current = None
        bucket = []
        for city in self.by_name:
            letter = city.name[0].upper()
            if letter != current:
                if bucket:
                    groups.append((current, bucket))
                current = letter
                bucket = [city]
            else:
                bucket.append(city)
        if bucket:
            groups.append((current, bucket))
        for letter, _cities in groups:
            letters.append(f'<a href="#letter-{esc(letter)}">{esc(letter)}</a>')
        sections = []
        for letter, cities in groups:
            items = "".join(
                f'<li><a href="{city.path}">{esc(city.name)}</a> <span class="muted">({city.count})</span></li>'
                for city in cities
            )
            sections.append(f'<section class="letter-group" id="letter-{esc(letter)}"><h2>{esc(letter)}</h2><ul>{items}</ul></section>')
        crumbs = [("Home", "/"), ("Cities", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <h1>Texas cities with photo studios</h1>
  <hr class="rule">
  <p class="lede">{comma(len(self.cities))} cities, from {esc(self.by_name[0].name)} to {esc(self.by_name[-1].name)}. Each city links to its studio listings.</p>
  <nav class="letters" aria-label="Letters">{"".join(letters)}</nav>
  {"".join(sections)}
  {self.cta()}
</div>"""
        title = "Texas Cities with Photo Studios | PhotoStudiosTexas.com"
        description = f"Alphabetical index of {comma(len(self.cities))} Texas cities and the photo studios listed in each one."
        self.write_page(path, self.layout(
            title, description, path, body, "cities",
            [self.breadcrumb_schema(crumbs, path)],
        ))

    def studio_title(self, studio: dict, name_counts: Counter, name_zip_counts: Counter) -> str:
        name = studio["name"]
        city = studio["city"]
        if name_zip_counts[(name, studio.get("postal_code"))] > 1:
            return f"{name} | {studio['address'] or studio['slug']}"
        if name_counts[name] > 1 and studio.get("postal_code"):
            return f"{name} ({studio['postal_code']}) | {city}, TX Photo Studio"
        return f"{name} | {city}, TX Photo Studio"

    def build_city(self, city: City) -> None:
        studios = sorted(city.studios, key=lambda studio: (
            studio.get("rating") is None,
            -(studio.get("rating") or 0),
            -(studio.get("review_count") or 0),
            studio["name"].lower(),
            studio["place_id"],
        ))
        cards = "".join(self.studio_card(studio, show_city=False) for studio in studios)
        crumbs = [("Home", "/"), ("Texas", "/tx/"), (city.name, None)]
        noun = "photo studio" if city.count == 1 else "photo studios"
        temporary = sum(1 for studio in studios if studio.get("business_status") == "CLOSED_TEMPORARILY")
        closed_note = ""
        if temporary:
            closed_note = f" <span class=\"muted\">{temporary} marked temporarily closed.</span>"
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <p class="eyebrow"><a href="/tx/">Texas</a></p>
  <h1>Photo studios in {esc(city.name)}, Texas</h1>
  <hr class="rule">
  <p class="lede">{comma(city.count)} {noun} in {esc(city.name)}.{closed_note}</p>
</div>
<section class="section"><div class="wrap"><div class="card-grid">{cards}</div></div></section>
<div class="wrap">{self.nearby_html(city)}{self.cta()}</div>"""
        item_list = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": f"Photo studios in {city.name}, Texas",
            "numberOfItems": city.count,
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index,
                    "name": studio["name"],
                    "url": self.abs_url(studio["url_path"]),
                }
                for index, studio in enumerate(studios, start=1)
            ],
        }
        title = f"Photo Studios in {city.name}, TX | PhotoStudiosTexas"
        description = (
            f"{comma(city.count)} photo studios in {city.name}, Texas, with ratings, addresses, "
            "phone numbers, hours, and a page for each studio."
        )
        self.write_page(city.path, self.layout(
            title, description, city.path, body, "",
            [self.breadcrumb_schema(crumbs, city.path), item_list],
        ))

    def facts_html(self, studio: dict) -> str:
        rows = []
        if studio.get("address"):
            rows.append(("Address", esc(studio["address"])))
        if studio.get("phone"):
            rows.append(("Phone", f'<a href="{esc(tel_href(studio["phone"]))}">{esc(studio["phone"])}</a>'))
        website = http_url(studio.get("website"))
        if website:
            label = re.sub(r"^www\.", "", re.sub(r"^https?://", "", website).split("/")[0])
            rows.append((
                "Website",
                f'<a href="{esc(website)}" rel="noopener noreferrer" target="_blank">{esc(label)}</a>',
            ))
        maps = http_url(studio.get("maps_url"))
        if maps:
            rows.append((
                "Map",
                f'<a href="{esc(maps)}" rel="noopener noreferrer" target="_blank">Google Maps</a>',
            ))
        if studio.get("located_in"):
            rows.append(("Located in", esc(studio["located_in"])))
        if studio.get("postal_code"):
            rows.append(("ZIP", esc(studio["postal_code"])))
        return "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows)

    def hours_html(self, hours: dict | None) -> str:
        if not hours:
            return ""
        rows = []
        seen = set()
        for day in DAY_ORDER + [day for day in hours if day not in DAY_ORDER]:
            if day in seen or day not in hours:
                continue
            seen.add(day)
            spans = ", ".join(str(span) for span in hours[day])
            rows.append(f'<tr><th scope="row">{esc(day)}</th><td>{esc(spans)}</td></tr>')
        return f'<table class="hours"><caption class="visually-hidden">Hours</caption><tbody>{"".join(rows)}</tbody></table>'

    def local_business(self, studio: dict) -> dict:
        data = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": studio["name"],
            "url": self.abs_url(studio["url_path"]),
            "address": {
                "@type": "PostalAddress",
                "addressLocality": studio["city"],
                "addressRegion": "TX",
                "addressCountry": "US",
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": studio["latitude"],
                "longitude": studio["longitude"],
            },
        }
        street = studio.get("street") or studio.get("address")
        if street:
            data["address"]["streetAddress"] = street
        if studio.get("postal_code"):
            data["address"]["postalCode"] = studio["postal_code"]
        if studio.get("phone"):
            data["telephone"] = studio["phone"]
        website = http_url(studio.get("website"))
        if website:
            data["sameAs"] = website
        photo = http_url(studio.get("photo"))
        if photo:
            data["image"] = photo
        maps = http_url(studio.get("maps_url"))
        if maps:
            data["hasMap"] = maps
        if studio.get("description"):
            data["description"] = studio["description"]
        elif studio.get("category"):
            data["description"] = f'{studio["category"]} in {studio["city"]}, Texas.'
        if studio.get("rating") is not None and studio.get("review_count"):
            data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": studio["rating"],
                "reviewCount": studio["review_count"],
                "bestRating": 5,
                "worstRating": 1,
            }
        hours = opening_hours(studio.get("hours"))
        if hours:
            data["openingHoursSpecification"] = hours
        return data

    def build_studio(self, studio: dict, city: City, title: str) -> None:
        others = [
            other for other in city.studios
            if other["place_id"] != studio["place_id"]
        ]
        others.sort(key=lambda item: (item["name"].lower(), item["place_id"]))
        other_links = "".join(
            f'<li><a href="{esc(other["url_path"])}">{esc(other["name"])}</a></li>'
            for other in others
        )
        other_section = ""
        if other_links:
            other_section = f'<section class="section"><h2>Other studios in {esc(city.name)}</h2><ul class="link-cols">{other_links}</ul></section>'
        subtypes = [item for item in studio.get("subtypes") or [] if item.lower() != (studio.get("category") or "").lower()]
        subtype_html = ""
        if subtypes:
            subtype_html = f'<p class="muted">Also listed as {esc(", ".join(subtypes))}.</p>'
        description = ""
        if studio.get("description"):
            description = f'<p>{esc(studio["description"])}</p>'
        category = studio.get("category") or "Photo studio"
        crumbs = [("Home", "/"), ("Texas", "/tx/"), (city.name, city.path), (studio["name"], None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <div class="studio-layout">
    <div>
      {photo_block(studio, "studio-hero")}
      {badge(studio)}
      <h1>{esc(studio["name"])}</h1>
      <hr class="rule">
      <p class="lede">{esc(category)} in {esc(city.name)}, Texas.</p>
      {rating_html(studio)}
      {description}
      {subtype_html}
    </div>
    <aside class="panel">
      <h2>Details</h2>
      <dl class="facts">{self.facts_html(studio)}</dl>
      {self.hours_html(studio.get("hours"))}
    </aside>
  </div>
  {self.cta()}
  {other_section}
  {self.nearby_html(city)}
  <p><a href="{city.path}">All photo studios in {esc(city.name)}</a></p>
</div>"""
        bits = [f"{studio['name']} is a {category.lower()} in {city.name}, Texas."]
        if studio.get("rating") is not None and studio.get("review_count"):
            bits.append(f"Rated {float(studio['rating']):.1f} from {int(studio['review_count'])} reviews.")
        if studio.get("address"):
            bits.append(studio["address"] + ".")
        description_text = " ".join(bits)
        self.write_page(studio["url_path"], self.layout(
            title,
            description_text,
            studio["url_path"],
            body,
            "",
            [self.breadcrumb_schema(crumbs, studio["url_path"]), self.local_business(studio)],
        ))

    def build_studios(self) -> None:
        for city in self.by_name:
            name_counts = Counter(studio["name"] for studio in city.studios)
            name_zip_counts = Counter((studio["name"], studio.get("postal_code")) for studio in city.studios)
            self.build_city(city)
            for studio in city.studios:
                self.build_studio(studio, city, self.studio_title(studio, name_counts, name_zip_counts))

    def service_gallery(self, service: dict) -> str:
        examples = service.get("beforeAfter") or []
        if not examples:
            return ""
        cards = []
        for item in examples:
            href = f"{EXAMPLE_URL}/{item['file']}.webp"
            cards.append(
                "<figure class=\"ba-card\">"
                f'<a href="{esc(href)}" data-lightbox data-caption="{esc(item["caption"])}">'
                f"{example_picture(item)}"
                "</a>"
                f'<figcaption>{esc(item["caption"])}</figcaption>'
                "</figure>"
            )
        return f"""<section class="section ba-gallery" id="before-after">
  <h2>Before &amp; After</h2>
  <p>Examples of the retouching work. Each image already shows the original and the finished edit. Click any example to enlarge it.</p>
  <div class="ba-grid">{"".join(cards)}</div>
</section>
"""

    def service_body(self, service: dict) -> str:
        includes = "".join(f"<div><strong>{esc(item)}</strong></div>" for item in service["packageIncludes"])
        covered = "".join(f"<li>{esc(item)}</li>" for item in service["covered"])
        payment = self.payment_link(service)
        if payment:
            button = (
                f'<a class="btn btn-orange" id="order-now" href="{esc(payment)}" '
                f'target="_blank" rel="noopener noreferrer">{esc(service["orderButtonLabel"])}</a>'
            )
            payment_note = "<p>You’ll complete payment on the secure checkout page.</p>"
        else:
            button = f'<a class="btn btn-orange" id="order-now" href="#order">{esc(service["orderButtonLabel"])}</a>'
            payment_note = "<p>Include a link to your photos in the order form.</p>"
        others = [
            other for other in self.services
            if other["slug"] != service["slug"]
        ]
        other_html = ""
        if others:
            links = "".join(
                f'<li><a href="/services/{esc(other["slug"])}/">{esc(other["name"])}</a></li>'
                for other in others
            )
            other_html = f"<h2>Other services</h2><ul>{links}</ul>"
        return f"""<div class="split">
  <div>
    <p class="lede">{esc(service["summary"])}</p>
    <div class="include-grid">{includes}</div>
    <h2>What you can send</h2>
    <ul class="cover-list">{covered}</ul>
    <p><a href="/cities/">Find a photo studio in Texas</a> if you still need the pictures taken.</p>
    {other_html}
  </div>
  <aside class="panel">
    <p class="price">{esc(service["priceDisplay"])} <span>{esc(service["priceNote"])}</span></p>
    <p>{esc(service["delivery"])} · {esc(service["revisions"])}</p>
    <!-- STRIPE_PAYMENT_LINK is read from config/site.json. Leave it empty until the Stripe Payment Link exists. -->
    {button}
    {payment_note}
  </aside>
</div>
{self.service_gallery(service)}
<section class="section" id="order">
  <h2>Order</h2>
  {self.order_form(service, f'{service["name"]} order', "Send order")}
</section>"""

    def build_services(self) -> None:
        cards = []
        for service in self.services:
            cards.append(
                f'<a class="studio-card" href="/services/{esc(service["slug"])}/"><div class="card-body">'
                f'<p class="eyebrow">Service</p><h3>{esc(service["name"])}</h3>'
                f'<p class="price">{esc(service["priceDisplay"])} <span>{esc(service["priceNote"])}</span></p>'
                f'<p>{esc(service["summary"])}</p></div></a>'
            )
        index_path = "/services/"
        crumbs = [("Home", "/"), ("Services", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <h1>Services</h1>
  <hr class="rule">
  <p class="lede">Photo editing is the first service. More can be added beside it without changing the directory.</p>
  <div class="card-grid">{"".join(cards)}</div>
</div>"""
        self.write_page(index_path, self.layout(
            "Services | PhotoStudiosTexas.com",
            "Photo editing and retouching from PhotoStudiosTexas.com. One package is $39.88 per order.",
            index_path,
            body,
            "service",
            [self.breadcrumb_schema(crumbs, index_path)],
        ))
        for service in self.services:
            path = f"/services/{service['slug']}/"
            service_crumbs = [("Home", "/"), ("Services", "/services/"), (service["name"], None)]
            page = f"""<div class="wrap page-head">
  {self.crumbs(service_crumbs)}
  <p class="eyebrow">Service</p>
  <h1>{esc(service["name"])}</h1>
  <hr class="rule">
  {self.service_body(service)}
</div>"""
            price = service["priceDisplay"].replace("$", "").replace(",", "").strip()
            offer = {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": service["name"],
                "serviceType": service["name"],
                "url": self.abs_url(path),
                "areaServed": "Texas",
                "provider": {"@type": "Organization", "name": "PhotoStudiosTexas.com", "url": self.abs_url("/")},
                "offers": {
                    "@type": "Offer",
                    "price": price,
                    "priceCurrency": "USD",
                    "description": f'{service["delivery"]}, {service["revisions"]}',
                    "url": self.abs_url(path),
                },
            }
            self.write_page(path, self.layout(
                f'{service["name"]} | {service["priceDisplay"]}',
                service["summary"],
                path,
                page,
                "service",
                [self.breadcrumb_schema(service_crumbs, path), offer],
            ))

    def build_about(self) -> None:
        path = "/about/"
        crumbs = [("Home", "/"), ("About / Contact", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <h1>About PhotoStudiosTexas.com</h1>
  <hr class="rule">
  <p class="lede">PhotoStudiosTexas.com lists photography studios in Texas and offers professional photo editing.</p>
  <p>Studios come from a public Google Maps export for the search “Photography studio in TX.” The build keeps Texas listings, drops permanently closed businesses, and removes duplicate records that share a name and address. Temporarily closed businesses stay, with a label on the page. Ratings, hours, phone numbers, websites, and photos are shown only when that export included them.</p>
  <p>City pages are the hubs. Every studio links up to its city, and each city links back to the Texas directory. Nothing here is an endorsement of a studio, and the site is not affiliated with Google or with the businesses listed.</p>
  <p><a href="/services/{esc(self.primary_service["slug"])}/">Professional photo editing</a> is {esc(self.primary_service["priceDisplay"])} {esc(self.primary_service["priceNote"])}, with {esc(self.primary_service["delivery"]).lower()} and {esc(self.primary_service["revisions"]).lower()}.</p>
  <h2>Contact</h2>
  {self.order_form(None, "PhotoStudiosTexas contact", "Send message")}
</div>"""
        self.write_page(path, self.layout(
            "About & Contact | PhotoStudiosTexas.com",
            "About the Texas photo studio directory: where listings come from, how they are cleaned, and how to get in touch.",
            path,
            body,
            "about",
            [self.breadcrumb_schema(crumbs, path)],
        ))

    def build_html_sitemap(self) -> None:
        path = "/sitemap/"
        static = [
            ("/", "Home"),
            ("/tx/", "Texas"),
            ("/cities/", "Cities"),
            ("/services/", "Services"),
            (f"/services/{self.primary_service['slug']}/", self.primary_service["name"]),
            ("/about/", "About / Contact"),
        ]
        static_html = "".join(f'<li><a href="{href}">{esc(label)}</a></li>' for href, label in static)
        groups = []
        for city in self.by_name:
            studios = sorted(city.studios, key=lambda studio: studio["name"].lower())
            links = "".join(
                f'<li><a href="{esc(studio["url_path"])}">{esc(studio["name"])}</a></li>'
                for studio in studios
            )
            groups.append(
                f'<section class="letter-group"><h2><a href="{city.path}">{esc(city.name)}</a></h2><ul>{links}</ul></section>'
            )
        crumbs = [("Home", "/"), ("HTML sitemap", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <h1>HTML sitemap</h1>
  <hr class="rule">
  <p class="lede">Every page on PhotoStudiosTexas.com, grouped by city.</p>
  <ul class="plain-list">{static_html}</ul>
  {"".join(groups)}
</div>"""
        self.write_page(path, self.layout(
            "HTML Sitemap | PhotoStudiosTexas.com",
            "HTML sitemap of the Texas photo studio directory, including every city and studio page.",
            path,
            body,
            "",
            [self.breadcrumb_schema(crumbs, path)],
        ))

    def build_404(self) -> None:
        body = """<div class="wrap page-head">
  <h1>Page not found</h1>
  <hr class="rule">
  <p>That page is not in the directory.</p>
  <p><a class="btn" href="/">Back to Texas studios</a></p>
</div>"""
        document = self.layout(
            "Page not found | PhotoStudiosTexas.com",
            "That page is not on PhotoStudiosTexas.com.",
            "/404.html",
            body,
            "",
            [],
            robots="noindex,follow",
        )
        target = DIST / "404.html"
        target.write_text(document, encoding="utf-8")

    def build_feeds(self) -> None:
        urls = [self.abs_url(path) for path, _relative in self.pages]
        body = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for url in urls:
            body.append(f"  <url><loc>{esc(url)}</loc></url>")
        body.append("</urlset>\n")
        (DIST / "sitemap.xml").write_text("\n".join(body), encoding="utf-8")
        robots = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /assets/\n"
            f"Sitemap: {self.abs_url('/sitemap.xml')}\n"
        )
        (DIST / "robots.txt").write_text(robots, encoding="utf-8")

    def copy_image_dir(self, src: Path, dest: Path) -> None:
        if not src.is_dir():
            return
        dest.mkdir(parents=True, exist_ok=True)
        for item in sorted(src.iterdir()):
            if item.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png"}:
                shutil.copyfile(item, dest / item.name)

    def write_runtime_assets(self) -> None:

        config = {
            "STRIPE_PAYMENT_LINK": str(self.config.get("STRIPE_PAYMENT_LINK") or ""),
            "ORDER_FORM_ENDPOINT": str(self.config.get("ORDER_FORM_ENDPOINT") or ""),
            "CONTACT_EMAIL": self.email,
        }
        script = "window.SITE_CONFIG = " + json.dumps(config, indent=2) + ";\n"
        assets = DIST / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / "site-config.js").write_text(script, encoding="utf-8")
        index = []
        for studio in self.studios:
            index.append({
                "name": studio["name"],
                "city": studio["city"],
                "url": studio["url_path"],
                "rating": studio.get("rating"),
                "reviews": studio.get("review_count"),
                "closed": studio.get("business_status") == "CLOSED_TEMPORARILY",
            })
        index.sort(key=lambda item: (item["city"].lower(), item["name"].lower()))
        (assets / "search-index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        shutil.copyfile(ROOT / "assets" / "site.css", assets / "site.css")
        shutil.copyfile(ROOT / "assets" / "site.js", assets / "site.js")
        shutil.copyfile(BRAND / "logo-light.svg", assets / "logo-light.svg")
        shutil.copyfile(BRAND / "logo-dark.svg", assets / "logo-dark.svg")
        for name in ROOT_ASSETS:
            shutil.copyfile(BRAND / name, DIST / name)
        self.copy_image_dir(EXAMPLES_DIR, DIST / "images" / "retouching")
        self.copy_image_dir(HERO_DIR, DIST / "images" / "hero")

    def build(self) -> None:
        if DIST.exists():
            shutil.rmtree(DIST)
        DIST.mkdir(parents=True)
        self.build_home()
        self.build_texas()
        self.build_cities_index()
        self.build_services()
        self.build_about()
        self.build_studios()
        self.build_html_sitemap()
        self.build_404()
        self.build_feeds()
        self.write_runtime_assets()
        print(
            f"Built {len(self.pages)} indexable pages "
            f"({len(self.cities)} cities, {len(self.studios)} studios) in {DIST}"
        )


def main() -> None:
    if not DATA_PATH.is_file():
        raise SystemExit("data/studios.json is missing. Run scripts/clean_data.py first.")
    Site().build()


if __name__ == "__main__":
    main()
