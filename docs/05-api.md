# 5. Flask API Surface

All endpoints expect `Authorization: Bearer <Firebase ID token>` unless marked **public**. Roles are enforced server-side via Firebase custom claims (`consumer` / `farmer` / `admin`).

| Endpoint | Who | Purpose |
|---|---|---|
| `POST /auth/register-profile` | any signed-in user | Create the Firestore user profile + role after Firebase signup; sets the role custom claim. |
| `GET /me` | any | Own profile, role, verification status. |
| `POST /products` · `PUT /products/{id}` | farmer | Create/update a product (image URL from Cloudinary). |
| `POST /batches` · `PATCH /batches/{id}` | farmer | Add inventory lots; set `is_ugly` + discount; server validates price against the AI fair-price band (warning, not a block). |
| `GET /browse` | **public** | Catalogue with filters: category, max distance, price range, ugly-only, in-stock; distance computed from caller lat/lng. |
| `POST /orders` | consumer | Checkout: validates cart server-side, reserves stock in a transaction, creates PLACED order + event. |
| `POST /orders/{id}/transition` | farmer / consumer / admin | Single guarded endpoint for all state-machine moves (accept, pack, deliver, cancel, dispute); rejects illegal transitions. |
| `POST /group-orders` · `POST /group-orders/{id}/join` | farmer / consumer | Open a group; transactional join capped at `target_qty`; deadline resolution on read (MVP). |
| `POST /reviews` | consumer | Only if the caller has a COMPLETED order for the product. |
| `POST /admin/kyc/{id}/decide` · `POST /admin/reports/{id}/decide` | admin | Approve/reject verification; hide/dismiss reported content. |
| `GET /ai/price-suggest?product=&is_ugly=&harvest_date=` | farmer | Fair-price band from the mandi-data model + adjustments. |
| `GET /ai/recommendations` | consumer | Personalised product list (popularity + content-based). |
| `GET /ai/demand` | farmer | "In demand this week" categories with expected direction. |
| `POST /ai/retrain` *(roadmap)* | cron | Retrain models blending live transactions with mandi data. |

Conventions:

- Every write endpoint runs inside a Firestore transaction where stock or shared state is involved.
- Illegal state-machine transitions return an error; every successful transition appends an `order_events` document.
- Rate limiting via `flask-limiter` (stricter on writes); CORS locked to the Firebase Hosting origin.
