"""Render a QR layout to SVG (vector) or PNG (raster)."""

import base64
import io
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

from .layout import Layout, build_layout
from .style import QRStyle

FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "Inter-SemiBold.woff2"
MAX_PNG_SIZE = 4096
MAX_LOGO_PX = 512


def prepare_logo(raw: bytes | None) -> bytes | None:
    """Decode any supported raster image and re-encode it as a clean PNG.

    User files are never embedded as-is (no SVG, no metadata, bounded size).
    """
    if not raw:
        return None
    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGBA")
        img.thumbnail((MAX_LOGO_PX, MAX_LOGO_PX))
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def render_svg(content: str, style: QRStyle, logo: bytes | None = None) -> str:
    logo = prepare_logo(logo)
    layout = build_layout(content, style, logo)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(layout.width)} '
        f'{_fmt(layout.height)}" shape-rendering="geometricPrecision" role="img" '
        f'aria-label="QR code">'
    ]
    merged: dict[str, list[str]] = {}
    for p in layout.prims:
        if p.group == "module":
            merged.setdefault(p.color, []).append(f"M{_fmt(p.x)} {_fmt(p.y)}h1v1h-1z")
            continue
        if merged:  # flush merged module paths before drawing anything on top
            for color, d in merged.items():
                parts.append(f'<path fill="{color}" d="{"".join(d)}"/>')
            merged = {}
        if p.kind == "rect":
            rx = f' rx="{_fmt(p.r)}"' if p.r else ""
            parts.append(f'<rect x="{_fmt(p.x)}" y="{_fmt(p.y)}" width="{_fmt(p.w)}" '
                         f'height="{_fmt(p.h)}"{rx} fill="{p.color}"/>')
        elif p.kind == "circle":
            parts.append(f'<circle cx="{_fmt(p.x)}" cy="{_fmt(p.y)}" r="{_fmt(p.r)}" '
                         f'fill="{p.color}"/>')
        elif p.kind == "image":
            b64 = base64.b64encode(p.data).decode()
            parts.append(f'<image x="{_fmt(p.x)}" y="{_fmt(p.y)}" width="{_fmt(p.w)}" '
                         f'height="{_fmt(p.h)}" preserveAspectRatio="xMidYMid meet" '
                         f'href="data:image/png;base64,{b64}"/>')
        elif p.kind == "text":
            parts.append(f'<text x="{_fmt(p.x)}" y="{_fmt(p.y)}" fill="{p.color}" '
                         f'font-family="Inter, Arial, Helvetica, sans-serif" font-weight="600" '
                         f'font-size="{_fmt(p.size)}" text-anchor="middle" '
                         f'dominant-baseline="central">{escape(p.text)}</text>')
    for color, d in merged.items():
        parts.append(f'<path fill="{color}" d="{"".join(d)}"/>')
    parts.append("</svg>")
    return "".join(parts)


@lru_cache(maxsize=32)
def _font(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), px)


def _draw_png(layout: Layout, scale: float) -> Image.Image:
    w, h = round(layout.width * scale), round(layout.height * scale)
    img = Image.new("RGB", (w, h), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    def box(x, y, bw, bh):
        return [round(x * scale), round(y * scale),
                round((x + bw) * scale) - 1, round((y + bh) * scale) - 1]

    for p in layout.prims:
        if p.kind == "rect":
            if p.r:
                draw.rounded_rectangle(box(p.x, p.y, p.w, p.h), radius=p.r * scale, fill=p.color)
            else:
                draw.rectangle(box(p.x, p.y, p.w, p.h), fill=p.color)
        elif p.kind == "circle":
            draw.ellipse(box(p.x - p.r, p.y - p.r, 2 * p.r, 2 * p.r), fill=p.color)
        elif p.kind == "image":
            with Image.open(io.BytesIO(p.data)) as logo:
                logo = logo.convert("RGBA")
                target = (max(1, round(p.w * scale)), max(1, round(p.h * scale)))
                logo.thumbnail(target, Image.Resampling.LANCZOS)
                ox = round(p.x * scale) + (target[0] - logo.width) // 2
                oy = round(p.y * scale) + (target[1] - logo.height) // 2
                img.paste(logo, (ox, oy), logo)
        elif p.kind == "text":
            px = max(6, round(p.size * scale))
            font = _font(px)
            while px > 6 and draw.textlength(p.text, font=font) > p.w * scale:
                px -= 1
                font = _font(px)
            draw.text((p.x * scale, p.y * scale), p.text, fill=p.color, font=font, anchor="mm")
    return img


def render_png(content: str, style: QRStyle, size: int = 1024,
               logo: bytes | None = None) -> bytes:
    """``size`` is the output width in pixels (height follows the frame)."""
    size = max(128, min(int(size), MAX_PNG_SIZE))
    layout = build_layout(content, style, prepare_logo(logo))
    # Supersample small/medium images for smooth curves, then downscale.
    factor = 3 if size <= 1400 else (2 if size <= 2400 else 1)
    big = _draw_png(layout, size * factor / layout.width)
    img = big if factor == 1 else big.resize(
        (size, round(size * layout.height / layout.width)), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True, dpi=(300, 300))
    return out.getvalue()
