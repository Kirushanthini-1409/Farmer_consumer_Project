"""Products, batches (inventory lots) and the public /browse catalogue."""
from flask import Blueprint, g, jsonify, request
from firebase_admin import firestore

import config
import firebase
from auth_guard import require_auth
from helpers import bad_request, doc_with_id, effective_price, haversine_km, parse_date

bp = Blueprint("catalog", __name__)


def _validate_product(body):
    name = (body.get("name") or "").strip()
    if not name:
        return None, "name is required"
    category = body.get("category")
    if category not in config.VALID_CATEGORIES:
        return None, f"category must be one of {config.VALID_CATEGORIES}"
    try:
        base_price = float(body.get("base_price", 0))
    except (TypeError, ValueError):
        return None, "base_price must be a number"
    if base_price <= 0:
        return None, "base_price must be positive"
    return {
        "name": name,
        "category": category,
        "description": (body.get("description") or "").strip(),
        "image_url": (body.get("image_url") or "").strip(),
        "base_price": base_price,
        "unit": (body.get("unit") or "kg").strip(),
        "active": bool(body.get("active", True)),
    }, None


@bp.post("/products")
@require_auth(roles=["farmer"])
def create_product():
    data, err = _validate_product(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    db = firebase.db()
    data.update({"farmer_id": g.user["uid"], "created_at": firestore.SERVER_TIMESTAMP})
    ref = db.collection("products").add(data)[1]
    return jsonify({"id": ref.id, **{k: v for k, v in data.items() if k != "created_at"}}), 201


@bp.put("/products/<pid>")
@require_auth(roles=["farmer"])
def update_product(pid):
    db = firebase.db()
    ref = db.collection("products").document(pid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "Product not found"}), 404
    if snap.to_dict().get("farmer_id") != g.user["uid"]:
        return jsonify({"error": "Not your product"}), 403
    data, err = _validate_product(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    ref.update(data)
    return jsonify({"id": pid, **data})


@bp.get("/products/mine")
@require_auth(roles=["farmer"])
def my_products():
    db = firebase.db()
    snaps = db.collection("products").where("farmer_id", "==", g.user["uid"]).get()
    return jsonify([doc_with_id(s) for s in snaps])


@bp.post("/batches")
@require_auth(roles=["farmer"])
def create_batch():
    body = request.get_json(silent=True) or {}
    db = firebase.db()

    product_snap = db.collection("products").document(body.get("product_id", "")).get()
    if not product_snap.exists:
        return bad_request("Unknown product_id")
    product = product_snap.to_dict()
    if product["farmer_id"] != g.user["uid"]:
        return jsonify({"error": "Not your product"}), 403

    try:
        qty = float(body["qty_available"])
        price = float(body["price"])
        harvest_date = parse_date(body["harvest_date"])
    except (KeyError, TypeError, ValueError):
        return bad_request("qty_available, price and harvest_date (YYYY-MM-DD) are required")
    if qty <= 0 or price <= 0:
        return bad_request("qty_available and price must be positive")

    is_ugly = bool(body.get("is_ugly", False))
    discount_pct = int(body.get("discount_pct") or 0)
    if is_ugly:
        # Ugly batches carry a mandatory discount within the configured range.
        if not (config.UGLY_DISCOUNT_MIN_PCT <= discount_pct <= config.UGLY_DISCOUNT_MAX_PCT):
            return bad_request(
                f"Ugly batches need discount_pct between {config.UGLY_DISCOUNT_MIN_PCT} "
                f"and {config.UGLY_DISCOUNT_MAX_PCT}"
            )

    batch = {
        "product_id": product_snap.id,
        "farmer_id": g.user["uid"],
        "qty_available": qty,
        "unit": product.get("unit", "kg"),
        "price": price,
        "harvest_date": harvest_date,
        "shelf_life_days": int(body["shelf_life_days"]) if body.get("shelf_life_days") else None,
        "is_ugly": is_ugly,
        "discount_pct": discount_pct if is_ugly else 0,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    ref = db.collection("batches").add(batch)[1]

    # Advisory (never blocking): compare against the AI fair-price band.
    warning = None
    try:
        from ai.pricing import price_band

        band = price_band(product["name"], product["category"], is_ugly, harvest_date)
        if band and not (band["low"] <= price <= band["high"]):
            warning = (
                f"Price ₹{price:.0f} is outside the suggested fair band "
                f"₹{band['low']:.0f}–₹{band['high']:.0f}"
            )
    except Exception:
        pass

    return jsonify({"id": ref.id, "warning": warning}), 201


@bp.patch("/batches/<bid>")
@require_auth(roles=["farmer"])
def update_batch(bid):
    body = request.get_json(silent=True) or {}
    db = firebase.db()
    ref = db.collection("batches").document(bid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "Batch not found"}), 404
    if snap.to_dict().get("farmer_id") != g.user["uid"]:
        return jsonify({"error": "Not your batch"}), 403

    updates = {}
    if "price" in body:
        price = float(body["price"])
        if price <= 0:
            return bad_request("price must be positive")
        updates["price"] = price
    if "qty_available" in body:
        qty = float(body["qty_available"])
        if qty < 0:
            return bad_request("qty_available cannot be negative")
        updates["qty_available"] = qty
    if "is_ugly" in body or "discount_pct" in body:
        current = snap.to_dict()
        is_ugly = bool(body.get("is_ugly", current.get("is_ugly")))
        discount_pct = int(body.get("discount_pct", current.get("discount_pct") or 0))
        if is_ugly and not (
            config.UGLY_DISCOUNT_MIN_PCT <= discount_pct <= config.UGLY_DISCOUNT_MAX_PCT
        ):
            return bad_request(
                f"Ugly batches need discount_pct between {config.UGLY_DISCOUNT_MIN_PCT} "
                f"and {config.UGLY_DISCOUNT_MAX_PCT}"
            )
        updates["is_ugly"] = is_ugly
        updates["discount_pct"] = discount_pct if is_ugly else 0
    if not updates:
        return bad_request("Nothing to update")
    ref.update(updates)
    return jsonify({"id": bid, **updates})


@bp.get("/batches/mine")
@require_auth(roles=["farmer"])
def my_batches():
    db = firebase.db()
    snaps = db.collection("batches").where("farmer_id", "==", g.user["uid"]).get()
    out = []
    products = {}
    for s in snaps:
        b = doc_with_id(s)
        pid = b["product_id"]
        if pid not in products:
            psnap = db.collection("products").document(pid).get()
            products[pid] = psnap.to_dict() if psnap.exists else {}
        category = products[pid].get("category", "vegetable")
        b["product_name"] = products[pid].get("name", "?")
        b["effective_price"], b["applied_discount_pct"], b["freshness"] = effective_price(
            b, category
        )
        b["harvest_date"] = str(b["harvest_date"])[:10]
        out.append(b)
    return jsonify(out)


@bp.get("/browse")
def browse():
    """Public catalogue with filters: category, price range, ugly-only, in-stock,
    max distance from caller lat/lng. Joins products + in-stock batches + farmer info."""
    db = firebase.db()
    args = request.args
    category = args.get("category")
    ugly_only = args.get("ugly_only") == "1"
    max_price = float(args["max_price"]) if args.get("max_price") else None
    min_price = float(args["min_price"]) if args.get("min_price") else None
    try:
        lat = float(args["lat"]) if args.get("lat") else None
        lng = float(args["lng"]) if args.get("lng") else None
        max_km = float(args["max_km"]) if args.get("max_km") else None
    except ValueError:
        return bad_request("lat/lng/max_km must be numbers")

    products_q = db.collection("products").where("active", "==", True)
    if category:
        products_q = products_q.where("category", "==", category)
    products = {s.id: s.to_dict() for s in products_q.get()}
    if not products:
        return jsonify({"items": [], "farmers": []})

    farmer_ids = {p["farmer_id"] for p in products.values()}
    farmers = {}
    for fid in farmer_ids:
        fsnap = db.collection("users").document(fid).get()
        if fsnap.exists:
            f = fsnap.to_dict()
            farmers[fid] = {
                "id": fid,
                "name": f.get("name"),
                "verified": bool(f.get("verified")),
                "rating_avg": f.get("rating_avg", 0),
                "rating_count": f.get("rating_count", 0),
                "lat": f.get("lat"),
                "lng": f.get("lng"),
            }
            if lat is not None and lng is not None and f.get("lat") is not None:
                farmers[fid]["distance_km"] = round(
                    haversine_km(lat, lng, f["lat"], f["lng"]), 1
                )

    items = []
    batch_snaps = db.collection("batches").where("qty_available", ">", 0).get()
    for s in batch_snaps:
        b = doc_with_id(s)
        product = products.get(b["product_id"])
        if not product:
            continue
        if ugly_only and not b.get("is_ugly"):
            continue
        farmer = farmers.get(b["farmer_id"])
        if not farmer:
            continue
        if max_km is not None and farmer.get("distance_km") is not None:
            if farmer["distance_km"] > max_km:
                continue
        price, discount_pct, fresh = effective_price(b, product["category"])
        if fresh["expired"]:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_price is not None and price < min_price:
            continue
        items.append(
            {
                "batch_id": b["id"],
                "product_id": b["product_id"],
                "name": product["name"],
                "category": product["category"],
                "description": product.get("description", ""),
                "image_url": product.get("image_url", ""),
                "unit": b.get("unit", "kg"),
                "qty_available": b["qty_available"],
                "list_price": b["price"],
                "price": price,
                "discount_pct": discount_pct,
                "is_ugly": bool(b.get("is_ugly")),
                "freshness": fresh,
                "farmer": farmer,
            }
        )

    items.sort(key=lambda i: (i["farmer"].get("distance_km") or 9999, i["price"]))
    return jsonify({"items": items, "farmers": list(farmers.values())})
