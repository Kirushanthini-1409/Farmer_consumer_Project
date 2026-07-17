# 4. Data Model (Firestore collections)

| Collection | Purpose | Key fields |
|---|---|---|
| `users` | All accounts, role-based | `role` (consumer\|farmer\|admin), `name`, `email`, `phone`, `lat`, `lng`, `geohash`, `verified` (farmers), `rating_avg`, `rating_count`, `created_at` |
| `products` | Farmer catalogue entries | `farmer_id`, `name`, `category` (vegetable\|fruit\|dairy\|eggs\|grains\|homemade), `description`, `image_url`, `base_price`, `unit`, `active` |
| `batches` | Sellable inventory lots | `product_id`, `farmer_id`, `qty_available`, `price`, `harvest_date`, `shelf_life_days`, `is_ugly`, `discount_pct`, `created_at` |
| `orders` | One per purchase | `consumer_id`, `farmer_id`, `items[{batch_id, qty, unit_price}]`, `total`, `status`, `delivery_type` (delivery\|pickup), `payment_mode`, `address`, `created_at` |
| `orders/{id}/order_events` | Audit trail (sub-collection) | `actor_uid`, `from_status`, `to_status`, `note`, `at` |
| `group_orders` | Group buying | `batch_id`, `farmer_id`, `target_qty`, `joined_qty`, `discounted_price`, `deadline`, `radius_km`, `status` (open\|met\|cancelled), `members[{uid, qty}]` |
| `reviews` | Verified-purchase reviews | `product_id`, `farmer_id`, `consumer_id`, `order_id`, `stars`, `text`, `created_at`, `hidden` |
| `kyc_requests` | Farmer verification queue | `farmer_id`, `id_doc_url`, `land_doc_url`, `status` (pending\|approved\|rejected), `reviewed_by`, `reviewed_at` |
| `reports` | Moderation | `target_type` (product\|review), `target_id`, `reporter_id`, `reason`, `status` |
| `notifications` | In-app notifications | `uid`, `type`, `text`, `order_id?`, `read`, `created_at` |
| `price_reference` | Cached mandi price data | `commodity`, `market`, `state`, `modal_price`, `date` (loaded from the Agmarknet CSV) |
| `ledger` *(roadmap)* | Escrow money trail | `order_id`, `type` (capture\|release\|refund), `amount`, `balance_after`, `at` |
| `subscriptions` *(roadmap)* | Recurring orders | `consumer_id`, batch/product ref, `qty`, `frequency`, `next_run`, `status` |

Notes:

- All writes to every collection go through the Flask backend (service account); Firestore security rules set `allow write: if false` for clients — see [02-architecture.md](02-architecture.md).
- `notifications` has no dedicated API endpoint: the backend writes notifications as a side effect of other actions (order transitions, group-order resolution) and the UI reads them for the signed-in user.
- The `ledger` is append-only by design, giving a full money audit trail once Razorpay escrow lands (roadmap R1).
