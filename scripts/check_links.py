#!/usr/bin/env python3
"""Fail if the built site has broken internal links, orphans, or missing SEO files."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CONFIG = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
BASE = CONFIG["canonicalBase"].rstrip("/")

REQUIRED_SNIPPETS = [
    "/favicon.svg",
    "/favicon.ico",
    "/apple-touch-icon.png",
    "/icon-192.png",
    "/icon-512.png",
    "/site.webmanifest",
    "/og-image.png",
    "/assets/logo-light.svg",
    "/assets/logo-dark.svg",
    'rel="canonical"',
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
    "assets/site-config.js",
    "assets/search-index.json",
]


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
    path = unquote(urldefrag(path)[0])
    if not path.startswith("/"):
        return "RELATIVE"
    if path != "/" and not Path(path).suffix and not path.endswith("/"):
        path += "/"
    return path


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

    orphans = [path for path in pages if path not in seen and path != "/404.html"]
    deep = [f"{path} depth {depth}" for path, depth in seen.items() if depth > 3]
    if orphans:
        errors.append(f"{len(orphans)} orphan pages, e.g. {orphans[:8]}")
    if deep:
        errors.append(f"pages deeper than 3 clicks: {deep[:8]}")

    sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap)
    expected_locs = {BASE + path for path in pages if path != "/404.html"}
    if set(locs) != expected_locs:
        missing = sorted(expected_locs - set(locs))[:8]
        extra = sorted(set(locs) - expected_locs)[:8]
        errors.append(f"sitemap mismatch missing={missing} extra={extra} counts {len(locs)} vs {len(expected_locs)}")

    robots = (DIST / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {BASE}/sitemap.xml" not in robots:
        errors.append("robots.txt is missing the sitemap URL")

    service = pages.get("/services/photo-editing/", {})
    service_text = service.get("text", "")
    if "Order Now - $39.88" not in service_text:
        errors.append("photo editing page is missing the Order Now button label")
    if "$39.88" not in service_text:
        errors.append("photo editing page is missing the price")

    runtime = (DIST / "assets" / "site-config.js").read_text(encoding="utf-8")
    if "STRIPE_PAYMENT_LINK" not in runtime or "STRIPE_PAYMENT_LINK" not in CONFIG:
        errors.append("STRIPE_PAYMENT_LINK is not exposed from config/site.json")

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
            if city_path not in studio_html or "/services/photo-editing/" not in studio_html:
                errors.append(f"{studio['url_path']} is missing a city or service link")
                break

    indexable = [path for path in pages if path != "/404.html"]
    print(
        f"Checked {len(html_files)} HTML files, {len(indexable)} indexable, "
        f"{city_pages} cities, {len(data['studios'])} studios, max depth {max(seen.values())}"
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
