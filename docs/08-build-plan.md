# 8. The 2-Day Build Schedule & Roadmap

Solo build, AI-assisted. Four half-day blocks, each ending with acceptance checks you can actually run. **Cut from the bottom of each block, never from the checks.** Deploy early (Block A), then every block ships to the live URLs. The block structure is the contract: never start a block before the previous block's checks pass.

## Block A — Day 1 morning: foundations, live from hour one

- Create the GitHub repo (two folders: `web/` and `api/`), Firebase project (enable Auth email/password + Firestore), Render web service connected to the repo, Cloudinary account + unsigned upload preset.
- Flask skeleton: `firebase-admin` token verification middleware, `/me`, CORS, deployed to Render. Frontend skeleton: Bootstrap layout, Firebase Auth signup/login with role choice (consumer/farmer), deployed to Firebase Hosting.
- `POST /auth/register-profile` sets the role custom claim and creates the user document.

**Checks:** live Hosting URL loads; signup as farmer and consumer works; `GET /me` on Render returns the right role for each; unauthenticated call gets 401.

## Block B — Day 1 afternoon: catalogue + map discovery

- Farmer dashboard: create product (Cloudinary image upload) and batches (qty, price, harvest_date, is_ugly, discount).
- Consumer browse page: category/price/ugly filters, freshness badges computed from `harvest_date`.
- Leaflet map: farmer markers (verified badge in popup), "use my location", distance filter chips (2 / 5 / 10 km) using client-side haversine; farmer location picked on a map at registration.

**Checks:** a product listed by the farmer appears in consumer browse within seconds; a consumer 3 km away sees the farmer under the 5 km filter but not under 2 km; an ugly batch shows the discounted price.

## Block C — Day 2 morning: orders end-to-end + ugly produce

- Cart (localStorage) → checkout calls `POST /orders`: server-side price/stock validation, transactional stock decrement, simulated payment step, PLACED order created.
- Order screens for both roles driven by `POST /orders/{id}/transition`: farmer accepts → packs → delivers; consumer confirms; cancel path restores stock; `order_events` timeline rendered in the UI.
- "Ugly but Tasty" section + farmer-dashboard "kg saved from waste" counter.

**Checks:** two browsers buying the last batch simultaneously — exactly one succeeds; cancelled order restores stock; illegal transition (consumer tries to "accept") is rejected; timeline shows every step.

## Block D — Day 2 afternoon: AI + seed data + demo polish

- Load the Agmarknet CSV into `price_reference`; implement `/ai/price-suggest` (fair band + freshness/ugly adjustments) shown inline on the farmer's batch form; `/ai/recommendations` rail on the consumer home; `/ai/demand` chips on the farmer dashboard.
- Seed script (run once against the API): ~8 farmers around your city, ~30 products with images, 3 weeks of synthetic order history so recommendations and demand chips look alive.
- Demo polish: home page with platform "kg saved" counter, empty-state messages, cron-job.org ping on the Render service, full demo run-through (see [09-risks-and-demo.md](09-risks-and-demo.md)).

**Checks:** price suggestion changes when `is_ugly` is toggled; recommendations differ between two consumer accounts with different histories; the whole demo script runs on live URLs without touching a terminal.

## Stretch goals (only if the checks above all pass)

- Simplified group buying (open + join + resolve-on-page-load).
- Razorpay Test Mode checkout replacing the simulated payment step.
- Admin KYC queue UI (approve → Verified badge appears on map popups and listings).

## Post-deadline roadmap

| Phase | Feature | Approach (still free) |
|---|---|---|
| R1 | Razorpay test-mode escrow | Capture on PLACED, `ledger` collection, release on COMPLETED, refund on cancel; webhook endpoint on Flask. |
| R1 | Admin module completion | KYC queue, reports moderation, platform analytics dashboard. |
| R2 | Subscriptions | `subscriptions` collection + GitHub Actions cron (daily) calling a backend endpoint that generates orders; pause/skip/cancel. |
| R2 | Group-buy automation + notifications | Same cron resolves deadlines; in-app `notifications` collection now, FCM push / Brevo email (300/day free) later. |
| R3 | Real ML | Weekly retrain blending live transactions with mandi data; collaborative-filtering recommendations; per-category demand forecasts. |
| R3 | Scale & reach | Geohash range queries (`geofire-common`), multilingual UI (i18n JSON dictionaries), PWA manifest for installable mobile experience. |
