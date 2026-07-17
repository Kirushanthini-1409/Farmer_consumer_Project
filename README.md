# 🌾 FarmConnect

A farmer-to-consumer marketplace that removes intermediaries, promotes fair pricing, and reduces
food waste through an **Ugly Produce Marketplace**. Full-stack: Bootstrap + vanilla JS frontend,
Firebase (Auth/Firestore/Hosting), a trusted Flask backend on Render that owns **all writes**,
scikit-learn AI (fair-price bands, demand chips, recommendations), and Leaflet/OpenStreetMap for
nearby-farmer discovery. Runs 100% on free tiers — no credit card anywhere.

Design docs live in [docs/](docs/README.md). This repo implements the full MVP scope from the
implementation plan **plus** the stretch goals (group buying, admin KYC queue, reports moderation).

```
web/   Frontend (deploy to Firebase Hosting)     api/   Flask backend + ML (deploy to Render)
```

## What's implemented

- **Auth & roles** — Firebase email/password; roles (consumer/farmer/admin) as custom claims set by
  `POST /auth/register-profile`; admins are provisioned via the seed script, never self-service.
- **Catalogue** — products + harvest **batches** (`qty`, `price`, `harvest_date`, `is_ugly`,
  `discount_pct`), freshness badges from per-category shelf life, auto −20% discount past 60% of
  shelf life, expired batches hidden.
- **Ugly Produce Marketplace** — mandatory 30–50% discount, dedicated filter/section, farmer +
  platform-wide "kg saved from waste" counters (awarded on order COMPLETED).
- **Discovery** — Leaflet map with farmer markers and Verified badges, "use my location",
  2/5/10 km distance chips (client haversine + server-side distance filter in `/browse`).
- **Orders** — cart (localStorage) → `POST /orders` recomputes prices server-side and reserves
  stock in a **Firestore transaction** (concurrent buyers can't oversell); full state machine
  `PLACED → CONFIRMED → PACKED → OUT_FOR_DELIVERY/READY_FOR_PICKUP → DELIVERED → COMPLETED`
  with REJECTED/CANCELLED (stock restored)/DISPUTED; every move appends to `order_events`
  (audit trail + timeline UI); 12 h accept timeout and 48 h auto-complete resolve lazily on read.
- **Group buying** — open a group on a batch, transactional joins capped at target, leave locked at
  ≥80% of target, deadline resolution on read (one CONFIRMED order per member, single stock
  decrement) + manual admin resolve.
- **Reviews & trust** — verified-purchase reviews only (COMPLETED order required), farmer rating
  aggregates, report listing/review → admin hide/dismiss queue, farmer KYC queue → Verified badge.
- **AI (honest cold start, v1)** — fair-price band from a bundled Agmarknet-style mandi CSV via a
  scikit-learn regression (adjusted for ugly flag + freshness, shown live on the batch form; price
  outside the band is a warning, never a block); demand chips (seasonality + 7-day moving average);
  personalised recommendations (popularity + content-based + browsing history + proximity);
  `POST /ai/retrain` blends live completed-order prices (cron + shared secret).
- **Hardening** — backend verifies Firebase ID tokens on every call, CORS allowlist, flask-limiter
  rate limits, server-side validation everywhere, `firestore.rules` deny all client writes.

## Local development

```bash
# 1. Firebase project (free Spark plan): enable Email/Password auth + Firestore.
#    Project settings → Service accounts → generate key → save as api/service-account.json
# 2. Backend
cd api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # point GOOGLE_APPLICATION_CREDENTIALS at your key
.venv/bin/python seed.py        # demo data: 8 farmers, ~30 products, 3 weeks of orders, admin login
.venv/bin/python app.py         # http://localhost:8000

# 3. Frontend — fill web/js/config.js (firebaseConfig, API_BASE, Cloudinary), then:
cd ../web && python3 -m http.server 5500   # http://localhost:5500

# 4. Tests
cd ../api && .venv/bin/python -m pytest tests/ -q
```

Seeded logins (password `Demo@1234`): `admin@farmconnect.example.com`,
`ravi.farm@example.com` (farmer), `arjun.c@example.com` (consumer), and friends — see `api/seed.py`.

## Deploy (all free, no card)

| Piece | Where | How |
|---|---|---|
| Frontend | Firebase Hosting | `firebase deploy --only hosting` (uses `firebase.json`, publishes `web/`) |
| Firestore rules | Firebase | `firebase deploy --only firestore:rules` |
| Backend + ML | Render free web service | `render.yaml` blueprint; set `FIREBASE_SERVICE_ACCOUNT_JSON` + `ALLOWED_ORIGINS` env vars |
| Images | Cloudinary | create an **unsigned preset** (images only, size cap) named in `web/js/config.js` |
| Keep-alive | cron-job.org | ping `https://<render-app>/health` every 10 min (cold start ~50 s otherwise) |

Full API surface, data model and architecture: [docs/05-api.md](docs/05-api.md),
[docs/04-data-model.md](docs/04-data-model.md), [docs/02-architecture.md](docs/02-architecture.md).
Five-minute demo script: [docs/09-risks-and-demo.md](docs/09-risks-and-demo.md).

## Roadmap (designed, not built)

Razorpay test-mode escrow with an append-only `ledger`, subscriptions via GitHub Actions cron,
group-buy cron automation + FCM/Brevo notifications, collaborative-filtering recommendations,
geohash range queries at scale — see [docs/08-build-plan.md](docs/08-build-plan.md).
