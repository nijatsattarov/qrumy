"""Tiny, safe formatter for legal texts: "## " headings, "- " lists, blank-line paragraphs.
All text is HTML-escaped first, so staff-entered content can never inject markup."""

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def legal_markup(text: str) -> str:
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for raw in (text or "").splitlines():
        line = escape(raw.strip())
        if not line:
            flush()
        elif raw.strip().startswith("## "):
            flush()
            out.append(f"<h2>{line[3:]}</h2>")
        elif raw.strip().startswith("- "):
            if para:
                flush()
            items.append(line[2:])
        else:
            if items:
                flush()
            para.append(line)
    flush()
    return mark_safe("".join(out))  # noqa: S308 — every piece was escaped above


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+|/[^\s)]*)\)")
_IMAGE = re.compile(r"^!\[([^\]\n]*)\]\((/media/public/[^\s)]+)\)$")


def _inline(escaped: str) -> str:
    def link(m):
        url = m.group(2)
        rel = "" if url.startswith("/") else ' rel="noopener nofollow"'
        return f'<a href="{url}"{rel}>{m.group(1)}</a>'

    return _LINK.sub(link, _BOLD.sub(r"<strong>\1</strong>", escaped))


@register.filter
def content_markup(text: str) -> str:
    """Blog formatting: ##/### headings, "- " lists, **bold**, [text](url) links and
    ![alt](/media/public/…) images on their own line. Input is escaped first; only these
    patterns become markup, links must be http(s) or site-relative, and images must be
    files uploaded to the site (the CSP blocks other hosts anyway)."""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for raw in (text or "").splitlines():
        stripped = raw.strip()
        line = escape(stripped)
        image = _IMAGE.match(line)
        if not stripped:
            flush()
        elif image:
            flush()
            out.append(f'<figure><img src="{image.group(2)}" alt="{image.group(1)}" '
                       f'loading="lazy"></figure>')
        elif stripped.startswith("### "):
            flush()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif stripped.startswith("## "):
            flush()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif stripped.startswith("- "):
            if para:
                flush()
            items.append(_inline(line[2:]))
        else:
            if items:
                flush()
            para.append(_inline(line))
    flush()
    return mark_safe("".join(out))  # noqa: S308 — escaped, then only whitelisted patterns
