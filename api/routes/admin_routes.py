"""Admin module: farmer KYC decisions and report moderation."""
from flask import Blueprint, g, jsonify, request
from firebase_admin import firestore

import firebase
from auth_guard import require_auth
from helpers import bad_request, doc_with_id, notify

bp = Blueprint("admin", __name__)


@bp.get("/admin/kyc")
@require_auth(roles=["admin"])
def kyc_queue():
    db = firebase.db()
    snaps = db.collection("kyc_requests").where("status", "==", "pending").get()
    out = []
    for s in snaps:
        d = doc_with_id(s)
        d["created_at"] = str(d.get("created_at"))
        d["reviewed_at"] = str(d.get("reviewed_at")) if d.get("reviewed_at") else None
        out.append(d)
    return jsonify(out)


@bp.post("/admin/kyc/<rid>/decide")
@require_auth(roles=["admin"])
def kyc_decide(rid):
    decision = (request.get_json(silent=True) or {}).get("decision")
    if decision not in ("approved", "rejected"):
        return bad_request("decision must be approved or rejected")
    db = firebase.db()
    ref = db.collection("kyc_requests").document(rid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "KYC request not found"}), 404
    req = snap.to_dict()
    if req["status"] != "pending":
        return bad_request("Already decided")

    ref.update(
        {
            "status": decision,
            "reviewed_by": g.user["uid"],
            "reviewed_at": firestore.SERVER_TIMESTAMP,
        }
    )
    if decision == "approved":
        db.collection("users").document(req["farmer_id"]).update({"verified": True})
    notify(
        db,
        req["farmer_id"],
        "kyc",
        "Your farmer verification was approved — Verified badge is live"
        if decision == "approved"
        else "Your farmer verification was rejected — please re-submit documents",
    )
    return jsonify({"id": rid, "status": decision})


@bp.get("/admin/reports")
@require_auth(roles=["admin"])
def report_queue():
    db = firebase.db()
    snaps = db.collection("reports").where("status", "==", "pending").get()
    out = []
    for s in snaps:
        d = doc_with_id(s)
        d["created_at"] = str(d.get("created_at"))
        out.append(d)
    return jsonify(out)


@bp.post("/admin/reports/<rid>/decide")
@require_auth(roles=["admin"])
def report_decide(rid):
    """hide = take the content down; dismiss = leave it up."""
    decision = (request.get_json(silent=True) or {}).get("decision")
    if decision not in ("hide", "dismiss"):
        return bad_request("decision must be hide or dismiss")
    db = firebase.db()
    ref = db.collection("reports").document(rid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "Report not found"}), 404
    report = snap.to_dict()
    if report["status"] != "pending":
        return bad_request("Already decided")

    if decision == "hide":
        if report["target_type"] == "product":
            db.collection("products").document(report["target_id"]).update({"active": False})
        else:
            db.collection("reviews").document(report["target_id"]).update({"hidden": True})
    ref.update({"status": decision, "reviewed_by": g.user["uid"]})
    return jsonify({"id": rid, "status": decision})


@bp.get("/stats")
def platform_stats():
    """Public: platform-wide 'kg saved from waste' counter for the home page."""
    db = firebase.db()
    snap = db.collection("stats").document("platform").get()
    return jsonify({"kg_saved": (snap.to_dict() or {}).get("kg_saved", 0) if snap.exists else 0})
