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

import categories as cat
import studio_info as si
from category_pages import CategoryMixin
from directory_pages import DirectoryMixin
from extra_pages import TOOLS, ExtrasMixin
from lead_form import LeadMixin
from trust_pages import LEGAL_LINKS, TrustMixin

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


class Site(DirectoryMixin, CategoryMixin, ExtrasMixin, TrustMixin, LeadMixin):
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
        self.year = 2026

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

    def service_price(self, service: dict) -> str:
        price = str(service.get("priceDisplay") or "").strip()
        if not price or price.upper().startswith("TODO"):
            return ""
        return price

    def _about_services(self) -> str:
        parts = []
        for service in self.services:
            href = f'/services/{esc(service["slug"])}/'
            parts.append(
                f'<a href="{href}">{esc(service["name"])}</a> '
                f'({esc(service["delivery"]).lower()}, {esc(service["revisions"]).lower()})'
            )
        if not parts:
            return "see the services page for details."
        if len(parts) == 1:
            return parts[0] + "."
        return "; ".join(parts[:-1]) + "; and " + parts[-1] + "."

    def head_links(self, image: dict | None = None) -> str:
        if image:
            og_url = image.get("abs") or image.get("src")
            og_w, og_h = int(image.get("width", 1200)), int(image.get("height", 630))
            og_alt = image.get("alt") or "PhotoStudiosTexas.com photo studios across Texas"
        else:
            og_url = self.abs_url("/og-image.png")
            og_w, og_h = 1200, 630
            og_alt = "PhotoStudiosTexas.com — photo studios across Texas"
        return f"""
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#111111">
<meta property="og:image" content="{esc(og_url)}">
<meta property="og:image:width" content="{og_w}">
<meta property="og:image:height" content="{og_h}">
<meta property="og:image:alt" content="{esc(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{esc(og_url)}">
<meta name="twitter:image:alt" content="{esc(og_alt)}">"""

    def header(self, active: str) -> str:
        items = [
            ("home", "/", "Home"),
            ("cities", "/cities/", "Cities"),
            *(("categories", "/categories/", "Categories"),) * bool(self.categories_exist()),
            ("blog", "/blog/", "Blog"),
            ("tools", "/tools/", "Free Tools"),
            ("service", "/services/", "Services"),
            ("about", "/about/", "About"),
        ]
        links = []
        for key, href, label in items:
            current = ' aria-current="page"' if key == active else ""
            links.append(f'<a href="{href}"{current}>{esc(label)}</a>')
        return f"""<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="/"><img src="/assets/logo-light.svg" alt="PhotoStudiosTexas" width="276" height="48"></a>
    <input class="nav-toggle" id="nav-toggle" type="checkbox">
    <label class="nav-burger" for="nav-toggle" role="button"><b class="visually-hidden">Menu</b><span></span></label>
    <nav class="nav" aria-label="Primary">{''.join(links)}</nav>
  </div>
</header>"""

    def footer(self) -> str:
        explore = [
            ("/", "Home"),
            ("/tx/", "Texas"),
            ("/cities/", "All cities"),
            *(("/categories/", "Categories"),) * bool(self.categories_exist()),
            ("/blog/", "Blog"),
            ("/tools/", "Free photo tools"),
            ("/services/", "Services"),
            ("/about/", "About / Contact"),
            ("/sitemap/", "HTML sitemap"),
            ("/sitemap.xml", "XML sitemap"),
        ]
        explore_html = "".join(f'<li><a href="{href}">{esc(label)}</a></li>' for href, label in explore)
        service_html = "".join(
            f'<li><a href="/services/{esc(service["slug"])}/">{esc(service["name"])}</a></li>'
            for service in self.services
        ) + "".join(
            f'<li><a href="/tools/{tool["slug"]}/">{esc(tool["name"])}</a> <span class="muted">(free)</span></li>'
            for tool in TOOLS[:2]
        )
        city_html = "".join(
            f'<li><a href="{city.path}">{esc(city.name)}</a> <span class="muted">({city.count})</span></li>'
            for city in self.footer_cities
        )
        return f"""<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <a class="footer-logo" href="/"><img src="/assets/logo-dark.svg" alt="PhotoStudiosTexas" width="276" height="48"></a>
      <p>A directory of photo studios in Texas, plus photo editing and photo enhancement when you need the pictures finished.</p>
    </div>
    <div>
      <h2>Explore</h2>
      <ul>{explore_html}</ul>
    </div>
    <div>
      <h2>Services &amp; tools</h2>
      <ul>{service_html}</ul>
    </div>
    <div>
      <h2>Top cities</h2>
      <ul>{city_html}</ul>
    </div>
  </div>
  <div class="wrap legal">
    <p class="legal-links">{self.legal_links_html()} · <a href="{self.claim_href()}">Claim or remove a listing</a></p>
    <p>Listing details come from public Google Maps information and may be out of date. PhotoStudiosTexas.com is independent and is not affiliated with Google or the studios listed. &copy; {self.year} Photo Studios Texas.</p>
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
        sentences = []
        buttons = []
        for service in self.services:
            href = f'/services/{esc(service["slug"])}/'
            sentences.append(
                f'<a href="{href}">{esc(service["name"])}</a> includes '
                f'{esc(service["delivery"]).lower()} and {esc(service["revisions"]).lower()}.'
            )
            label = service.get("navLabel") or service["name"]
            buttons.append(f'<a class="btn" href="{href}" aria-label="Learn more about {esc(label)}">Learn More: {esc(label)}</a>')
        teaser = ""
        for service in self.services:
            examples = service.get("beforeAfter") or []
            if examples:
                item = examples[0]
                teaser = f"""
    <a class="cta-teaser" href="/services/{esc(service["slug"])}/#before-after">
      {example_picture(item)}
      <span class="cta-teaser-label">See before &amp; after</span>
    </a>"""
                break
        return f"""<aside class="cta">
  <div class="cta-inner">
    <div class="cta-copy">
      <p class="eyebrow">Services</p>
      <h2>Editing and enhancement when the shoot is done</h2>
      <p>{" ".join(sentences)}</p>
      <div class="cta-actions">{"".join(buttons)}</div>
      <p class="cta-all"><a href="/services/">See all services</a></p>
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

    def layout(self, title: str, description: str, path: str, body: str, active: str, schemas: list, robots: str = "index,follow", extra_head: str = "", image: dict | None = None, directory: bool = False) -> str:
        canonical = self.abs_url(path)
        description = meta_text(description)
        schema_html = "\n".join(json_script(item) for item in schemas)
        extra_js = '\n<script src="/assets/directory.js" defer></script>' if directory else ""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-4F7YLXF581"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-4F7YLXF581');
</script>
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
{self.head_links(image)}
<link rel="stylesheet" href="/assets/site.css">
<link rel="stylesheet" href="/assets/directory.css">
{extra_head}{schema_html}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{self.header(active)}
<main id="main">{body}</main>
{self.footer()}
<script src="/assets/site-config.js"></script>
<script src="/assets/site.js"></script>
<script src="/assets/lead-form.js" defer></script>{extra_js}
<script>window.va=window.va||function(){{(window.vaq=window.vaq||[]).push(arguments);}};</script>
<script defer src="/_vercel/insights/script.js"></script>
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

    def build_home(self) -> None:
        studio_count = len(self.studios)
        city_count = len(self.cities)
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
        major = [city for city in self.by_count[:10]]
        major_opts = "".join(
            f'<option value="{city.path}">{esc(city.name)} ({city.count})</option>' for city in major
        )
        all_opts = "".join(
            f'<option value="{city.path}">{esc(city.name)} ({city.count})</option>' for city in self.by_name
        )
        datalist = (f'<option value="">Choose a Texas city…</option>'
                    f'<optgroup label="Largest cities">{major_opts}</optgroup>'
                    f'<optgroup label="All cities A–Z">{all_opts}</optgroup>')
        city_paths = {city.name.lower(): city.path for city in self.cities}
        featured = "".join(self.studio_card(studio) for studio in self.featured)
        blog_chips = "".join(
            f'<a class="chip" href="{self.blog_path(city)}">Best in {esc(city.name)}</a>'
            for city in self.blog_cities[:12]
        )
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
    <p class="lede">{comma(studio_count)} photography studios across {comma(city_count)} cities. Pick your city to open its studios, or see the top-rated studios near you below.</p>
    <form class="hero-city-search" id="hero-city-select" action="/cities/" method="get" onsubmit="var v=this.elements['city'].value;if(v){{location.href=v;}}return false;">
      <label class="visually-hidden" for="city-select">Choose a Texas city</label>
      <select id="city-select" name="city" onchange="if(this.value)location.href=this.value">{datalist}</select>
      <button class="btn btn-orange" type="submit">Go</button>
    </form>
    <script type="application/json" id="city-paths">{json.dumps(city_paths, ensure_ascii=False, separators=(",", ":"))}</script>
    <div class="hero-actions">
      <a class="btn btn-orange" href="#cities">Browse Cities</a>
      <a class="btn btn-ghost" href="/services/">Photo services</a>
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
<section class="section section-sand" id="near-you"><div class="wrap">
  <div class="section-head"><h2 id="near-title">Featured studios across Texas</h2><a id="near-link" href="/cities/">All cities</a></div>
  <div class="near-bar" id="near-bar" hidden>
    <p class="muted" id="near-note"></p>
    <button type="button" class="btn" id="near-precise">Use my precise location</button>
  </div>
  <div class="card-grid" id="near-grid">{featured}</div>
</div></section>
<section class="section"><div class="wrap">
  <div class="section-head"><h2>Best photo studios by city</h2><a href="/blog/">All city guides</a></div>
  <div class="chips">{blog_chips}</div>
</div></section>
{self.category_home_section()}
<section class="section" id="cities"><div class="wrap">
  <div class="section-head"><h2>Cities</h2><a href="/cities/">Alphabetical index</a></div>
  <div class="city-grid">{cities}</div>
</div></section>
{self.home_lead_section()}
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
            f"Compare ratings and hours, then book a studio with one quick form."
        )
        extra_head += '<script src="/assets/home-geo.js" defer></script>\n'
        self.write_page("/", self.layout(title, description, "/", body, "home", [schema], extra_head=extra_head, directory=True))

    def build_texas(self) -> None:
        path = "/tx/"
        cities = "".join(self.city_card(city) for city in self.by_count)
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
  <p class="muted">{comma(temporary)} listings are marked temporarily closed in the source data and stay in the directory.</p>
</div>
{self.category_home_section("Texas photo studios by category")}
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

    def service_steps(self, service: dict) -> str:
        steps = service.get("howItWorks") or []
        if not steps:
            return ""
        items = []
        for step in steps:
            if isinstance(step, dict):
                items.append(
                    f'<li><strong>{esc(step["title"])}</strong> {esc(step["text"])}</li>'
                )
            else:
                items.append(f"<li>{esc(step)}</li>")
        return f"""<section class="section" id="how-it-works">
  <h2>How it works</h2>
  <ol class="steps">{"".join(items)}</ol>
</section>
"""

    def service_faq(self, service: dict) -> str:
        faqs = service.get("faq") or []
        if not faqs:
            return ""
        items = "".join(
            f"<dt>{esc(item['q'])}</dt><dd>{esc(item['a'])}</dd>"
            for item in faqs
        )
        return f"""<section class="section" id="faq">
  <h2>Frequently asked questions</h2>
  <dl class="faq">{items}</dl>
</section>
"""

    def service_body(self, service: dict) -> str:
        includes = "".join(f"<div><strong>{esc(item)}</strong></div>" for item in service["packageIncludes"])
        covered = "".join(f"<li>{esc(item)}</li>" for item in service["covered"])
        price = self.service_price(service)
        payment = self.payment_link(service)
        key = service.get("paymentLinkKey", "STRIPE_PAYMENT_LINK")
        if price and payment:
            button = (
                f'<a class="btn btn-orange" id="order-now" href="{esc(payment)}" '
                f'data-payment-key="{esc(key)}" '
                f'target="_blank" rel="noopener noreferrer">{esc(service["orderButtonLabel"])}</a>'
            )
            payment_note = '<p>You’ll complete payment on the secure checkout page, then send your photos in the <a href="#order">order form</a>. See our <a href="/refund-policy/">refund policy</a>.</p>'
        elif price:
            button = (
                f'<a class="btn btn-orange" id="order-now" href="#order" '
                f'data-payment-key="{esc(key)}">{esc(service["orderButtonLabel"])}</a>'
            )
            payment_note = '<p>Upload your photos in the <a href="#order">order form</a> below.</p>'
        else:
            button = '<a class="btn btn-orange" href="#order">Request this service</a>'
            payment_note = "<p>The price will appear here once it is set. Use the form below to request this service.</p>"
        price_html = (
            f'<p class="price">{esc(price)} <span>{esc(service["priceNote"])}</span></p>'
            if price else ""
        )
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
            other_html = f'<h2>Other services</h2><ul class="plain-list">{links}</ul>'
        other_html += (
            '<p><a href="/services/">See all photo services</a> · '
            '<a href="/tools/">Try our free photo tools</a></p>'
        )
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
    {price_html}
    <p>{esc(service["delivery"])} · {esc(service["revisions"])}</p>
    <!-- Payment links are read from config/site.json by paymentLinkKey. Leave the key empty until the Stripe Payment Link exists. -->
    {button}
    {payment_note}
  </aside>
</div>
{self.service_gallery(service)}
{self.service_steps(service)}
{self.service_faq(service)}
<section class="section" id="order">
  <h2>Order</h2>
  {self.order_form(service, f'{service["name"]} order', "Send order")}
</section>"""

    def build_services(self) -> None:
        cards = []
        for service in self.services:
            cards.append(
                f'<a class="studio-card service-card" href="/services/{esc(service["slug"])}/"><div class="card-body">'
                f'<p class="eyebrow">Service</p><h3>{esc(service["name"])}</h3>'
                f'<p>{esc(service["delivery"])} · {esc(service["revisions"])}</p>'
                f'<p>{esc(service["summary"])}</p><span class="btn btn-orange">Learn More</span></div></a>'
            )
        index_path = "/services/"
        crumbs = [("Home", "/"), ("Services", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <h1>Services</h1>
  <hr class="rule">
  <p class="lede">Professional photo editing and photo enhancement for studios and clients across Texas. Pick a service to see what’s included, how it works, and how to order.</p>
  <div class="card-grid">{"".join(cards)}</div>
  <p>Just need a quick fix? Our <a href="/tools/">free photo tools</a> include an <a href="/tools/image-background-remover/">image background remover</a>, resizer, compressor, cropper, and format converter.</p>
</div>"""
        self.write_page(index_path, self.layout(
            "Services | PhotoStudiosTexas.com",
            "Photo editing, retouching, enhancement, and upscaling from PhotoStudiosTexas.com, with turnaround and what's included.",
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
            price = self.service_price(service).replace("$", "").replace(",", "").strip()
            offer = {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": service["name"],
                "serviceType": service["name"],
                "url": self.abs_url(path),
                "areaServed": "Texas",
                "provider": {"@type": "Organization", "name": "PhotoStudiosTexas.com", "url": self.abs_url("/")},
            }
            if price:
                offer["offers"] = {
                    "@type": "Offer",
                    "price": price,
                    "priceCurrency": "USD",
                    "description": f'{service["delivery"]}, {service["revisions"]}',
                    "url": self.abs_url(path),
                }
            title = service["name"] if not self.service_price(service) else f'{service["name"]} | {self.service_price(service)}'
            self.write_page(path, self.layout(
                f"{title}",
                service["summary"],
                path,
                page,
                "service",
                [self.breadcrumb_schema(service_crumbs, path), offer],
            ))

    def build_about(self) -> None:
        path = "/about/"
        crumbs = [("Home", "/"), ("About", None)]
        blog_count = len(self.blog_cities)
        largest = ", ".join(
            f'<a href="{city.path}">{esc(city.name)}</a> ({city.count})' for city in self.by_count[:6]
        )
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <p class="eyebrow">About</p>
  <h1>About PhotoStudiosTexas.com</h1>
  <hr class="rule">
  <p class="lede">PhotoStudiosTexas.com helps you find a photo studio anywhere in Texas, compare them on real ratings and hours, and get your photos finished once the shoot is done.</p>
  <div class="stat-row">
    <div class="stat"><b>{comma(len(self.studios))}</b> studios</div>
    <div class="stat"><b>{comma(len(self.cities))}</b> cities</div>
    <div class="stat"><b>{blog_count}</b> city guides</div>
    <div class="stat"><b>{len(TOOLS)}</b> free tools</div>
  </div>
  <div class="split about-split">
    <div>
      <h2>What you'll find here</h2>
      <ul class="plain-list about-list">
        <li><strong><a href="/cities/">City directories</a>.</strong> Every studio sits on its city page, with filters for specialty, rating, open now, and online booking. The largest are {largest}.</li>
        <li><strong>Studio pages.</strong> Hours, specialties, amenities, the Google rating and star breakdown, a map, and links to nearby studios.</li>
        <li><strong><a href="/blog/">City guides</a>.</strong> Ranked lists of the best photo studios in {blog_count} Texas cities, using one open formula that weighs rating by review count.</li>
        <li><strong><a href="/tools/">Free photo tools</a>.</strong> A <a href="/tools/image-background-remover/">background remover</a>, resizer, compressor, cropper, and converter that run in your browser.</li>
        <li><strong><a href="/services/">Photo services</a>.</strong> {self._about_services()}</li>
      </ul>
      <h2>Where the listings come from</h2>
      <p>Studios come from a public Google Maps export for the search “Photography studio in TX.” The build keeps Texas listings, drops permanently closed businesses, and removes duplicate records that share a name and address. Temporarily closed businesses stay, with a label on the page. Ratings, hours, and photos are shown only when the listing includes them. Studio phone numbers, emails, and websites are not published; use the Book Now form instead. Specialties are matched from each listing's Google categories, name, and the studio's own website.</p>
      <h2>How we rank studios</h2>
      <p>Lists and guides never take payment for placement. Where we rank, we blend each studio's Google rating with the statewide average, weighted by its number of reviews, so a 5.0 from three reviews does not beat a 4.9 from three hundred. The formula is printed in every <a href="/blog/">city guide</a>.</p>
      <h2>Own a studio?</h2>
      <p>If your details are wrong or your studio is missing, send a correction with the form below. Updating your Google Business Profile also fixes the next refresh.</p>
      <p class="muted">PhotoStudiosTexas.com is independent. It is not affiliated with Google or with the businesses listed, and a listing is not an endorsement.</p>
    </div>
    <aside class="panel" id="contact">
      <h2>Contact</h2>
      <p>Questions, corrections, or orders: use the form{f' or email <a href="mailto:{esc(self.email)}">{esc(self.email)}</a>' if self.email else ''}.</p>
      {self.order_form(None, "PhotoStudiosTexas contact", "Send message")}
    </aside>
  </div>
</div>"""
        about_schema = {
            "@context": "https://schema.org", "@type": "AboutPage", "url": self.abs_url(path),
            "name": "About PhotoStudiosTexas.com",
            "mainEntity": {"@type": "Organization", "name": "PhotoStudiosTexas.com", "url": self.abs_url("/"),
                           "logo": self.abs_url("/icon-512.png"), "areaServed": "Texas"},
        }
        if self.email:
            about_schema["mainEntity"]["email"] = self.email
        self.write_page(path, self.layout(
            "About PhotoStudiosTexas.com | Texas Photo Studio Directory",
            "About the Texas photo studio directory: where listings come from, how studios are ranked, our free tools and photo services, and how to get in touch.",
            path,
            body,
            "about",
            [self.breadcrumb_schema(crumbs, path), about_schema],
        ))

    def build_html_sitemap(self) -> None:
        path = "/sitemap/"
        static = [
            ("/", "Home"),
            ("/tx/", "Texas"),
            ("/cities/", "Cities"),
            ("/services/", "Services"),
        ]
        static[3:3] = self.category_sitemap_entries()
        static.extend(
            (f"/services/{service['slug']}/", service["name"])
            for service in self.services
        )
        static.append(("/blog/", "Blog"))
        static.extend((self.blog_path(city), self.blog_title(city)) for city in self.blog_cities)
        static.append(("/tools/", "Free photo tools"))
        static.extend((f"/tools/{tool['slug']}/", tool["name"]) for tool in TOOLS)
        static.append(("/about/", "About / Contact"))
        static.extend(LEGAL_LINKS)
        static_html = "".join(f'<li><a href="{href}">{esc(label)}</a></li>' for href, label in static)
        groups = []
        self.prepare_directory()
        for city in self.by_name:
            studios = sorted(city.studios, key=lambda studio: studio["name"].lower())
            cat_links = "".join(
                f'<li><a href="{city.path}{si.SPEC_BY_ID[sid][2]}/">'
                f'{esc(cat.CAT_BY_ID[sid][3].replace(" in Texas", "") if sid in getattr(cat, "NAMED_CITY_IDS", ()) else si.SPEC_BY_ID[sid][3])} in {esc(city.name)}</a></li>'
                for sid, _m in sorted((self.spec_pages.get(city.slug) or {}).items(), key=lambda kv: si.SPEC_BY_ID[kv[0]][1])
            )
            links = "".join(
                f'<li><a href="{esc(studio["url_path"])}">{esc(studio["name"])}</a></li>'
                for studio in studios
            )
            groups.append(
                f'<section class="letter-group"><h2><a href="{city.path}">{esc(city.name)}</a></h2><ul>{cat_links}{links}</ul></section>'
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
        city_links = "".join(
            f'<li><a href="{city.path}">{esc(city.name)}</a> <span class="muted">({city.count})</span></li>'
            for city in self.by_count[:8]
        )
        body = f"""<div class="wrap page-head not-found">
  <p class="eyebrow">Error 404</p>
  <h1>That page isn’t in the frame</h1>
  <hr class="rule">
  <p class="lede">The page you were looking for has moved or doesn’t exist. Try one of these instead.</p>
  <p><a class="btn btn-orange" href="/">Back to Texas studios</a> <a class="btn" href="/cities/">Browse all cities</a></p>
  <div class="split">
    <div>
      <h2>Popular cities</h2>
      <ul class="plain-list">{city_links}</ul>
    </div>
    <div>
      <h2>More from the site</h2>
      <ul class="plain-list">
        <li><a href="/blog/">Best photo studios by city</a></li>
        {'<li><a href="/categories/">Photo studio categories</a></li>' if self.categories_exist() else ""}
        <li><a href="/tools/">Free photo tools</a></li>
        <li><a href="/services/">Photo editing &amp; enhancement</a></li>
        <li><a href="/about/">About &amp; contact</a></li>
        <li><a href="/sitemap/">HTML sitemap</a></li>
      </ul>
    </div>
  </div>
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
            "Disallow: /api/\n"
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
            "STRIPE_PAYMENT_LINK_ENHANCE": str(self.config.get("STRIPE_PAYMENT_LINK_ENHANCE") or ""),
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
        shutil.copyfile(ROOT / "assets" / "lead-form.js", assets / "lead-form.js")
        shutil.copyfile(ROOT / "assets" / "blob-upload.js", assets / "blob-upload.js")
        shutil.copyfile(ROOT / "assets" / "directory.css", assets / "directory.css")
        shutil.copyfile(ROOT / "assets" / "directory.js", assets / "directory.js")
        city_images = ROOT / "assets" / "city-images"
        if city_images.is_dir():
            (DIST / "images" / "city").mkdir(parents=True, exist_ok=True)
            for image_file in sorted(city_images.glob("*.png")):
                shutil.copyfile(image_file, DIST / "images" / "city" / image_file.name)
        self.copy_category_images()
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
        self.build_categories()
        self.build_blog()
        self.build_tools()
        self.build_legal()
        self.build_claim_pages()
        self.build_html_sitemap()
        self.build_404()
        self.build_feeds()
        self.write_runtime_assets()
        self.write_geo_index()
        self.write_llms()
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
