#!/usr/bin/env python3
"""Render the PhotoStudiosTexas logo, favicons, and social image.

Outputs are committed under assets/brand/. The site build copies them.
This script is local-only (Pillow, fontTools, CairoSVG). Vercel does not run it.

    python3 scripts/render_brand.py
"""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path

import cairosvg
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand"


def find_font() -> Path:
    candidates = [
        Path("/usr/share/fonts/truetype/macos/Inter-SemiBold.ttf"),
        Path("/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf"),
        Path("/Library/Fonts/Inter-SemiBold.ttf"),
        Path.home() / "Library/Fonts/Inter-SemiBold.ttf",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    import subprocess
    match = subprocess.run(
        ["fc-match", "-f", "%{file}", "Inter:weight=600"],
        capture_output=True,
        text=True,
        check=False,
    )
    found = Path(match.stdout.strip()) if match.stdout.strip() else None
    if found and found.is_file():
        return found
    raise SystemExit("Inter SemiBold was not found. Install Inter, then re-run this script.")


FONT_PATH = find_font()

BLACK = "#111111"
ORANGE = "#e85d04"
WHITE = "#ffffff"

SUBSET_TEXT = (
    "PhotoStudiosTexas.com www.photostudiostexas.com "
    "A directory of photo studios across Texas"
)


def star_points(cx: float, cy: float, outer: float, inner: float, count: int = 5) -> list[tuple[float, float]]:
    points = []
    for index in range(count * 2):
        radius = outer if index % 2 == 0 else inner
        angle = math.radians(-90 + index * (180 / count))
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def blade_points(cx: float, cy: float, index: int) -> list[tuple[float, float]]:
    """One twisted shutter blade. Six of these read as an aperture."""
    samples = 12
    outer_radius = 23.4
    inner_radius = 15.5
    sweep = 46
    twist = 26
    start = -90 + index * 60 + 6
    points = []
    for step in range(samples + 1):
        angle = math.radians(start + sweep * step / samples)
        points.append((cx + outer_radius * math.cos(angle), cy + outer_radius * math.sin(angle)))
    for step in range(samples, -1, -1):
        angle = math.radians(start + twist + sweep * step / samples)
        points.append((cx + inner_radius * math.cos(angle), cy + inner_radius * math.sin(angle)))
    return points


def path_from_points(points: list[tuple[float, float]]) -> str:
    commands = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    commands.append("Z")
    return " ".join(commands)


def mark_elements(star_fill: str, knockout: str) -> str:
    blades = "\n".join(
        f'    <path fill="{ORANGE}" d="{path_from_points(blade_points(32, 32, index))}"/>'
        for index in range(6)
    )
    star = path_from_points(star_points(32, 32, 11.4, 4.7))
    return f"""    <circle cx="32" cy="32" r="27.2" fill="none" stroke="{ORANGE}" stroke-width="2.4"/>
{blades}
    <circle cx="32" cy="32" r="14.3" fill="{knockout}"/>
    <path fill="{star_fill}" d="{star}"/>"""


def subset_font_data() -> bytes:
    font = TTFont(FONT_PATH)
    options = Options()
    options.layout_features = ["*"]
    options.desubroutinize = True
    options.name_IDs = ["*"]
    options.notdef_outline = True
    subsetter = Subsetter(options=options)
    subsetter.populate(text=SUBSET_TEXT)
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


def font_css(font_data: bytes) -> str:
    encoded = base64.b64encode(font_data).decode("ascii")
    return f"""@font-face {{
      font-family: "PhotoStudiosTexas";
      src: url("data:font/ttf;base64,{encoded}") format("truetype");
      font-weight: 600;
      font-style: normal;
    }}"""


def text_width(text: str, size: int) -> float:
    from PIL import ImageFont

    font = ImageFont.truetype(str(FONT_PATH), size)
    return float(font.getlength(text))


def logo_svg(word_fill: str, star_fill: str, knockout: str, font_data: bytes) -> tuple[str, float]:
    size = 23
    photo_width = text_width("PhotoStudios", size)
    texas_width = text_width("Texas", size)
    text_x = 52
    texas_x = text_x + photo_width + 8
    width = math.ceil(texas_x + texas_width + 1)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 48" role="img" aria-labelledby="title">
  <title id="title">PhotoStudiosTexas</title>
  <style>{font_css(font_data)}</style>
  <svg x="0" y="4" width="40" height="40" viewBox="0 0 64 64">
{mark_elements(star_fill, knockout)}
  </svg>
  <text x="{text_x:.2f}" y="33" fill="{word_fill}" font-family="PhotoStudiosTexas, Inter, Helvetica, Arial, sans-serif" font-size="{size}" font-weight="600">PhotoStudios</text>
  <text x="{texas_x:.2f}" y="33" fill="{ORANGE}" font-family="PhotoStudiosTexas, Inter, Helvetica, Arial, sans-serif" font-size="{size}" font-weight="600">Texas</text>
</svg>
"""
    return svg, width


def icon_svg(star_fill: str = WHITE, rounded: bool = False, pad: float = 0) -> str:
    radius = 14 if rounded else 0
    background = f'<rect width="64" height="64" rx="{radius}" fill="{BLACK}"/>'
    if pad:
        inner = 64 * (1 - pad * 2)
        offset = 64 * pad
        transform = f' transform="translate({offset:.2f} {offset:.2f}) scale({inner / 64:.4f})"'
    else:
        transform = ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  {background}
  <g{transform}>
{mark_elements(star_fill, BLACK)}
  </g>
</svg>
"""


def og_svg(font_data: bytes) -> str:
    logo, logo_width = logo_svg(WHITE, WHITE, BLACK, font_data)
    logo_height = 560 * 48 / logo_width
    placed_logo = logo.replace(
        "<svg ",
        f'<svg x="76" y="176" width="560" height="{logo_height:.2f}" ',
        1,
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <style>{font_css(font_data)}</style>
  <rect width="1200" height="630" fill="{BLACK}"/>
  <rect width="14" height="630" fill="{ORANGE}"/>
  {placed_logo}
  <text x="80" y="360" fill="{WHITE}" font-family="PhotoStudiosTexas, Inter, Helvetica, Arial, sans-serif" font-size="32" font-weight="600">Photo studios across Texas</text>
  <rect x="80" y="392" width="92" height="6" fill="{ORANGE}"/>
  <text x="80" y="520" fill="{ORANGE}" font-family="PhotoStudiosTexas, Inter, Helvetica, Arial, sans-serif" font-size="22" font-weight="600">www.photostudiostexas.com</text>
  <svg x="830" y="155" width="300" height="300" viewBox="0 0 64 64">
{mark_elements(WHITE, BLACK)}
  </svg>
</svg>
"""


def render_png(svg: str, width: int, height: int) -> Image.Image:
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width, output_height=height)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font_data = subset_font_data()
    light, light_width = logo_svg(WHITE, WHITE, BLACK, font_data)
    dark, dark_width = logo_svg(BLACK, BLACK, WHITE, font_data)
    (OUT / "logo-light.svg").write_text(light, encoding="utf-8")
    (OUT / "logo-dark.svg").write_text(dark, encoding="utf-8")

    favicon = icon_svg(rounded=True, pad=0.06)
    (OUT / "favicon.svg").write_text(favicon, encoding="utf-8")

    ico_image = render_png(icon_svg(rounded=False, pad=0.08), 32, 32).convert("RGBA")
    ico_16 = render_png(icon_svg(rounded=False, pad=0.08), 16, 16).convert("RGBA")
    ico_image.save(OUT / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32)], append_images=[ico_16])

    render_png(icon_svg(rounded=False, pad=0.1), 180, 180).save(OUT / "apple-touch-icon.png", format="PNG")
    render_png(icon_svg(rounded=False, pad=0.1), 192, 192).save(OUT / "icon-192.png", format="PNG")
    render_png(icon_svg(rounded=False, pad=0.1), 512, 512).save(OUT / "icon-512.png", format="PNG")
    render_png(og_svg(font_data), 1200, 630).convert("RGB").save(OUT / "og-image.png", format="PNG", optimize=True)

    manifest = """{
  "name": "PhotoStudiosTexas.com",
  "short_name": "PhotoStudiosTX",
  "description": "Directory of photo studios in Texas.",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#111111",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    }
  ]
}
"""
    (OUT / "site.webmanifest").write_text(manifest, encoding="utf-8")
    print(f"logo viewBox width light={light_width} dark={dark_width}")
    print(f"wrote brand assets to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
