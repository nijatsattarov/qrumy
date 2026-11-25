"""Scannability safeguards: color contrast rules and a real decode test."""

import io

import zxingcpp
from django.utils.translation import gettext as _
from PIL import Image

from .render import render_png
from .style import QRStyle


def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


MIN_CONTRAST = 4.0


def contrast_problems(style: QRStyle) -> list[str]:
    problems = []
    if _luminance(style.fg) >= _luminance(style.bg):
        problems.append(_("Use a dark code color on a light background — many scanners "
                          "cannot read inverted codes."))
    for color in {style.fg, style.eye, style.ball}:
        if contrast_ratio(color, style.bg) < MIN_CONTRAST:
            problems.append(_("Increase the contrast between the code colors and the "
                              "background."))
            break
    if style.frame in ("bottom", "top", "pill") and style.cta_text and \
            contrast_ratio(style.frame_fill, style.bg) < 3:
        problems.append(_("The frame color is too close to the background color."))
    return problems


def is_scannable(content: str, style: QRStyle, logo: bytes | None = None) -> bool:
    """Render the design and decode it with ZXing. True only if the content round-trips."""
    png = render_png(content, style, size=600, logo=logo)
    with Image.open(io.BytesIO(png)) as img:
        results = zxingcpp.read_barcodes(img.convert("L"))
    return any(r.text == content for r in results)
