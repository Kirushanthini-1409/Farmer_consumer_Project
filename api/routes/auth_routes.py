"""Profile creation (with role custom claim) and /me."""
from flask import Blueprint, g, jsonify, request
from firebase_admin import auth as fb_auth, firestore

import config
import firebase
from auth_guard import require_auth
from helpers import bad_request, doc_with_id

bp = Blueprint("auth", __name__)


@bp.post("/auth/register-profile")
def register_profile():
    """Called once right after Firebase signup. Verifies the fresh ID token directly
    (the role claim does not exist yet, so require_auth's role check can't be used),
    sets the role custom claim, and creates the Firestore user document."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"error": "Missing bearer token"}), 401
    try:
        firebase.init_app()
        decoded = fb_auth.verify_id_token(header.split(" ", 1)[1].strip())
    except Exception:
        return jsonify({"error": "Invalid or expired token"}), 401

    body = request.get_json(silent=True) or {}
    role = body.get("role")
    name = (body.get("name") or "").strip()
    if role not in ("consumer", "farmer"):  # admins are provisioned manually, never self-service
        return bad_request("role must be consumer or farmer")
    if not name:
        return bad_request("name is required")

    uid = decoded["uid"]
    db = firebase.db()
    user_ref = db.collection("users").document(uid)
    if user_ref.get().exists:
        return bad_request("Profile already exists")

    profile = {
        "role": role,
        "name": name,
        "email": decoded.get("email"),
        "phone": (body.get("phone") or "").strip(),
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    if role == "farmer":
        try:
            profile["lat"] = float(body["lat"])
            profile["lng"] = float(body["lng"])
        except (KeyError, TypeError, ValueError):
            return bad_request("Farmers must provide lat/lng (picked on the map)")
        profile.update(
            {
                "verified": False,
                "rating_avg": 0.0,
                "rating_count": 0,
                "kg_saved": 0.0,
                "address": (body.get("address") or "").strip(),
            }
        )

    fb_auth.set_custom_user_claims(uid, {"role": role})
    user_ref.set(profile)

    # Farmer KYC: document URLs (Cloudinary) land in the admin review queue.
    if role == "farmer" and (body.get("id_doc_url") or body.get("land_doc_url")):
        db.collection("kyc_requests").add(
            {
                "farmer_id": uid,
                "farmer_name": name,
                "id_doc_url": body.get("id_doc_url", ""),
                "land_doc_url": body.get("land_doc_url", ""),
                "status": "pending",
                "reviewed_by": None,
                "reviewed_at": None,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    return jsonify({"ok": True, "role": role, "claims_refreshed": True}), 201


@bp.get("/me")
@require_auth()
def me():
    db = firebase.db()
    snap = db.collection("users").document(g.user["uid"]).get()
    if not snap.exists:
        return jsonify({"error": "Profile not found"}), 404
    profile = doc_with_id(snap)
    profile["uid"] = g.user["uid"]
    if profile.get("role") == "farmer":
        pending = (
            db.collection("kyc_requests")
            .where("farmer_id", "==", g.user["uid"])
            .where("status", "==", "pending")
            .limit(1)
            .get()
        )
        profile["kyc_pending"] = len(list(pending)) > 0
    return jsonify(profile)


@bp.get("/notifications")
@require_auth()
def notifications():
    db = firebase.db()
    snaps = db.collection("notifications").where("uid", "==", g.user["uid"]).limit(100).get()
    out = sorted(
        (doc_with_id(s) for s in snaps),
        key=lambda n: str(n.get("created_at") or ""),
        reverse=True,
    )[:30]
    for n in out:
        n["created_at"] = str(n.get("created_at"))
    return jsonify(out)
