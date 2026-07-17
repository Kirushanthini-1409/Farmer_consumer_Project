"""Verified-purchase reviews + content reports."""
from flask import Blueprint, g, jsonify, request
from firebase_admin import firestore

import firebase
from auth_guard import require_auth
from helpers import bad_request, notify

bp = Blueprint("reviews", __name__)


@bp.post("/reviews")
@require_auth(roles=["consumer"])
def create_review():
    """Only a consumer with a COMPLETED order for the product may review it."""
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    order_id = body.get("order_id")
    try:
        stars = int(body["stars"])
    except (KeyError, TypeError, ValueError):
        return bad_request("stars (1-5) is required")
    if not (1 <= stars <= 5):
        return bad_request("stars must be 1-5")
    if not product_id or not order_id:
        return bad_request("product_id and order_id are required")

    db = firebase.db()
    order_snap = db.collection("orders").document(order_id).get()
    if not order_snap.exists:
        return bad_request("Unknown order")
    order = order_snap.to_dict()
    if order["consumer_id"] != g.user["uid"]:
        return jsonify({"error": "Not your order"}), 403
    if order["status"] != "COMPLETED":
        return bad_request("Reviews unlock after the order is COMPLETED")
    if not any(i["product_id"] == product_id for i in order["items"]):
        return bad_request("This order does not contain that product")

    dup = (
        db.collection("reviews")
        .where("order_id", "==", order_id)
        .where("product_id", "==", product_id)
        .limit(1)
        .get()
    )
    if len(list(dup)) > 0:
        return bad_request("You already reviewed this product for this order")

    farmer_id = order["farmer_id"]
    db.collection("reviews").add(
        {
            "product_id": product_id,
            "farmer_id": farmer_id,
            "consumer_id": g.user["uid"],
            "order_id": order_id,
            "stars": stars,
            "text": (body.get("text") or "").strip(),
            "hidden": False,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )

    # Farmer rating = average over visible verified reviews.
    visible = [
        r.to_dict()["stars"]
        for r in db.collection("reviews")
        .where("farmer_id", "==", farmer_id)
        .where("hidden", "==", False)
        .get()
    ]
    db.collection("users").document(farmer_id).update(
        {
            "rating_avg": round(sum(visible) / len(visible), 2) if visible else 0,
            "rating_count": len(visible),
        }
    )
    notify(db, farmer_id, "review", f"New {stars}-star review", order_id)
    return jsonify({"ok": True}), 201


@bp.post("/reports")
@require_auth()
def report_content():
    """Any listing or review can be reported with a reason; lands in the admin queue."""
    body = request.get_json(silent=True) or {}
    target_type = body.get("target_type")
    target_id = body.get("target_id")
    reason = (body.get("reason") or "").strip()
    if target_type not in ("product", "review"):
        return bad_request("target_type must be product or review")
    if not target_id or not reason:
        return bad_request("target_id and reason are required")

    db = firebase.db()
    collection = "products" if target_type == "product" else "reviews"
    if not db.collection(collection).document(target_id).get().exists:
        return bad_request(f"Unknown {target_type}")

    db.collection("reports").add(
        {
            "target_type": target_type,
            "target_id": target_id,
            "reporter_id": g.user["uid"],
            "reason": reason,
            "status": "pending",
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return jsonify({"ok": True}), 201
