# 7. Free Hosting Plan (no credit card anywhere)

| Component | Platform | Free tier | Caveat / mitigation |
|---|---|---|---|
| Frontend | Firebase Hosting (Spark) | 10 GB storage, 360 MB/day transfer | Plenty for a demo; deploy with the Firebase CLI. |
| Auth | Firebase Authentication | Email/password sign-in, free | Phone-number OTP costs money — stick to email/password. |
| Database | Firestore (Spark) | 50k reads, 20k writes, 20k deletes/day; 1 GiB | Design queries to avoid hot loops; cache the catalogue in memory on the client. |
| Backend + ML | Render free web service | 750 instance-hours/month | Sleeps after 15 min idle; cold start ~50 s. Ping it via cron-job.org and warm it up 10 min before any demo. |
| Images | Cloudinary | 25 credits/month (≈25 GB or 25k transformations) | Compress images client-side before upload. |
| Maps / geocoding | Leaflet + OSM tiles + Nominatim | Free | Nominatim: max 1 req/s, set a proper User-Agent, cache geocodes in Firestore. |
| Scheduled jobs *(roadmap)* | GitHub Actions cron | 2,000 min/month (free on public repos) | Used later for subscriptions, group-order deadlines, model retraining. |
| Payments *(roadmap)* | Razorpay Test Mode | Free, unlimited test transactions | No real money moves; live mode needs business KYC. |

## Accounts to create (all free, ~30 minutes)

- Google/Firebase project (enable Auth email/password + Firestore + Hosting)
- Render
- Cloudinary (+ unsigned upload preset)
- GitHub (repo + Actions)
- cron-job.org (keep-alive ping for Render)

None asks for a card.
