"""Spendwise: personal finance tracker (Flask + SQLite). Application factory."""
import hmac
import secrets
from pathlib import Path

from flask import Flask, abort, g, jsonify, render_template, request, session

import api
import auth
import db

BASE = Path(__file__).parent


def load_secret_key():
    f = BASE / "secret.key"                 # generated once, never hard-coded
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=load_secret_key(), DATABASE=str(BASE / "spendwise.db"), SEED_DEMO=True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=64 * 1024)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(api.bp)

    @app.before_request
    def csrf_protect():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
            token = session.get("csrf", "")
            if not token or not hmac.compare_digest(token, sent):
                abort(400)

    def csrf_token():
        session.setdefault("csrf", secrets.token_hex(16))
        return session["csrf"]
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.route("/")
    @auth.login_required
    def dashboard():
        return render_template("dashboard.html")

    messages = {400: "Bad request. Refresh the page and try again.", 404: "Not found.", 405: "Method not allowed.", 413: "Request too large."}
    for code, msg in messages.items():
        def handler(e, c=code, m=msg):
            if request.path.startswith("/api/"):
                return jsonify(error=m), c
            return render_template("error.html", code=c, message=m), c
        app.register_error_handler(code, handler)
    return app


app = create_app()
if __name__ == "__main__":
    app.run(debug=True)
