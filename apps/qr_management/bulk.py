"""Bulk creation of dynamic website QR codes from CSV."""

import csv
import io
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from . import services
from .engine import QRStyle
from .types import DYNAMIC, SafeURLField

MAX_ROWS = 500
MAX_BYTES = 1024 * 1024
TEMPLATE = "name,url,tags\nSpring menu,https://example.com/menu,restaurant\n" \
           "Table card,https://example.com/feedback,\"tables, feedback\"\n"


@dataclass
class BulkResult:
    created: list = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_csv(upload) -> tuple[list[dict], list[str]]:
    if upload.size > MAX_BYTES:
        return [], [_("The file must be 1 MB or smaller.")]
    raw = upload.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [_("Save the file as UTF-8 CSV.")]
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    if "url" not in headers:
        return [], [_("The first row must contain the column names, including 'url'.")]
    reader.fieldnames = headers
    rows, errors = [], []
    field = SafeURLField()
    for line, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values()):
            continue
        if len(rows) >= MAX_ROWS:
            errors.append(_("Only %(n)s rows can be imported at once.") % {"n": MAX_ROWS})
            break
        url = (row.get("url") or "").strip()
        try:
            url = field.clean(url)
        except ValidationError as exc:
            errors.append(_("Row %(line)s: %(error)s") % {"line": line, "error": exc.messages[0]})
            continue
        name = (row.get("name") or "").strip()[:120] or url[:120]
        tags = [t for t in (row.get("tags") or "").split(",") if t.strip()]
        rows.append({"name": name, "url": url, "tags": tags})
    if not rows and not errors:
        errors.append(_("The file has no rows to import."))
    return rows, errors


@transaction.atomic
def create_from_rows(*, organization, actor, rows, folder=None, request=None) -> list:
    services.check_dynamic_quota(organization, increment=len(rows))
    style = QRStyle()
    return [services.create_qr(organization=organization, actor=actor, qr_type="url",
                               mode=DYNAMIC, name=r["name"], payload={"url": r["url"]},
                               style=style, folder=folder, tags=r["tags"], request=request,
                               verify=False)  # default style is always scannable
            for r in rows]
