# ADR 0006 — Surveys & feedback

Date: 2026-11-25 · Status: accepted

**Model.** `Survey` → ordered `Question`s (14 types in `surveys/qtypes.py`; each type builds
its own form field and knows how to store and summarise answers) → `Response` → `Answer`
(text / number / list). NPS and CSAT values are copied onto `Response` for fast filtering.
`SurveyDailyStat` counts page views (once per browser per day, bots excluded) as the
denominator of the completion rate. Conditional logic has a JSON field (`Question.logic`)
but no evaluation yet.

**Scores.** NPS = % promoters (9–10) − % detractors (0–6); CSAT = % of 4–5 answers on 1–5;
CES = average on 1–7 (+ % easy 5–7). Pure functions in `surveys/scoring.py`.

**Public pages.** `/s/<token>` (12-char random token), `/s/<token>/embed` (frameable:
`frame-ancestors *`, no X-Frame-Options) and `/s/<token>/theme.css` (survey colours as CSS
variables, so pages need no inline styles under the strict CSP). The submit endpoint is
CSRF-exempt because it must work inside third-party iframes; instead it requires a signed,
survey-bound start token (24 h), a honeypot field and per-IP rate limits. Respondent IPs are
never stored. Contact details are stored only with recorded consent text.

**Limits.** Submissions lock the survey row (`SELECT … FOR UPDATE`) so `response_limit` holds
under concurrency; monthly responses are metered in `UsageCounter` against
`surveys.responses_month`; `surveys.max` limits the number of surveys.

**QR integration.** The surveys app registers a non-listed `survey` QR type; a survey's QR is
a normal dynamic code (scan analytics included) that redirects to `/s/<token>?src=qr`.
Deleting a survey pauses its QR code instead of leaving a dangling redirect.
