#!/usr/bin/env python3
"""Fail if the built site has broken internal links, orphans, or missing SEO files."""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CONFIG = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
BASE = CONFIG["canonicalBase"].rstrip("/")
NOINDEX: set[str] = set()  # noindex pages (404, thanks, claim form): kept out of the sitemap and orphan check

REQUIRED_SNIPPETS = [
    "/favicon.svg",
    "/favicon.ico",
    "/apple-touch-icon.png",
    "/icon-192.png",
    "/icon-512.png",
    "/site.webmanifest",
    "/assets/logo-light.svg",
    "/assets/logo-dark.svg",
    'rel="canonical"',
    'property="og:image"',
    'name="twitter:image"',
]

ROOT_FILES = [
    "favicon.svg",
    "favicon.ico",
    "apple-touch-icon.png",
    "icon-192.png",
    "icon-512.png",
    "og-image.png",
    "site.webmanifest",
    "sitemap.xml",
    "robots.txt",
    "assets/logo-light.svg",
    "assets/logo-dark.svg",
    "assets/site.css",
    "assets/site.js",
    "assets/blob-upload.js",
    "assets/directory.css",
    "assets/directory.js",
    "assets/site-config.js",
    "assets/search-index.json",
    "assets/geo-index.json",
    "assets/home-geo.js",
    "assets/tools/tools.js",
    "assets/tools/bg-remover.js",
    "assets/tools/tools.css",
    "llms.txt",
]

TOOL_SLUGS = [
    "image-background-remover",
    "image-resizer",
    "image-compressor",
    "image-cropper",
    "image-format-converter",
]
BLOG_MIN_STUDIOS = 10


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.title = ""
        self._in_title = False
        self.canonical = ""

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "a" and data.get("href"):
            self.hrefs.append(data["href"])
        elif tag in {"img", "script"} and data.get("src"):
            self.hrefs.append(data["src"])
        elif tag == "link" and data.get("href"):
            self.hrefs.append(data["href"])
            if "canonical" in (data.get("rel") or ""):
                self.canonical = data["href"]
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def page_path(file: Path) -> str:
    relative = file.relative_to(DIST).as_posix()
    if relative == "index.html":
        return "/"
    if relative == "404.html":
        return "/404.html"
    if relative.endswith("/index.html"):
        return "/" + relative[: -len("index.html")]
    return "/" + relative


def file_for(path: str) -> Path:
    if path == "/":
        return DIST / "index.html"
    relative = path.strip("/")
    last = relative.split("/")[-1]
    if "." in last:
        return DIST / relative
    return DIST / relative / "index.html"


def internal_target(href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    if href.startswith("//"):
        return None
    if href.startswith(("http://", "https://")):
        parts = urlsplit(href)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin != BASE:
            return None
        path = parts.path or "/"
    else:
        path = href
    path = unquote(urldefrag(path)[0]).split("?", 1)[0]
    if path.startswith(("/_vercel/", "/api/")):
        return None  # served by Vercel at runtime
    if not path.startswith("/"):
        return "RELATIVE"
    if path != "/" and not Path(path).suffix and not path.endswith("/"):
        path += "/"
    return path


def sitemap_paths(locs: list[str]) -> set[str]:
    return {loc[len(BASE):] or "/" for loc in locs}


def main() -> int:
    errors: list[str] = []
    if not DIST.is_dir():
        print("dist/ is missing. Run python3 scripts/build.py", file=sys.stderr)
        return 1

    for relative in ROOT_FILES:
        if not (DIST / relative).is_file():
            errors.append(f"missing file dist/{relative}")

    html_files = sorted(DIST.rglob("*.html"))
    pages = {}
    titles = {}
    for file in html_files:
        text = file.read_text(encoding="utf-8")
        parser = Collector()
        parser.feed(text)
        path = page_path(file)
        pages[path] = {"file": file, "hrefs": parser.hrefs, "title": parser.title.strip(), "canonical": parser.canonical, "text": text}
        if 'name="robots" content="noindex' in text:
            NOINDEX.add(path)
        if path != "/404.html":
            titles.setdefault(parser.title.strip(), []).append(path)
        for snippet in REQUIRED_SNIPPETS:
            if snippet not in text:
                errors.append(f"{path} is missing {snippet}")
        if "fiverr" in text.lower():
            errors.append(f"{path} mentions Fiverr")

    for title, paths in titles.items():
        if len(paths) > 1:
            errors.append(f"duplicate title {title!r} on {paths[:5]}")

    graph = {}
    for path, page in pages.items():
        links = []
        expected = BASE + ("/" if path == "/" else path)
        if path != "/404.html" and page["canonical"] != expected:
            errors.append(f"{path} canonical is {page['canonical']!r}, expected {expected}")
        for href in page["hrefs"]:
            target = internal_target(href)
            if target is None:
                continue
            if target == "RELATIVE":
                errors.append(f"{path} has a relative link {href}")
                continue
            destination = file_for(target)
            if not destination.is_file():
                errors.append(f"{path} broken link {href} -> {target}")
                continue
            if target.endswith(".html") or not Path(target).suffix:
                links.append(target if target == "/404.html" or Path(target).suffix else target)
            # Directory targets are crawlable pages. Asset files are not pages.
            if destination.suffix == ".html":
                links.append(page_path(destination))
        graph[path] = links

    seen = {"/": 0}
    queue = ["/"]
    while queue:
        current = queue.pop(0)
        for target in graph.get(current, []):
            if target in seen or target not in pages:
                continue
            seen[target] = seen[current] + 1
            queue.append(target)

    orphans = [path for path in pages if path not in seen and path not in NOINDEX]
    deep = [f"{path} depth {depth}" for path, depth in seen.items() if depth > 3]
    if orphans:
        errors.append(f"{len(orphans)} orphan pages, e.g. {orphans[:8]}")
    if deep:
        errors.append(f"pages deeper than 3 clicks: {deep[:8]}")

    sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap)
    expected_locs = {BASE + path for path in pages if path not in NOINDEX}
    if set(locs) != expected_locs:
        missing = sorted(expected_locs - set(locs))[:8]
        extra = sorted(set(locs) - expected_locs)[:8]
        errors.append(f"sitemap mismatch missing={missing} extra={extra} counts {len(locs)} vs {len(expected_locs)}")

    robots = (DIST / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {BASE}/sitemap.xml" not in robots:
        errors.append("robots.txt is missing the sitemap URL")

    services = json.loads((ROOT / "config" / "services.json").read_text(encoding="utf-8"))
    hub = pages.get("/services/", {}).get("text", "")
    if not hub:
        errors.append("missing services hub /services/")
    for service in services:
        path = f"/services/{service['slug']}/"
        if path not in pages:
            errors.append(f"missing service page {path}")
            continue
        service_text = pages[path]["text"]
        price = str(service.get("priceDisplay") or "").strip()
        if price.startswith("$"):
            if price not in service_text:
                errors.append(f"{path} is missing the price")
            label = service.get("orderButtonLabel") or ""
            if label and label not in service_text:
                errors.append(f"{path} is missing the Order Now button label")
        if path not in hub or service["name"] not in unescape(hub):
            errors.append(f"services hub is missing {service['name']}")
        if "fiverr" in json.dumps(service).lower():
            errors.append(f"service {service['slug']} config mentions Fiverr")

    runtime = (DIST / "assets" / "site-config.js").read_text(encoding="utf-8")
    for key in ("STRIPE_PAYMENT_LINK", "STRIPE_PAYMENT_LINK_ENHANCE"):
        if key not in runtime or key not in CONFIG:
            errors.append(f"{key} is not exposed from config/site.json")

    data = json.loads((ROOT / "data" / "studios.json").read_text(encoding="utf-8"))
    home = pages["/"]["text"]
    city_pages = 0
    for studio in data["studios"]:
        city_path = f"/tx/{studio['city_slug']}/"
        if studio["url_path"] not in pages:
            errors.append(f"missing studio page {studio['url_path']}")
            break
        if city_path not in home:
            errors.append(f"home page does not link to {city_path}")
            break
    city_slugs = {studio["city_slug"] for studio in data["studios"]}
    for slug in city_slugs:
        city_path = f"/tx/{slug}/"
        city_pages += 1
        if city_path not in pages:
            errors.append(f"missing city page {city_path}")
            continue
        city_html = pages[city_path]["text"]
        for studio in data["studios"]:
            if studio["city_slug"] != slug:
                continue
            if studio["url_path"] not in city_html:
                errors.append(f"{city_path} does not link to {studio['url_path']}")
                break
            studio_html = pages[studio["url_path"]]["text"]
            if (
                city_path not in studio_html
                or "/services/" not in studio_html
                or "/services/photo-editing/" not in studio_html
                or "/services/photo-enhancement/" not in studio_html
            ):
                errors.append(f"{studio['url_path']} is missing a city or service link")
                break

    # Featured image, filter bar, schema image, and reviews/hours sections.
    for studio in data["studios"]:
        text = pages[studio["url_path"]]["text"]
        if 'class="featured studio-featured"' not in text or 'fetchpriority="high"' not in text:
            errors.append(f"{studio['url_path']} has no featured image")
        if '"image":' not in text or 'name="twitter:image"' not in text:
            errors.append(f"{studio['url_path']} is missing image metadata")
        if 'id="reviews"' not in text or 'id="services"' not in text:
            errors.append(f"{studio['url_path']} is missing the reviews or services section")
        if studio.get("hours") and 'id="hours"' not in text:
            errors.append(f"{studio['url_path']} has hours data but no hours section")
    for slug in city_slugs:
        text = pages[f"/tx/{slug}/"]["text"]
        if 'class="featured"' not in text or 'id="filter-bar"' not in text:
            errors.append(f"/tx/{slug}/ is missing the featured image or filter bar")
        if f"/images/city/{slug}.png" not in text or not (DIST / "images" / "city" / f"{slug}.png").is_file():
            errors.append(f"/tx/{slug}/ city image missing")

    # Header nav, blog, tools, services cross-links, robots/llms.
    for need in ("/blog/", "/tools/", "/about/", "/services/"):
        if f'href="{need}"' not in home.split("</header>")[0]:
            errors.append(f"header nav is missing {need}")
    # Statewide category hubs: exist only for categories with evidence, link everywhere, list exactly the evidenced studios.
    sys.path.insert(0, str(ROOT / "scripts"))
    import categories as cat_rules  # noqa: E402

    ev_path = ROOT / "data" / "category-evidence.json"
    ev = json.loads(ev_path.read_text(encoding="utf-8")) if ev_path.is_file() else {"studios": {}}
    by_pid = {s["place_id"]: s for s in data["studios"]}
    cat_pages = 0
    llms_text = (DIST / "llms.txt").read_text(encoding="utf-8") if (DIST / "llms.txt").is_file() else ""
    for cid, slug, _label, _h1, _noun in cat_rules.CATEGORIES:
        path = f"/categories/{slug}/"
        members = {pid for pid, v in ev["studios"].items() if cid in v["categories"]}
        if not members:
            if path in pages or any(path in page["text"] for page in pages.values()):
                errors.append(f"{path} has no qualifying studios but a page or link exists")
            continue
        cat_pages += 1
        if path not in pages:
            errors.append(f"missing category page {path}")
            continue
        text = pages[path]["text"]
        listed = set(re.findall(r'<a class="studio-card" href="([^"]+)"', text))
        expected = {by_pid[pid]["url_path"] for pid in members if pid in by_pid}
        if listed != expected:
            errors.append(f"{path} lists {len(listed)} studios, evidence says {len(expected)}")
        for need in ('id="filter-bar"', 'class="featured"', '"@type":"CollectionPage"', '"@type":"ItemList"', '"@type":"BreadcrumbList"', 'id="f-city"'):
            if need not in text:
                errors.append(f"{path} is missing {need}")
        if f"/images/category/{slug}.png" not in text or not (DIST / "images" / "category" / f"{slug}.png").is_file():
            errors.append(f"{path} image missing")
        for source, label in (("/", "home"), ("/tx/", "Texas hub"), ("/categories/", "categories hub"), ("/sitemap/", "HTML sitemap")):
            if path not in pages.get(source, {}).get("text", ""):
                errors.append(f"{label} does not link to {path}")
        if path not in llms_text:
            errors.append(f"llms.txt is missing {path}")
        for pid in members:
            studio = by_pid.get(pid)
            if not studio:
                continue
            studio_html = pages.get(studio["url_path"], {}).get("text", "")
            if f'href="{path}"' not in studio_html:
                errors.append(f"{studio['url_path']} does not link to {path}")
                break
        for pid in list(members)[:400]:
            city_html = pages.get(f"/tx/{by_pid[pid]['city_slug']}/", {}).get("text", "")
            if f'href="{path}"' not in city_html:
                errors.append(f"/tx/{by_pid[pid]['city_slug']}/ does not link to {path}")
                break
    if cat_pages:
        if "/categories/" not in pages:
            errors.append("missing /categories/ hub")
        if 'href="/categories/"' not in home.split("</header>")[0]:
            errors.append("header nav is missing /categories/")
    elif "/categories/" in pages:
        errors.append("/categories/ exists but no category has qualifying studios")
    # A studio must not be on a category page without evidence (links to a category it does not qualify for).
    for studio in data["studios"]:
        mine = ev["studios"].get(studio["place_id"], {}).get("categories", {})
        text = pages[studio["url_path"]]["text"]
        for cid, slug, *_rest in cat_rules.CATEGORIES:
            if cid not in mine and f'href="/categories/{slug}/"' in text:
                errors.append(f"{studio['url_path']} links to /categories/{slug}/ without evidence")
                break
    if "Disallow: /assets/" in robots:
        errors.append("robots.txt blocks /assets/ (CSS/JS needed for rendering)")
    llms = (DIST / "llms.txt").read_text(encoding="utf-8") if (DIST / "llms.txt").is_file() else ""
    for need in ("/blog/", "/tools/", "/services/"):
        if need not in llms:
            errors.append(f"llms.txt is missing {need}")
    city_counts = {}
    for studio in data["studios"]:
        city_counts[studio["city_slug"]] = city_counts.get(studio["city_slug"], 0) + 1
    blog_hub = pages.get("/blog/", {}).get("text", "")
    if not blog_hub:
        errors.append("missing blog hub /blog/")
    blog_posts = 0
    for slug, count in city_counts.items():
        if count < BLOG_MIN_STUDIOS:
            continue
        post = f"/blog/best-photo-studios-in-{slug}-tx/"
        if post not in pages:
            errors.append(f"missing blog post {post}")
            continue
        blog_posts += 1
        text = pages[post]["text"]
        if post not in blog_hub:
            errors.append(f"blog hub does not link to {post}")
        if post not in pages[f"/tx/{slug}/"]["text"]:
            errors.append(f"/tx/{slug}/ does not link to its blog post")
        if f'href="/tx/{slug}/"' not in text or '"@type":"Article"' not in text or '"@type":"ItemList"' not in text:
            errors.append(f"{post} is missing the city link or Article/ItemList schema")
        if f"/images/city/{slug}.png" not in text:
            errors.append(f"{post} is missing its featured image")
    tools_hub = pages.get("/tools/", {}).get("text", "")
    for slug in TOOL_SLUGS:
        tool = f"/tools/{slug}/"
        if tool not in pages:
            errors.append(f"missing tool page {tool}")
            continue
        if tool not in tools_hub:
            errors.append(f"tools hub does not link to {tool}")
        text = pages[tool]["text"]
        if "/services/" not in text or 'id="tool-app"' not in text:
            errors.append(f"{tool} is missing the tool UI or a services link")
    for service in services:
        path = f"/services/{service['slug']}/"
        text = pages.get(path, {}).get("text", "")
        body = text.split("</header>", 1)[-1].split("<footer", 1)[0]
        if 'href="/services/"' not in body:
            errors.append(f"{path} does not link to /services/ in the page body")
        for other in services:
            if other["slug"] != service["slug"] and f'href="/services/{other["slug"]}/"' not in body:
                errors.append(f"{path} does not link to /services/{other['slug']}/ in the page body")

    # Forms, legal pages, claim links, analytics, 404.
    legal = ["/privacy/", "/terms/", "/refund-policy/", "/disclaimer/"]
    for path in legal:
        if path not in pages:
            errors.append(f"missing legal page {path}")
            continue
        if path in NOINDEX:
            errors.append(f"{path} should be indexable")
        if path not in sitemap_paths(locs):
            errors.append(f"{path} is not in sitemap.xml")
        if "fiverr" in pages[path]["text"].lower():
            errors.append(f"{path} mentions Fiverr")
    for path, page in pages.items():
        text = page["text"]
        if path != "/404.html" and "/_vercel/insights/script.js" not in text:
            errors.append(f"{path} is missing the analytics script")
        if path != "/404.html" and not all(f'href="{p}"' in text for p in legal):
            errors.append(f"{path} footer is missing a legal link")
    for path in ("/claim-listing/", "/thanks/"):
        if path not in pages:
            errors.append(f"missing {path}")
    if "/claim-listing/" in pages and 'action="/api/submit/"' not in pages["/claim-listing/"]["text"]:
        errors.append("/claim-listing/ form does not post to /api/submit/")
    for service in services:
        path = f"/services/{service['slug']}/"
        text = pages.get(path, {}).get("text", "")
        if 'action="/api/submit/"' not in text or 'type="file"' not in text:
            errors.append(f"{path} order form does not post to /api/submit with a file upload")
        for need in ("/refund-policy/", "/terms/", "/privacy/"):
            if need not in text.split("</header>", 1)[-1].split("<footer", 1)[0]:
                errors.append(f"{path} body does not link to {need}")
        if "mailto:" in text:
            errors.append(f"{path} still uses mailto:")
    if 'action="/api/submit/"' not in pages.get("/about/", {}).get("text", ""):
        errors.append("/about/ contact form does not post to /api/submit/")
    for studio in data["studios"]:
        text = pages[studio["url_path"]]["text"]
        if "/claim-listing/?studio=" not in text or "type=removal" not in text:
            errors.append(f"{studio['url_path']} is missing the claim/removal links")
            break
    for name in ("api/submit.js", "api/upload.js"):
        if not (ROOT / name).is_file():
            errors.append(f"missing {name}")
    nf = pages.get("/404.html", {}).get("text", "")
    if "/cities/" not in nf or "/blog/" not in nf or "/services/" not in nf:
        errors.append("404.html is missing helpful links")
    for path, page in pages.items():
        if "<img" in page["text"]:
            for tag in re.findall(r"<img\b[^>]*>", page["text"]):
                if "width=" not in tag or "height=" not in tag:
                    errors.append(f"{path} has an <img> without width/height: {tag[:90]}")
                    break
            else:
                continue
            break

    indexable = [path for path in pages if path not in NOINDEX]
    print(
        f"Checked {len(html_files)} HTML files, {len(indexable)} indexable, "
        f"{city_pages} cities, {len(data['studios'])} studios, {blog_posts} blog posts, max depth {max(seen.values())}"
    )
    if errors:
        print(f"{len(errors)} problems:", file=sys.stderr)
        for error in errors[:40]:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Internal links, sitemap, icons, and orphans: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
