"""Request authentication: verifies Firebase ID tokens and enforces roles via custom claims."""
from functools import wraps

from flask import g, jsonify, request
from firebase_admin import auth as fb_auth

import firebase


def _verify_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, ("Missing bearer token", 401)
    token = header.split(" ", 1)[1].strip()
    try:
        firebase.init_app()
        decoded = fb_auth.verify_id_token(token)
    except Exception:
        return None, ("Invalid or expired token", 401)
    return decoded, None


def require_auth(roles=None):
    """Decorator: reject unauthenticated calls; optionally restrict to the given roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            decoded, err = _verify_bearer_token()
            if err:
                return jsonify({"error": err[0]}), err[1]
            role = decoded.get("role")
            if roles and role not in roles:
                return jsonify({"error": f"Requires role: {', '.join(roles)}"}), 403
            g.user = {"uid": decoded["uid"], "role": role, "email": decoded.get("email")}
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def optional_auth(fn):
    """Attach g.user when a valid token is present, but allow anonymous access."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.user = None
        if request.headers.get("Authorization", "").startswith("Bearer "):
            decoded, err = _verify_bearer_token()
            if decoded:
                g.user = {"uid": decoded["uid"], "role": decoded.get("role")}
        return fn(*args, **kwargs)

    return wrapper
