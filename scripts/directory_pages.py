"""Studio, city-hub, and specialty pages for PhotoStudiosTexas.com.

Mixed into build.Site. Stdlib only. Everything shown comes from the listing
data and each studio's own public website info; see scripts/studio_info.py.
"""

from __future__ import annotations

import html
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import studio_info as si

ROOT = Path(__file__).resolve().parents[1]
ENRICH_PATH = ROOT / "data" / "website-enrichment.json"
CITY_IMG_DIR = ROOT / "assets" / "city-images"
MIN_SPECIALTY_PAGE = 3
TZ_LABEL = {
    "America/Chicago": "Central Time", "America/Denver": "Mountain Time",
    "America/New_York": "Eastern Time", "America/Detroit": "Eastern Time",
    "America/Phoenix": "Mountain Time (no DST)",
}
SOCIAL_LABEL = {"instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok",
                "youtube": "YouTube", "pinterest": "Pinterest", "x": "X", "linkedin": "LinkedIn"}
SOURCE_LABEL = {"listing categories": "its Google listing categories", "business name": "its name",
                "listing description": "its listing description", "customer review topics": "topics customers mention in reviews",
                "booking page": "its booking page link", "website": "its website"}


def esc(value) -> str:
    return "" if value is None else html.escape(str(value), quote=True)


def comma(value: int) -> str:
    return f"{value:,}"


def http_url(value):
    if value and str(value).strip().lower().startswith(("https://", "http://")):
        return str(value).strip()
    return None


def tel_href(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return ("tel:+" if phone.strip().startswith("+") else "tel:") + digits


def initials(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    if not parts:
        return "PS"
    return parts[0][:2].upper() if len(parts) == 1 else (parts[0][0] + parts[1][0]).upper()


def host_label(url: str) -> str:
    return re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])


def haversine(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 3958.7613 * math.asin(math.sqrt(min(1, a)))


def stars(rating: float) -> str:
    return f'<span class="stars" style="--r:{float(rating):.2f}" aria-hidden="true"></span>'


class DirectoryMixin:
    """Needs Site attributes: studios, cities, city_by_slug, nearby, config, services."""

    # ------------------------------------------------------------ preparation
    def prepare_directory(self) -> None:
        if getattr(self, "_prepared", False):
            return
        enrich = json.loads(ENRICH_PATH.read_text(encoding="utf-8")) if ENRICH_PATH.is_file() else {}
        self.info: dict[str, dict] = {}
        for studio in self.studios:
            site = si.clean_site_info(enrich.get(studio["place_id"]))
            week = si.parse_week(studio.get("hours"))
            specs = si.detect_specialties(studio, site)
            feats = si.detect_features(studio)
            self.info[studio["place_id"]] = {
                "site": site, "week": week, "specs": specs, "feats": feats,
                "hours_attr": si.hours_attr(week),
                "summary": si.summary(studio, specs, week, feats),
            }
        # specialty sub-pages: 3+ studios in the city and not every studio in it
        self.city_specs: dict[str, dict[str, list[dict]]] = {}
        self.spec_pages: dict[str, dict[str, list[dict]]] = {}
        for city in self.cities:
            by_spec: dict[str, list[dict]] = defaultdict(list)
            for studio in city.studios:
                for spec_id in self.info[studio["place_id"]]["specs"]:
                    by_spec[spec_id].append(studio)
            self.city_specs[city.slug] = by_spec
            slugs = {studio["slug"] for studio in city.studios}
            pages = {}
            for spec_id, members in by_spec.items():
                spec_slug = si.SPEC_BY_ID[spec_id][2]
                if MIN_SPECIALTY_PAGE <= len(members) < city.count and spec_slug not in slugs:
                    pages[spec_id] = members
            self.spec_pages[city.slug] = pages
        self._prepared = True

    # ------------------------------------------------------------ images
    def city_image(self, city) -> dict:
        slug = city.slug
        return {
            "src": f"/images/city/{slug}.png", "abs": self.abs_url(f"/images/city/{slug}.png"),
            "width": 1200, "height": 630,
            "alt": f"Photo studios in {city.name}, Texas: PhotoStudiosTexas.com directory",
            "generated": True,
        }

    def studio_image(self, studio: dict, city) -> dict:
        photo = http_url(studio.get("photo"))
        generated = self.city_image(city)
        if not photo:
            return {**generated, "fallback": generated["src"], "og": generated, "own": False}
        is_street = "streetview" in photo
        alt = (f"Street view of {studio['name']} in {studio['city']}, Texas" if is_street
               else f"{studio['name']}, photo studio in {studio['city']}, Texas")
        og = generated
        if not is_street:
            og = {"abs": photo.replace("=w800-h500-k-no", "=w1200-h630-k-no"), "width": 1200, "height": 630,
                  "alt": alt}
        return {"src": photo, "width": 800, "height": 500, "alt": alt, "fallback": generated["src"],
                "og": og, "own": True, "abs": photo}

    # ------------------------------------------------------------ chips
    def tag_ids(self, studio: dict) -> list[str]:
        info = self.info[studio["place_id"]]
        return list(info["specs"]) + [f"f-{key}" for key in info["feats"]]

    @staticmethod
    def tag_label(tag: str) -> str:
        if tag.startswith("f-"):
            return si.FEATURE_LABEL[tag[2:]]
        return si.SPEC_BY_ID[tag][1]

    def chips_html(self, studio: dict, limit: int = 6) -> str:
        tags = self.tag_ids(studio)
        if not tags:
            return ""
        shown = tags[:limit]
        parts = []
        for tag in shown:
            kind = "tag-feat" if tag.startswith("f-") else "tag-spec"
            parts.append(f'<span class="tag {kind}">{esc(self.tag_label(tag))}</span>')
        if len(tags) > limit:
            parts.append(f'<span class="tag tag-more">+{len(tags) - limit} more</span>')
        return f'<div class="tags">{"".join(parts)}</div>'

    # ------------------------------------------------------------ cards
    def studio_card(self, studio: dict, show_city: bool = True, index: int = 0) -> str:
        self.prepare_directory()
        info = self.info[studio["place_id"]]
        city_line = f'<p class="muted card-city">{esc(studio["city"])}, TX</p>' if show_city else ""
        category = f'<p class="muted card-cat">{esc(studio["category"])}</p>' if studio.get("category") else ""
        rating = studio.get("rating")
        count = studio.get("review_count") or 0
        if rating is not None:
            noun = "review" if count == 1 else "reviews"
            review_line = (f'<p class="rating">{stars(rating)} <b>{float(rating):.1f}</b> '
                           f'<span class="muted">({comma(int(count))} {noun})</span></p>') if count else \
                          f'<p class="rating">{stars(rating)} <b>{float(rating):.1f}</b></p>'
        else:
            review_line = '<p class="rating muted">No reviews yet</p>'
        attrs = {
            "data-name": studio["name"].lower(),
            "data-rating": f'{float(rating):.1f}' if rating is not None else "0",
            "data-reviews": str(int(count)),
            "data-tags": " ".join(self.tag_ids(studio)),
            "data-site": "1" if http_url(studio.get("website")) else "0",
            "data-has-hours": "1" if info["hours_attr"] else "0",
            "data-index": str(index),
        }
        if info["hours_attr"]:
            attrs["data-hours"] = info["hours_attr"]
            attrs["data-tz"] = studio.get("time_zone") or "America/Chicago"
        attr_html = " ".join(f'{key}="{esc(value)}"' for key, value in attrs.items())
        photo = self.photo_block_v2(studio)
        return f"""<a class="studio-card" href="{esc(studio["url_path"])}" {attr_html}>
  {photo}
  <div class="card-body">
    {self.badge(studio)}
    <h3>{esc(studio["name"])}</h3>
    {review_line}
    {city_line}
    {category}
    {self.chips_html(studio)}
    <p class="open-status" hidden></p>
  </div>
</a>"""

    def badge(self, studio: dict) -> str:
        if studio.get("business_status") == "CLOSED_TEMPORARILY":
            return '<p class="badge">Temporarily closed</p>'
        return ""

    def photo_block_v2(self, studio: dict) -> str:
        mark = f'<span aria-hidden="true">{esc(initials(studio["name"]))}</span>'
        photo = http_url(studio.get("photo"))
        image = ""
        if photo:
            kind = "Street view of" if "streetview" in photo else ""
            alt = f'{kind} {studio["name"]} in {studio["city"]}, Texas'.strip()
            image = (f'<img src="{esc(photo)}" alt="{esc(alt)}" width="800" height="500" loading="lazy" '
                     f'decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">')
        return f'<div class="photo">{mark}{image}</div>'

    # ------------------------------------------------------------ city hub
    def filter_bar(self, city) -> str:
        counts: Counter = Counter()
        for studio in city.studios:
            for tag in self.tag_ids(studio):
                counts[tag] += 1
        spec_tags = [t for t in counts if not t.startswith("f-")]
        feat_tags = [t for t in counts if t.startswith("f-")]
        spec_order = {item[0]: i for i, item in enumerate(si.SPECIALTIES)}
        feat_order = {f"f-{key}": i for i, (key, _l) in enumerate(si.FEATURES)}
        spec_tags.sort(key=lambda t: (-counts[t], spec_order[t]))
        feat_tags.sort(key=lambda t: feat_order[t])
        chips = "".join(
            f'<button type="button" class="fchip {"tag-feat" if t.startswith("f-") else "tag-spec"}" '
            f'data-tag="{esc(t)}" aria-pressed="false">{esc(self.tag_label(t))} <span class="fcount">{counts[t]}</span></button>'
            for t in spec_tags + feat_tags
        )
        chips_html = f'<div class="filter-chips" role="group" aria-label="Filter by what studios offer">{chips}</div>' if chips else ""
        return f"""<form class="filter-bar" id="filter-bar" role="search" aria-label="Filter {esc(city.name)} photo studios" hidden onsubmit="return false">
  <div class="filter-row">
    <label class="f-field f-search"><span>Search by name</span><input type="search" id="f-q" placeholder="Studio name" autocomplete="off"></label>
    <label class="f-field"><span>Minimum rating</span><select id="f-rating"><option value="0">Any rating</option><option value="3">3.0 and up</option><option value="4">4.0 and up</option><option value="4.5">4.5 and up</option><option value="4.8">4.8 and up</option></select></label>
    <label class="f-field"><span>Sort by</span><select id="f-sort"><option value="rating">Top rated</option><option value="reviews">Most reviews</option><option value="name">Name A–Z</option></select></label>
  </div>
  <div class="filter-row filter-toggles">
    <label class="toggle"><input type="checkbox" id="f-open"> Open now</label>
    <label class="toggle"><input type="checkbox" id="f-hours"> Has listed hours</label>
    <label class="toggle"><input type="checkbox" id="f-site"> Has website</label>
  </div>
  {chips_html}
  <div class="filter-foot"><span id="f-count" aria-live="polite"></span><button type="button" class="link-btn" id="f-reset">Reset filters</button></div>
</form>"""

    def specialty_links(self, city) -> str:
        pages = self.spec_pages.get(city.slug) or {}
        if not pages:
            return ""
        items = []
        for spec_id, members in sorted(pages.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            _id, label, slug, plural, *_ = si.SPEC_BY_ID[spec_id]
            items.append(
                f'<a class="chip" href="{city.path}{slug}/">{esc(plural)} <span class="muted">{len(members)}</span></a>')
        return f"""<section class="section" id="by-specialty">
  <h2>{esc(city.name)} photo studios by specialty</h2>
  <div class="chips">{"".join(items)}</div>
</section>"""

    def build_city(self, city) -> None:
        self.prepare_directory()
        studios = sorted(city.studios, key=lambda s: (
            s.get("rating") is None, -(s.get("rating") or 0), -(s.get("review_count") or 0),
            s["name"].lower(), s["place_id"]))
        cards = "".join(self.studio_card(s, show_city=False, index=i) for i, s in enumerate(studios))
        image = self.city_image(city)
        crumbs = [("Home", "/"), ("Texas", "/tx/"), (city.name, None)]
        noun = "photo studio" if city.count == 1 else "photo studios"
        temporary = sum(1 for s in studios if s.get("business_status") == "CLOSED_TEMPORARILY")
        closed_note = f' <span class="muted">{temporary} marked temporarily closed.</span>' if temporary else ""
        rated = [s for s in studios if s.get("rating") is not None and s.get("review_count")]
        facts = []
        if rated:
            top = rated[0]
            facts.append(f'Top rated: <a href="{esc(top["url_path"])}">{esc(top["name"])}</a> ({float(top["rating"]):.1f} from {comma(int(top["review_count"]))} reviews).')
        with_hours = sum(1 for s in studios if self.info[s["place_id"]]["hours_attr"])
        body = f"""<div class="wrap page-head head-split">
  <div class="head-copy">
    {self.crumbs(crumbs)}
    <p class="eyebrow"><a href="/tx/">Texas</a></p>
    <h1>Photo studios in {esc(city.name)}, Texas</h1>
    <hr class="rule">
    <p class="lede">{comma(city.count)} {noun} in {esc(city.name)}.{closed_note}</p>
    <p class="muted">{" ".join(facts)} {comma(with_hours)} of {comma(city.count)} list opening hours.</p>
  </div>
  <figure class="featured"><img src="{esc(image["src"])}" alt="{esc(image["alt"])}" width="1200" height="630" fetchpriority="high" decoding="async"></figure>
</div>
<div class="wrap">{self.city_blog_callout(city)}</div>
{self.specialty_links(city)and '<div class="wrap">' + self.specialty_links(city) + '</div>'}
<section class="section" id="studios"><div class="wrap">
  <h2 class="visually-hidden">All {esc(city.name)} photo studios</h2>
  {self.filter_bar(city)}
  <div class="card-grid" id="studio-grid" data-city="{esc(city.name)}">{cards}</div>
  <p class="no-results" id="no-results" hidden>No studios match those filters. <button type="button" class="link-btn" id="f-reset-2">Reset filters</button></p>
</div></section>
<div class="wrap">{self.nearby_html(city)}{self.cta()}</div>"""
        item_list = {
            "@context": "https://schema.org", "@type": "ItemList",
            "name": f"Photo studios in {city.name}, Texas", "numberOfItems": city.count,
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": s["name"], "url": self.abs_url(s["url_path"])}
                for i, s in enumerate(studios, start=1)],
        }
        page = {
            "@context": "https://schema.org", "@type": "CollectionPage",
            "name": f"Photo studios in {city.name}, Texas", "url": self.abs_url(city.path),
            "primaryImageOfPage": {"@type": "ImageObject", "url": image["abs"], "width": 1200, "height": 630,
                                   "caption": image["alt"]},
            "image": image["abs"],
        }
        title = f"Photo Studios in {city.name}, TX | PhotoStudiosTexas"
        description = (f"{comma(city.count)} photo studios in {city.name}, Texas, with ratings, reviews, hours, "
                       "specialties, and contact details. Filter to the exact studio you need.")
        self.write_page(city.path, self.layout(
            title, description, city.path, body, "",
            [self.breadcrumb_schema(crumbs, city.path), page, item_list], image=image, directory=True))
        for spec_id, members in (self.spec_pages.get(city.slug) or {}).items():
            self.build_specialty(city, spec_id, members)

    def build_specialty(self, city, spec_id: str, members: list[dict]) -> None:
        _id, label, slug, plural, *_ = si.SPEC_BY_ID[spec_id]
        path = f"{city.path}{slug}/"
        members = sorted(members, key=lambda s: (s.get("rating") is None, -(s.get("rating") or 0),
                                                 -(s.get("review_count") or 0), s["name"].lower()))
        cards = "".join(self.studio_card(s, show_city=False, index=i) for i, s in enumerate(members))
        image = self.city_image(city)
        crumbs = [("Home", "/"), ("Texas", "/tx/"), (city.name, city.path), (plural, None)]
        sibling = [
            f'<a class="chip" href="{city.path}{si.SPEC_BY_ID[o][2]}/">{esc(si.SPEC_BY_ID[o][3])} <span class="muted">{len(m)}</span></a>'
            for o, m in sorted(self.spec_pages[city.slug].items(), key=lambda kv: (-len(kv[1]), kv[0])) if o != spec_id]
        sibling_html = f'<section class="section"><h2>More ways to browse {esc(city.name)}</h2><div class="chips">{"".join(sibling)}</div></section>' if sibling else ""
        near = []
        for miles, other in self.nearby[city.slug]:
            if spec_id in self.spec_pages.get(other.slug, {}):
                near.append(f'<a class="chip" href="{other.path}{slug}/">{esc(plural)} in {esc(other.name)}</a>')
        near_html = f'<section class="section"><h2>{esc(plural)} in nearby cities</h2><div class="chips">{"".join(near[:8])}</div></section>' if near else ""
        rated = [s for s in members if s.get("rating") is not None and s.get("review_count")]
        top = ""
        if rated:
            t = rated[0]
            top = f' Top rated: <a href="{esc(t["url_path"])}">{esc(t["name"])}</a> ({float(t["rating"]):.1f} from {comma(int(t["review_count"]))} reviews).'
        body = f"""<div class="wrap page-head head-split">
  <div class="head-copy">
    {self.crumbs(crumbs)}
    <p class="eyebrow"><a href="{city.path}">{esc(city.name)}</a></p>
    <h1>{esc(plural)} in {esc(city.name)}, TX</h1>
    <hr class="rule">
    <p class="lede">{comma(len(members))} of {comma(city.count)} {esc(city.name)} photo studios list {esc(label.lower())} in their details.{top}</p>
    <p class="muted">Matched from each listing's Google categories, name, and website. <a href="{city.path}">See all {comma(city.count)} {esc(city.name)} studios</a>.</p>
  </div>
  <figure class="featured"><img src="{esc(image["src"])}" alt="{esc(image["alt"])}" width="1200" height="630" fetchpriority="high" decoding="async"></figure>
</div>
<section class="section"><div class="wrap"><div class="card-grid" id="studio-grid">{cards}</div></div></section>
<div class="wrap">{sibling_html}{near_html}<p><a href="{city.path}">All photo studios in {esc(city.name)}</a></p>{self.cta()}</div>"""
        item_list = {
            "@context": "https://schema.org", "@type": "ItemList",
            "name": f"{plural} in {city.name}, Texas", "numberOfItems": len(members),
            "itemListElement": [{"@type": "ListItem", "position": i, "name": s["name"], "url": self.abs_url(s["url_path"])}
                                for i, s in enumerate(members, start=1)],
        }
        title = f"{plural} in {city.name}, TX | PhotoStudiosTexas"
        description = f"{comma(len(members))} {city.name}, Texas photo studios that list {label.lower()}, with ratings, hours, and contact details."
        self.write_page(path, self.layout(title, description, path, body, "",
                                          [self.breadcrumb_schema(crumbs, path), item_list], image=image, directory=True))

    # ------------------------------------------------------------ studio page
    def hours_section(self, studio: dict, info: dict) -> str:
        week = info["week"]
        tz = studio.get("time_zone") or "America/Chicago"
        extra = ""
        if studio.get("other_hours"):
            for block in studio["other_hours"]:
                rows = "".join(
                    f'<tr><th scope="row">{esc(day)}</th><td>{esc(text)}</td></tr>'
                    for day, text in block["hours"].items())
                extra += (f'<h3>{esc(si.humanize(block["label"]))}</h3>'
                          f'<table class="hours-table hours-extra"><tbody>{rows}</tbody></table>')
        if not week and not extra:
            return ""
        status = ""
        if studio.get("business_status") == "CLOSED_TEMPORARILY":
            status = '<p class="badge">Temporarily closed on Google. Hours below are the regular schedule.</p>'
        table = ""
        if week:
            rows = []
            for day in si.DAY_ORDER + [d for d in week if d not in si.DAY_ORDER]:
                if day not in week:
                    continue
                idx = si.JS_DAY.get(day, "")
                closed = ' class="is-closed"' if week[day]["closed"] else ""
                rows.append(f'<tr data-day="{idx}"{closed}><th scope="row">{esc(day)}</th><td>{esc(week[day]["label"])}</td></tr>')
            attr = f' data-hours="{esc(info["hours_attr"])}" data-tz="{esc(tz)}"' if info["hours_attr"] else ""
            table = (f'<p class="open-status-line" id="open-status" hidden></p>'
                     f'<table class="hours-table"{attr}><caption class="visually-hidden">Opening hours</caption><tbody>{"".join(rows)}</tbody></table>')
        tzl = TZ_LABEL.get(tz, tz)
        return f"""<section class="section-block" id="hours"><h2>Hours</h2>{status}{table}{extra}
<p class="note">Times are in {esc(tzl)}. Hours come from the studio's Google listing and can change, so call before you go.</p></section>"""

    def services_section(self, studio: dict, city, info: dict) -> str:
        parts = []
        specs = info["specs"]
        pages = self.spec_pages.get(city.slug, {})
        if specs:
            chips = []
            for spec_id in specs:
                label = si.SPEC_BY_ID[spec_id][1]
                if spec_id in pages:
                    chips.append(f'<a class="tag tag-spec tag-link" href="{city.path}{si.SPEC_BY_ID[spec_id][2]}/">{esc(label)}</a>')
                else:
                    chips.append(f'<span class="tag tag-spec">{esc(label)}</span>')
            sources = []
            for srcs in specs.values():
                for s in srcs:
                    if s not in sources:
                        sources.append(s)
            based = si.join_list([SOURCE_LABEL.get(s, s) for s in sources])
            parts.append(f'<h3>Specialties (based on listing details)</h3><div class="tags tags-lg">{"".join(chips)}</div>'
                         f'<p class="note">Inferred from {esc(based)}. Not confirmed by the studio.</p>')
        subtypes = studio.get("subtypes") or []
        if subtypes:
            chips = "".join(f'<span class="tag">{esc(s)}</span>' for s in subtypes)
            parts.append(f'<h3>Listed as</h3><div class="tags tags-lg">{chips}</div>')
        website_desc = (info["site"] or {}).get("description")
        if website_desc:
            parts.append(f'<h3>From the studio\'s website</h3><blockquote class="site-quote">{esc(website_desc[:320].rstrip())}{"…" if len(website_desc) > 320 else ""}</blockquote>')
        if studio.get("description"):
            parts.append(f'<p>{esc(studio["description"])}</p>')
        return f'<section class="section-block" id="services"><h2>Services &amp; specialties</h2>{"".join(parts)}</section>'

    def amenities_section(self, studio: dict) -> str:
        groups = si.amenity_groups(studio)
        if not groups:
            return ""
        blocks = "".join(
            f'<div class="amenity"><h3>{esc(label)}</h3><ul>{"".join(f"<li>{esc(i)}</li>" for i in items)}</ul></div>'
            for label, items in groups)
        return f'<section class="section-block" id="amenities"><h2>Amenities &amp; details</h2><div class="amenity-grid">{blocks}</div><p class="note">From the studio\'s Google listing. Only features Google marks as available are shown.</p></section>'

    def reviews_section(self, studio: dict) -> str:
        rating, count = studio.get("rating"), studio.get("review_count") or 0
        link = http_url(studio.get("reviews_link")) or http_url(studio.get("maps_url"))
        if rating is None:
            body = '<p class="muted">This listing has no Google reviews yet.</p>'
            if link:
                body += f'<p><a class="btn btn-small" href="{esc(link)}" rel="noopener noreferrer" target="_blank">View on Google</a></p>'
            return f'<section class="section-block" id="reviews"><h2>Reviews</h2>{body}</section>'
        noun = "review" if count == 1 else "reviews"
        breakdown = studio.get("rating_breakdown")
        bars = ""
        if breakdown:
            total = sum(breakdown.values()) or 1
            rows = []
            for star in ("5", "4", "3", "2", "1"):
                n = breakdown.get(star, 0)
                pct = round(n * 100 / total)
                rows.append(f'<li><span class="bar-label">{star} star</span><span class="bar"><span style="width:{pct}%"></span></span><span class="bar-n">{comma(n)}</span></li>')
            bars = f'<ul class="rating-bars" aria-label="Rating breakdown">{"".join(rows)}</ul>'
        topics = ""
        if studio.get("review_topics"):
            topics = ('<h3>Customers mention</h3><div class="tags">'
                      + "".join(f'<span class="tag">{esc(t)}</span>' for t in studio["review_topics"])
                      + '</div><p class="note">Topics Google surfaces from customer reviews.</p>')
        read = ""
        if link:
            read = f'<p><a class="btn btn-small" href="{esc(link)}" rel="noopener noreferrer" target="_blank">Read reviews on Google</a></p>'
        return f"""<section class="section-block" id="reviews"><h2>Reviews</h2>
<div class="review-summary"><div class="review-score"><b>{float(rating):.1f}</b>{stars(rating)}<span class="muted">{comma(int(count))} Google {noun}</span></div>{bars}</div>
{topics}{read}
<p class="note">Rating and counts come from Google. Individual review text isn't copied here; read the full reviews on Google.</p></section>"""

    def map_section(self, studio: dict) -> str:
        lat, lon = studio["latitude"], studio["longitude"]
        d = 0.006
        bbox = f"{lon - d:.5f}%2C{lat - d:.5f}%2C{lon + d:.5f}%2C{lat + d:.5f}"
        src = f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&amp;layer=mapnik&amp;marker={lat:.6f}%2C{lon:.6f}"
        big = f"https://www.openstreetmap.org/?mlat={lat:.6f}&amp;mlon={lon:.6f}#map=16/{lat:.5f}/{lon:.5f}"
        directions = f"https://www.google.com/maps/dir/?api=1&amp;destination={lat:.6f},{lon:.6f}"
        addr = esc(studio.get("address") or "")
        return f"""<section class="section-block" id="map"><h2>Location</h2>
<p>{addr}</p>
<iframe class="map" title="Map of {esc(studio["name"])}" loading="lazy" referrerpolicy="no-referrer" src="{src}" width="600" height="320"></iframe>
<p class="note"><a href="{big}" rel="noopener noreferrer" target="_blank">View larger map</a> · <a href="{directions}" rel="noopener noreferrer" target="_blank">Directions on Google Maps</a> · Map data © OpenStreetMap contributors</p></section>"""

    def actions_html(self, studio: dict) -> str:
        info = self.info[studio["place_id"]]
        buttons = []
        book = http_url(studio.get("booking_link"))
        if book:
            buttons.append(f'<a class="btn btn-orange" href="{esc(book)}" rel="nofollow noopener noreferrer" target="_blank">Book online</a>')
        site = http_url(studio.get("website"))
        if site:
            buttons.append(f'<a class="btn" href="{esc(site)}" rel="noopener noreferrer" target="_blank">Website</a>')
        if studio.get("phone"):
            buttons.append(f'<a class="btn btn-ghost" href="{esc(tel_href(studio["phone"]))}">Call {esc(studio["phone"])}</a>')
        lat, lon = studio["latitude"], studio["longitude"]
        buttons.append(f'<a class="btn btn-ghost" href="https://www.google.com/maps/dir/?api=1&amp;destination={lat:.6f},{lon:.6f}" rel="noopener noreferrer" target="_blank">Directions</a>')
        social = (info["site"] or {}).get("social") or {}
        soc = "".join(
            f'<a href="{esc(url)}" rel="nofollow noopener noreferrer" target="_blank">{esc(SOCIAL_LABEL.get(k, k))}</a>'
            for k, url in social.items() if http_url(url))
        soc_html = f'<p class="social-links muted">Find them on: {soc}</p>' if soc else ""
        return f'<div class="actions">{"".join(buttons)}</div>{soc_html}'

    def facts_html(self, studio: dict) -> str:
        info = self.info[studio["place_id"]]
        rows = []
        if studio.get("address"):
            rows.append(("Address", esc(studio["address"])))
        if studio.get("neighborhood"):
            rows.append(("Area", esc(studio["neighborhood"])))
        if studio.get("phone"):
            rows.append(("Phone", f'<a href="{esc(tel_href(studio["phone"]))}">{esc(studio["phone"])}</a>'))
        site = http_url(studio.get("website"))
        if site:
            rows.append(("Website", f'<a href="{esc(site)}" rel="noopener noreferrer" target="_blank">{esc(host_label(site))}</a>'))
        book = http_url(studio.get("booking_link"))
        if book and book != site:
            rows.append(("Booking", f'<a href="{esc(book)}" rel="nofollow noopener noreferrer" target="_blank">{esc(host_label(book))}</a>'))
        maps = http_url(studio.get("maps_url"))
        if maps:
            label = "Google Maps"
            if studio.get("photos_count"):
                label += f" ({comma(studio['photos_count'])} photos)"
            rows.append(("Map", f'<a href="{esc(maps)}" rel="noopener noreferrer" target="_blank">{esc(label)}</a>'))
        if studio.get("located_in"):
            rows.append(("Located in", esc(studio["located_in"])))
        if studio.get("postal_code"):
            rows.append(("ZIP", esc(studio["postal_code"])))
        if studio.get("plus_code"):
            rows.append(("Plus code", esc(studio["plus_code"])))
        rows.append(("Google profile", "Verified" if studio.get("verified") else "Not verified"))
        return "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)

    def related_html(self, studio: dict, city, info: dict) -> str:
        blocks = []
        pages = self.spec_pages.get(city.slug, {})
        shown = 0
        for spec_id in info["specs"]:
            members = [s for s in self.city_specs[city.slug].get(spec_id, []) if s["place_id"] != studio["place_id"]]
            if not members or shown >= 2:
                continue
            shown += 1
            members.sort(key=lambda s: (s.get("rating") is None, -(s.get("rating") or 0), -(s.get("review_count") or 0), s["name"].lower()))
            label = si.SPEC_BY_ID[spec_id][1]
            items = "".join(
                f'<li><a href="{esc(s["url_path"])}">{esc(s["name"])}</a>'
                + (f' <span class="muted">★ {float(s["rating"]):.1f}</span>' if s.get("rating") is not None else "") + "</li>"
                for s in members[:6])
            more = ""
            if spec_id in pages:
                plural = si.SPEC_BY_ID[spec_id][3]
                more = f'<p><a href="{city.path}{si.SPEC_BY_ID[spec_id][2]}/">All {esc(plural.lower())} in {esc(city.name)} ({len(pages[spec_id])})</a></p>'
            blocks.append(f'<div><h3>More {esc(label.lower())} studios in {esc(city.name)}</h3><ul class="plain-list">{items}</ul>{more}</div>')
        near = sorted((s for s in city.studios if s["place_id"] != studio["place_id"]),
                      key=lambda s: haversine(studio["latitude"], studio["longitude"], s["latitude"], s["longitude"]))[:4]
        near_cards = ""
        if near:
            idx = {s["place_id"]: i for i, s in enumerate(city.studios)}
            near_cards = (f'<h3>Studios near {esc(studio["name"])}</h3><div class="card-grid card-grid-small">'
                          + "".join(self.studio_card(s, show_city=False, index=idx[s["place_id"]]) for s in near) + "</div>")
        links = (f'<p class="related-links"><a href="{city.path}">All photo studios in {esc(city.name)}</a> · '
                 f'<a href="/services/">Photo editing &amp; enhancement services</a> · <a href="/tx/">All Texas cities</a>'
                 f'{self.studio_blog_link(studio)}</p>')
        return f'<section class="section-block" id="related"><h2>Related studios</h2><div class="related-grid">{"".join(blocks)}</div>{near_cards}{links}</section>'

    def local_business(self, studio: dict) -> dict:
        info = self.info[studio["place_id"]]
        image = self.studio_image(studio, self.city_by_slug[studio["city_slug"]])
        city_img = self.city_image(self.city_by_slug[studio["city_slug"]])["abs"]
        images = [image["og"]["abs"], city_img] if image["own"] and "streetview" not in image["abs"] else [city_img]
        data = {
            "@context": "https://schema.org",
            "@type": ["LocalBusiness", "ProfessionalService"],
            "@id": self.abs_url(studio["url_path"]) + "#business",
            "name": studio["name"],
            "url": self.abs_url(studio["url_path"]),
            "address": {"@type": "PostalAddress", "addressLocality": studio["city"], "addressRegion": "TX", "addressCountry": "US"},
            "geo": {"@type": "GeoCoordinates", "latitude": studio["latitude"], "longitude": studio["longitude"]},
            "image": images,
            "description": info["summary"],
        }
        street = studio.get("street") or studio.get("address")
        if street:
            data["address"]["streetAddress"] = street
        if studio.get("postal_code"):
            data["address"]["postalCode"] = studio["postal_code"]
        if studio.get("phone"):
            data["telephone"] = studio["phone"]
        same = []
        site = http_url(studio.get("website"))
        if site:
            same.append(site)
        same += [u for u in ((info["site"] or {}).get("social") or {}).values() if http_url(u)]
        if same:
            data["sameAs"] = same
        maps = http_url(studio.get("maps_url"))
        if maps:
            data["hasMap"] = maps
        if studio.get("rating") is not None and studio.get("review_count"):
            data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": studio["rating"],
                                        "reviewCount": studio["review_count"], "bestRating": 5, "worstRating": 1}
        spec = si.schema_hours(info["week"])
        if spec:
            data["openingHoursSpecification"] = spec
        about = studio.get("about") or {}
        amenity = [{"@type": "LocationFeatureSpecification", "name": item, "value": True}
                   for group in ("Accessibility", "Parking", "Amenities", "Children") for item in about.get(group, [])]
        if amenity:
            data["amenityFeature"] = amenity
        pay = about.get("Payments")
        if pay:
            data["paymentAccepted"] = ", ".join(pay)
        book = http_url(studio.get("booking_link"))
        if book:
            data["potentialAction"] = {"@type": "ReserveAction", "target": {"@type": "EntryPoint", "urlTemplate": book},
                                        "result": {"@type": "Reservation", "name": "Book an appointment"}}
        if info["specs"]:
            data["knowsAbout"] = [si.SPEC_BY_ID[k][1] for k in info["specs"]]
        return data

    def studio_title(self, studio: dict, name_counts: Counter, name_zip_counts: Counter) -> str:
        name, city = studio["name"], studio["city"]
        if name_zip_counts[(name, studio.get("postal_code"))] > 1:
            return f"{name} | {studio['address'] or studio['slug']}"
        if name_counts[name] > 1 and studio.get("postal_code"):
            return f"{name} ({studio['postal_code']}) | {city}, TX Photo Studio"
        return f"{name} | {city}, TX Photo Studio"

    def build_studio(self, studio: dict, city, title: str) -> None:
        info = self.info[studio["place_id"]]
        image = self.studio_image(studio, city)
        others = sorted((o for o in city.studios if o["place_id"] != studio["place_id"]),
                        key=lambda o: (o["name"].lower(), o["place_id"]))
        other_links = "".join(f'<li><a href="{esc(o["url_path"])}">{esc(o["name"])}</a></li>' for o in others)
        other_section = (f'<section class="section"><h2>Other studios in {esc(city.name)}</h2><ul class="link-cols">{other_links}</ul></section>'
                         if other_links else "")
        category = studio.get("category") or "Photo studio"
        crumbs = [("Home", "/"), ("Texas", "/tx/"), (city.name, city.path), (studio["name"], None)]
        rating = studio.get("rating")
        rating_line = ""
        if rating is not None:
            count = studio.get("review_count") or 0
            noun = "review" if count == 1 else "reviews"
            tail = f' <a class="muted" href="#reviews">({comma(int(count))} {noun})</a>' if count else ""
            rating_line = f'<p class="rating rating-lg">{stars(rating)} <b>{float(rating):.1f}</b>{tail}</p>'
        onerr = f"this.onerror=null;this.src='{image['fallback']}';this.width=1200;this.height=630"
        hero = (f'<figure class="featured studio-featured"><img src="{esc(image["src"])}" alt="{esc(image["alt"])}" '
                f'width="{image["width"]}" height="{image["height"]}" fetchpriority="high" decoding="async" '
                f'referrerpolicy="no-referrer" onerror="{onerr}"></figure>')
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <div class="studio-layout">
    <div class="studio-main">
      {hero}
      {self.badge(studio)}
      <h1>{esc(studio["name"])}</h1>
      <hr class="rule">
      <p class="lede">{esc(category)} in <a href="{city.path}">{esc(city.name)}</a>, Texas.</p>
      {rating_line}
      {self.chips_html(studio, limit=8)}
      {self.actions_html(studio)}
      <p class="summary">{esc(info["summary"])}</p>
      {self.services_section(studio, city, info)}
      {self.hours_section(studio, info)}
      {self.amenities_section(studio)}
      {self.reviews_section(studio)}
      {self.map_section(studio)}
    </div>
    <aside class="panel studio-aside">
      <h2>Details</h2>
      <dl class="facts">{self.facts_html(studio)}</dl>
      <p class="note">Listing data comes from Google and the studio's website and may be out of date. <a href="/disclaimer/">About our data</a>.</p>
      <p class="claim-links"><strong>Own or manage this studio?</strong><br><a href="{esc(self.claim_href(studio["name"], studio["url_path"]))}" rel="nofollow">Claim or update this listing</a><br><a href="{esc(self.claim_href(studio["name"], studio["url_path"], True))}" rel="nofollow">Request removal</a></p>
    </aside>
  </div>
  {self.related_html(studio, city, info)}
  {self.cta()}
  {other_section}
  {self.nearby_html(city)}
  <p><a href="{city.path}">All photo studios in {esc(city.name)}</a></p>
</div>"""
        bits = [f"{studio['name']} is a {category.lower()} in {city.name}, Texas."]
        if studio.get("rating") is not None and studio.get("review_count"):
            bits.append(f"Rated {float(studio['rating']):.1f} from {int(studio['review_count'])} reviews.")
        labels = [si.SPEC_BY_ID[k][1] for k in list(info["specs"])[:3]]
        if labels:
            bits.append("Specialties: " + ", ".join(labels) + ".")
        if studio.get("address"):
            bits.append(studio["address"] + ".")
        self.write_page(studio["url_path"], self.layout(
            title, " ".join(bits), studio["url_path"], body, "",
            [self.breadcrumb_schema(crumbs, studio["url_path"]), self.local_business(studio)],
            image=image["og"] | {"src": image["og"].get("abs")}, directory=True))

    def build_studios(self) -> None:
        self.prepare_directory()
        for city in self.by_name:
            name_counts = Counter(s["name"] for s in city.studios)
            name_zip_counts = Counter((s["name"], s.get("postal_code")) for s in city.studios)
            self.build_city(city)
            for studio in city.studios:
                self.build_studio(studio, city, self.studio_title(studio, name_counts, name_zip_counts))
