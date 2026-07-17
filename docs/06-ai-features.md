# 6. AI Features — with an honest cold-start strategy

The weakest part of the original proposal was "scikit-learn will recommend prices" with no data source. Every model below has a **v1** that works on day one and a **v2** that activates as real platform data accumulates. Stating this openly makes the project more credible, not less.

| Feature | v1 — ships in the 2-day build | v2 — after real data accumulates |
|---|---|---|
| **Fair price recommendation** | Bundle a CSV of public Agmarknet mandi prices (data.gov.in daily commodity prices). Backend returns a fair-price **band**: mandi modal price ± adjustments for freshness, ugly flag and category, served through a scikit-learn regression trained on that CSV. | Blend platform transaction prices with mandi data; weekly retrain via the `/ai/retrain` endpoint on a GitHub Actions cron. |
| **Demand prediction** | Seasonality heuristics + 7-day moving average over seeded order history; UI shows "In demand this week" chips. The doc and demo state plainly that real forecasts need weeks of live data. | Time-series model (e.g., gradient boosting on lag features) per category, including festival/weather seasonality. |
| **Personalised recommendations** | Popularity + content-based: same category, nearby, in stock, boosted by the consumer's browsing/purchase history stored in Firestore. | Collaborative filtering (implicit-feedback matrix factorisation) once the user-item matrix is dense enough. |

Where the AI surfaces in the product:

- **Farmer batch form** — the fair-price band appears inline as the farmer sets a price; toggling `is_ugly` visibly lowers the suggestion. The server validates submitted prices against the band as a *warning*, not a block.
- **Consumer home** — a personalised recommendations rail (`GET /ai/recommendations`).
- **Farmer dashboard** — "In demand this week" chips (`GET /ai/demand`).

Demo honesty note: seeded data powers the v1 demo. Present it as "AI v1 runs on public mandi data + seeded history; v2 retrains on live transactions" — this is a strength, not a weakness.
