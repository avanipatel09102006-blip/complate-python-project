"""Accounts: register, login, logout and the login_required guard."""
import re
from functools import wraps

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db, now

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_user():
    uid = session.get("user_id")
    g.user = get_db().execute("SELECT id, username FROM users WHERE id=?", (uid,)).fetchone() if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in"), 401
            return redirect(url_for("auth.login"))
        return view(*a, **kw)
    return wrapped


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, pw = request.form.get("username", "").strip(), request.form.get("password", "")
        error = None
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", name):
            error = "Username must be 3-20 characters: letters, numbers or underscore."
        elif len(pw) < 6:
            error = "Password must be at least 6 characters."
        elif pw != request.form.get("confirm", ""):
            error = "Passwords do not match."
        if not error:
            db = get_db()
            try:
                uid = db.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                                 (name, generate_password_hash(pw, method="pbkdf2:sha256"), now())).lastrowid
                db.commit()
            except Exception:
                error = "That username is already taken."
            else:
                session.clear()
                session["user_id"] = uid
                return redirect(url_for("dashboard"))
        flash(error, "error")
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE username=?", (request.form.get("username", "").strip(),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("auth/login.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
