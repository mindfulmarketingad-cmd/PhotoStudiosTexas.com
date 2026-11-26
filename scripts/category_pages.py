"""Statewide category hubs for PhotoStudiosTexas.com (/categories/ and /categories/<slug>/).

Mixed into build.Site, after DirectoryMixin. Stdlib only. A category page exists
only when at least one studio has evidence for it (data/category-evidence.json,
produced by scripts/generate_category_evidence.py from scripts/categories.py);
categories with no qualifying studio get no page and are never linked.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import categories as cat
import studio_info as si
from directory_pages import comma, esc

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_IMG_DIR = ROOT / "assets" / "category-images"
TOP_CITY_CHIPS = 30

INTRO = {
    "portraits": (
        "Portrait studios photograph individuals, couples, and groups, in a studio or on location. "
        "Every studio below has evidence it offers portrait photography: Google lists it as a portrait studio, "
        "\u201cportrait\u201d is in its name, or its own website describes portrait sessions."
    ),
    "family": (
        "Family photographers capture parents, children, and extended families in lifestyle, studio, or outdoor sessions. "
        "Every studio below has evidence it offers family photography: its name, its Google listing, or its own website "
        "mentions family portraits, sessions, or photos. \u201cFamily-owned\u201d does not count."
    ),
    "headshots": (
        "Headshot studios make professional profile, corporate, actor, and personal-brand portraits. "
        "Every studio below has evidence it offers headshots: the word appears in its name, its Google listing, "
        "or on its own website. A generic \u201cphotographer\u201d listing does not count."
    ),
    "weddings": (
        "Wedding photographers cover ceremonies, receptions, bridal portraits, engagements, and elopements. "
        "Every studio below has evidence it photographs weddings: Google lists it as a wedding photographer, "
        "or its name or own website describes wedding photography. Wedding venues, planners, and shops are not included."
    ),
    "prom": (
        "Prom photographers shoot formal portraits, couples, and group photos around prom and school dances. "
        "Every studio below has evidence it offers prom photography: prom is named on its own website or listing."
    ),
    "maternity": (
        "Maternity photographers photograph expecting parents during pregnancy, in the studio or outdoors. "
        "Every studio below has evidence it offers maternity or pregnancy photography: its name, its Google listing, "
        "or its own website says so. Maternity clothing stores and pregnancy centers are not included."
    ),
    "christmas": (
        "Christmas photographers offer holiday mini sessions, Santa portraits, and seasonal family photos. "
        "Every studio below has evidence it offers Christmas or holiday photo sessions: the service is named on its "
        "own website or listing. A holiday closure notice, a Christmas gallery label, or the word “holiday” alone does not count."
    ),
    "graduation": (
        "Graduation photographers shoot cap-and-gown, college, and senior graduation sessions. "
        "Every studio below has evidence it offers graduation photography: graduation, grads, or cap and gown appears "
        "on its own website or listing. Senior portraits count only when they are tied to graduation. Schools and gown shops are not included."
    ),
    "natural-light": (
        "Natural light photo studios shoot in daylight, window light, or a sunlit studio rather than relying only on strobes. "
        "Every studio below has evidence it is a natural light studio or offers natural light photography: the phrase appears "
        "in its name, its listing, or on its own website. A “natural look,” a testimonial, or a one-off mention of outdoor sunlight does not count. "
        "Rental studios that clearly advertise natural light are included."
    ),
    "prop-rental": (
        "These businesses rent photo props, backdrops, themed sets, or photography equipment. "
        "Every studio below has evidence it offers those items for rent — a prop or backdrop rental, a set rental, or a prop library for renters. "
        "A studio that only uses props in its own sessions is not listed here."
    ),
    "couples": (
        "Couples photographers shoot engagement, anniversary, proposal, and couples portrait sessions. "
        "Every studio below has evidence it offers couples, engagement, anniversary, or proposal photography on its listing or its own website. "
        "A testimonial about “the happy couple,” the phrase “a couple of,” or a husband-and-wife team bio does not count."
    ),
    "newborn": (
        "Newborn and baby photographers photograph infants in the first days and months, including posed newborn sessions and cake smashes. "
        "Every studio below has evidence it offers newborn or baby photography on its listing or its own website."
    ),
    "seniors": (
        "Senior photographers shoot high school senior portraits and class-of sessions. "
        "Every studio below has evidence it offers senior photography. Senior living communities and senior-citizen discounts do not count."
    ),
    "quinceanera": (
        "Quinceañera photographers cover the traditional celebration, portraits, and event. "
        "Every studio below has evidence it photographs quinceañeras. Venues, dress shops, and planners are not included."
    ),
    "boudoir": (
        "Boudoir photographers make intimate, usually in-studio portraits. "
        "Every studio below has evidence it offers boudoir photography on its listing or its own website."
    ),
    "commercial": (
        "Commercial and product photographers shoot brands, products, and business imagery. "
        "Every studio below has evidence it offers commercial or product photography. A generic photographer listing does not count."
    ),
    "real-estate": (
        "Real estate photographers photograph homes, listings, and architecture for agents and owners. "
        "Every studio below has evidence it offers real estate or architectural photography. Real estate agencies that do not photograph are not included."
    ),
    "events": (
        "Event photographers cover parties, corporate gatherings, and celebrations. "
        "Every studio below has evidence it offers event photography. Event venues and planners are not included."
    ),
    "pets": (
        "Pet photographers make portraits of dogs, cats, and other animals, in the studio or on location. "
        "Every studio below has evidence it offers pet, dog, or cat photography sessions. "
        "A “pets welcome” or pet-friendly studio, a pet store, or a groomer does not count."
    ),
    "passport": (
        "Passport and ID photo studios make official passport, visa, and identification photographs. "
        "Every studio below has evidence it offers passport or ID photos."
    ),
    "rental": (
        "These are studios you can rent by the hour or session, including self-service and backdrop spaces. "
        "Every studio below has evidence it rents studio space. A studio that only photographs clients is not listed here just because it has a room."
    ),
    "video": (
        "Video production studios offer videography, films, or commercial video alongside or instead of still photography. "
        "Every studio below has evidence it offers video production or videography."
    ),
    "drone": (
        "Aerial and drone photographers capture stills and video from the air. "
        "Every studio below has evidence it offers drone or aerial photography."
    ),
    "photo-booth": (
        "Photo booth providers bring a booth, 360 booth, or similar setup to events. "
        "Every studio below has evidence it offers a photo booth."
    ),
    "restoration": (
        "Photo restoration studios repair, retouch, or digitize damaged or old photographs. "
        "Every studio below has evidence it offers photo restoration. A metaphor about “restoring memories” does not count."
    ),
    "classes": (
        "These studios teach photography classes, workshops, or courses. "
        "Every studio below has evidence it offers classes or workshops for photographers or the public."
    ),
    "models": (
        "Model portfolio photographers create comp cards and modeling portfolios. "
        "Every studio below has evidence it offers model portfolio photography."
    ),
}
SOURCE_GROUP = {
    "listing categories": "Google category", "business name": "name", "listing description": "listing description",
    "booking page": "booking page", "manual review": "manual review",
}
SOURCE_PHRASE = {
    "Google category": "a Google listing category",
    "name": "the studio's business name",
    "listing description": "its Google listing description",
    "booking page": "its booking page",
    "manual review": "a manual review",
    "website": "the studio's own website",
}


def _group(source: str) -> str:
    return SOURCE_GROUP.get(source, "website")


class CategoryMixin:
    # ------------------------------------------------------------ data
    def prepare_categories(self) -> None:
        if getattr(self, "_cats_ready", False):
            return
        self.prepare_directory()
        self.categories: list[dict] = []
        for cid, slug, label, h1, noun in cat.CATEGORIES:
            members = [s for s in self.studios if cid in self.cat_ev.get(s["place_id"], {})]
            if not members:
                continue  # nothing qualifies: no page, no links
            members.sort(key=lambda s: (s.get("rating") is None, -(s.get("rating") or 0),
                                        -(s.get("review_count") or 0), s["name"].lower(), s["place_id"]))
            per_city = Counter(s["city_slug"] for s in members)
            groups = Counter()
            for s in members:
                groups[_group(self.cat_ev[s["place_id"]][cid][0]["source"])] += 1
            self.categories.append({
                "id": cid, "slug": slug, "label": label, "h1": h1, "noun": noun,
                "path": f"/categories/{slug}/", "members": members, "per_city": per_city, "groups": groups,
            })
        self.cat_by_id = {c["id"]: c for c in self.categories}
        self._cats_ready = True

    def categories_exist(self) -> bool:
        self.prepare_categories()
        return bool(self.categories)

    def copy_category_images(self) -> None:
        self.prepare_categories()
        out = ROOT / "dist" / "images" / "category"
        names = ["categories"] + [c["slug"] for c in self.categories] if self.categories else []
        for name in names:
            src = CATEGORY_IMG_DIR / f"{name}.png"
            if src.is_file():
                out.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, out / src.name)

    def why_listed(self, studio: dict, cid: str) -> str:
        items = self.cat_ev.get(studio["place_id"], {}).get(cid) or []
        names = []
        for item in items:
            g = _group(item["source"])
            if g not in names:
                names.append(g)
        return ", ".join(names)

    def category_image(self, slug: str) -> dict:
        src = f"/images/category/{slug}.png"
        return {"src": src, "abs": self.abs_url(src), "width": 1200, "height": 630,
                "alt": f"{slug.replace('-', ' ').title()} in Texas: PhotoStudiosTexas.com directory", "generated": True}

    # ------------------------------------------------------------ links used elsewhere
    def category_home_section(self, heading: str = "Browse by category") -> str:
        self.prepare_categories()
        if not self.categories:
            return ""
        chips = "".join(
            f'<a class="chip" href="{c["path"]}">{esc(c["h1"])} <span class="muted">{comma(len(c["members"]))}</span></a>'
            for c in self.categories)
        return f"""<section class="section"><div class="wrap">
  <div class="section-head"><h2>{esc(heading)}</h2><a href="/categories/">All categories</a></div>
  <div class="chips">{chips}</div>
</div></section>"""

    def city_category_links(self, city) -> str:
        self.prepare_categories()
        items = []
        for c in self.categories:
            n = c["per_city"].get(city.slug, 0)
            if n:
                items.append(f'<a class="chip" href="{c["path"]}">{esc(c["h1"])} <span class="muted">{n} in {esc(city.name)}</span></a>')
        if not items:
            return ""
        return f"""<section class="section" id="by-category">
  <h2>{esc(city.name)} studios in statewide categories</h2>
  <div class="chips">{"".join(items)}</div>
</section>"""

    def studio_category_links(self, studio: dict) -> str:
        self.prepare_categories()
        mine = self.cat_ev.get(studio["place_id"], {})
        links = [f'<a href="{c["path"]}">{esc(c["h1"])}</a>' for c in self.categories if c["id"] in mine]
        if not links:
            return ""
        return f'<p class="related-links">Also listed in: {" · ".join(links)}</p>'

    def statewide_link(self, spec_id: str) -> str:
        self.prepare_categories()
        c = self.cat_by_id.get(spec_id)
        if not c:
            return ""
        return f' <a href="{c["path"]}">See all {esc(c["noun"])} in Texas ({comma(len(c["members"]))})</a>.'

    def category_sitemap_entries(self) -> list[tuple[str, str]]:
        self.prepare_categories()
        if not self.categories:
            return []
        return [("/categories/", "Categories")] + [(c["path"], c["h1"]) for c in self.categories]

    def category_llms_lines(self) -> list[str]:
        self.prepare_categories()
        if not self.categories:
            return []
        lines = ["", "## Statewide categories",
                 "Each studio is listed only with evidence it offers the service (Google category, business name, or its own website).",
                 f"- [Photo studio categories]({self.abs_url('/categories/')})"]
        for c in self.categories:
            lines.append(f"- [{c['h1']}]({self.abs_url(c['path'])}): {len(c['members'])} studios in {len(c['per_city'])} cities")
        return lines

    # ------------------------------------------------------------ filter bar
    def category_filter_bar(self, c: dict) -> str:
        counts: Counter = Counter()
        for studio in c["members"]:
            for tag in self.tag_ids(studio):
                counts[tag] += 1
        spec_tags = [t for t in counts if not t.startswith("f-") and t != c["id"]]
        feat_tags = [t for t in counts if t.startswith("f-")]
        spec_order = {item[0]: i for i, item in enumerate(si.SPECIALTIES)}
        feat_order = {f"f-{key}": i for i, (key, _l) in enumerate(si.FEATURES)}
        spec_tags.sort(key=lambda t: (-counts[t], spec_order[t]))
        feat_tags.sort(key=lambda t: feat_order[t])
        chips = "".join(
            f'<button type="button" class="fchip {"tag-feat" if t.startswith("f-") else "tag-spec"}" '
            f'data-tag="{esc(t)}" aria-pressed="false">{esc(self.tag_label(t))} <span class="fcount">{counts[t]}</span></button>'
            for t in spec_tags + feat_tags)
        city_names = {s["city_slug"]: s["city"] for s in c["members"]}
        city_opts = "".join(
            f'<option value="{esc(slug)}">{esc(city_names[slug])} ({n})</option>'
            for slug, n in sorted(c["per_city"].items(), key=lambda kv: city_names[kv[0]].lower()))
        chips_html = f'<div class="filter-chips" role="group" aria-label="Filter by what studios offer">{chips}</div>' if chips else ""
        return f"""<form class="filter-bar" id="filter-bar" role="search" aria-label="Filter {esc(c["noun"])} in Texas" hidden onsubmit="return false">
  <div class="filter-row">
    <label class="f-field f-search"><span>Search by name</span><input type="search" id="f-q" placeholder="Studio name" autocomplete="off"></label>
    <label class="f-field"><span>City</span><select id="f-city"><option value="">All cities</option>{city_opts}</select></label>
    <label class="f-field"><span>Minimum rating</span><select id="f-rating"><option value="0">Any rating</option><option value="3">3.0 and up</option><option value="4">4.0 and up</option><option value="4.5">4.5 and up</option><option value="4.8">4.8 and up</option></select></label>
    <label class="f-field"><span>Sort by</span><select id="f-sort"><option value="rating">Top rated</option><option value="reviews">Most reviews</option><option value="city">City A–Z</option><option value="name">Name A–Z</option></select></label>
  </div>
  <div class="filter-row filter-toggles">
    <label class="toggle"><input type="checkbox" id="f-open"> Open now</label>
    <label class="toggle"><input type="checkbox" id="f-hours"> Has listed hours</label>
  </div>
  {chips_html}
  <div class="filter-foot"><span id="f-count" aria-live="polite"></span><button type="button" class="link-btn" id="f-reset">Reset filters</button></div>
</form>"""

    # ------------------------------------------------------------ pages
    def build_categories(self) -> None:
        self.prepare_categories()
        if not self.categories:
            return
        for c in self.categories:
            self.build_category(c)
        self.build_categories_hub()

    def _city_chips(self, c: dict) -> str:
        city_by_slug = self.city_by_slug
        rows = sorted(c["per_city"].items(), key=lambda kv: (-kv[1], city_by_slug[kv[0]].name.lower()))
        spec_pages = {slug: self.spec_pages.get(slug, {}) for slug, _n in rows}

        def chip(slug: str, n: int) -> str:
            city = city_by_slug[slug]
            href = city.path
            if c["id"] in spec_pages[slug]:
                href = f'{city.path}{si.SPEC_BY_ID[c["id"]][2]}/'
            return f'<a class="chip" href="{href}">{esc(city.name)} <span class="muted">{n}</span></a>'

        top = "".join(chip(s, n) for s, n in rows[:TOP_CITY_CHIPS])
        rest = rows[TOP_CITY_CHIPS:]
        more = ""
        if rest:
            more = (f'<details class="more-chips"><summary>Show {len(rest)} more cities</summary>'
                    f'<div class="chips">{"".join(chip(s, n) for s, n in rest)}</div></details>')
        return f'<div class="chips">{top}</div>{more}'

    def build_category(self, c: dict) -> None:
        members = c["members"]
        path = c["path"]
        cid = c["id"]
        image = self.category_image(c["slug"])
        crumbs = [("Home", "/"), ("Categories", "/categories/"), (c["h1"], None)]
        cards = "".join(
            self.studio_card(s, show_city=True, index=i, why=self.why_listed(s, cid))
            for i, s in enumerate(members))
        n, cities = len(members), len(c["per_city"])
        rated = [s for s in members if s.get("rating") is not None and s.get("review_count")]
        top = ""
        if rated:
            t = rated[0]
            top = (f' Top rated: <a href="{esc(t["url_path"])}">{esc(t["name"])}</a> in {esc(t["city"])} '
                   f'({float(t["rating"]):.1f} from {comma(int(t["review_count"]))} reviews).')
        sibs = "".join(
            f'<a class="chip" href="{o["path"]}">{esc(o["h1"])} <span class="muted">{comma(len(o["members"]))}</span></a>'
            for o in self.categories if o["id"] != cid)
        sib_html = f'<section class="section"><h2>More ways to browse Texas photo studios</h2><div class="chips">{sibs}<a class="chip" href="/cities/">All cities</a><a class="chip" href="/tx/">Texas hub</a></div></section>' if sibs else \
            '<section class="section"><h2>More ways to browse Texas photo studios</h2><div class="chips"><a class="chip" href="/cities/">All cities</a><a class="chip" href="/tx/">Texas hub</a></div></section>'
        groups = c["groups"]
        basis = "; ".join(f"{comma(v)} by {SOURCE_PHRASE[k]}" for k, v in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0])))
        noun_cap = c["noun"]
        method = f"""<section class="section" id="how-we-choose">
  <h2>How these studios were chosen</h2>
  <p>A studio appears here only if there is real evidence it offers this service. We check its Google listing categories, its business name, its listing description, and the text on its own website (title, descriptions, headings, menu links, and service pages). A generic &ldquo;photographer&rdquo; listing with no mention of the service is not enough, and phrases that merely look similar (for example &ldquo;family-owned&rdquo; or &ldquo;wedding venue&rdquo;) do not count.</p>
  <p class="muted">Strongest evidence for the {comma(n)} {esc(noun_cap)} listed: {esc(basis)}. Each card shows the evidence type. Details can change, so confirm services with the studio before booking.</p>
</section>"""
        body = f"""<div class="wrap page-head head-split">
  <div class="head-copy">
    {self.crumbs(crumbs)}
    <p class="eyebrow"><a href="/categories/">Category</a></p>
    <h1>{esc(c["h1"])}</h1>
    <hr class="rule">
    <p class="lede">{comma(n)} {esc(noun_cap)} across {comma(cities)} Texas {"city" if cities == 1 else "cities"}.{top}</p>
    <p class="muted">{esc(INTRO[cid])}</p>
  </div>
  <figure class="featured"><img src="{esc(image["src"])}" alt="{esc(image["alt"])}" width="1200" height="630" fetchpriority="high" decoding="async"></figure>
</div>
<section class="section" id="by-city"><div class="wrap">
  <h2>{esc(c["h1"].replace(" in Texas", ""))} by city</h2>
  {self._city_chips(c)}
</div></section>
<section class="section" id="studios"><div class="wrap">
  <h2 class="visually-hidden">All {esc(noun_cap)} in Texas</h2>
  {self.category_filter_bar(c)}
  <div class="card-grid" id="studio-grid" data-category="{esc(cid)}">{cards}</div>
  <p class="no-results" id="no-results" hidden>No studios match those filters. <button type="button" class="link-btn" id="f-reset-2">Reset filters</button></p>
</div></section>
<div class="wrap">{method}{sib_html}{self.cta()}</div>"""
        item_list = {
            "@context": "https://schema.org", "@type": "ItemList",
            "name": c["h1"], "numberOfItems": n,
            "itemListElement": [{"@type": "ListItem", "position": i, "name": s["name"], "url": self.abs_url(s["url_path"])}
                                for i, s in enumerate(members, start=1)],
        }
        page = {
            "@context": "https://schema.org", "@type": "CollectionPage",
            "name": c["h1"], "url": self.abs_url(path),
            "primaryImageOfPage": {"@type": "ImageObject", "url": image["abs"], "width": 1200, "height": 630, "caption": image["alt"]},
            "image": image["abs"],
        }
        title = f'{c["h1"]} | PhotoStudiosTexas'
        description = (f'{comma(n)} {c["noun"]} in {comma(cities)} Texas cities, each with real evidence it offers the service. '
                       "Compare ratings, reviews, and hours, then request a booking.")
        self.write_page(path, self.layout(title, description, path, body, "categories",
                                          [self.breadcrumb_schema(crumbs, path), page, item_list], image=image, directory=True))

    def build_categories_hub(self) -> None:
        path = "/categories/"
        image = self.category_image("categories")
        crumbs = [("Home", "/"), ("Categories", None)]
        tiles = []
        for c in self.categories:
            img = self.category_image(c["slug"])
            tiles.append(
                f'<a class="category-tile" href="{c["path"]}">'
                f'<img src="{esc(img["src"])}" alt="{esc(c["h1"])}" width="1200" height="630" loading="lazy" decoding="async">'
                f'<h2>{esc(c["h1"])}</h2></a>')
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <p class="eyebrow">Browse by service</p>
  <h1>Photo Studio Categories in Texas</h1>
  <hr class="rule">
</div>
<section class="section"><div class="wrap"><div class="category-tile-grid">{"".join(tiles)}</div></div></section>
<div class="wrap"><section class="section"><h2>More ways to browse</h2><div class="chips"><a class="chip" href="/cities/">All cities</a><a class="chip" href="/tx/">Texas hub</a><a class="chip" href="/blog/">City guides</a></div></section>{self.cta()}</div>"""
        item_list = {
            "@context": "https://schema.org", "@type": "ItemList",
            "name": "Photo studio categories in Texas", "numberOfItems": len(self.categories),
            "itemListElement": [{"@type": "ListItem", "position": i, "name": c["h1"], "url": self.abs_url(c["path"])}
                                for i, c in enumerate(self.categories, start=1)],
        }
        page = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Photo Studio Categories in Texas",
                "url": self.abs_url(path),
                "primaryImageOfPage": {"@type": "ImageObject", "url": image["abs"], "width": 1200, "height": 630, "caption": image["alt"]},
                "image": image["abs"]}
        description = (f"Browse Texas photo studios by service: {', '.join(c['label'].lower() for c in self.categories)}. "
                       "Every studio listed has real evidence it offers the service.")
        self.write_page(path, self.layout("Photo Studio Categories in Texas | PhotoStudiosTexas", description, path, body,
                                          "categories", [self.breadcrumb_schema(crumbs, path), page, item_list], image=image))
