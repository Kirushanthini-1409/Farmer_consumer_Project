"""Pure-logic tests: state machine, freshness/pricing helpers, AI price model, app boot.
Run: .venv/bin/python -m pytest tests/ -q   (from api/)"""
import sys, os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import state_machine
from helpers import effective_price, freshness, haversine_km, utcnow


# ---------- state machine ----------
def test_full_happy_path():
    path = [("PLACED", "accept"), ("CONFIRMED", "pack"), ("PACKED", "out_for_delivery"),
            ("OUT_FOR_DELIVERY", "delivered")]
    for frm, action in path:
        to, err = state_machine.resolve(frm, action, "farmer", False, True)
        assert err is None, err
    to, err = state_machine.resolve("DELIVERED", "complete", "consumer", True, False)
    assert to == "COMPLETED" and err is None


def test_illegal_transition_rejected():
    to, err = state_machine.resolve("PLACED", "delivered", "farmer", False, True)
    assert to is None and "Illegal" in err


def test_consumer_cannot_accept():
    to, err = state_machine.resolve("PLACED", "accept", "consumer", True, False)
    assert to is None and "Role" in err


def test_cancel_only_before_packed():
    to, err = state_machine.resolve("CONFIRMED", "cancel", "consumer", True, False)
    assert to == "CANCELLED"
    to, err = state_machine.resolve("PACKED", "cancel", "consumer", True, False)
    assert to is None


def test_admin_resolves_dispute():
    to, err = state_machine.resolve("DISPUTED", "resolve_complete", "admin", False, False)
    assert to == "COMPLETED"
    to, err = state_machine.resolve("DISPUTED", "resolve_cancel", "admin", False, False)
    assert to == "CANCELLED"


def test_non_party_farmer_rejected():
    # A farmer who is NOT the order's farmer can't accept it.
    to, err = state_machine.resolve("PLACED", "accept", "farmer", False, False)
    assert to is None


def test_restock_states():
    assert state_machine.RESTOCK_STATES == {"CANCELLED", "REJECTED"}


# ---------- freshness + effective price ----------
def test_fresh_today_no_discount():
    batch = {"price": 100, "harvest_date": utcnow(), "is_ugly": False}
    price, pct, fresh = effective_price(batch, "fruit")
    assert price == 100 and pct == 0
    assert fresh["label"] == "Fresh today" and not fresh["aging"]


def test_aging_auto_discount():
    # fruit shelf life 7d; 5 days old = 71% used -> 20% auto discount
    batch = {"price": 100, "harvest_date": utcnow() - timedelta(days=5), "is_ugly": False}
    price, pct, fresh = effective_price(batch, "fruit")
    assert fresh["aging"] and pct == config.AGING_DISCOUNT_PCT and price == 80.0


def test_ugly_mandatory_discount():
    batch = {"price": 100, "harvest_date": utcnow(), "is_ugly": True, "discount_pct": 40}
    price, pct, _ = effective_price(batch, "vegetable")
    assert pct == 40 and price == 60.0


def test_expired_flag():
    batch = {"price": 100, "harvest_date": utcnow() - timedelta(days=10), "is_ugly": False}
    _, _, fresh = effective_price(batch, "vegetable")  # veg shelf life 3d
    assert fresh["expired"]


def test_haversine_known_distance():
    # Bengaluru centre -> Mysuru ~ 128-145 km
    d = haversine_km(12.9716, 77.5946, 12.2958, 76.6394)
    assert 120 < d < 150


# ---------- AI price model ----------
def test_price_band_from_mandi_csv():
    from ai import pricing
    info = pricing.train()
    assert info["rows"] > 1000 and info["commodities"] >= 20
    band = pricing.price_band("Tomato", "vegetable")
    assert band and band["low"] < band["base"] < band["high"]
    assert 10 < band["base"] < 60  # sane ₹/kg for tomato in the synthetic data


def test_ugly_lowers_suggestion():
    from ai import pricing
    normal = pricing.price_band("Tomato", "vegetable", is_ugly=False)
    ugly = pricing.price_band("Tomato", "vegetable", is_ugly=True)
    assert ugly["base"] < normal["base"]


def test_unknown_commodity_falls_back():
    from ai import pricing
    band = pricing.price_band("Dragonfruit Surprise", "fruit")
    assert band and "average" in band["source"]


# ---------- app boot + auth guard ----------
def test_app_boots_and_health():
    from app import app
    client = app.test_client()
    assert client.get("/health").status_code == 200


def test_unauthenticated_me_is_401():
    from app import app
    client = app.test_client()
    res = client.get("/me")
    assert res.status_code == 401


def test_write_endpoints_require_auth():
    from app import app
    client = app.test_client()
    for path in ("/products", "/batches", "/orders", "/reviews", "/group-orders"):
        assert client.post(path, json={}).status_code == 401, path
    assert client.post("/admin/kyc/x/decide", json={}).status_code == 401
