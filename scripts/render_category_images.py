#!/usr/bin/env python3
"""Render one branded 1200x630 featured image per statewide category (plus the hub).

Outputs are committed under assets/category-images/; the site build copies the
ones it needs to /images/category/. Local-only (Pillow):

    python3 scripts/render_category_images.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import categories as cat  # noqa: E402
from render_city_images import BLACK, GREY, H, ICON, ORANGE, W, WHITE, font, wrap  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "category-images"


def render(title: str, slug: str, icon: Image.Image) -> None:
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([760, 0, W, H], fill=BLACK)
    d.rectangle([748, 0, 760, H], fill=ORANGE)
    mark = icon.resize((300, 300), Image.LANCZOS)
    img.paste(mark, (760 + (440 - 300) // 2, 120), mark if mark.mode == "RGBA" else None)
    d.text((760 + 220, 470), "PhotoStudiosTexas.com", font=font(26, 600), fill=WHITE, anchor="mm")
    d.rectangle([64, 96, 64 + 84, 96 + 8], fill=ORANGE)
    d.text((64, 128), "STATEWIDE CATEGORY", font=font(26, 700), fill=ORANGE)
    f, lines = wrap(d, title, 104, 640, max_lines=3)
    y = 186
    for line in lines:
        d.text((64, y), line, font=f, fill=BLACK)
        y += int(f.size * 1.12)
    d.text((64, H - 86), "Studios with real evidence they offer it,", font=font(28, 500), fill=GREY)
    d.text((64, H - 52), "with ratings, hours, and contact details.", font=font(28, 500), fill=GREY)
    img = img.quantize(colors=24, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    img.save(OUT / f"{slug}.png", optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = Image.open(ICON).convert("RGBA")
    items = [(c[3], c[1]) for c in cat.CATEGORIES] + [("Photo Studio Categories in Texas", "categories")]
    for title, slug in items:
        render(title, slug, icon)
    print(f"Rendered {len(items)} category images to {OUT}")


if __name__ == "__main__":
    main()
