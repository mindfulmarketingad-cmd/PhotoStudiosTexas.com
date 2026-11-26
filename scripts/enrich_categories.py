#!/usr/bin/env python3
"""Collect extra public evidence from each studio's own homepage for category pages.

For every studio with a website this reads the homepage once and saves, per
place_id: title, meta/og descriptions, navigation/link labels with their URL
paths, headings (h1-h4), and short visible-text snippets that mention a
category keyword. It stores facts the studio published itself, nothing else.
Output: data/website-evidence.json (used by scripts/generate_category_evidence.py).

Dev-only (needs aiohttp, beautifulsoup4, lxml); scripts/build.py stays stdlib:

    python3 scripts/enrich_categories.py            # fetch missing entries
    python3 scripts/enrich_categories.py --refresh  # refetch everything
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
OUT = ROOT / "data" / "website-evidence.json"
import os

UA = os.environ.get("PSTX_UA") or "Mozilla/5.0 (compatible; PhotoStudiosTexasBot/1.0; +https://photostudiostexas.com)"
MAX_SUBPAGES = 10
SKIP_HOSTS = ("facebook.com", "instagram.com", "linktr.ee", "google.com", "goo.gl", "yelp.com", "fiverr.com")
SERVICE_PAGE = re.compile(
    r"services?|pricing|prices|packages?|investment|sessions?|offerings?|what[- ]we|photography|portfolio|gallery|galleries|"
    r"seniors?|kids|children|newborn|events?|couples?|engagement|anniversary|proposal|graduat|homecoming|formal|mini|about|specialt|experience|studio|christmas|holiday|santa|grads?|natural[- ]light|daylight|backdrop|props?|rental",
    re.I,
)
KEYWORD = re.compile(r"portrait|head\s?-?shots?|wedding|bridal|maternity|pregnan|\bproms?\b|\bfamil(y|ies)\b|christmas|\bsanta\b|holiday|\bgraduation\b|\bgrads?\b|cap[\s-]*(?:and|&)?[\s-]*gown|newborn|boudoir|quincea|senior|pets?|drone|aerial|passport|videograph|photobooth|photo[- ]?booth|restoration|workshop|natural[- ]light|natural lighting|daylight|north[- ]facing|sunlit|sun[- ]lit|window[- ]light|prop[- ]rental|backdrop[- ]rental|prop library|equipment rental|set rental|\bcouples?\b|engagement|anniversary|proposal", re.I)


def clean(text, limit):
    if not text:
        return None
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text[:limit] if text else None


def parse(html: str, base_host: str = "") -> dict:
    soup = BeautifulSoup(html, "lxml")
    out: dict = {
        "title": clean(soup.title.string if soup.title and soup.title.string else None, 200),
        "meta": [],
        "links": [],
        "headings": [],
        "snippets": [],
        "_candidates": [],
    }
    for attrs in ({"name": "description"}, {"property": "og:description"}, {"property": "og:title"},
                  {"name": "twitter:description"}):
        tag = soup.find("meta", attrs=attrs)
        value = clean(tag.get("content") if tag else None, 400)
        if value and value not in out["meta"]:
            out["meta"].append(value)
    seen = set()
    for a in soup.find_all("a", href=True):
        label = clean(a.get_text(" "), 70) or ""
        href = a["href"].strip()
        parsed = urlparse(href)
        path = parsed.path or ""
        if parsed.netloc and not re.search(r"\.", parsed.netloc):
            continue
        key = (label.lower(), path.lower())
        if key in seen or not (label or path.strip("/")):
            continue
        seen.add(key)
        if (not parsed.netloc or parsed.netloc.lower().removeprefix("www.") == base_host) and path and path != "/" \
                and not re.search(r"\.(jpe?g|png|gif|pdf|zip|webp|svg)$", path, re.I):
            if KEYWORD.search(label) or KEYWORD.search(path) or SERVICE_PAGE.search(label) or SERVICE_PAGE.search(path):
                out["_candidates"].append(href)
        if KEYWORD.search(label) or KEYWORD.search(path):
            out["links"].append([label, path[:120]])
        if len(out["links"]) >= 40 and len(out["_candidates"]) >= 60:
            break
    for tag in soup.find_all(["h1", "h2", "h3", "h4"], limit=60):
        label = clean(tag.get_text(" "), 120)
        if label and KEYWORD.search(label) and label not in out["headings"]:
            out["headings"].append(label)
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    text = clean(soup.get_text(" "), 400_000) or ""
    for sentence in re.split(r"(?<=[.!?])\s+|\s{2,}|\s[|•·]\s", text):
        sentence = sentence.strip()
        if 12 <= len(sentence) <= 400 and KEYWORD.search(sentence):
            sentence = sentence[:240]
            if sentence not in out["snippets"]:
                out["snippets"].append(sentence)
        if len(out["snippets"]) >= 25:
            break
    return out


async def read_capped(resp, cap: int) -> bytes:
    data = bytearray()
    async for chunk in resp.content.iter_chunked(65536):
        data += chunk
        if len(data) >= cap:
            break
    return bytes(data)


async def fetch_one(session, sem, studio):
    raw = studio["website"].strip()
    if not raw.lower().startswith(("http://", "https://")):
        raw = "https://" + raw
    url = re.split(r"(?:\?|%3[Ff])", raw, maxsplit=1)[0]
    host = urlparse(url).netloc.lower().removeprefix("www.")
    result: dict = {"url": url}
    if any(host.endswith(h) for h in SKIP_HOSTS):
        result["status"] = "skipped"
        return studio["place_id"], result
    candidates = [url]
    if url.startswith("http://"):
        candidates.insert(0, "https://" + url[7:])
    async with sem:
        for candidate in candidates:
            try:
                async with session.get(candidate, allow_redirects=True, max_redirects=5) as resp:
                    result["status"] = resp.status
                    ctype = resp.headers.get("content-type", "")
                    if resp.status == 200 and "html" in ctype.lower():
                        body = await read_capped(resp, 900_000)
                        final = str(resp.url)
                        host_now = urlparse(final).netloc.lower().removeprefix("www.")
                        result.update(parse(body.decode(resp.charset or "utf-8", errors="replace"), host_now))
                        result["final_url"] = final
                        break
            except Exception as exc:  # noqa: BLE001
                result["status"] = f"error:{type(exc).__name__}"
    candidates_found = result.pop("_candidates", [])
    if result.get("status") == 200 and candidates_found:
        base = result.get("final_url") or url
        seen_urls = {base.rstrip("/")}
        picked = []
        for href in candidates_found:
            absolute = urljoin(base, href.split("#")[0])
            key = absolute.rstrip("/")
            if key in seen_urls or urlparse(absolute).scheme not in ("http", "https"):
                continue
            if re.search(r"/(blog|news|post|tag|category|author|cart|checkout|login|account)(/|$)|/20\d\d/", absolute, re.I):
                continue
            seen_urls.add(key)
            picked.append(absolute)
            if len(picked) >= MAX_SUBPAGES:
                break
        pages = []
        async with sem:
            for absolute in picked:
                try:
                    async with session.get(absolute, allow_redirects=True, max_redirects=4) as resp:
                        if resp.status == 200 and "html" in resp.headers.get("content-type", "").lower():
                            body = await read_capped(resp, 600_000)
                            sub = parse(body.decode(resp.charset or "utf-8", errors="replace"), urlparse(str(resp.url)).netloc.lower().removeprefix("www."))
                            sub.pop("_candidates", None)
                            sub["path"] = urlparse(str(resp.url)).path[:120]
                            sub.pop("links", None)
                            pages.append(sub)
                except Exception:  # noqa: BLE001
                    pass
        result["pages"] = pages
    return studio["place_id"], result


async def main() -> None:
    refresh = "--refresh" in sys.argv
    studios = [s for s in json.loads(STUDIOS.read_text())["studios"] if s.get("website")]
    existing = {}
    if OUT.exists() and not refresh:
        existing = {k: v for k, v in json.loads(OUT.read_text()).items() if str(v.get("status")) == "200"}
    todo = [s for s in studios if s["place_id"] not in existing]
    print(f"{len(studios)} websites, {len(todo)} to fetch", flush=True)
    sem = asyncio.Semaphore(40)
    timeout = aiohttp.ClientTimeout(total=20, connect=8)
    conn = aiohttp.TCPConnector(limit=80, ssl=False)
    headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
    async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=conn) as session:
        tasks = [asyncio.create_task(fetch_one(session, sem, s)) for s in todo]
        done = 0
        for fut in asyncio.as_completed(tasks):
            pid, res = await fut
            existing[pid] = res
            done += 1
            if done % 200 == 0:
                print(done, flush=True)
    OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    ok = sum(1 for r in existing.values() if r.get("status") == 200)
    print(f"saved {len(existing)}; {ok} fetched OK")


if __name__ == "__main__":
    asyncio.run(main())
