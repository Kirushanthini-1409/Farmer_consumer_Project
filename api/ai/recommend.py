"""Personalised recommendations v1: popularity + content-based (same categories the
consumer browsed/bought, nearby, in stock). v2 (roadmap): collaborative filtering
once the user-item matrix is dense enough."""
from collections import Counter

from helpers import doc_with_id, effective_price, haversine_km


def recommendations(db, uid, lat=None, lng=None, limit=8):
    # 1. Consumer taste profile from purchase + browsing history.
    category_weight = Counter()
    bought_products = set()
    for snap in db.collection("orders").where("consumer_id", "==", uid).limit(50).get():
        order = snap.to_dict()
        if order.get("status") in ("CANCELLED", "REJECTED"):
            continue
        for item in order.get("items", []):
            bought_products.add(item["product_id"])
            psnap = db.collection("products").document(item["product_id"]).get()
            if psnap.exists:
                category_weight[psnap.to_dict().get("category", "vegetable")] += 2
    for snap in (
        db.collection("browse_history").where("uid", "==", uid).limit(100).get()
    ):
        category_weight[snap.to_dict().get("category", "vegetable")] += 1

    # 2. Popularity: units sold per product across the platform.
    popularity = Counter()
    for snap in db.collection("orders").limit(300).get():
        order = snap.to_dict()
        if order.get("status") in ("CANCELLED", "REJECTED"):
            continue
        for item in order.get("items", []):
            popularity[item["product_id"]] += item["qty"]

    # 3. Score in-stock batches.
    products = {s.id: s.to_dict() for s in db.collection("products").where("active", "==", True).get()}
    farmers = {}
    scored = []
    for snap in db.collection("batches").where("qty_available", ">", 0).get():
        b = doc_with_id(snap)
        product = products.get(b["product_id"])
        if not product:
            continue
        fid = b["farmer_id"]
        if fid not in farmers:
            fsnap = db.collection("users").document(fid).get()
            farmers[fid] = fsnap.to_dict() if fsnap.exists else {}
        farmer = farmers[fid]

        price, discount_pct, fresh = effective_price(b, product["category"])
        if fresh["expired"]:
            continue
        score = popularity.get(b["product_id"], 0)
        score += 5 * category_weight.get(product["category"], 0)
        if b["product_id"] in bought_products:
            score += 3  # repeat purchases are likely
        score += 2 * (1 - fresh["life_used"])  # fresher is better
        if lat is not None and lng is not None and farmer.get("lat") is not None:
            dist = haversine_km(lat, lng, farmer["lat"], farmer["lng"])
            score += max(0.0, 10 - dist) / 2  # nearby boost
        scored.append(
            (
                score,
                {
                    "batch_id": b["id"],
                    "product_id": b["product_id"],
                    "name": product["name"],
                    "category": product["category"],
                    "image_url": product.get("image_url", ""),
                    "price": price,
                    "unit": b.get("unit", "kg"),
                    "is_ugly": bool(b.get("is_ugly")),
                    "freshness": fresh["label"],
                    "farmer_name": farmer.get("name", "?"),
                },
            )
        )

    scored.sort(key=lambda t: -t[0])
    seen_products, out = set(), []
    for _, item in scored:
        if item["product_id"] in seen_products:
            continue
        seen_products.add(item["product_id"])
        out.append(item)
        if len(out) >= limit:
            break
    return out
