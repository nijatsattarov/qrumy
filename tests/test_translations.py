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
