"""AI endpoints: price suggestion, personalised recommendations, demand chips, retrain."""
import os

from flask import Blueprint, g, jsonify, request
from firebase_admin import firestore

import firebase
from ai import demand as demand_ai
from ai import pricing
from ai import recommend
from auth_guard import require_auth
from helpers import bad_request

bp = Blueprint("ai", __name__)


@bp.get("/ai/price-suggest")
@require_auth(roles=["farmer"])
def price_suggest():
    args = request.args
    product = (args.get("product") or "").strip()
    if not product:
        return bad_request("product is required")
    category = args.get("category", "vegetable")
    is_ugly = args.get("is_ugly") == "1"
    harvest_date = args.get("harvest_date") or None
    try:
        band = pricing.price_band(product, category, is_ugly, harvest_date)
    except ValueError:
        return bad_request("harvest_date must be YYYY-MM-DD")
    if band is None:
        return jsonify({"error": "Price model unavailable (mandi CSV missing)"}), 503
    return jsonify(band)


@bp.get("/ai/recommendations")
@require_auth(roles=["consumer"])
def recs():
    args = request.args
    lat = float(args["lat"]) if args.get("lat") else None
    lng = float(args["lng"]) if args.get("lng") else None
    db = firebase.db()
    return jsonify(recommend.recommendations(db, g.user["uid"], lat, lng))


@bp.post("/ai/browse-event")
@require_auth(roles=["consumer"])
def browse_event():
    """Lightweight browsing-history signal used by the recommender."""
    body = request.get_json(silent=True) or {}
    category = body.get("category")
    if not category:
        return bad_request("category is required")
    db = firebase.db()
    db.collection("browse_history").add(
        {
            "uid": g.user["uid"],
            "category": category,
            "product_id": body.get("product_id"),
            "at": firestore.SERVER_TIMESTAMP,
        }
    )
    return jsonify({"ok": True}), 201


@bp.get("/ai/demand")
@require_auth(roles=["farmer"])
def demand():
    db = firebase.db()
    return jsonify(demand_ai.demand_signals(db))


@bp.post("/ai/retrain")
def retrain():
    """Roadmap endpoint, called by a GitHub Actions cron with a shared secret.
    Blends live platform transaction prices into the mandi model."""
    secret = os.environ.get("RETRAIN_SECRET", "")
    if not secret or request.headers.get("X-Retrain-Secret") != secret:
        return jsonify({"error": "Forbidden"}), 403
    db = firebase.db()
    extra = []
    for snap in db.collection("orders").where("status", "==", "COMPLETED").limit(500).get():
        order = snap.to_dict()
        for item in order.get("items", []):
            psnap = db.collection("products").document(item["product_id"]).get()
            if psnap.exists:
                extra.append(
                    {
                        "commodity": psnap.to_dict().get("name", ""),
                        "modal_price": item["unit_price"],
                        "date": str(order.get("placed_at") or "")[:10] or "2026-01-01",
                    }
                )
    info = pricing.train(extra_rows=extra or None)
    return jsonify({"ok": True, "blended_transactions": len(extra), **info})
