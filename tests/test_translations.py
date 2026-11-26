"""CI guard: the Azerbaijani catalog must be complete and keep placeholders intact."""

import re
from pathlib import Path

import polib

PO = Path(__file__).resolve().parent.parent / "locale/az/LC_MESSAGES/django.po"
PH = re.compile(r"%\(\w+\)[sd]")


def test_az_catalog_complete_and_consistent():
    po = polib.pofile(str(PO))
    untranslated = [e.msgid for e in po.untranslated_entries()]
    fuzzy = [e.msgid for e in po.fuzzy_entries()]
    assert not untranslated, untranslated
    assert not fuzzy, fuzzy
    for e in po.translated_entries():
        if not e.msgid_plural:
            assert sorted(PH.findall(e.msgid)) == sorted(PH.findall(e.msgstr)), e.msgid


SIMPLE_PY = re.compile(r"""\b_\(\s*"((?:[^"\\\n]|\\.)+)"\s*\)""")
SIMPLE_TPL = re.compile(r"""{%\s*translate\s+"([^"\n]+)"\s*%}""")


def test_catalog_covers_source_strings():
    """Every simple _("…") / {% translate "…" %} string in the code is in the catalog.

    Catches strings dropped by a wrong makemessages --ignore pattern (e.g. "assets/*"
    also matches apps/assets/).
    """
    root = PO.parents[3]
    ids = {e.msgid for e in polib.pofile(str(PO))}
    missing = []
    for folder in ("apps", "templates"):
        for path in (root / folder).rglob("*"):
            if path.suffix not in (".py", ".html") or "tests" in path.parts \
                    or "migrations" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            pattern = SIMPLE_PY if path.suffix == ".py" else SIMPLE_TPL
            for msgid in pattern.findall(text):
                msgid = msgid.replace('\\"', '"')
                if msgid not in ids and msgid.replace("%", "%%") not in ids:
                    missing.append(f"{path.relative_to(root)}: {msgid}")
    assert not missing, missing[:20]
