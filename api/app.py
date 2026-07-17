"""FarmConnect Flask backend — the single trusted writer for all marketplace state."""
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config


def create_app():
    app = Flask(__name__)
    CORS(app, origins=config.ALLOWED_ORIGINS, supports_credentials=False)

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["60 per minute"],
        storage_uri="memory://",
    )

    from routes.auth_routes import bp as auth_bp
    from routes.catalog_routes import bp as catalog_bp
    from routes.order_routes import bp as order_bp
    from routes.group_routes import bp as group_bp
    from routes.review_routes import bp as review_bp
    from routes.admin_routes import bp as admin_bp
    from routes.ai_routes import bp as ai_bp

    for bp in (auth_bp, catalog_bp, order_bp, group_bp, review_bp, admin_bp, ai_bp):
        app.register_blueprint(bp)

    # Stricter limits on write-heavy blueprints.
    limiter.limit("20 per minute")(order_bp)
    limiter.limit("20 per minute")(group_bp)
    limiter.limit("10 per minute")(review_bp)

    @app.get("/health")
    @limiter.exempt
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(429)
    def ratelimited(e):
        return jsonify({"error": "Rate limit exceeded, slow down."}), 429

    @app.errorhandler(500)
    def internal(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
