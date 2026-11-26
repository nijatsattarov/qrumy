"""Branded cover images (1200×630) for blog posts without their own photo."""

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = (Path(__file__).resolve().parent.parent / "qr_management" / "fonts"
        / "Inter-SemiBold.woff2")
NAVY, NAVY_2, ACCENT = (16, 27, 58), (29, 46, 91), (79, 124, 255)


def make_cover(title: str, label: str = "Qrumy") -> bytes:
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), NAVY)
    draw = ImageDraw.Draw(img)
    for y in range(h):  # soft vertical gradient
        t = y / h
        shade = tuple(int(a + (b - a) * t) for a, b in zip(NAVY, NAVY_2, strict=True))
        draw.line([(0, y), (w, y)], fill=shade)
    # Decorative QR-like squares on the right.
    cell, ox, oy = 26, 820, 150
    for r in range(12):
        for c in range(12):
            in_finder = (r < 4 and (c < 4 or c > 7)) or (r > 7 and c < 4)
            if not in_finder and (r * 7 + c * 3 + r * c) % 5 in (0, 2):
                draw.rounded_rectangle([ox + c * cell, oy + r * cell, ox + c * cell + 20,
                                        oy + r * cell + 20], 5, fill=(60, 82, 140))
    for fx, fy in ((ox, oy), (ox + 9 * cell, oy), (ox, oy + 9 * cell)):
        draw.rounded_rectangle([fx, fy, fx + 3 * cell - 6, fy + 3 * cell - 6], 12, outline=ACCENT,
                               width=10)
    font_title = ImageFont.truetype(str(FONT), 54)
    font_label = ImageFont.truetype(str(FONT), 26)
    draw.text((80, 80), label.upper(), font=font_label, fill=ACCENT)
    y = 150
    for line in textwrap.wrap(title, width=24)[:5]:
        draw.text((80, y), line, font=font_title, fill=(255, 255, 255))
        y += 70
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()
