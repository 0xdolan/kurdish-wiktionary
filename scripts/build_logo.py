#!/usr/bin/env python3
# ruff: noqa: E501 - inline SVG.
"""Rebuild the 135x155 Kurdish Wiktionary logo as high-resolution vector outlines.

Each text line is shaped with HarfBuzz, turned into glyph outlines and fitted to the box that line
occupies in the official PNG, so the result needs no fonts and lines up with the original.

Usage: uv run --with uharfbuzz --with fonttools --with pillow --with numpy \
         python scripts/build_logo.py <official.png> <output.svg> [comparison.png]
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

WIDTH, HEIGHT = 135, 155
LIBERTINE_BOLD = "/usr/share/fonts/opentype/linux-libertine/LinLibertine_RB.otf"
LIBERTINE = "/usr/share/fonts/opentype/linux-libertine/LinLibertine_R.otf"
ARIAL_BOLD = "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf"
# The original is likely Tahoma Bold, which is not freely available; Sahel Bold fits it best here.
ARABIC_BOLD = "/home/dolan/.fonts/sahel-font-v3.4.0/Sahel-Bold.ttf"


@dataclass(frozen=True)
class Line:
    text: str
    font: str
    fill: str
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in logo pixels
    embossed: bool = False


LINES = (
    Line("[wikʲifɛrˈhɛŋ]", LIBERTINE, "#3c3c3c", (41.2, 7.5, 131.1, 23.9)),
    Line("Wîkîferheng", LIBERTINE_BOLD, "#000000", (4.4, 23.1, 130.2, 47.7)),
    Line("pirrzimanî", LIBERTINE, "#808080", (3.8, 43.0, 73.2, 58.2)),
    Line("Ferhenga azad", ARIAL_BOLD, "#7a7a7a", (3.8, 64.1, 105.4, 81.6)),
    Line("ویکیفەرھەنگ", ARABIC_BOLD, "#ffffff", (4.7, 83.5, 130.5, 107.5), True),
    Line("پڕزمانی", ARABIC_BOLD, "#ffffff", (83.6, 107.0, 130.3, 127.0), True),
    Line("فەرھەنگا ئازاد", ARABIC_BOLD, "#ffffff", (6.2, 135.0, 131.0, 151.5), True),
)


def shape(text: str, font_path: str) -> tuple[TTFont, list[tuple[str, float, float]]]:
    """Glyph names and positions in font units, in visual order."""
    data = Path(font_path).read_bytes()
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(hb.Font(hb.Face(data)), buffer)
    tt_font = TTFont(font_path)
    order = tt_font.getGlyphOrder()
    placed: list[tuple[str, float, float]] = []
    x = 0.0
    for info, position in zip(buffer.glyph_infos, buffer.glyph_positions, strict=True):
        placed.append((order[info.codepoint], x + position.x_offset, position.y_offset))
        x += position.x_advance
    return tt_font, placed


def outline(line: Line) -> str:
    """SVG path data for one line, scaled to exactly fill its box."""
    tt_font, placed = shape(line.text, line.font)
    glyphs = tt_font.getGlyphSet()
    bounds = BoundsPen(glyphs)
    for name, x, y in placed:
        glyphs[name].draw(TransformPen(bounds, (1, 0, 0, 1, x, y)))
    x_min, y_min, x_max, y_max = bounds.bounds
    x0, y0, x1, y1 = line.box
    scale_x = (x1 - x0) / (x_max - x_min)
    scale_y = (y1 - y0) / (y_max - y_min)
    pen = SVGPathPen(glyphs, ntos=lambda value: f"{value:.3f}".rstrip("0").rstrip("."))
    for name, x, y in placed:
        # Font y points up, SVG y points down.
        transform = (
            scale_x,
            0,
            0,
            -scale_y,
            x0 + (x - x_min) * scale_x,
            y1 + (y_min - y) * scale_y,
        )
        glyphs[name].draw(TransformPen(pen, transform))
    return pen.getCommands()


def build_svg() -> str:
    flat = "\n".join(
        f'  <path fill="{line.fill}" d="{outline(line)}"/>' for line in LINES if not line.embossed
    )
    embossed = "\n".join(
        f'  <path fill="{line.fill}" filter="url(#emboss)" d="{outline(line)}"/>'
        for line in LINES
        if line.embossed
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="1080" height="1240" role="img" aria-label="Wîkîferheng">
  <title>Wîkîferheng, the Kurdish Wiktionary</title>
  <desc>Vector redraw of Wiktionary-logo-ku.png (Wikimedia Commons, CC BY-SA 3.0). Wiktionary and its logo are trademarks of the Wikimedia Foundation.</desc>
  <defs>
    <filter id="emboss" x="-5%" y="-20%" width="110%" height="150%" color-interpolation-filters="sRGB">
      <feDropShadow dx="0.7" dy="1" stdDeviation="0.8" flood-color="#4a4a4a" flood-opacity="1"/>
    </filter>
  </defs>
{flat}
{embossed}
</svg>
"""


def render(svg_path: Path, png_path: Path, scale: int, background: str) -> None:
    html = png_path.with_suffix(".html")
    html.write_text(
        f"<!doctype html><style>*{{margin:0}}html,body{{background:{background}}}"
        f"img{{display:block;width:{WIDTH * scale}px;height:{HEIGHT * scale}px}}</style>"
        f'<img src="{svg_path.resolve().as_uri()}">',
        encoding="utf-8",
    )
    subprocess.run(
        [
            "google-chrome",
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            "--default-background-color=FFFFFFFF",
            f"--window-size={WIDTH * scale},{HEIGHT * scale}",
            f"--screenshot={png_path}",
            html.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def compare(official: Path, svg_path: Path, output: Path | None) -> float:
    """Mean absolute grey difference (0 to 255) at the original size, and a side-by-side image."""
    with tempfile.TemporaryDirectory() as folder:
        large = Path(folder) / "large.png"
        render(svg_path, large, 8, "#fff")
        ours_large = Image.open(large).convert("L")
    ours = ours_large.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    base = Image.new("RGBA", (WIDTH, HEIGHT), "white")
    base.alpha_composite(Image.open(official).convert("RGBA"))
    theirs = base.convert("L")
    difference = float(np.abs(np.asarray(ours, float) - np.asarray(theirs, float)).mean())
    if output is not None:
        zoom = 6
        canvas = Image.new("L", (WIDTH * zoom * 3 + 40, HEIGHT * zoom), 255)
        canvas.paste(theirs.resize((WIDTH * zoom, HEIGHT * zoom), Image.Resampling.NEAREST), (0, 0))
        canvas.paste(
            ours.resize((WIDTH * zoom, HEIGHT * zoom), Image.Resampling.NEAREST),
            (WIDTH * zoom + 20, 0),
        )
        canvas.paste(
            ours_large.resize((WIDTH * zoom, HEIGHT * zoom), Image.Resampling.LANCZOS),
            (WIDTH * zoom * 2 + 40, 0),
        )
        canvas.save(output)
    return difference


def main() -> None:
    official, svg_path = Path(sys.argv[1]), Path(sys.argv[2])
    svg_path.write_text(build_svg(), encoding="utf-8")
    report = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    print(f"mean grey difference from the official PNG: {compare(official, svg_path, report):.2f}/255")


if __name__ == "__main__":
    main()
