# ADR 0005 — QR engine, redirects and scan analytics

Date: 2026-11-25 · Status: accepted

**Rendering.** `segno` builds the matrix; Qrumy's own renderer turns it into drawing
primitives (module and finder shapes, colours, logo tile, frame and call-to-action),
drawn identically to SVG and PNG (Pillow, supersampled). Logos are always re-encoded
to PNG (user SVGs are never embedded); error correction switches to H when a logo is used.

**Scannability.** Before a design is saved, colour rules are checked (dark-on-light,
contrast ≥ 4:1) and the design is rendered and decoded with ZXing (`zxing-cpp`).
A design that does not round-trip is rejected. The full style matrix (756 combinations,
four logo kinds) decodes; one weak combination found during testing (round finder frame +
square centre + logo) is rendered with slightly rounded centre corners.

**Redirect path.** `/q/<code>` reads a cached summary (5 min, invalidated on every
change), checks status/expiry, records the scan and returns 302 (or a hosted page/file).
Short codes are 7 characters from an unambiguous 55-letter alphabet, immutable, and never
reused (codes are soft-deleted). Redirect targets are validated on save: http(s) only, no
credentials, no private IPs, no Qrumy short links, staff blocklist, optional Safe Browsing.

**Scans.** The redirect pushes a small snapshot to a Redis list (falls back to a direct
write if Redis is down). A Celery beat task drains it every 15 s: user-agent parsing,
bot/preview detection (bots stored but not counted), optional GeoLite2 lookup, bulk insert,
then `INSERT … ON CONFLICT` upserts into daily rollups per dimension. Dashboards read only
rollups. Raw IPs are never stored — only an HMAC with a daily salt (used for unique
estimates). Raw scans are purged after `QRUMY_SCAN_RETENTION_DAYS` (default 180).

**Hosted files.** PDF/image files behind codes are type-sniffed from their bytes, size-
limited per plan, stored outside the web root and served by the app (Nginx X-Accel in
production) only while the code is active.
