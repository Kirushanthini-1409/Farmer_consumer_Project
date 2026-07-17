# 9. Risks, Free-Tier Gotchas & Demo Script

## 9.1 Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Render cold start (~50 s) | First API call during a demo hangs | cron-job.org ping every 10 min; open the site 10 min before presenting. |
| Firestore daily quotas (50k reads) | App stops reading if a loop runs wild | No polling loops; use one-shot queries + the real-time listener only on the order page. |
| Nominatim rate limit (1 req/s) | Geocoding fails under bursts | Geocode once at registration, cache in the user document; map picking needs no geocoding. |
| Seeded data in demos | Looks fake if oversold | Present it honestly: "AI v1 runs on public mandi data + seeded history; v2 retrains on live transactions" — this is a strength. |
| Solo 2-day scope creep | Nothing fully works | The block structure is the contract: never start a block before the previous block's checks pass. |
| Secrets leakage | Firebase service key in repo | Render env vars only; `.gitignore` the key; firebase config in `web/` is public by design (rules protect data). |

## 9.2 Five-minute demo script

1. **Home page:** platform pitch + live "kg saved from waste" counter.
2. **Farmer login:** add a batch of tomatoes — show the AI price band appear, toggle "ugly" and watch the suggestion drop; mention mandi data as the source.
3. **Consumer login (second browser):** Leaflet map, "near me" 5 km filter, open the farmer, add to cart, checkout; show the Ugly-but-Tasty section on the way.
4. **Farmer accepts → packs → delivers;** consumer's order timeline updates live; consumer confirms and leaves a verified-purchase review.
5. **Close with the architecture slide:** trust boundary, transactions, free-tier hosting — the engineering story behind the demo.
