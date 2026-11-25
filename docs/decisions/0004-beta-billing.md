# ADR 0004 — Free beta billing

Date: 2026-11-25 · Status: accepted

**Decision.** No payment provider during the free beta. Plans, features and limits are
real and enforced (`subscriptions.entitlements`); every new organization gets the `beta`
plan. `billing.gateways.PaymentGateway` defines the provider contract; the only
implementation is `ManualGateway`, which refuses self-service checkout and lets staff
assign plans in the admin (audited as `admin.billing.plan_assigned`). A subscription will
only ever be activated by a verified provider webhook once a provider is added.
