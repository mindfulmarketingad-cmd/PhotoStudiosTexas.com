#!/usr/bin/env python3
"""Render one branded 1200x630 featured image per city (white, orange, black).

Outputs are committed under assets/city-images/ (palette PNG, about 15-25 KB).
The site build copies them to /images/city/. Local-only (Pillow); Vercel does
not run this. Re-run when cities change:

    python3 scripts/render_city_images.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "city-images"
ICON = ROOT / "assets" / "brand" / "icon-512.png"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf",
    "/usr/share/fonts/truetype/macos/Inter-SemiBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
W, H = 1200, 630
BLACK, ORANGE, WHITE, GREY = (17, 17, 17), (232, 93, 4), (255, 255, 255), (92, 86, 79)


def font(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            f = ImageFont.truetype(path, size)
            try:
                f.set_variation_by_axes([14, weight])  # opsz, wght for Inter variable
            except Exception:  # noqa: BLE001
                pass
            return f
    return ImageFont.load_default()


def wrap(draw, text, size, max_width, weight=700, max_lines=2):
    for current in range(size, 40, -4):
        f = font(current, weight)
        words, lines, line = text.split(), [], ""
        for word in words:
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=f) <= max_width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= max_width for l in lines):
            return f, lines
    return font(40, weight), [text]


def render(city: str, slug: str, icon: Image.Image) -> None:
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    # right black panel with logo mark, orange divider
    d.rectangle([760, 0, W, H], fill=BLACK)
    d.rectangle([748, 0, 760, H], fill=ORANGE)
    mark = icon.resize((300, 300), Image.LANCZOS)
    img.paste(mark, (760 + (440 - 300) // 2, 120), mark if mark.mode == "RGBA" else None)
    sf = font(26, 600)
    d.text((760 + 220, 470), "PhotoStudiosTexas.com", font=sf, fill=WHITE, anchor="mm")
    # left: eyebrow, city, label
    d.rectangle([64, 96, 64 + 84, 96 + 8], fill=ORANGE)
    d.text((64, 128), "PHOTO STUDIOS IN TEXAS", font=font(26, 700), fill=ORANGE)
    f, lines = wrap(d, city, 120, 640, max_lines=2)
    y = 190
    for line in lines:
        d.text((64, y), line, font=f, fill=BLACK)
        y += int(f.size * 1.12)
    d.text((64, H - 150), "Texas", font=font(54, 600), fill=BLACK)
    d.text((64, H - 86), "Browse photo studios by specialty,", font=font(28, 500), fill=GREY)
    d.text((64, H - 52), "hours, ratings, and contact details.", font=font(28, 500), fill=GREY)
    img = img.quantize(colors=24, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    img.save(OUT / f"{slug}.png", optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = Image.open(ICON).convert("RGBA")
    studios = json.loads((ROOT / "data" / "studios.json").read_text(encoding="utf-8"))["studios"]
    cities = {s["city_slug"]: s["city"] for s in studios}
    for slug, city in sorted(cities.items()):
        render(city, slug, icon)
    # state-level image reused for the Texas hub if wanted
    print(f"Rendered {len(cities)} city images to {OUT}")


if __name__ == "__main__":
    main()
