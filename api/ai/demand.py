"""Demand prediction v1: seasonality heuristics + 7-day moving average over order
history (seeded at first). Real forecasts need weeks of live data — say so in the UI.
v2 (roadmap): per-category time-series model with lag features."""
from collections import defaultdict
from datetime import timedelta

from helpers import utcnow

# Simple Indian seasonality prior: months in which a category typically sees higher demand.
SEASONAL_BOOST = {
    "vegetable": {6, 7, 8, 11, 12},   # monsoon + winter greens
    "fruit": {3, 4, 5, 6},            # summer fruit season
    "dairy": {10, 11, 12, 1},         # festival season
    "eggs": {11, 12, 1, 2},           # winter
    "grains": {4, 5, 10, 11},         # post-harvest
    "homemade": {10, 11, 12},         # festival gifting
}


def demand_signals(db):
    """Return per-category chips: direction (up/steady) + a small human explanation."""
    now = utcnow()
    week_ago = now - timedelta(days=7)
    fortnight_ago = now - timedelta(days=14)

    recent = defaultdict(float)
    previous = defaultdict(float)
    orders = db.collection("orders").where("placed_at", ">=", fortnight_ago).get()
    for snap in orders:
        order = snap.to_dict()
        if order.get("status") in ("CANCELLED", "REJECTED"):
            continue
        placed = order.get("placed_at")
        for item in order.get("items", []):
            product = db.collection("products").document(item["product_id"]).get()
            category = (product.to_dict() or {}).get("category", "vegetable") if product.exists else "vegetable"
            if placed and placed >= week_ago:
                recent[category] += item["qty"]
            else:
                previous[category] += item["qty"]

    month = now.month
    chips = []
    for category in ("vegetable", "fruit", "dairy", "eggs", "grains", "homemade"):
        r, p = recent.get(category, 0), previous.get(category, 0)
        seasonal = month in SEASONAL_BOOST.get(category, set())
        trending = r > p * 1.2 and r > 0
        if trending and seasonal:
            direction, why = "up", "sales up week-over-week and in season"
        elif trending:
            direction, why = "up", f"7-day sales ({r:.0f}) above the week before ({p:.0f})"
        elif seasonal:
            direction, why = "up", "seasonal demand window"
        else:
            direction, why = "steady", "no strong signal yet"
        chips.append(
            {
                "category": category,
                "direction": direction,
                "why": why,
                "recent_qty": round(r, 1),
                "previous_qty": round(p, 1),
            }
        )
    chips.sort(key=lambda c: (c["direction"] != "up", -c["recent_qty"]))
    return {
        "chips": chips,
        "note": "v1: heuristics + 7-day moving average over early order history. "
        "Real forecasts activate after weeks of live data (v2).",
    }
