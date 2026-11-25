"""Tiny, safe formatter for legal texts: "## " headings, "- " lists, blank-line paragraphs.
All text is HTML-escaped first, so staff-entered content can never inject markup."""

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
