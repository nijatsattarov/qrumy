# Qrumy — SEO

## What is in place
- **Free QR generator without an account** on the homepage and on 10 landing pages, each for
  its own search intent (EN + AZ): `/qr-code-generator/`, `/url-qr-code-generator/`,
  `/wifi-qr-code-generator/`, `/email-qr-code-generator/`, `/phone-qr-code-generator/`,
  `/whatsapp-qr-code-generator/`, `/sms-qr-code-generator/`, `/vcard-qr-code-generator/`,
  `/location-qr-code-generator/`, `/text-qr-code-generator/` (Azerbaijani: `/az/…`).
  Content: `apps/marketing/seo_tools.py`. The generator is directly under the H1.
- **Metadata on every public page**: unique title/description/H1, canonical (`SITE_URL` +
  path, no query string), `hreflang` en/az/x-default only for pages that exist in both
  languages, Open Graph + Twitter card, default social image `static/brand/og-default.png`.
- **Structured data (JSON-LD)**: Organization + WebSite + WebApplication + FAQPage (home),
  WebApplication + BreadcrumbList + FAQPage (tool pages), BlogPosting + BreadcrumbList
  (posts). Only content that is visible on the page; no ratings, reviews or invented prices
  (the free tool is marked price 0 because it is free).
- **robots.txt** (`/robots.txt`): crawl everything public; block the app, accounts, internal
  endpoints and customers' QR/card/menu/survey/form pages. The admin path is *not* listed.
  `X-Robots-Tag: noindex` is sent for the admin, app and internal endpoints.
- **Sitemap** (`/sitemap.xml`): home, tool pages, pricing, blog, contact, published legal
  pages (with language alternates) and published posts with `lastmod`; always on
  `SITE_URL` (https://qrumy.com). Pages set to noindex in both languages are left out.
- **Redirects**: Nginx sends http → https and www → qrumy.com (one hop); Django adds the
  trailing slash.
- **404 page** with links to the generator and popular tools (HTTP 404, noindex).

## Editing SEO in the admin (Marketinq)
- **Səhifə SEO-su** — one row per page and language: SEO title, meta description, focus
  keyword (checked against title and description), keywords, H1, social image, noindex.
  Empty fields keep the built-in texts (shown on the row). Title/description lengths are
  colour-coded.
- **SEO ayarları** — title suffix, default social image, Google / Bing / Yandex
  verification codes, official social profiles (Organization `sameAs`).
- **Blog yazıları** — SEO title, meta description, keywords, cover image + alt text per post.

Note: Google does not use the keywords meta tag for ranking. Use the words naturally in the
title, H1, intro and FAQs.

## Funnel analytics (no cookies, no personal data)
Anonymous daily counters (`SiteEvent`): tool page views (with source search / social /
direct / other / internal), QR type selected, QR generated (once per page view), PNG / SVG
downloads, pricing views, dynamic-QR and upgrade CTA clicks, sign-ups (and Google sign-ups),
paid subscriptions started. Bots are excluded. See **admin → home → Acquisition funnel**.
If you add Google Analytics later, do it with a consent banner and extend the CSP.

## Google Search Console
1. https://search.google.com/search-console → **Add property**.
2. Prefer **Domain** property `qrumy.com` and verify with the DNS TXT record (covers https,
   http and www). Or use **URL prefix** `https://qrumy.com/` → *HTML tag* → copy only the
   `content` value into admin → **SEO ayarları → Google Search Console verification code**.
3. **Sitemaps** → submit `https://qrumy.com/sitemap.xml`.
4. **URL inspection** → test `https://qrumy.com/` and a few tool pages → *Request indexing*.
5. Check **Pages**, **Enhancements** (Breadcrumbs, FAQ) and **Core Web Vitals** after a few
   days. Validate structured data at https://search.google.com/test/rich-results.
6. Optional: Bing Webmaster Tools (import from Search Console) and Yandex Webmaster.

## Next content (write by hand, one solid article at a time)
1. How to Create a WiFi QR Code (link to the WiFi tool)
2. QR Codes for Restaurants (menu, WiFi, feedback → Digital Menu)
3. QR Code Size: How Small Can It Be? / How to Print QR Codes
4. How to Track QR Code Scans (dynamic QR + analytics)
5. QR Codes for Business Cards (vCard vs Qrumy Card)
6. QR Codes for Google Reviews / Customer Feedback (Surveys)
7. Can QR Codes Expire? / Are QR Codes Free?
For each post: SEO title + description in the admin, a cover with alt text, links to 1–2
tool pages, and an Azerbaijani version written for local search ("QR kod yaratmaq",
"pulsuz QR kod", "Wi-Fi QR kod", "menyu QR kod").
