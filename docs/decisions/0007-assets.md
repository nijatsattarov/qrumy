# ADR 0007 — Asset management

Date: 2026-11-25 · Status: accepted

**Model.** `Asset` (per-organization unique `asset_code`, generated as `AST-00001` when blank),
`AssetCategory`, `Location` (self-referencing tree: branch › building › floor › room /
department / area), `AssetDocument` (private photos/PDFs), `FaultReport` (task workflow:
new → assigned → in progress → waiting → completed / cancelled), `MaintenanceRecord`
(preventive / corrective / inspection, cost, optional link to a fault) and `AssetActivity`
(per-asset history). Location trees are small, so paths and descendants are computed in
memory (`assets/locations.py`); moves that would create a cycle are rejected, and a location
that still contains other locations cannot be deleted.

**QR profile.** Each asset can get a dynamic QR code (non-listed `asset` QR type) that opens
`/a/<token>`. The owner chooses what the public profile shows (minimal / standard / full);
serial numbers, prices, documents and history are never public. Signed-in members see an
"Open in Qrumy" link. Public asset and QR pages follow the visitor's phone language.

**Fault reporting.** Anyone who scans can report a fault with an optional photo. The form
uses a signed asset-bound token, a honeypot and per-IP rate limits; photos are type-checked
from their bytes and stored privately. The responsible person (or, if none, owners/admins/
managers) gets an in-app notification, plus an email for high/urgent faults. Completing a
fault can log a corrective maintenance record and set the asset back to Active.

**Files.** Documents and fault photos are served only to members of the organization
(X-Accel in production) with `nosniff` and `no-store`.

**Deferred to Phase 8:** preventive maintenance schedules, overdue/warranty notifications,
utilisation analytics.
