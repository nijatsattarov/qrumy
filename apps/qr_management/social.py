"""Social and contact platforms for link pages (multi-link, Qrumy Card).

Each platform has a brand colour, a simple white symbol (24×24, drawn for Qrumy — not
the brands' official logo files), how to turn a username into a link, and the domains
used to recognise a pasted link.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import quote, urlsplit

from django.utils.translation import gettext_lazy as _

# Symbols use stroke="currentColor" unless the path is marked solid with "F:".
SYMBOLS = {
    "camera": '<rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3.6"/>'
              '<circle cx="17" cy="7" r=".9" fill="currentColor" stroke="none"/>',
    "f": '<path d="M14.5 21v-7h2.6l.4-3h-3V9.2c0-.9.3-1.5 1.6-1.5h1.6V5.1c-.3 0-1.2-.1-2.3-.1'
         '-2.3 0-3.9 1.4-3.9 4V11H9v3h2.6v7" fill="currentColor" stroke="none"/>',
    "note": '<path d="M14 4v9.5a3.5 3.5 0 1 1-3-3.46" /><path d="M14 4c.6 2.4 2.3 3.9 5 4.2"/>',
    "play": '<rect x="3" y="6" width="18" height="12" rx="4"/>'
            '<path d="M10.5 9.5v5l4-2.5z" fill="currentColor" stroke="none"/>',
    "x": '<path d="M5 5l14 14M19 5 5 19"/>',
    "in": '<path d="M7 10v7M7 7v.01M11 17v-7M11 13.5c0-2 1.3-3.5 3-3.5s3 1.2 3 3.5V17"/>',
    "chat": '<path d="M5.5 18.5 4 21l3-1a8 8 0 1 0-1.5-1.5z"/>'
            '<path d="M9.5 9.5c.3 2 2 3.8 4 4.5l1.3-1.2 1.7.9" />',
    "plane": '<path d="M21 4 3 11l6 2 2 6 3-4 4 3z"/><path d="m9 13 7-5"/>',
    "at": '<circle cx="12" cy="12" r="3.5"/><path d="M15.5 12v1.5a2.5 2.5 0 0 0 5 0V12a8.5 8.5 0'
          ' 1 0-3.3 6.7"/>',
    "pin": '<path d="M12 21s-6-5.3-6-11a6 6 0 1 1 12 0c0 5.7-6 11-6 11z"/><circle cx="12" '
           'cy="10" r="2.2"/>',
    "ghost": '<path d="M12 4c-3 0-5 2.2-5 5v3l-2 1.5 2 .5c-.4 1.5-1.5 2.5-3 3 2 .7 3 .8 4 1.5'
             ' 1 .7 2 1.5 4 1.5s3-.8 4-1.5c1-.7 2-.8 4-1.5-1.5-.5-2.6-1.5-3-3l2-.5L17 12V9'
             'c0-2.8-2-5-5-5z"/>',
    "waves": '<circle cx="12" cy="12" r="9"/><path d="M7.5 10c3-1 6.5-.7 9 .8M8 13.2c2.5-.7 5.2'
             '-.4 7.2.7M8.6 16c2-.4 4-.2 5.6.6"/>',
    "code": '<path d="m9 8-4 4 4 4M15 8l4 4-4 4"/>',
    "game": '<rect x="3" y="7" width="18" height="11" rx="5"/><path d="M8 11v3M6.5 12.5h3"/>'
            '<circle cx="15.5" cy="12" r=".9" fill="currentColor" stroke="none"/>'
            '<circle cx="17.5" cy="14" r=".9" fill="currentColor" stroke="none"/>',
    "phone": '<path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1'
             ' 3 6a2 2 0 0 1 2-2z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14'
             ' 0 0 0 0 18"/>',
    "star": '<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8L3.5 9.7'
            'l5.9-.9z"/>',
    "bag": '<path d="M6 8h12l-1 12H7z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    "pin2": '<circle cx="12" cy="12" r="9"/><path d="M12 7v10M7 12h10"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0'
            ' 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "brush": '<circle cx="12" cy="12" r="9"/><path d="M7 15c3-6 7-6 10-3"/>',
    "msg": '<path d="M12 3c5 0 9 3.6 9 8.2S17 19.5 12 19.5c-1 0-2-.1-2.9-.4L5 21l1-3.6A7.9 7.9 0'
           ' 0 1 3 11.2C3 6.6 7 3 12 3z"/><path d="m7.5 13 3-3 2.5 2 3.5-3"/>',
}


@dataclass(frozen=True)
class Platform:
    key: str
    name: object
    color: str
    symbol: str
    domains: tuple[str, ...] = ()
    # How a username becomes a link ({} = the cleaned username). Empty: a full link is needed.
    profile_url: str = ""
    placeholder: str = "https://"
    kind: str = "social"  # social | contact | web
    extra: dict = field(default_factory=dict)


PLATFORMS: dict[str, Platform] = {p.key: p for p in [
    Platform("instagram", "Instagram", "#E1306C", "camera", ("instagram.com", "instagr.am"),
             "https://instagram.com/{}", "@username"),
    Platform("facebook", "Facebook", "#1877F2", "f", ("facebook.com", "fb.com", "fb.me"),
             "https://facebook.com/{}", "facebook.com/yourpage"),
    Platform("tiktok", "TikTok", "#111111", "note", ("tiktok.com",),
             "https://www.tiktok.com/@{}", "@username"),
    Platform("youtube", "YouTube", "#FF0000", "play", ("youtube.com", "youtu.be"),
             "https://youtube.com/@{}", "@channel"),
    Platform("whatsapp", "WhatsApp", "#25D366", "chat", ("wa.me", "whatsapp.com"),
             "https://wa.me/{}", "+994 50 123 45 67", "contact"),
    Platform("telegram", "Telegram", "#229ED9", "plane", ("t.me", "telegram.me"),
             "https://t.me/{}", "@username"),
    Platform("x", "X (Twitter)", "#000000", "x", ("x.com", "twitter.com"),
             "https://x.com/{}", "@username"),
    Platform("linkedin", "LinkedIn", "#0A66C2", "in", ("linkedin.com",),
             "", "linkedin.com/in/your-name"),
    Platform("threads", "Threads", "#000000", "at", ("threads.net", "threads.com"),
             "https://www.threads.net/@{}", "@username"),
    Platform("snapchat", "Snapchat", "#FFFC00", "ghost", ("snapchat.com",),
             "https://snapchat.com/add/{}", "username"),
    Platform("pinterest", "Pinterest", "#E60023", "pin2", ("pinterest.com", "pin.it"),
             "https://pinterest.com/{}", "username"),
    Platform("spotify", "Spotify", "#1DB954", "waves", ("spotify.com",), "", "open.spotify.com/…"),
    Platform("github", "GitHub", "#181717", "code", ("github.com",),
             "https://github.com/{}", "username"),
    Platform("discord", "Discord", "#5865F2", "game", ("discord.gg", "discord.com"),
             "", "discord.gg/invite"),
    Platform("messenger", "Messenger", "#0084FF", "msg", ("m.me", "messenger.com"),
             "https://m.me/{}", "yourpage"),
    Platform("behance", "Behance", "#1769FF", "brush", ("behance.net",),
             "https://behance.net/{}", "username"),
    Platform("google_maps", _("Google Maps"), "#34A853", "pin",
             ("maps.google.com", "goo.gl", "maps.app.goo.gl", "g.page"), "",
             "maps.app.goo.gl/…", "contact"),
    Platform("google_review", _("Google review"), "#FBBC04", "star", ("g.page",), "",
             "g.page/r/…/review", "contact"),
    Platform("wolt", "Wolt", "#009DE0", "bag", ("wolt.com",), "", "wolt.com/…"),
    Platform("phone", _("Phone"), "#101B3A", "phone", (), "tel:{}", "+994 50 123 45 67",
             "contact"),
    Platform("email", _("Email"), "#101B3A", "mail", (), "mailto:{}", "name@company.com",
             "contact"),
    Platform("website", _("Website"), "#101B3A", "globe", (), "", "example.com", "web"),
    Platform("link", _("Other link"), "#4F7CFF", "link", (), "", "example.com", "web"),
]}

CHOICES = [(p.key, p.name) for p in PLATFORMS.values()]
USERNAME = re.compile(r"^@?[\w.\-]{1,64}$")


def detect(url: str) -> str:
    """Platform key for a pasted link, "website" when unknown."""
    host = (urlsplit(url if "//" in url else "https://" + url).hostname or "").lower()
    host = host.removeprefix("www.").removeprefix("m.")
    for p in PLATFORMS.values():
        if any(host == d or host.endswith("." + d) for d in p.domains):
            return p.key
    return "website"


def build_url(platform: str, value: str) -> str:
    """Turn what the user typed (username, number, address or link) into a link."""
    p = PLATFORMS.get(platform) or PLATFORMS["link"]
    value = (value or "").strip()
    if p.key == "email":
        return "mailto:" + value.removeprefix("mailto:")
    if p.key == "phone":
        return "tel:" + re.sub(r"[^\d+]", "", value.removeprefix("tel:"))
    if p.key == "whatsapp" and not ("/" in value or "." in value):
        return "https://wa.me/" + re.sub(r"\D", "", value)
    if (p.profile_url and "/" not in value and USERNAME.match(value)
            and not _looks_like_domain(value)):
        return p.profile_url.format(quote(value.lstrip("@")))
    return value


def _looks_like_domain(value: str) -> bool:
    return bool(re.match(r"^[\w\-]+(\.[\w\-]+)+(/.*)?$", value.lstrip("@")))


def icon_svg(platform: str, size: str = "size-5") -> str:
    """The symbol alone, in the current text colour."""
    p = PLATFORMS.get(platform) or PLATFORMS["link"]
    return (f'<svg viewBox="0 0 24 24" class="{size}" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{SYMBOLS[p.symbol]}</svg>')


def icon_tile(platform: str, size: str = "size-10", radius: int = 7) -> str:
    """Brand-coloured tile with the symbol. Colours are SVG attributes, so the strict CSP
    (no inline styles) is respected."""
    p = PLATFORMS.get(platform) or PLATFORMS["link"]
    fg = text_color(platform)
    return (f'<svg viewBox="0 0 24 24" class="{size} shrink-0" aria-hidden="true">'
            f'<rect width="24" height="24" rx="{radius}" fill="{p.color}"/>'
            f'<g transform="translate(4.8 4.8) scale(.6)" fill="none" stroke="{fg}" '
            f'color="{fg}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            f'{SYMBOLS[p.symbol]}</g></svg>')


def text_color(platform: str) -> str:
    """White or dark symbol, readable on the brand colour."""
    p = PLATFORMS.get(platform) or PLATFORMS["link"]
    r, g, b = (int(p.color[i:i + 2], 16) for i in (1, 3, 5))
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 186 else "#FFFFFF"
