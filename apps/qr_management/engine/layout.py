"""Turns a QR matrix + style into drawing primitives in *module units*.

Both renderers (SVG, PNG) draw the same primitives, so exports look identical.
"""

from dataclasses import dataclass, field

import segno

from .style import QRStyle

BORDER = 4  # quiet zone in modules (QR spec minimum)


@dataclass
class Prim:
    kind: str  # rect | circle | text | image
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    r: float = 0          # corner radius (rect) or radius (circle)
    color: str = "#000"
    text: str = ""
    size: float = 0       # font size (text)
    data: bytes = b""     # image bytes (PNG)
    group: str = ""       # "module" for plain modules (SVG path merging)


@dataclass
class Layout:
    width: float
    height: float
    prims: list[Prim] = field(default_factory=list)


def make_matrix(content: str, has_logo: bool) -> list[list[bool]]:
    qr = segno.make(content, error="h" if has_logo else "m", micro=False,
                    boost_error=not has_logo)
    return [[bool(v) for v in row] for row in qr.matrix]


def _in_finder(r: int, c: int, n: int) -> bool:
    return (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7)


def _shape(kind, x, y, size, color, rounded_r, circle) -> Prim:
    if kind == "circle":
        return Prim("circle", x + size / 2, y + size / 2, r=circle, color=color)
    return Prim("rect", x, y, size, size, r=rounded_r if kind == "rounded" else 0, color=color)


def build_layout(content: str, style: QRStyle, logo: bytes | None = None) -> Layout:
    matrix = make_matrix(content, has_logo=bool(logo))
    n = len(matrix)
    code_size = n + 2 * BORDER

    # Frame geometry
    pad = 0.0
    band = 0.0
    top_band = bottom_band = 0.0
    if style.frame in ("bottom", "top"):
        pad, band = 1.2, 6.0
        if style.frame == "bottom":
            bottom_band = band
        else:
            top_band = band
    elif style.frame == "pill":
        bottom_band = 7.0

    width = code_size + 2 * pad
    height = code_size + 2 * pad + top_band + bottom_band
    ox, oy = pad, pad + top_band  # origin of the code square (incl. quiet zone)
    prims: list[Prim] = []

    # Canvas background
    if style.frame in ("bottom", "top"):
        prims.append(Prim("rect", 0, 0, width, height, r=2.4, color=style.frame_fill))
        prims.append(Prim("rect", ox, oy, code_size, code_size, r=1.4, color=style.bg))
    else:
        prims.append(Prim("rect", 0, 0, width, height, color=style.bg))

    # Logo area to clear (centered, in modules)
    logo_box = None
    if logo:
        size = round(n * style.logo_scale)
        size += (n - size) % 2  # keep it centered on the module grid
        start = (n - size) // 2
        logo_box = (start - 1, start - 1, start + size + 1, start + size + 1)

    qx, qy = ox + BORDER, oy + BORDER
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if not dark or _in_finder(r, c, n):
                continue
            if logo_box and logo_box[0] <= c < logo_box[2] and logo_box[1] <= r < logo_box[3]:
                continue
            if style.module_shape == "dots":
                p = Prim("circle", qx + c + 0.5, qy + r + 0.5, r=0.46, color=style.fg)
            elif style.module_shape == "rounded":
                p = Prim("rect", qx + c + 0.04, qy + r + 0.04, 0.92, 0.92, r=0.32,
                         color=style.fg)
            else:
                p = Prim("rect", qx + c, qy + r, 1, 1, color=style.fg, group="module")
            prims.append(p)

    # Finder patterns ("eyes")
    for (r, c) in ((0, 0), (0, n - 7), (n - 7, 0)):
        x, y = qx + c, qy + r
        if style.eye_frame == "circle":
            prims.append(Prim("circle", x + 3.5, y + 3.5, r=3.5, color=style.eye))
            prims.append(Prim("circle", x + 3.5, y + 3.5, r=2.5, color=style.bg))
        else:
            rr = (2.1, 1.3) if style.eye_frame == "rounded" else (0, 0)
            prims.append(Prim("rect", x, y, 7, 7, r=rr[0], color=style.eye))
            prims.append(Prim("rect", x + 1, y + 1, 5, 5, r=rr[1], color=style.bg))
        if style.eye_frame == "circle" and style.eye_ball == "square":
            # Sharp square corners sit too close to a round frame for reliable detection
            # once a logo removes part of the error-correction budget; soften them.
            prims.append(Prim("rect", x + 2, y + 2, 3, 3, r=0.6, color=style.ball))
        else:
            prims.append(_shape(style.eye_ball, x + 2, y + 2, 3, style.ball, 0.9, 1.5))

    # Logo (drawn on a background tile so modules never touch it)
    if logo_box:
        x0, y0, x1, y1 = logo_box
        tile = Prim("rect", qx + x0, qy + y0, x1 - x0, y1 - y0, r=1.0, color=style.bg)
        prims.append(tile)
        inset = 1.0
        prims.append(Prim("image", tile.x + inset, tile.y + inset, tile.w - 2 * inset,
                          tile.h - 2 * inset, data=logo))

    # Call-to-action text
    text = style.cta_text
    if style.frame in ("bottom", "top") and text:
        ty = (oy + code_size + pad + band / 2) if style.frame == "bottom" else (pad + band / 2)
        prims.append(Prim("text", width / 2, ty, text=text, size=min(3.0, band * 0.5),
                          color=style.bg, w=width - 4))
    elif style.frame == "pill" and text:
        pill_w = min(code_size - 2, max(14.0, len(text) * 1.75 + 6))
        px = (width - pill_w) / 2
        py = oy + code_size + 0.8
        prims.append(Prim("rect", px, py, pill_w, 5.2, r=2.6, color=style.frame_fill))
        prims.append(Prim("text", width / 2, py + 2.6, text=text, size=2.4, color=style.bg,
                          w=pill_w - 2))
    return Layout(width=width, height=height, prims=prims)
