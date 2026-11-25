import io
import itertools

import pytest
from PIL import Image

from apps.qr_management.engine import (
    QRStyle,
    StyleError,
    contrast_problems,
    is_scannable,
    render_png,
    render_svg,
)
from apps.qr_management.engine.render import prepare_logo
from apps.qr_management.engine.style import EYE_BALLS, EYE_FRAMES, FRAMES, MODULE_SHAPES

URL = "https://qrumy.com/q/Ab3xK9p"


def _logo():
    img = Image.new("RGBA", (300, 300), (79, 124, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("ms,ef,eb,fr", list(itertools.product(
    MODULE_SHAPES, EYE_FRAMES, EYE_BALLS, FRAMES))[::5])
def test_styled_codes_decode(ms, ef, eb, fr):
    style = QRStyle(module_shape=ms, eye_frame=ef, eye_ball=eb, frame=fr, cta_text="Menyuya baxın")
    assert is_scannable(URL, style)
    assert is_scannable(URL, style, _logo())


def test_png_size_and_svg_output():
    style = QRStyle(frame="bottom", cta_text="<script>x</script>")
    png = render_png(URL, style, size=512)
    with Image.open(io.BytesIO(png)) as img:
        assert img.width == 512 and img.height > 512  # frame adds a label band
    svg = render_svg(URL, style)
    assert svg.startswith("<svg") and "<script>" not in svg and "&lt;script&gt;" in svg


def test_png_size_is_clamped():
    with Image.open(io.BytesIO(render_png(URL, QRStyle(), size=99999))) as img:
        assert img.width == 4096


def test_style_validation():
    with pytest.raises(StyleError):
        QRStyle.from_dict({"fg": "red"})
    with pytest.raises(StyleError):
        QRStyle.from_dict({"module_shape": "stars"})
    s = QRStyle.from_dict({"cta_text": "x" * 100, "logo_scale": 5})
    assert len(s.cta_text) == 30 and s.logo_scale == 0.25


def test_contrast_rules():
    assert contrast_problems(QRStyle(fg="#FFFFFF", bg="#101B3A"))  # inverted
    assert contrast_problems(QRStyle(fg="#CCCCCC"))                # too light
    assert not contrast_problems(QRStyle())


def test_logo_is_reencoded_and_svg_logo_rejected():
    out = prepare_logo(_logo())
    assert out.startswith(b"\x89PNG")
    with pytest.raises(Exception):  # noqa: B017 — any decode error is fine
        prepare_logo(b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>")
