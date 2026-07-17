# 2. Architecture

## 2.1 Overview

```
        Browser  (Consumer / Farmer / Admin)
        HTML + CSS + Bootstrap 5 + Vanilla JS (ES6)
        Firebase Auth SDK          Leaflet + OpenStreetMap
            |                                |
            |  Firebase ID token on          |  image uploads
            |  every API call                |  (unsigned preset)
            v                                v
   +---------------------------+      +----------------+
   |  Flask backend  (Render)  |      |   Cloudinary   |
   |  - verifies ID tokens     |      |  (images, free)|
   |    with firebase-admin    |      +----------------+
   |  - ALL writes: orders,    |
   |    stock, groups, reviews,|
   |    KYC decisions          |
   |  - scikit-learn models:   |
   |    price / demand / recs  |
   +------------+--------------+
                |  service-account credentials
                v
   +---------------------------+
   |  Firebase  (Spark, free)  |
   |  - Authentication         |
   |  - Firestore (database)   |
   |  - Hosting (frontend)     |
   +---------------------------+

   Browser reads PUBLIC data (products, farmers, reviews) directly
   from Firestore for speed; every WRITE goes through Flask.
```

## 2.2 The trust boundary (the key upgrade over v1)

- **Reads:** the browser queries Firestore directly for public data (product catalogue, farmer profiles, reviews) and its own orders — fast, real-time, and free of backend load.
- **Writes:** the browser never writes orders, stock, group orders, reviews, or verification state. It calls the Flask API with the user's Firebase ID token; Flask verifies the token with `firebase-admin`, checks the role (custom claim: `consumer` / `farmer` / `admin`), and performs the write with service-account credentials inside a Firestore transaction.
- **Why it matters:** prices, stock and order totals computed in browser JavaScript can be edited by anyone in DevTools. Recomputing them server-side is what makes the marketplace logic trustworthy.

## 2.3 Firestore security rules (sketch)

```
rules_version = '2';
service cloud.firestore {
  match /databases/{db}/documents {
    match /products/{id}   { allow read: if true;  allow write: if false; }
    match /batches/{id}    { allow read: if true;  allow write: if false; }
    match /users/{uid}     { allow read: if request.auth.uid == uid
                                        || resource.data.role == 'farmer';
                             allow write: if false; }
    match /orders/{id}     { allow read: if request.auth.uid == resource.data.consumer_id
                                        || request.auth.uid == resource.data.farmer_id;
                             allow write: if false; }
    match /reviews/{id}    { allow read: if true;  allow write: if false; }
    // 'allow write: if false' = only the backend service account writes.
  }
}
```

## 2.4 Geolocation without Google

- **Farmer registration:** pick location on a Leaflet map (or one Nominatim geocode of the address — free, 1 request/second, requires an app `User-Agent`). Store `lat`, `lng` and a geohash.
- **MVP distance filter:** fetch farmers in the region and compute haversine distance client-side — fine at demo scale, zero extra infrastructure.
- **Scale-up path (documented, not built):** geohash range queries with the `geofire-common` library so "farmers within 5 km" stays cheap at thousands of farmers.

## 2.5 Hardening checklist

- CORS locked to the Firebase Hosting origin; `flask-limiter` rate limits (e.g., 60 req/min/IP, stricter on writes).
- All secrets (service-account JSON, Cloudinary keys) live in Render environment variables — never in the repo.
- Input validation on every endpoint (pydantic or marshmallow); quantities and prices validated server-side.
- Cloudinary uploads via an unsigned preset restricted to images with a size cap; the backend stores only the returned URL.
- Structured logging of every state transition (already required by `order_events`).
