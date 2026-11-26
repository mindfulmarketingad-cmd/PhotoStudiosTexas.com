#!/usr/bin/env python3
"""Read each studio's own homepage for a few public facts the export lacks.

Collects only: page title, meta description, public social profile links, and
short heading / menu labels (used for specialty keyword matching). Nothing is
invented. Output: data/website-enrichment.json keyed by place_id.

Needs aiohttp and beautifulsoup4 (dev-only; scripts/build.py stays stdlib):

    pip install aiohttp beautifulsoup4 lxml
    python3 scripts/enrich_websites.py            # fetch missing entries
    python3 scripts/enrich_websites.py --refresh  # refetch everything
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
STUDIOS = ROOT / "data" / "studios.json"
OUT = ROOT / "data" / "website-enrichment.json"
UA = "Mozilla/5.0 (compatible; PhotoStudiosTexasBot/1.0; +https://www.photostudiostexas.com)"
SOCIAL = {
    "instagram": r"instagram\.com",
    "facebook": r"facebook\.com",
    "tiktok": r"tiktok\.com",
    "youtube": r"youtube\.com",
    "pinterest": r"pinterest\.[a-z.]+",
    "x": r"(?:twitter|x)\.com",
    "linkedin": r"linkedin\.com",
}
BAD_SOCIAL_PATH = re.compile(
    r"^/(sharer|share|intent|plugins|dialog|tr|login|help|policies|p/|reel/|explore|hashtag|embed|watch|results|v/|oauth|home|i/)",
    re.I,
)
SKIP_HOSTS = ("facebook.com", "instagram.com", "linktr.ee", "google.com", "goo.gl", "yelp.com")


def clean(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return text[:limit]


def parse(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = clean(soup.title.string if soup.title and soup.title.string else None, 160)
    desc = None
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            desc = clean(tag["content"], 400)
            if desc:
                break
    social = {}
    topics = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        host = parsed.netloc.lower().removeprefix("www.")
        for key, pattern in SOCIAL.items():
            if re.fullmatch(r"(?:[a-z]+\.)?" + pattern, host) and key not in social:
                path = parsed.path or "/"
                if len(path.strip("/")) >= 2 and not BAD_SOCIAL_PATH.match(path):
                    social[key] = f"https://{host}{path.rstrip('/')}" if key != "facebook" or path.strip("/") else absolute
        label = clean(a.get_text(" "), 40)
        if label and 2 < len(label) and label.lower() not in seen and len(topics) < 45:
            seen.add(label.lower())
            topics.append(label)
    for tag in soup.find_all(["h1", "h2", "h3"], limit=14):
        label = clean(tag.get_text(" "), 90)
        if label and label.lower() not in seen:
            seen.add(label.lower())
            topics.append(label)
    return {"title": title, "description": desc, "social": social, "topics": topics}


async def fetch_one(session, sem, studio) -> tuple[str, dict]:
    url = studio["website"]
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    if url.lower().startswith("http://"):
        url = "https://" + url[7:]  # try the secure site first
    url = re.split(r"(?:\?|%3[Ff])", url, maxsplit=1)[0]  # drop tracking query, even when encoded
    host = urlparse(url).netloc.lower().removeprefix("www.")
    result: dict = {"url": url}
    if any(host.endswith(h) for h in SKIP_HOSTS):
        result["status"] = "skipped-social"
        key = next(k for k, p in SOCIAL.items() if re.search(p, host)) if any(re.search(p, host) for p in SOCIAL.values()) else None
        if key:
            result["social"] = {key: url.split("?")[0].rstrip("/")}
        return studio["place_id"], result
    async with sem:
        try:
            async with session.get(url, allow_redirects=True, max_redirects=5) as resp:
                result["status"] = resp.status
                ctype = resp.headers.get("content-type", "")
                if resp.status == 200 and "html" in ctype.lower():
                    raw = await resp.content.read(600_000)
                    html = raw.decode(resp.charset or "utf-8", errors="replace")
                    result.update(parse(html, str(resp.url)))
        except Exception as exc:  # noqa: BLE001
            result["status"] = f"error:{type(exc).__name__}"
    return studio["place_id"], result


async def main() -> None:
    refresh = "--refresh" in sys.argv
    studios = [s for s in json.loads(STUDIOS.read_text())["studios"] if s.get("website")]
    existing = {}
    if OUT.exists() and not refresh:
        existing = json.loads(OUT.read_text())
    existing = {k: v for k, v in existing.items() if str(v.get("status")) in {"200", "skipped-social", "403", "401"}}
    todo = [s for s in studios if s["place_id"] not in existing]
    print(f"{len(studios)} websites, {len(todo)} to fetch")
    sem = asyncio.Semaphore(40)
    timeout = aiohttp.ClientTimeout(total=14, connect=7)
    conn = aiohttp.TCPConnector(limit=80, ssl=False)
    async with aiohttp.ClientSession(headers={"User-Agent": UA, "Accept": "text/html"}, timeout=timeout, connector=conn) as session:
        tasks = [asyncio.create_task(fetch_one(session, sem, s)) for s in todo]
        done = 0
        for fut in asyncio.as_completed(tasks):
            pid, res = await fut
            existing[pid] = res
            done += 1
            if done % 100 == 0:
                print(done, flush=True)
    OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    ok = sum(1 for r in existing.values() if r.get("status") == 200 and (r.get("title") or r.get("description")))
    print(f"saved {len(existing)}; {ok} with page info")


if __name__ == "__main__":
    asyncio.run(main())
