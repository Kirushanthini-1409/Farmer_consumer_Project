"""Shared domain helpers: freshness, effective pricing, distance, notifications."""
import math
from datetime import datetime, timezone

from firebase_admin import firestore

import config


def utcnow():
    return datetime.now(timezone.utc)


def parse_date(value):
    """Accept 'YYYY-MM-DD' or ISO strings; return an aware datetime (UTC midnight for dates)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def shelf_life_days(category, override=None):
    if override:
        return int(override)
    return config.SHELF_LIFE_DAYS.get(category, config.DEFAULT_SHELF_LIFE_DAYS)


def freshness(batch, category):
    """Freshness metadata for a batch: age, remaining life, label, and aging flag."""
    life = shelf_life_days(category, batch.get("shelf_life_days"))
    age_days = max(0.0, (utcnow() - parse_date(batch["harvest_date"])).total_seconds() / 86400)
    used = age_days / life if life else 1.0
    if age_days < 1:
        label = "Fresh today"
    elif age_days < 2:
        label = "1 day old"
    else:
        label = f"{int(age_days)} days old"
    return {
        "age_days": round(age_days, 1),
        "shelf_life_days": life,
        "label": label,
        "life_used": round(min(used, 1.0), 2),
        "aging": used >= config.AGING_DISCOUNT_THRESHOLD,
        "expired": used >= 1.0,
    }


def effective_price(batch, category):
    """Server-computed sale price: base price minus ugly discount, minus the auto-aging
    discount once a batch passes the shelf-life threshold. Never trusted from the client."""
    price = float(batch["price"])
    discount_pct = 0
    if batch.get("is_ugly"):
        discount_pct = int(batch.get("discount_pct") or config.UGLY_DISCOUNT_MIN_PCT)
    fresh = freshness(batch, category)
    if fresh["aging"] and not batch.get("is_ugly"):
        discount_pct = max(discount_pct, config.AGING_DISCOUNT_PCT)
    return round(price * (1 - discount_pct / 100.0), 2), discount_pct, fresh


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def notify(db, uid, ntype, text, order_id=None):
    """Write an in-app notification (backend-only side effect of other actions)."""
    db.collection("notifications").add(
        {
            "uid": uid,
            "type": ntype,
            "text": text,
            "order_id": order_id,
            "read": False,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )


def doc_with_id(snap):
    d = snap.to_dict()
    d["id"] = snap.id
    return d


def bad_request(message):
    from flask import jsonify

    return jsonify({"error": message}), 400
