"""One-shot demo seed: ~8 farmers around a city centre, ~30 products with batches,
3 weeks of synthetic order history so recommendations and demand chips look alive,
plus one admin account.

Run once, locally, with service-account credentials configured:
    python seed.py [--city-lat 12.9716 --city-lng 77.5946]

Uses the Admin SDK directly (it IS the trusted backend, same trust boundary).
"""
import argparse
import random
from datetime import timedelta

from firebase_admin import auth as fb_auth, firestore

import firebase
from helpers import utcnow

random.seed(7)

FARMERS = [
    ("Ravi Kumar", "ravi.farm@example.com"),
    ("Lakshmi Devi", "lakshmi.greens@example.com"),
    ("Suresh Gowda", "suresh.dairy@example.com"),
    ("Manjula B", "manjula.fruits@example.com"),
    ("Krishnappa N", "krishnappa.organics@example.com"),
    ("Geetha R", "geetha.homefoods@example.com"),
    ("Basavaraj P", "basavaraj.grains@example.com"),
    ("Anitha S", "anitha.eggs@example.com"),
]
CONSUMERS = [
    ("Arjun Mehta", "arjun.c@example.com"),
    ("Priya Nair", "priya.c@example.com"),
    ("Rahul Shetty", "rahul.c@example.com"),
    ("Sneha Rao", "sneha.c@example.com"),
]
ADMIN = ("Platform Admin", "admin@farmconnect.example.com")
PASSWORD = "Demo@1234"  # demo-only accounts

CATALOGUE = {
    "vegetable": ["Tomato", "Onion", "Potato", "Spinach", "Carrot", "Cauliflower", "Brinjal", "Okra", "Cabbage", "Green Chilli"],
    "fruit": ["Banana", "Apple", "Mango", "Papaya", "Guava"],
    "dairy": ["Milk", "Curd", "Paneer"],
    "eggs": ["Eggs"],
    "grains": ["Wheat", "Rice"],
    "homemade": ["Honey", "Mango Pickle", "Ragi Flour"],
}
BASE_PRICE = {
    "Tomato": 26, "Onion": 24, "Potato": 20, "Spinach": 32, "Carrot": 38,
    "Cauliflower": 30, "Brinjal": 28, "Okra": 34, "Cabbage": 22, "Green Chilli": 60,
    "Banana": 45, "Apple": 130, "Mango": 90, "Papaya": 38, "Guava": 55,
    "Milk": 58, "Curd": 75, "Paneer": 340, "Eggs": 8, "Wheat": 30, "Rice": 48,
    "Honey": 380, "Mango Pickle": 250, "Ragi Flour": 60,
}
UNIT = {"Milk": "litre", "Curd": "kg", "Eggs": "piece", "Honey": "jar", "Mango Pickle": "jar"}


def upsert_user(email, name, role, extra=None):
    try:
        user = fb_auth.get_user_by_email(email)
    except fb_auth.UserNotFoundError:
        user = fb_auth.create_user(email=email, password=PASSWORD, display_name=name)
    fb_auth.set_custom_user_claims(user.uid, {"role": role})
    db = firebase.db()
    profile = {"role": role, "name": name, "email": email, "phone": "",
               "created_at": firestore.SERVER_TIMESTAMP}
    if extra:
        profile.update(extra)
    db.collection("users").document(user.uid).set(profile, merge=True)
    return user.uid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--city-lat", type=float, default=12.9716)  # Bengaluru
    parser.add_argument("--city-lng", type=float, default=77.5946)
    args = parser.parse_args()

    firebase.init_app()
    db = firebase.db()

    admin_uid = upsert_user(ADMIN[1], ADMIN[0], "admin")
    print("admin:", ADMIN[1], "/", PASSWORD)

    farmer_uids = []
    for i, (name, email) in enumerate(FARMERS):
        # Scatter farmers 1–9 km around the city centre.
        lat = args.city_lat + random.uniform(-0.08, 0.08)
        lng = args.city_lng + random.uniform(-0.08, 0.08)
        uid = upsert_user(
            email, name, "farmer",
            {"lat": lat, "lng": lng, "verified": i < 5, "rating_avg": 0,
             "rating_count": 0, "kg_saved": 0.0, "address": "Near Bengaluru"},
        )
        farmer_uids.append(uid)
        if i >= 5:  # leave a few pending for the admin KYC demo
            db.collection("kyc_requests").add({
                "farmer_id": uid, "farmer_name": name,
                "id_doc_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "land_doc_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "status": "pending", "reviewed_by": None, "reviewed_at": None,
                "created_at": firestore.SERVER_TIMESTAMP,
            })
    consumer_uids = [upsert_user(e, n, "consumer") for n, e in CONSUMERS]
    print(f"{len(farmer_uids)} farmers, {len(consumer_uids)} consumers seeded")

    # Products + batches (~30 products across farmers).
    all_products = [(c, n) for c, names in CATALOGUE.items() for n in names]
    product_refs = []
    for idx, (category, name) in enumerate(all_products):
        farmer_id = farmer_uids[idx % len(farmer_uids)]
        pref = db.collection("products").add({
            "farmer_id": farmer_id, "name": name, "category": category,
            "description": f"Farm-fresh {name.lower()} directly from the grower.",
            "image_url": "", "base_price": BASE_PRICE.get(name, 40),
            "unit": UNIT.get(name, "kg"), "active": True,
            "created_at": firestore.SERVER_TIMESTAMP,
        })[1]
        product_refs.append((pref.id, farmer_id, category, name))
        is_ugly = random.random() < 0.25 and category in ("vegetable", "fruit")
        db.collection("batches").add({
            "product_id": pref.id, "farmer_id": farmer_id,
            "qty_available": random.choice([10, 20, 30, 50]),
            "unit": UNIT.get(name, "kg"),
            "price": BASE_PRICE.get(name, 40),
            "harvest_date": utcnow() - timedelta(days=random.randint(0, 3)),
            "shelf_life_days": None,
            "is_ugly": is_ugly,
            "discount_pct": random.choice([30, 40, 50]) if is_ugly else 0,
            "created_at": firestore.SERVER_TIMESTAMP,
        })
    print(f"{len(product_refs)} products with batches seeded")

    # 3 weeks of synthetic completed order history.
    n_orders = 0
    for day in range(21, 0, -1):
        placed = utcnow() - timedelta(days=day)
        for _ in range(random.randint(2, 5)):
            pid, farmer_id, category, name = random.choice(product_refs)
            consumer = random.choice(consumer_uids)
            qty = random.choice([1, 2, 3, 5])
            price = BASE_PRICE.get(name, 40)
            order_ref = db.collection("orders").document()
            order_ref.set({
                "consumer_id": consumer, "farmer_id": farmer_id,
                "items": [{"batch_id": "seed", "product_id": pid, "product_name": name,
                           "qty": qty, "unit": UNIT.get(name, "kg"),
                           "unit_price": price, "is_ugly": False}],
                "total": round(qty * price, 2), "status": "COMPLETED",
                "delivery_type": "pickup", "payment_mode": "COD/simulated",
                "address": "", "created_at": placed, "placed_at": placed,
                "delivered_at": placed + timedelta(hours=20),
            })
            order_ref.collection("order_events").add({
                "actor_uid": "seed", "from_status": None, "to_status": "COMPLETED",
                "note": "seeded history", "at": placed,
            })
            n_orders += 1
    print(f"{n_orders} historical orders seeded")

    db.collection("stats").document("platform").set({"kg_saved": 137.5}, merge=True)
    print("Done. Login with any seeded email +", PASSWORD)


if __name__ == "__main__":
    main()
