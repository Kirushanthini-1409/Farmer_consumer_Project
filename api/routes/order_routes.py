"""Order checkout + state-machine transitions. All stock mutations happen inside
Firestore transactions so concurrent buyers can never oversell a batch."""
from datetime import datetime, timedelta, timezone

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

from flask import Blueprint, g, jsonify, request
from firebase_admin import firestore

import config
import firebase
import state_machine
from auth_guard import require_auth
from helpers import bad_request, doc_with_id, effective_price, notify, utcnow

bp = Blueprint("orders", __name__)


def _append_event(order_ref, actor_uid, from_status, to_status, note=""):
    order_ref.collection("order_events").add(
        {
            "actor_uid": actor_uid,
            "from_status": from_status,
            "to_status": to_status,
            "note": note,
            "at": firestore.SERVER_TIMESTAMP,
        }
    )


def _restock(db, transaction, order):
    """Give reserved quantities back to their batches (must run inside the transaction)."""
    for item in order["items"]:
        batch_ref = db.collection("batches").document(item["batch_id"])
        snap = batch_ref.get(transaction=transaction)
        if snap.exists:
            transaction.update(
                batch_ref,
                {"qty_available": firestore.Increment(item["qty"])},
            )


def _award_kg_saved(db, order):
    """On COMPLETED: count ugly-batch kilograms toward farmer + platform impact totals."""
    kg = sum(i["qty"] for i in order["items"] if i.get("is_ugly"))
    if kg <= 0:
        return
    db.collection("users").document(order["farmer_id"]).update(
        {"kg_saved": firestore.Increment(kg)}
    )
    db.collection("stats").document("platform").set(
        {"kg_saved": firestore.Increment(kg)}, merge=True
    )


@bp.post("/orders")
@require_auth(roles=["consumer"])
def checkout():
    """Cart -> PLACED order. Prices are recomputed server-side; stock is reserved atomically."""
    body = request.get_json(silent=True) or {}
    items_in = body.get("items") or []
    delivery_type = body.get("delivery_type")
    if delivery_type not in ("delivery", "pickup"):
        return bad_request("delivery_type must be delivery or pickup")
    if not items_in or not isinstance(items_in, list):
        return bad_request("items is required")
    if delivery_type == "delivery" and not (body.get("address") or "").strip():
        return bad_request("address is required for delivery")

    db = firebase.db()
    transaction = db.transaction()

    @firestore.transactional
    def place(transaction):
        # -- reads first (Firestore transaction rule) --
        resolved = []
        farmer_ids = set()
        for it in items_in:
            try:
                qty = float(it["qty"])
                batch_id = str(it["batch_id"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Each item needs batch_id and qty")
            if qty <= 0:
                raise ValueError("qty must be positive")
            batch_ref = db.collection("batches").document(batch_id)
            batch_snap = batch_ref.get(transaction=transaction)
            if not batch_snap.exists:
                raise ValueError(f"Batch {batch_id} not found")
            batch = batch_snap.to_dict()
            if batch["qty_available"] < qty:
                raise ValueError(
                    f"Only {batch['qty_available']} {batch.get('unit','kg')} left of this batch"
                )
            product_snap = db.collection("products").document(batch["product_id"]).get(
                transaction=transaction
            )
            product = product_snap.to_dict() if product_snap.exists else {}
            unit_price, _, _ = effective_price(batch, product.get("category", "vegetable"))
            farmer_ids.add(batch["farmer_id"])
            resolved.append(
                {
                    "batch_ref": batch_ref,
                    "batch_id": batch_id,
                    "product_id": batch["product_id"],
                    "product_name": product.get("name", "?"),
                    "qty": qty,
                    "unit": batch.get("unit", "kg"),
                    "unit_price": unit_price,
                    "is_ugly": bool(batch.get("is_ugly")),
                    "farmer_id": batch["farmer_id"],
                }
            )
        if len(farmer_ids) != 1:
            raise ValueError("One order per farmer — split your cart by farmer")

        # -- writes --
        for r in resolved:
            transaction.update(
                r["batch_ref"], {"qty_available": firestore.Increment(-r["qty"])}
            )
        order_ref = db.collection("orders").document()
        order = {
            "consumer_id": g.user["uid"],
            "farmer_id": farmer_ids.pop(),
            "items": [
                {k: r[k] for k in ("batch_id", "product_id", "product_name", "qty", "unit", "unit_price", "is_ugly")}
                for r in resolved
            ],
            "total": round(sum(r["qty"] * r["unit_price"] for r in resolved), 2),
            "status": "PLACED",
            "delivery_type": delivery_type,
            "payment_mode": "COD/simulated",
            "address": (body.get("address") or "").strip(),
            "created_at": firestore.SERVER_TIMESTAMP,
            "placed_at": utcnow(),
            "delivered_at": None,
        }
        transaction.set(order_ref, order)
        return order_ref, order

    try:
        order_ref, order = place(transaction)
    except ValueError as e:
        return bad_request(str(e))

    _append_event(order_ref, g.user["uid"], None, "PLACED", "Order placed (simulated payment)")
    notify(db, order["farmer_id"], "order", "New order received", order_ref.id)
    return jsonify({"id": order_ref.id, "total": order["total"], "status": "PLACED"}), 201


def _apply_lazy_timeouts(db, order_ref, order):
    """MVP: time-based transitions run when an order is next read, instead of a cron.
    - PLACED older than 12 h  -> CANCELLED (stock restored)
    - DELIVERED older than 48 h -> COMPLETED"""
    now = utcnow()
    status = order["status"]
    if status == "PLACED" and order.get("placed_at"):
        if now - order["placed_at"] > timedelta(hours=config.FARMER_ACCEPT_TIMEOUT_H):
            transaction = db.transaction()

            @firestore.transactional
            def auto_cancel(transaction):
                snap = order_ref.get(transaction=transaction)
                current = snap.to_dict()
                if current["status"] != "PLACED":
                    return current["status"]
                _restock(db, transaction, current)
                transaction.update(order_ref, {"status": "CANCELLED"})
                return "CANCELLED"

            new_status = auto_cancel(transaction)
            if new_status == "CANCELLED":
                _append_event(order_ref, "system", "PLACED", "CANCELLED", "12h accept timeout")
                order["status"] = "CANCELLED"
    elif status == "DELIVERED" and order.get("delivered_at"):
        if now - order["delivered_at"] > timedelta(hours=config.AUTO_COMPLETE_AFTER_H):
            order_ref.update({"status": "COMPLETED"})
            _append_event(order_ref, "system", "DELIVERED", "COMPLETED", "48h auto-complete")
            order["status"] = "COMPLETED"
            _award_kg_saved(db, order)
    return order


@bp.get("/orders")
@require_auth()
def list_orders():
    """Own orders (consumer or farmer side), with lazy timeout resolution applied."""
    db = firebase.db()
    field = "farmer_id" if g.user["role"] == "farmer" else "consumer_id"
    # No order_by here: filter + order_by would need a composite Firestore index;
    # sorting in Python keeps the demo zero-setup.
    snaps = db.collection("orders").where(field, "==", g.user["uid"]).limit(100).get()
    snaps = sorted(snaps, key=lambda s: s.to_dict().get("placed_at") or EPOCH, reverse=True)[:50]
    out = []
    for s in snaps:
        order = doc_with_id(s)
        order = _apply_lazy_timeouts(db, s.reference, order)
        for key in ("created_at", "placed_at", "delivered_at"):
            if order.get(key):
                order[key] = str(order[key])
        out.append(order)
    return jsonify(out)


@bp.get("/orders/<oid>/events")
@require_auth()
def order_events(oid):
    db = firebase.db()
    order_ref = db.collection("orders").document(oid)
    snap = order_ref.get()
    if not snap.exists:
        return jsonify({"error": "Order not found"}), 404
    order = snap.to_dict()
    if g.user["uid"] not in (order["consumer_id"], order["farmer_id"]) and g.user["role"] != "admin":
        return jsonify({"error": "Not your order"}), 403
    events = order_ref.collection("order_events").order_by("at").get()
    out = []
    for e in events:
        d = e.to_dict()
        d["at"] = str(d.get("at"))
        out.append(d)
    return jsonify(out)


@bp.post("/orders/<oid>/transition")
@require_auth()
def transition(oid):
    """Single guarded endpoint for every state-machine move; rejects illegal transitions."""
    body = request.get_json(silent=True) or {}
    action = body.get("action")
    if not action:
        return bad_request("action is required")

    db = firebase.db()
    order_ref = db.collection("orders").document(oid)
    transaction = db.transaction()

    @firestore.transactional
    def do_transition(transaction):
        snap = order_ref.get(transaction=transaction)
        if not snap.exists:
            return None, ("Order not found", 404)
        order = snap.to_dict()
        to_state, err = state_machine.resolve(
            order["status"],
            action,
            g.user["role"],
            is_order_consumer=(g.user["uid"] == order["consumer_id"]),
            is_order_farmer=(g.user["uid"] == order["farmer_id"]),
        )
        if err:
            return None, (err, 409 if "Illegal" in err else 403)
        updates = {"status": to_state}
        if to_state == "DELIVERED":
            updates["delivered_at"] = utcnow()
        if to_state in state_machine.RESTOCK_STATES:
            _restock(db, transaction, order)
        transaction.update(order_ref, updates)
        return (order["status"], to_state, order), None

    result, err = do_transition(transaction)
    if err:
        return jsonify({"error": err[0]}), err[1]
    from_state, to_state, order = result

    _append_event(order_ref, g.user["uid"], from_state, to_state, body.get("note", ""))
    if to_state == "COMPLETED":
        _award_kg_saved(db, order)

    other = order["farmer_id"] if g.user["uid"] == order["consumer_id"] else order["consumer_id"]
    notify(db, other, "order", f"Order moved to {to_state}", oid)
    return jsonify({"id": oid, "status": to_state})
