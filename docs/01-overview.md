# 1. Overview

## Problem statement

Small and medium-scale farmers often struggle to earn fair profits due to their dependence on intermediaries and the lack of direct access to consumers. Existing marketplaces primarily focus on large-scale suppliers and provide limited support for local farmers to sell their produce directly. As a result, farmers have little control over pricing, reduced market visibility, and often experience food wastage due to unsold or cosmetically imperfect ("ugly") produce.

Consumers, on the other hand, face higher prices, limited access to fresh locally grown products, and difficulty in identifying trusted nearby farmers. They also lack convenient features such as subscription-based purchases, group buying, and location-based discovery of local produce.

Therefore, there is a need for a transparent, intelligent, and user-friendly digital platform that directly connects farmers and consumers, promotes fair pricing, reduces food wastage, and supports sustainable local agriculture.

## Proposed solution

FarmConnect is an AI-powered full-stack web platform that enables direct interaction between farmers and consumers, eliminating unnecessary intermediaries while promoting fair pricing, transparency, and sustainable agriculture.

Farmers list agricultural products such as vegetables, fruits, milk, eggs, grains, and homemade products. Consumers search for nearby farmers on a map, filter products by distance, category, and price, and purchase through one-time orders, recurring subscriptions (roadmap), or community group buying to reduce overall purchasing costs.

### Key features

- **AI-based price recommendations** — help farmers determine fair selling prices based on market trends and local demand.
- **Demand prediction** — identify products expected to be in higher demand, so farmers can prioritise what to stock or promote.
- **Personalised product recommendations** — based on consumers' browsing and purchase history.
- **Distance-based farmer discovery** — map-based nearby-farmer search with distance filters.
- **Ugly Produce Marketplace** — fruits and vegetables with irregular shapes or cosmetic imperfections sold at discounted prices, reducing waste and recovering value for farmers.
- **Live inventory and freshness indicators** — harvest-batch model with per-category shelf life.
- **Flexible delivery** — farmer delivery or self-pickup.
- **Group buying** — community bulk orders at discounted prices.
- **Reviews and ratings** — verified-purchase reviews only.
- **Analytics dashboards** — for farmers and administrators.
- **Admin module** — verifies farmer registrations (KYC), manages users, and moderates reported content.
- **Subscriptions** *(roadmap R2)* — recurring orders for frequently purchased products.

## Tech stack (corrected, v2.0)

| Layer | Technology | Why it is used |
|---|---|---|
| Frontend | HTML5, CSS3, Bootstrap 5, JavaScript (ES6) | Structure, styling, responsive pre-built components, and client-side logic (filtering, cart, API calls). |
| Backend / Database | Firebase Firestore (Spark plan) | Stores users, products, orders, reviews, and inventory in a scalable NoSQL cloud database with real-time sync. |
| Authentication | Firebase Authentication | Secure email/password login for Farmers, Consumers, and Admin with role-based custom claims. |
| Image storage | Cloudinary (free tier) | Product images and farmer profile images via unsigned upload preset. *(Replaces Firebase Storage — no free bucket on new projects.)* |
| Maps & location | Leaflet + OpenStreetMap + Nominatim | Farmer locations, nearby search, distance filtering — fully free. *(Replaces Google Maps API — billing card required.)* |
| API + business logic | Flask (Python) on Render | Verifies Firebase ID tokens and owns **all writes** (orders, stock, groups, reviews, KYC). |
| AI / ML | Python, scikit-learn | Fair-price recommendation, demand prediction, personalised recommendations, served through the same Flask API. |
| Dev tools | VS Code, Git, GitHub | Development, version control, collaboration; GitHub Actions cron for roadmap jobs. |

## MVP scope (2-day sprint)

Core marketplace loop (signup → list → discover → order → status flow), Leaflet nearby-farmer discovery, demo-grade AI (price suggestion, recommendations, demand highlights), and the Ugly Produce Marketplace. Group buying, Razorpay test checkout and the admin KYC queue are stretch goals; everything else is phased into the roadmap (see [08-build-plan.md](08-build-plan.md)).
