"""Group buying: open a group on a batch, transactional joins capped at target_qty,
deadline resolution on read (MVP — the roadmap moves this to a cron)."""
from flask import Blueprint, g, jsonify, request
from firebase_admin import firestore

import config
import firebase
from auth_guard import require_auth
from helpers import bad_request, doc_with_id, haversine_km, notify, parse_date, utcnow

bp = Blueprint("groups", __name__)


def _resolve_if_due(db, ref, group):
    """At/after the deadline: target met -> one CONFIRMED order per member and a single
    stock decrement; target missed -> group cancelled. Idempotent via status check."""
    if group["status"] != "open" or utcnow() < group["deadline"]:
        return group

    transaction = db.transaction()

    @firestore.transactional
    def resolve(transaction):
        snap = ref.get(transaction=transaction)
        grp = snap.to_dict()
        if grp["status"] != "open":
            return grp
        met = grp["joined_qty"] >= grp["target_qty"]
        batch_ref = db.collection("batches").document(grp["batch_id"])
        batch_snap = batch_ref.get(transaction=transaction)
        if met and batch_snap.exists and batch_snap.to_dict()["qty_available"] >= grp["joined_qty"]:
            transaction.update(
                batch_ref, {"qty_available": firestore.Increment(-grp["joined_qty"])}
            )
            transaction.update(ref, {"status": "met"})
            grp["status"] = "met"
        else:
            transaction.update(ref, {"status": "cancelled"})
            grp["status"] = "cancelled"
        return grp

    group = resolve(transaction)

    if group["status"] == "met":
        batch = db.collection("batches").document(group["batch_id"]).get().to_dict()
        product = db.collection("products").document(group["product_id"]).get().to_dict() or {}
        for m in group["members"]:
            order_ref = db.collection("orders").document()
            order_ref.set(
                {
                    "consumer_id": m["uid"],
                    "farmer_id": group["farmer_id"],
                    "items": [
                        {
                            "batch_id": group["batch_id"],
                            "product_id": group["product_id"],
                            "product_name": product.get("name", "?"),
                            "qty": m["qty"],
                            "unit": batch.get("unit", "kg") if batch else "kg",
                            "unit_price": group["discounted_price"],
                            "is_ugly": bool(batch.get("is_ugly")) if batch else False,
                        }
                    ],
                    "total": round(m["qty"] * group["discounted_price"], 2),
                    "status": "CONFIRMED",
                    "delivery_type": "pickup",
                    "payment_mode": "COD/simulated",
                    "address": "",
                    "group_order_id": ref.id,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "placed_at": utcnow(),
                    "delivered_at": None,
                }
            )
            order_ref.collection("order_events").add(
                {
                    "actor_uid": "system",
                    "from_status": None,
                    "to_status": "CONFIRMED",
                    "note": "Group buy target met",
                    "at": firestore.SERVER_TIMESTAMP,
                }
            )
            notify(db, m["uid"], "group", "Group buy succeeded — order confirmed", order_ref.id)
        notify(db, group["farmer_id"], "group", "Group buy target met", None)
    elif group["status"] == "cancelled":
        for m in group["members"]:
            notify(db, m["uid"], "group", "Group buy did not reach its target and was cancelled")
    return group


@bp.post("/group-orders")
@require_auth(roles=["farmer", "consumer"])
def open_group():
    body = request.get_json(silent=True) or {}
    db = firebase.db()
    batch_snap = db.collection("batches").document(body.get("batch_id", "")).get()
    if not batch_snap.exists:
        return bad_request("Unknown batch_id")
    batch = batch_snap.to_dict()
    if g.user["role"] == "farmer" and batch["farmer_id"] != g.user["uid"]:
        return jsonify({"error": "Not your batch"}), 403
    try:
        target_qty = float(body["target_qty"])
        discounted_price = float(body["discounted_price"])
        deadline = parse_date(body["deadline"])
        radius_km = float(body.get("radius_km", 10))
    except (KeyError, TypeError, ValueError):
        return bad_request("target_qty, discounted_price and deadline are required")
    if target_qty <= 0 or discounted_price <= 0:
        return bad_request("target_qty and discounted_price must be positive")
    if discounted_price >= batch["price"]:
        return bad_request("Discounted price must be below the batch price")
    if deadline <= utcnow():
        return bad_request("Deadline must be in the future")

    ref = db.collection("group_orders").add(
        {
            "batch_id": batch_snap.id,
            "product_id": batch["product_id"],
            "farmer_id": batch["farmer_id"],
            "opened_by": g.user["uid"],
            "target_qty": target_qty,
            "joined_qty": 0,
            "discounted_price": discounted_price,
            "deadline": deadline,
            "radius_km": radius_km,
            "status": "open",
            "members": [],
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )[1]
    return jsonify({"id": ref.id}), 201


@bp.get("/group-orders")
def list_groups():
    """Public list of open groups (resolves due deadlines on read). Optional lat/lng
    filters to groups whose farmer is within the group's radius of the caller."""
    db = firebase.db()
    args = request.args
    lat = float(args["lat"]) if args.get("lat") else None
    lng = float(args["lng"]) if args.get("lng") else None

    out = []
    for s in db.collection("group_orders").where("status", "==", "open").get():
        grp = _resolve_if_due(db, s.reference, doc_with_id(s))
        if grp["status"] != "open":
            continue
        product = db.collection("products").document(grp["product_id"]).get()
        farmer = db.collection("users").document(grp["farmer_id"]).get()
        grp["product_name"] = product.to_dict().get("name", "?") if product.exists else "?"
        fdata = farmer.to_dict() if farmer.exists else {}
        grp["farmer_name"] = fdata.get("name", "?")
        if lat is not None and lng is not None and fdata.get("lat") is not None:
            dist = haversine_km(lat, lng, fdata["lat"], fdata["lng"])
            if dist > grp["radius_km"]:
                continue
            grp["distance_km"] = round(dist, 1)
        grp["deadline"] = str(grp["deadline"])
        grp["created_at"] = str(grp.get("created_at"))
        grp["member_count"] = len(grp.get("members", []))
        grp.pop("members", None)  # membership details are not public
        out.append(grp)
    return jsonify(out)


@bp.post("/group-orders/<gid>/join")
@require_auth(roles=["consumer"])
def join_group(gid):
    body = request.get_json(silent=True) or {}
    try:
        qty = float(body["qty"])
    except (KeyError, TypeError, ValueError):
        return bad_request("qty is required")
    if qty <= 0:
        return bad_request("qty must be positive")

    db = firebase.db()
    ref = db.collection("group_orders").document(gid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "Group not found"}), 404
    group = _resolve_if_due(db, ref, doc_with_id(snap))
    if group["status"] != "open":
        return bad_request(f"Group is {group['status']}")

    transaction = db.transaction()

    @firestore.transactional
    def join(transaction):
        gsnap = ref.get(transaction=transaction)
        grp = gsnap.to_dict()
        if grp["status"] != "open":
            raise ValueError(f"Group is {grp['status']}")
        members = grp.get("members", [])
        if any(m["uid"] == g.user["uid"] for m in members):
            raise ValueError("Already joined")
        # The running total can never exceed target_qty: the last join is capped.
        remaining = grp["target_qty"] - grp["joined_qty"]
        if remaining <= 0:
            raise ValueError("Group is already full")
        take = min(qty, remaining)
        members.append({"uid": g.user["uid"], "qty": take})
        transaction.update(
            ref, {"members": members, "joined_qty": grp["joined_qty"] + take}
        )
        return take, grp["joined_qty"] + take, grp["target_qty"]

    try:
        take, joined, target = join(transaction)
    except ValueError as e:
        return bad_request(str(e))
    return jsonify({"joined_qty": take, "group_total": joined, "target_qty": target, "capped": take < qty})


@bp.post("/group-orders/<gid>/leave")
@require_auth(roles=["consumer"])
def leave_group(gid):
    """Members may leave freely until the group reaches 80% of target; after that,
    leaving requires the deadline to pass (i.e. it is refused here)."""
    db = firebase.db()
    ref = db.collection("group_orders").document(gid)
    transaction = db.transaction()

    @firestore.transactional
    def leave(transaction):
        snap = ref.get(transaction=transaction)
        if not snap.exists:
            raise ValueError("Group not found")
        grp = snap.to_dict()
        if grp["status"] != "open":
            raise ValueError(f"Group is {grp['status']}")
        if grp["joined_qty"] >= config.GROUP_LEAVE_LOCK_FRACTION * grp["target_qty"]:
            raise ValueError("Group has passed 80% of target — leaving is locked until the deadline")
        members = grp.get("members", [])
        mine = next((m for m in members if m["uid"] == g.user["uid"]), None)
        if not mine:
            raise ValueError("You are not a member")
        members.remove(mine)
        transaction.update(
            ref, {"members": members, "joined_qty": grp["joined_qty"] - mine["qty"]}
        )

    try:
        leave(transaction)
    except ValueError as e:
        return bad_request(str(e))
    return jsonify({"ok": True})


@bp.post("/group-orders/<gid>/resolve")
@require_auth(roles=["admin"])
def force_resolve(gid):
    """Manual admin fallback for deadline resolution (MVP simplification)."""
    db = firebase.db()
    ref = db.collection("group_orders").document(gid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "Group not found"}), 404
    group = doc_with_id(snap)
    if group["status"] == "open" and utcnow() < group["deadline"]:
        return bad_request("Deadline has not passed yet")
    group = _resolve_if_due(db, ref, group)
    return jsonify({"id": gid, "status": group["status"]})
