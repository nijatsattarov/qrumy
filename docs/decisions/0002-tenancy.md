# ADR 0002 — Tenant isolation

Date: 2026-11-25 · Status: accepted

**Decision.** Single database; every tenant row has `organization_id`. The organization is
part of the URL (`/app/<org_slug>/…`). `OrganizationMiddleware` resolves it only through
the signed-in user's membership; a non-member gets **404** (indistinguishable from a
missing org). Object lookups always filter by `request.organization`
(`Model.objects.for_org(org)` or `get_object_or_404(..., organization=request.organization)`).
Roles live on `Membership`; capabilities are checked server-side by `require_capability`.

**Why.** Django has no global query scopes; explicit scoping + an automated attack suite
is more reliable than implicit thread-local magic.

**Enforcement.** `tests/test_tenant_isolation.py` requests every org-scoped URL as another
organization and fails if a new object-level route lacks an attack test. Verified by
mutation: removing the organization filter from one view makes the suite fail.
Postgres Row-Level Security remains an optional hardening step (launch prep).
