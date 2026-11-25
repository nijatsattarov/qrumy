"""QR design options. Stored as JSON on QRCode.style; validated on every load."""

import re
from dataclasses import asdict, dataclass, fields

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

MODULE_SHAPES = ("square", "rounded", "dots")
EYE_FRAMES = ("square", "rounded", "circle")
EYE_BALLS = ("square", "rounded", "circle")
FRAMES = ("none", "bottom", "top", "pill")
CTA_MAX = 30


class StyleError(ValueError):
    pass


@dataclass
class QRStyle:
    fg: str = "#101B3A"
    bg: str = "#FFFFFF"
    eye_color: str = ""        # "" = same as fg
    eye_ball_color: str = ""   # "" = same as eye_color
    module_shape: str = "square"
    eye_frame: str = "square"
    eye_ball: str = "square"
    frame: str = "none"
    frame_color: str = ""      # "" = same as fg
    cta_text: str = ""
    logo_scale: float = 0.22   # logo width as a fraction of the code width

    @classmethod
    def from_dict(cls, data: dict | None) -> "QRStyle":
        data = data or {}
        known = {f.name for f in fields(cls)}
        style = cls(**{k: v for k, v in data.items() if k in known})
        style.validate()
        return style

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        for name in ("fg", "bg"):
            if not HEX.match(getattr(self, name) or ""):
                raise StyleError(f"Invalid color for {name}")
        for name in ("eye_color", "eye_ball_color", "frame_color"):
            value = getattr(self, name)
            if value and not HEX.match(value):
                raise StyleError(f"Invalid color for {name}")
        if self.module_shape not in MODULE_SHAPES:
            raise StyleError("Invalid module shape")
        if self.eye_frame not in EYE_FRAMES or self.eye_ball not in EYE_BALLS:
            raise StyleError("Invalid eye shape")
        if self.frame not in FRAMES:
            raise StyleError("Invalid frame")
        self.cta_text = (self.cta_text or "").strip()[:CTA_MAX]
        try:
            self.logo_scale = float(self.logo_scale)
        except (TypeError, ValueError) as exc:
            raise StyleError("Invalid logo size") from exc
        self.logo_scale = min(max(self.logo_scale, 0.12), 0.25)

    # Resolved colors
    @property
    def eye(self) -> str:
        return self.eye_color or self.fg

    @property
    def ball(self) -> str:
        return self.eye_ball_color or self.eye

    @property
    def frame_fill(self) -> str:
        return self.frame_color or self.fg
