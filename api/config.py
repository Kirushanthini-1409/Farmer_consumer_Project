"""Central configuration, all overridable via environment variables (Render env vars in prod)."""
import os

# Comma-separated list of allowed browser origins (Firebase Hosting URL + localhost for dev).
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if o.strip()
]

# Path to the Firebase service-account JSON. On Render, store the JSON itself in
# FIREBASE_SERVICE_ACCOUNT_JSON instead of shipping a file.
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")

# Order lifecycle timing rules (hours).
FARMER_ACCEPT_TIMEOUT_H = int(os.environ.get("FARMER_ACCEPT_TIMEOUT_H", "12"))
AUTO_COMPLETE_AFTER_H = int(os.environ.get("AUTO_COMPLETE_AFTER_H", "48"))

# Harvest-batch freshness model: per-category shelf life in days.
SHELF_LIFE_DAYS = {
    "vegetable": 3,   # leafy greens default; farmers can override per batch
    "fruit": 7,
    "dairy": 3,
    "eggs": 21,
    "grains": 90,
    "homemade": 14,
}
DEFAULT_SHELF_LIFE_DAYS = 7

# Auto-discount rule: past this fraction of shelf life, apply the discount.
AGING_DISCOUNT_THRESHOLD = float(os.environ.get("AGING_DISCOUNT_THRESHOLD", "0.6"))
AGING_DISCOUNT_PCT = int(os.environ.get("AGING_DISCOUNT_PCT", "20"))

# Ugly produce: mandatory discount range (farmer chooses within it).
UGLY_DISCOUNT_MIN_PCT = 30
UGLY_DISCOUNT_MAX_PCT = 50

# Group buying: members may leave freely below this fraction of target.
GROUP_LEAVE_LOCK_FRACTION = 0.8

VALID_CATEGORIES = ["vegetable", "fruit", "dairy", "eggs", "grains", "homemade"]
VALID_ROLES = ["consumer", "farmer", "admin"]

MANDI_CSV = os.path.join(os.path.dirname(__file__), "data", "mandi_prices.csv")
