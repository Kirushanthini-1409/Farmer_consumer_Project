# FarmConnect — Documentation

FarmConnect is a farmer-to-consumer marketplace that removes intermediaries, promotes fair pricing, and reduces food waste through an Ugly Produce Marketplace. It is a full-stack web platform (HTML/CSS/Bootstrap/vanilla JS + Firebase + Flask/scikit-learn) designed to run entirely on free-tier hosting and to be buildable in a 2-day solo, AI-assisted sprint.

These docs are generated from the two source documents in the project root:

- `FarmConnect.docx` — the original proposal (problem, solution, tech stack, architecture).
- `FarmConnect_Implementation_Plan.docx` — the v2.0 implementation plan (July 2026), which supersedes the original where they differ.

## Index

| Doc | Contents |
|---|---|
| [01-overview.md](01-overview.md) | Problem statement, proposed solution, features, tech stack |
| [02-architecture.md](02-architecture.md) | System architecture, trust boundary, security rules, geolocation, hardening |
| [03-business-logic.md](03-business-logic.md) | Order lifecycle, inventory & batches, ugly produce, group buying, trust, payments |
| [04-data-model.md](04-data-model.md) | Firestore collections and key fields |
| [05-api.md](05-api.md) | Flask API surface and auth conventions |
| [06-ai-features.md](06-ai-features.md) | AI features with v1/v2 cold-start strategy |
| [07-hosting.md](07-hosting.md) | Free-tier hosting plan and accounts |
| [08-build-plan.md](08-build-plan.md) | 2-day build schedule, stretch goals, roadmap |
| [09-risks-and-demo.md](09-risks-and-demo.md) | Risks, free-tier gotchas, five-minute demo script |

## Plan verification notes

The v2.0 implementation plan was verified against the original proposal before these docs were written. It is internally consistent (state machine ↔ transition table, API ↔ data model, schedule ↔ scope) and deliberately corrects the original in four places:

| Original choice | Replaced by | Why |
|---|---|---|
| Google Maps JavaScript API | Leaflet + OpenStreetMap + Nominatim | Google Maps now requires a billing card on file; Leaflet/OSM is fully free and covers maps, markers, and distance search. |
| Firebase Storage | Cloudinary (free tier) | Since Oct 2024 new Firebase projects cannot create a free Storage bucket (Blaze plan required); Cloudinary gives 25 free credits/month. |
| Browser writes directly to Firestore | Flask backend owns all writes | Client-side order/stock/price logic can be manipulated from DevTools and cannot enforce transactions or escrow. |
| Payments unspecified | Simulated checkout in MVP; Razorpay Test Mode in roadmap | Payments are deprioritised for the 2-day build; the escrow design still allows adding them without rework. |

Minor gaps noted during verification (not blockers):

- The `notifications` collection has no dedicated API endpoint — it is written by the backend as a side effect of other actions and read by the UI.
- Subscriptions are a headline feature in the original proposal but are intentionally deferred to roadmap phase R2.
- Group-order deadline resolution in the MVP happens on page load or via a manual admin action; the roadmap moves this to a GitHub Actions cron.
