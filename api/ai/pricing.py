"""Fair-price recommendation.

v1 (cold start): a scikit-learn regression trained on bundled Agmarknet mandi prices
(data/mandi_prices.csv — replace with a fresh export from data.gov.in). Returns a
fair-price BAND around the predicted modal price, adjusted for freshness and the
ugly flag. v2 (roadmap): /ai/retrain blends live platform transactions in weekly.
"""
import os
import threading

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

import config
from helpers import parse_date, shelf_life_days, utcnow

_lock = threading.Lock()
_model = None
_commodity_stats = None

BAND_PCT = 0.15  # band half-width around the predicted modal price


def _load_frame(extra_rows=None):
    df = pd.read_csv(config.MANDI_CSV)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    df["commodity"] = df["commodity"].str.strip().str.lower()
    if extra_rows:
        extra = pd.DataFrame(extra_rows)
        extra["month"] = pd.to_datetime(extra["date"]).dt.month
        extra["commodity"] = extra["commodity"].str.strip().str.lower()
        df = pd.concat([df[["commodity", "month", "modal_price"]],
                        extra[["commodity", "month", "modal_price"]]], ignore_index=True)
    return df


def train(extra_rows=None):
    """Fit commodity+month -> modal price. Ridge over one-hot features keeps it tiny,
    interpretable and instant to retrain on the free tier."""
    global _model, _commodity_stats
    df = _load_frame(extra_rows)
    pipeline = Pipeline(
        [
            (
                "encode",
                ColumnTransformer(
                    [("cats", OneHotEncoder(handle_unknown="ignore"), ["commodity", "month"])]
                ),
            ),
            ("reg", Ridge(alpha=1.0)),
        ]
    )
    pipeline.fit(df[["commodity", "month"]], df["modal_price"])
    with _lock:
        _model = pipeline
        _commodity_stats = df.groupby("commodity")["modal_price"].mean().to_dict()
    return {"rows": len(df), "commodities": len(_commodity_stats)}


def _ensure_model():
    if _model is None and os.path.exists(config.MANDI_CSV):
        train()
    return _model


def price_band(product_name, category, is_ugly=False, harvest_date=None):
    """Return {'low','high','base','source','adjustments'} in ₹/unit, or None if no model."""
    model = _ensure_model()
    if model is None:
        return None

    commodity = product_name.strip().lower()
    month = utcnow().month
    if commodity in (_commodity_stats or {}):
        base = float(model.predict(pd.DataFrame([{"commodity": commodity, "month": month}]))[0])
        source = "mandi (Agmarknet)"
    else:
        # Unknown commodity: fall back to the global average so the farmer still gets a hint.
        base = float(np.mean(list(_commodity_stats.values())))
        source = "category average (commodity not in mandi data)"

    adjustments = []
    factor = 1.0
    if harvest_date is not None:
        life = shelf_life_days(category)
        age = max(0.0, (utcnow() - parse_date(harvest_date)).total_seconds() / 86400)
        used = min(age / life, 1.0) if life else 1.0
        if used >= config.AGING_DISCOUNT_THRESHOLD:
            factor *= 1 - config.AGING_DISCOUNT_PCT / 100
            adjustments.append(f"-{config.AGING_DISCOUNT_PCT}% aging stock")
    if is_ugly:
        ugly_cut = (config.UGLY_DISCOUNT_MIN_PCT + config.UGLY_DISCOUNT_MAX_PCT) / 2 / 100
        factor *= 1 - ugly_cut
        adjustments.append(f"-{int(ugly_cut * 100)}% ugly produce")

    base_adj = base * factor
    return {
        "base": round(base_adj, 2),
        "low": round(base_adj * (1 - BAND_PCT), 2),
        "high": round(base_adj * (1 + BAND_PCT), 2),
        "source": source,
        "adjustments": adjustments,
    }
