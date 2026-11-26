"""Blog, free tools, homepage geolocation data, and llms.txt for PhotoStudiosTexas.com.

Mixed into build.Site together with DirectoryMixin. Stdlib only. Everything in
the blog comes from data/studios.json; nothing is invented.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from collections import Counter
from pathlib import Path

import studio_info as si
from directory_pages import comma, esc, haversine, http_url, stars

ROOT = Path(__file__).resolve().parents[1]
TOOLS_SRC = ROOT / "assets" / "tools"
BLOG_MIN_STUDIOS = 10
BLOG_TOP_N = 10
PRIOR_REVIEWS = 10  # Bayesian prior weight used in the ranking
WEEKEND = ("Saturday", "Sunday")

TOOLS = [
    {
        "slug": "image-background-remover",
        "name": "Image Background Remover",
        "short": "Background Remover",
        "blurb": "Cut out the subject and download a transparent PNG. The AI model runs in your browser.",
        "title": "Free Image Background Remover (No Upload, No Sign-Up)",
        "description": "Remove the background from any photo for free. The AI runs in your browser, so the image never leaves your device. Download a transparent PNG or add a solid color.",
        "script": "bg-remover.js",
        "module": True,
        "steps": [
            "Choose a JPG, PNG, or WebP photo, or drop it on the box.",
            "Pick a model: People & portraits for headshots and selfies, or Products, pets & objects for everything else.",
            "Wait while the model loads the first time (it is cached after that) and cuts out the subject.",
            "Keep the transparent background or pick a color, then download the PNG.",
        ],
        "faq": [
            ("Is the background remover really free?", "Yes. There is no sign-up, watermark, or limit. The model downloads once into your browser and runs on your own device."),
            ("Are my photos uploaded?", "No. The photo is read and processed inside your browser tab. Only the open-source AI model files (Apache-2.0 licensed) are downloaded, from Hugging Face."),
            ("Which model should I use?", "People & portraits (MODNet, about 7 MB) is tuned for people and keeps hair edges. Products, pets & objects (U²-Netp, about 5 MB) finds the main subject in any photo. If one result looks off, switch models and it reruns."),
            ("Why is the first run slow?", "The browser has to download the model the first time. Later runs reuse the cached copy. Phones and older laptops take longer than desktops."),
            ("Can you clean up the edges for me?", "Yes. For hair, glass, or tricky edges, our photo editing service does hand-finished cutouts and background swaps."),
        ],
    },
    {
        "slug": "image-resizer",
        "name": "Image Resizer",
        "short": "Resizer",
        "blurb": "Resize to exact pixels or a percentage, with presets for Instagram, headshots, and web.",
        "title": "Free Image Resizer: Resize Photos to Exact Pixels",
        "description": "Resize a photo to exact pixel dimensions or a percentage, with social and web presets. Free, private, and done in your browser.",
        "script": "tools.js",
        "steps": [
            "Choose a photo.",
            "Type a width or height, pick a percentage, or tap a preset. Keep aspect ratio is on by default.",
            "Choose JPG, PNG, or WebP and download the resized image.",
        ],
        "faq": [
            ("Does resizing lower quality?", "Making an image smaller keeps it sharp. Making it much larger than the original adds softness, because the extra pixels are estimated. For enlargements, use the photo enhancement service."),
            ("Are my photos uploaded?", "No. Resizing runs on a canvas in your browser."),
            ("What size should a headshot be?", "1080 × 1350 (4:5) works for most social profiles, and 1200 × 1200 is a safe square for LinkedIn and company sites."),
        ],
    },
    {
        "slug": "image-compressor",
        "name": "Image Compressor",
        "short": "Compressor",
        "blurb": "Shrink JPG, PNG, and WebP file size with a quality slider and a live size readout.",
        "title": "Free Image Compressor: Reduce JPG, PNG & WebP File Size",
        "description": "Compress photos for email and websites. Pick a quality, see the new file size instantly, and download. Free and private, nothing is uploaded.",
        "script": "tools.js",
        "steps": [
            "Choose a photo.",
            "Pick JPG or WebP and move the quality slider. The new size and savings update as you go.",
            "Optionally cap the longest side, then download.",
        ],
        "faq": [
            ("What quality setting should I use?", "75 to 85 looks the same as the original for most photos and cuts the file size a lot. Go lower only for thumbnails."),
            ("Why is my PNG bigger after compressing?", "PNG is lossless. Converting a photo to JPG or WebP is what makes it small. Keep PNG only for graphics that need transparency."),
            ("Are my photos uploaded?", "No. Compression happens in your browser."),
        ],
    },
    {
        "slug": "image-cropper",
        "name": "Image Cropper",
        "short": "Cropper",
        "blurb": "Drag to crop freehand or lock to 1:1, 4:5, 3:2, or 16:9.",
        "title": "Free Image Cropper: Crop Photos to 1:1, 4:5, 16:9 & More",
        "description": "Crop a photo by dragging a box, with square, portrait, and widescreen presets. Free, private, and runs in your browser.",
        "script": "tools.js",
        "steps": [
            "Choose a photo.",
            "Pick an aspect ratio, or Free for any shape.",
            "Drag on the photo to draw the crop. Drag inside the box to move it.",
            "Download the cropped image.",
        ],
        "faq": [
            ("Which aspect ratio is best for Instagram?", "4:5 portrait fills the most space in the feed. 1:1 is the classic square."),
            ("Does cropping reduce quality?", "No. The kept pixels are copied as they are. The image just has fewer of them."),
            ("Are my photos uploaded?", "No. Cropping happens in your browser."),
        ],
    },
    {
        "slug": "image-format-converter",
        "name": "Image Format Converter",
        "short": "Format Converter",
        "blurb": "Convert between JPG, PNG, and WebP. Pick a fill color for transparent areas.",
        "title": "Free Image Converter: JPG to PNG, PNG to JPG, WebP to JPG",
        "description": "Convert images between JPG, PNG, and WebP for free. Choose a background color for transparency. Nothing is uploaded.",
        "script": "tools.js",
        "steps": [
            "Choose one or more images (JPG, PNG, WebP, GIF, or BMP).",
            "Pick the format you need. For JPG, pick a color to fill transparent areas.",
            "Download each converted file.",
        ],
        "faq": [
            ("Can it convert HEIC from an iPhone?", "Only if your browser can open HEIC. Safari can; Chrome and Firefox usually cannot. On iPhone, sharing the photo usually converts it to JPG."),
            ("Which format should I use?", "JPG for photos, PNG for graphics or transparency, WebP for the smallest files on websites."),
            ("Are my photos uploaded?", "No. Conversion happens in your browser."),
        ],
    },
]
TOOL_BY_SLUG = {tool["slug"]: tool for tool in TOOLS}


class ExtrasMixin:
    """Needs Site attributes from build.Site and DirectoryMixin."""

    # ------------------------------------------------------------ ranking
    def _state_mean(self) -> float:
        if not hasattr(self, "_mean_rating"):
            rated = [s for s in self.studios if s.get("rating") is not None and s.get("review_count")]
            total = sum(int(s["review_count"]) for s in rated)
            self._mean_rating = sum(float(s["rating"]) * int(s["review_count"]) for s in rated) / total
        return self._mean_rating

    def rank_score(self, studio: dict) -> float:
        rating, count = studio.get("rating"), int(studio.get("review_count") or 0)
        if rating is None or not count:
            return 0.0
        mean = self._state_mean()
        return (count * float(rating) + PRIOR_REVIEWS * mean) / (count + PRIOR_REVIEWS)

    def ranked(self, studios: list[dict]) -> list[dict]:
        eligible = [s for s in studios if s.get("business_status") == "OPERATIONAL"
                    and s.get("rating") is not None and s.get("review_count")]
        eligible.sort(key=lambda s: (-self.rank_score(s), -int(s["review_count"]), s["name"].lower(), s["place_id"]))
        return eligible

    # ------------------------------------------------------------ blog data
    @property
    def blog_cities(self) -> list:
        return [city for city in self.by_count if city.count >= BLOG_MIN_STUDIOS and self.ranked(city.studios)]

    def blog_path(self, city) -> str:
        return f"/blog/best-photo-studios-in-{city.slug}-tx/"

    def blog_n(self, city) -> int:
        return min(BLOG_TOP_N, len(self.ranked(city.studios)))

    def blog_title(self, city) -> str:
        return f"The {self.blog_n(city)} Best Photo Studios in {city.name} Texas"

    def has_blog(self, city) -> bool:
        return city.count >= BLOG_MIN_STUDIOS and bool(self.ranked(city.studios))

    def city_blog_callout(self, city) -> str:
        if not self.has_blog(city):
            return ""
        return (f'<p class="blog-callout"><span class="eyebrow">Ranked guide</span> '
                f'<a href="{self.blog_path(city)}">{esc(self.blog_title(city))}</a> '
                f'<span class="muted">ranked by rating and review count</span></p>')

    def studio_blog_link(self, studio: dict) -> str:
        city = self.city_by_slug[studio["city_slug"]]
        if not self.has_blog(city):
            return ""
        return f' · <a href="{self.blog_path(city)}">{esc(self.blog_title(city))}</a>'

    def _blog_date(self) -> str:
        return dt.date.today().isoformat()

    def _fmt_date(self, iso: str) -> str:
        day = dt.date.fromisoformat(iso)
        return f"{day.strftime('%B')} {day.day}, {day.year}"

    def _weekend_open(self, studio: dict) -> bool:
        week = self.info[studio["place_id"]]["week"]
        return any(week.get(d, {}).get("spans") for d in WEEKEND)

    # ------------------------------------------------------------ blog post
    def blog_item(self, rank: int, studio: dict, city) -> str:
        info = self.info[studio["place_id"]]
        rating, count = float(studio["rating"]), int(studio["review_count"])
        noun = "review" if count == 1 else "reviews"
        photo = http_url(studio.get("photo"))
        fallback = self.city_image(city)["src"]
        img_src = photo or fallback
        alt = f"{studio['name']}, photo studio in {city.name}, Texas"
        onerr = f"this.onerror=null;this.src='{fallback}'"
        facts = []
        hours = si.hours_summary(info["week"]) if info["week"] else ""
        if hours:
            facts.append(f"<dt>Hours</dt><dd>{esc(hours)}</dd>")
        if studio.get("address"):
            facts.append(f"<dt>Address</dt><dd>{esc(studio['address'])}</dd>")
        if studio.get("phone"):
            facts.append(f'<dt>Phone</dt><dd><a href="tel:{esc(studio["phone"].replace(" ", "").replace("-", ""))}">{esc(studio["phone"])}</a></dd>')
        breakdown = studio.get("rating_breakdown") or {}
        five = int(breakdown.get("5") or 0)
        if count and five:
            facts.append(f"<dt>5-star share</dt><dd>{round(100 * five / count)}% of {comma(count)} reviews</dd>")
        site = http_url(studio.get("website"))
        links = [f'<a class="btn btn-orange" href="{esc(studio["url_path"])}">View {esc(studio["name"])} details</a>']
        if site:
            links.append(f'<a class="btn" href="{esc(site)}" rel="nofollow noopener noreferrer" target="_blank">Website</a>')
        if studio.get("reviews_link"):
            links.append(f'<a class="btn" href="{esc(studio["reviews_link"])}" rel="nofollow noopener noreferrer" target="_blank">Google reviews</a>')
        return f"""<article class="blog-item" id="rank-{rank}">
  <a class="blog-item-photo" href="{esc(studio["url_path"])}"><img src="{esc(img_src)}" alt="{esc(alt)}" width="800" height="500" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="{onerr}"></a>
  <div class="blog-item-body">
    <h2><span class="rank">{rank}</span> <a href="{esc(studio["url_path"])}">{esc(studio["name"])}</a></h2>
    <p class="rating">{stars(rating)} <b>{rating:.1f}</b> <span class="muted">({comma(count)} Google {noun}) · score {self.rank_score(studio):.2f}</span></p>
    {self.chips_html(studio, limit=6)}
    <p>{esc(info["summary"])}</p>
    <dl class="facts blog-facts">{"".join(facts)}</dl>
    <div class="blog-item-actions">{"".join(links)}</div>
  </div>
</article>"""

    def build_blog_post(self, city, others: list) -> None:
        path = self.blog_path(city)
        ranked = self.ranked(city.studios)
        top = ranked[: self.blog_n(city)]
        n = len(top)
        title_text = self.blog_title(city)
        image = self.city_image(city)
        date_iso = self._blog_date()
        rated_all = [s for s in city.studios if s.get("rating") is not None and s.get("review_count")]
        reviews_total = sum(int(s["review_count"]) for s in rated_all)
        avg = (sum(float(s["rating"]) * int(s["review_count"]) for s in rated_all) / reviews_total) if reviews_total else 0
        spec_counts: Counter = Counter()
        for studio in city.studios:
            for spec_id in self.info[studio["place_id"]]["specs"]:
                spec_counts[spec_id] += 1
        common = [si.SPEC_BY_ID[k][1].lower() for k, _ in spec_counts.most_common(3)]
        weekend = [s for s in top if self._weekend_open(s)]
        booking = [s for s in top if "booking" in self.info[s["place_id"]]["feats"]]
        first, most = top[0], max(top, key=lambda s: int(s["review_count"]))
        intro = [
            f"{esc(city.name)} has {comma(city.count)} photo studios in our directory, and {comma(len(rated_all))} of them have Google reviews "
            f"({comma(reviews_total)} reviews in total, averaging {avg:.2f} stars).",
            f"We ranked every open, reviewed studio with the same formula and kept the top {n}. "
            f'<a href="{esc(first["url_path"])}">{esc(first["name"])}</a> comes out first with {float(first["rating"]):.1f} stars from {comma(int(first["review_count"]))} reviews.',
        ]
        if common:
            intro.append(f"The most common specialties across {esc(city.name)} listings are {esc(si.join_list(common))}.")
        quick = "".join(
            f'<tr><td>{i}</td><td><a href="#rank-{i}">{esc(s["name"])}</a></td><td>{float(s["rating"]):.1f}</td>'
            f'<td>{comma(int(s["review_count"]))}</td><td>{self.rank_score(s):.2f}</td></tr>'
            for i, s in enumerate(top, start=1))
        items = "".join(self.blog_item(i, s, city) for i, s in enumerate(top, start=1))
        # FAQ from data
        faq = [
            (f"What is the best photo studio in {city.name}, Texas?",
             f"By our rating-and-review formula, {first['name']} ranks first, with {float(first['rating']):.1f} stars from {comma(int(first['review_count']))} Google reviews."),
            (f"How many photo studios are in {city.name}?",
             f"Our directory lists {comma(city.count)} photo studios in {city.name}, Texas, and {comma(len(rated_all))} of them have Google reviews."),
            (f"Which {city.name} photo studio has the most reviews?",
             f"Among the top {n}, {most['name']} has the most, with {comma(int(most['review_count']))} Google reviews and a {float(most['rating']):.1f}-star rating."),
        ]
        if weekend:
            faq.append((f"Which top {city.name} photo studios are open on weekends?",
                        f"{si.join_list([s['name'] for s in weekend[:5]])} list Saturday or Sunday hours. Hours change, so confirm before you go."))
        if booking:
            faq.append((f"Can I book a {city.name} photo studio online?",
                        f"{si.join_list([s['name'] for s in booking[:5]])} link to an online booking page from their Google listing."))
        faq.append(("How did you rank these studios?",
                    f"Each studio's score blends its Google rating with the Texas average ({self._state_mean():.2f}), weighted by its number of reviews, so a 5.0 from three reviews does not beat a 4.9 from 300. Temporarily closed studios and studios with no reviews are left out."))
        faq_html = "".join(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>" for q, a in faq)
        # Related links
        spec_pages = self.spec_pages.get(city.slug) or {}
        spec_links = "".join(
            f'<a class="chip" href="{city.path}{si.SPEC_BY_ID[k][2]}/">{esc(si.SPEC_BY_ID[k][3])} in {esc(city.name)}</a>'
            for k, _m in sorted(spec_pages.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:8])
        spec_block = f'<h3>{esc(city.name)} studios by specialty</h3><div class="chips">{spec_links}</div>' if spec_links else ""
        other_links = "".join(
            f'<li><a href="{self.blog_path(o)}">{esc(self.blog_title(o))}</a></li>' for o in others)
        tool_links = "".join(f'<li><a href="/tools/{t["slug"]}/">{esc(t["name"])}</a></li>' for t in TOOLS[:3])
        crumbs = [("Home", "/"), ("Blog", "/blog/"), (f"Best studios in {city.name}", None)]
        body = f"""<div class="wrap page-head head-split">
  <div class="head-copy">
    {self.crumbs(crumbs)}
    <p class="eyebrow"><a href="/blog/">Blog</a> · <a href="{city.path}">{esc(city.name)}</a></p>
    <h1>{esc(title_text)}</h1>
    <hr class="rule">
    <p class="muted">Updated <time datetime="{date_iso}">{self._fmt_date(date_iso)}</time> · Ranked from Google ratings and review counts</p>
  </div>
  <figure class="featured"><img src="{esc(image["src"])}" alt="{esc(f"The best photo studios in {city.name}, Texas")}" width="1200" height="630" fetchpriority="high" decoding="async"></figure>
</div>
<div class="wrap blog-post">
  <div class="blog-intro">{"".join(f"<p>{p}</p>" for p in intro)}</div>
  <section class="section-block" id="quick-list">
    <h2>Quick list</h2>
    <div class="table-wrap"><table class="rank-table"><thead><tr><th>#</th><th>Studio</th><th>Rating</th><th>Reviews</th><th>Score</th></tr></thead><tbody>{quick}</tbody></table></div>
  </section>
  {items}
  <section class="section-block" id="method">
    <h2>How we ranked {esc(city.name)} photo studios</h2>
    <p>A plain star average rewards studios with only a handful of reviews. We use a weighted score instead:</p>
    <p class="formula">score = (reviews × rating + {PRIOR_REVIEWS} × {self._state_mean():.2f}) ÷ (reviews + {PRIOR_REVIEWS})</p>
    <p>{self._state_mean():.2f} is the review-weighted average rating of every studio in our Texas directory. Each studio starts as if it had {PRIOR_REVIEWS} average reviews, and its own reviews pull the score up or down. Studios marked temporarily closed and studios without Google reviews are not ranked. No studio paid to be listed or ranked.</p>
    <p class="muted">Ratings, review counts, hours, and specialties come from public Google listings and studio websites, and can change. Check with the studio before you book.</p>
  </section>
  <section class="section-block" id="faq">
    <h2>Frequently asked questions</h2>
    <dl class="faq">{faq_html}</dl>
  </section>
  <section class="section-block" id="more">
    <h2>More in {esc(city.name)}</h2>
    <p><a class="btn btn-orange" href="{city.path}">See all {comma(city.count)} photo studios in {esc(city.name)}</a></p>
    {spec_block}
    <h3>Best photo studios in other Texas cities</h3>
    <ul class="link-cols">{other_links}</ul>
    <p><a href="/blog/">All city guides</a></p>
    <h3>Free photo tools</h3>
    <ul class="plain-list">{tool_links}<li><a href="/tools/">All free tools</a></li></ul>
  </section>
  {self.cta()}
</div>"""
        description = (f"The {n} best photo studios in {city.name}, Texas, ranked by Google rating and review count. "
                       f"Hours, specialties, and addresses for each, from {comma(city.count)} local listings.")
        article = {
            "@context": "https://schema.org", "@type": "Article",
            "headline": title_text, "description": description,
            "image": [image["abs"]], "datePublished": date_iso, "dateModified": date_iso,
            "author": {"@type": "Organization", "name": "PhotoStudiosTexas.com", "url": self.abs_url("/")},
            "publisher": {"@type": "Organization", "name": "PhotoStudiosTexas.com",
                          "logo": {"@type": "ImageObject", "url": self.abs_url("/icon-512.png")}},
            "mainEntityOfPage": self.abs_url(path),
            "about": {"@type": "City", "name": f"{city.name}, Texas"},
        }
        item_list = {
            "@context": "https://schema.org", "@type": "ItemList", "name": title_text, "numberOfItems": n,
            "itemListOrder": "https://schema.org/ItemListOrderDescending",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": s["name"], "url": self.abs_url(s["url_path"])}
                                for i, s in enumerate(top, start=1)],
        }
        faq_schema = {
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq],
        }
        self.write_page(path, self.layout(
            f"{title_text} ({dt.date.today().year})", description, path, body, "blog",
            [self.breadcrumb_schema(crumbs, path), article, item_list, faq_schema], image=image, directory=True))

    def build_blog(self) -> None:
        self.prepare_directory()
        cities = self.blog_cities
        for city in cities:
            near = sorted((o for o in cities if o.slug != city.slug),
                          key=lambda o: haversine(city.latitude, city.longitude, o.latitude, o.longitude))[:6]
            big = [o for o in cities[:4] if o.slug != city.slug and o not in near]
            self.build_blog_post(city, near + big)
        cards = []
        for city in cities:
            top = self.ranked(city.studios)[0]
            image = self.city_image(city)
            cards.append(
                f'<a class="studio-card blog-card" href="{self.blog_path(city)}">'
                f'<div class="photo"><img src="{esc(image["src"])}" alt="{esc(f"Best photo studios in {city.name}, Texas")}" width="1200" height="630" loading="lazy" decoding="async"></div>'
                f'<div class="card-body"><p class="eyebrow">{esc(city.name)} · {comma(city.count)} studios</p>'
                f'<h3>{esc(self.blog_title(city))}</h3>'
                f'<p class="muted">#1: {esc(top["name"])} ({float(top["rating"]):.1f}★, {comma(int(top["review_count"]))} reviews)</p></div></a>')
        path = "/blog/"
        crumbs = [("Home", "/"), ("Blog", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <p class="eyebrow">Blog</p>
  <h1>Photo studio guides for Texas cities</h1>
  <hr class="rule">
  <p class="lede">Ranked lists of the best photo studios in every Texas city with at least {BLOG_MIN_STUDIOS} studios in our directory: {comma(len(cities))} guides so far. Each guide uses the same open formula, blending Google rating with review count, and links to the full city directory.</p>
  <p class="muted">Looking for a smaller town? <a href="/cities/">Browse all {comma(len(self.cities))} cities</a>. Need your photos finished? See our <a href="/services/">photo services</a> or try the <a href="/tools/">free photo tools</a>.</p>
</div>
<section class="section"><div class="wrap"><div class="card-grid">{"".join(cards)}</div></div></section>
<div class="wrap">{self.cta()}</div>"""
        blog_schema = {
            "@context": "https://schema.org", "@type": "Blog", "name": "PhotoStudiosTexas.com Blog",
            "url": self.abs_url(path),
            "blogPost": [{"@type": "BlogPosting", "headline": self.blog_title(c), "url": self.abs_url(self.blog_path(c))} for c in cities],
        }
        self.write_page(path, self.layout(
            "Blog: Best Photo Studios in Texas Cities | PhotoStudiosTexas.com",
            f"{len(cities)} ranked guides to the best photo studios in Texas cities, from Houston and Dallas to Tyler and Sugar Land.",
            path, body, "blog", [self.breadcrumb_schema(crumbs, path), blog_schema]))

    # ------------------------------------------------------------ tools
    def tool_ui(self, tool: dict) -> str:
        slug = tool["slug"]
        drop = f"""<label class="tool-drop" for="tool-file">
      <input id="tool-file" type="file" accept="image/*"{" multiple" if slug == "image-format-converter" else ""}>
      <strong>Choose a photo</strong><span>or drop it here · JPG, PNG, WebP</span>
    </label>"""
        if slug == "image-background-remover":
            controls = """<div class="tool-controls" id="tool-controls">
      <label class="f-field"><span>Model</span><select id="bg-model"><option value="people">People &amp; portraits (~7 MB)</option><option value="any">Products, pets &amp; objects (~5 MB)</option></select></label>
      <label class="f-field"><span>Background</span><select id="bg-fill"><option value="">Transparent</option><option value="#ffffff">White</option><option value="#111111">Black</option><option value="#e85d04">Orange</option><option value="custom">Custom color</option></select></label>
      <label class="f-field" id="bg-color-wrap" hidden><span>Color</span><input type="color" id="bg-color" value="#f6f4f1"></label>
      <button type="button" class="btn btn-orange" id="bg-run" disabled>Remove background</button>
    </div>"""
        elif slug == "image-resizer":
            controls = """<div class="tool-controls" id="tool-controls">
      <label class="f-field"><span>Width (px)</span><input type="number" id="rs-w" min="1" max="12000"></label>
      <label class="f-field"><span>Height (px)</span><input type="number" id="rs-h" min="1" max="12000"></label>
      <label class="toggle"><input type="checkbox" id="rs-lock" checked> Keep aspect ratio</label>
      <label class="f-field"><span>Format</span><select id="rs-fmt"><option value="image/jpeg">JPG</option><option value="image/png">PNG</option><option value="image/webp">WebP</option></select></label>
      <div class="tool-presets" id="rs-presets">
        <button type="button" class="chip" data-pct="50">50%</button><button type="button" class="chip" data-pct="25">25%</button>
        <button type="button" class="chip" data-size="1080x1080">Instagram 1080×1080</button><button type="button" class="chip" data-size="1080x1350">Portrait 1080×1350</button>
        <button type="button" class="chip" data-size="1920x1080">HD 1920×1080</button><button type="button" class="chip" data-size="1200x630">Link preview 1200×630</button>
      </div>
    </div>"""
        elif slug == "image-compressor":
            controls = """<div class="tool-controls" id="tool-controls">
      <label class="f-field"><span>Format</span><select id="cp-fmt"><option value="image/jpeg">JPG</option><option value="image/webp">WebP</option></select></label>
      <label class="f-field f-range"><span>Quality <b id="cp-qv">75</b></span><input type="range" id="cp-q" min="10" max="100" value="75"></label>
      <label class="f-field"><span>Max longest side</span><select id="cp-max"><option value="0">Original size</option><option value="3000">3000 px</option><option value="2048">2048 px</option><option value="1600">1600 px</option><option value="1200">1200 px</option></select></label>
    </div>"""
        elif slug == "image-cropper":
            controls = """<div class="tool-controls" id="tool-controls">
      <div class="tool-presets" id="cr-ratios" role="group" aria-label="Aspect ratio">
        <button type="button" class="chip" data-ratio="0" aria-pressed="true">Free</button><button type="button" class="chip" data-ratio="1" aria-pressed="false">1:1</button>
        <button type="button" class="chip" data-ratio="0.8" aria-pressed="false">4:5</button><button type="button" class="chip" data-ratio="1.5" aria-pressed="false">3:2</button>
        <button type="button" class="chip" data-ratio="1.7778" aria-pressed="false">16:9</button><button type="button" class="chip" data-ratio="0.5625" aria-pressed="false">9:16</button>
      </div>
      <label class="f-field"><span>Format</span><select id="cr-fmt"><option value="image/jpeg">JPG</option><option value="image/png">PNG</option><option value="image/webp">WebP</option></select></label>
    </div>"""
        else:
            controls = """<div class="tool-controls" id="tool-controls">
      <label class="f-field"><span>Convert to</span><select id="cv-fmt"><option value="image/png">PNG</option><option value="image/jpeg">JPG</option><option value="image/webp">WebP</option></select></label>
      <label class="f-field"><span>Fill for transparency (JPG)</span><input type="color" id="cv-bg" value="#ffffff"></label>
    </div>"""
        return f"""<div class="tool-app" id="tool-app" data-tool="{slug}">
    {drop}
    {controls}
    <p class="tool-status" id="tool-status" aria-live="polite"></p>
    <div class="tool-stage" id="tool-stage" hidden></div>
    <div class="tool-output" id="tool-output"></div>
    <noscript><p>This tool runs in your browser and needs JavaScript.</p></noscript>
  </div>"""

    def tools_nav(self, current: str | None) -> str:
        items = []
        for tool in TOOLS:
            if tool["slug"] == current:
                continue
            items.append(f'<li><a href="/tools/{tool["slug"]}/">{esc(tool["name"])}</a> <span class="muted">{esc(tool["blurb"])}</span></li>')
        return f'<ul class="plain-list tool-list">{"".join(items)}</ul>'

    def tool_upsell(self, tool: dict) -> str:
        if tool["slug"] in {"image-resizer", "image-compressor"}:
            lead = ('Need a small photo made bigger and sharper? <a href="/services/photo-enhancement/">Photo Enhancement &amp; Upscaling</a> '
                    'is done by hand. For retouching, background swaps, and object removal, see <a href="/services/photo-editing/">Photo Editing &amp; Retouching</a>.')
        else:
            lead = ('Want it done by a pro? <a href="/services/photo-editing/">Photo Editing &amp; Retouching</a> covers clean cutouts, '
                    'background swaps, skin retouching, and object removal. <a href="/services/photo-enhancement/">Photo Enhancement &amp; Upscaling</a> '
                    'fixes blurry or low-resolution photos.')
        return f'<aside class="panel tool-upsell"><h2>Need more than a quick fix?</h2><p>{lead}</p><p><a class="btn btn-orange" href="/services/">See photo services</a></p></aside>'

    def build_tools(self) -> None:
        tools_dir = DIST_ASSETS = self._dist() / "assets" / "tools"
        DIST_ASSETS.mkdir(parents=True, exist_ok=True)
        for item in TOOLS_SRC.glob("*.js"):
            shutil.copyfile(item, tools_dir / item.name)
        shutil.copyfile(TOOLS_SRC / "tools.css", tools_dir / "tools.css")
        for tool in TOOLS:
            path = f"/tools/{tool['slug']}/"
            crumbs = [("Home", "/"), ("Free tools", "/tools/"), (tool["name"], None)]
            steps = "".join(f"<li>{esc(s)}</li>" for s in tool["steps"])
            faq = "".join(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>" for q, a in tool["faq"])
            script_type = ' type="module"' if tool.get("module") else " defer"
            body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <p class="eyebrow"><a href="/tools/">Free photo tools</a></p>
  <h1>{esc(tool["name"])}</h1>
  <hr class="rule">
  <p class="lede">{esc(tool["description"])}</p>
  {self.tool_ui(tool)}
  <p class="tool-privacy"><strong>100% free and private.</strong> Your photos stay on your device. Nothing is uploaded to our server.</p>
  <div class="split tool-info">
    <div>
      <section class="section-block"><h2>How to use the {esc(tool["name"].lower())}</h2><ol class="steps">{steps}</ol></section>
      <section class="section-block" id="faq"><h2>Frequently asked questions</h2><dl class="faq">{faq}</dl></section>
      <section class="section-block"><h2>More free photo tools</h2>{self.tools_nav(tool["slug"])}<p><a href="/tools/">All free tools</a></p></section>
    </div>
    {self.tool_upsell(tool)}
  </div>
  <p>Planning a shoot? <a href="/blog/">Read our city guides</a> or <a href="/cities/">find a photo studio near you</a>.</p>
</div>"""
            app = {
                "@context": "https://schema.org", "@type": "WebApplication", "name": tool["name"],
                "url": self.abs_url(path), "applicationCategory": "MultimediaApplication", "operatingSystem": "Any (web browser)",
                "browserRequirements": "Requires JavaScript", "isAccessibleForFree": True,
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                "description": tool["description"],
            }
            faq_schema = {"@context": "https://schema.org", "@type": "FAQPage",
                          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in tool["faq"]]}
            extra = (f'<link rel="stylesheet" href="/assets/tools/tools.css">\n'
                     f'<script src="/assets/tools/{tool["script"]}"{script_type}></script>\n')
            self.write_page(path, self.layout(
                f'{tool["title"]} | PhotoStudiosTexas', tool["description"], path, body, "tools",
                [self.breadcrumb_schema(crumbs, path), app, faq_schema], extra_head=extra))
        cards = "".join(
            f'<a class="studio-card service-card tool-card" href="/tools/{t["slug"]}/"><div class="card-body">'
            f'<p class="eyebrow">Free tool</p><h3>{esc(t["name"])}</h3><p>{esc(t["blurb"])}</p>'
            f'<span class="btn btn-orange">Open tool</span></div></a>' for t in TOOLS)
        path = "/tools/"
        crumbs = [("Home", "/"), ("Free tools", None)]
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <p class="eyebrow">Free tools</p>
  <h1>Free photo editing tools</h1>
  <hr class="rule">
  <p class="lede">{len(TOOLS)} simple photo tools that run in your browser. They are free, need no sign-up, add no watermark, and never upload your photos.</p>
  <div class="card-grid">{cards}</div>
  <section class="section-block"><h2>When to hire an editor instead</h2>
  <p>These tools handle quick jobs. For retouching, hand-cut backgrounds, and object removal, see <a href="/services/photo-editing/">Photo Editing &amp; Retouching</a>. For blurry, old, or low-resolution photos, see <a href="/services/photo-enhancement/">Photo Enhancement &amp; Upscaling</a>. Both are on the <a href="/services/">services page</a>.</p>
  <p>Still need the photos taken? <a href="/blog/">Read our guides to the best photo studios in Texas cities</a>.</p></section>
</div>
<div class="wrap">{self.cta()}</div>"""
        item_list = {"@context": "https://schema.org", "@type": "ItemList", "name": "Free photo editing tools",
                     "itemListElement": [{"@type": "ListItem", "position": i, "name": t["name"], "url": self.abs_url(f"/tools/{t['slug']}/")}
                                         for i, t in enumerate(TOOLS, start=1)]}
        self.write_page(path, self.layout(
            "Free Photo Editing Tools: Background Remover, Resizer & More | PhotoStudiosTexas",
            "Free online photo tools: background remover, image resizer, compressor, cropper, and format converter. They run in your browser, so nothing is uploaded.",
            path, body, "tools", [self.breadcrumb_schema(crumbs, path), item_list],
            extra_head='<link rel="stylesheet" href="/assets/tools/tools.css">\n'))

    # ------------------------------------------------------------ home geo
    def write_geo_index(self) -> None:
        self.prepare_directory()
        cities = [[c.name, c.path, round(c.latitude, 4), round(c.longitude, 4), c.count] for c in self.by_name]
        city_idx = {c.slug: i for i, c in enumerate(self.by_name)}
        studios = []
        for s in self.studios:
            if s.get("business_status") != "OPERATIONAL" or s.get("rating") is None or not s.get("review_count"):
                continue
            tags = [self.tag_label(t) for t in self.tag_ids(s)[:3]]
            studios.append([s["name"], s["url_path"], city_idx[s["city_slug"]], float(s["rating"]), int(s["review_count"]),
                            round(s["latitude"], 5), round(s["longitude"], 5), http_url(s.get("photo")) or "",
                            round(self.rank_score(s), 3), tags])
        out = self._dist() / "assets" / "geo-index.json"
        out.write_text(json.dumps({"cities": cities, "studios": studios}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        shutil.copyfile(ROOT / "assets" / "home-geo.js", self._dist() / "assets" / "home-geo.js")

    # ------------------------------------------------------------ llms.txt
    def write_llms(self) -> None:
        lines = [
            "# PhotoStudiosTexas.com",
            "",
            f"> Directory of {comma(len(self.studios))} photo studios across {comma(len(self.cities))} Texas cities, with ratings, review counts, hours, specialties, and contact details from public Google listings. Also offers paid photo editing and photo enhancement services, free in-browser photo tools, and ranked city guides.",
            "",
            "Listings are not paid placements. Ratings and hours come from public Google listings and studio websites and may be out of date. City pages (/tx/<city>/) are the hubs; each studio has its own page (/tx/<city>/<studio>/).",
            "",
            "## Key pages",
            f"- [Home]({self.abs_url('/')}): search, studios near the visitor, featured studios, every city",
            f"- [Texas hub]({self.abs_url('/tx/')}): all cities by number of studios",
            f"- [All cities A-Z]({self.abs_url('/cities/')})",
            f"- [Blog]({self.abs_url('/blog/')}): ranked guides to the best photo studios in each large Texas city",
            f"- [Free photo tools]({self.abs_url('/tools/')})",
            f"- [Services]({self.abs_url('/services/')})",
            f"- [About]({self.abs_url('/about/')})",
            f"- [HTML sitemap]({self.abs_url('/sitemap/')}) and [XML sitemap]({self.abs_url('/sitemap.xml')})",
            "",
            "## Services",
        ]
        for service in self.services:
            price = self.service_price(service)
            note = f" — {price} {service.get('priceNote', '')}".rstrip() if price else ""
            lines.append(f"- [{service['name']}]({self.abs_url('/services/' + service['slug'] + '/')}){note}: {service['summary']}")
        lines += ["", "## Free tools (run in the browser, nothing uploaded)"]
        for tool in TOOLS:
            lines.append(f"- [{tool['name']}]({self.abs_url('/tools/' + tool['slug'] + '/')}): {tool['blurb']}")
        lines += ["", "## City guides",
                  f"Ranking: score = (reviews x rating + {PRIOR_REVIEWS} x {self._state_mean():.2f}) / (reviews + {PRIOR_REVIEWS}); open, reviewed studios only."]
        for city in self.blog_cities:
            lines.append(f"- [{self.blog_title(city)}]({self.abs_url(self.blog_path(city))})")
        lines += self.category_llms_lines()
        lines += ["", "## Largest city directories"]
        for city in self.by_count[:20]:
            lines.append(f"- [Photo studios in {city.name}, TX]({self.abs_url(city.path)}): {city.count} studios")
        lines += ["", "## Policies",
                  f"- [Privacy Policy]({self.abs_url('/privacy/')})",
                  f"- [Terms of Service]({self.abs_url('/terms/')})",
                  f"- [Refund Policy]({self.abs_url('/refund-policy/')})",
                  f"- [Directory Disclaimer]({self.abs_url('/disclaimer/')}): listing data comes from public Google Maps information; not affiliated with Google or the studios",
                  "", "## Contact", f"- {self.email or 'Use the contact form on the About page: ' + self.abs_url('/about/') + '#contact'}", ""]
        (self._dist() / "llms.txt").write_text("\n".join(lines), encoding="utf-8")

    def _dist(self) -> Path:
        return ROOT / "dist"
