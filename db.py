"""Database layer: schema, per-request connection, demo data."""
import random
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

EXPENSE_CATEGORIES = ("Food", "Transport", "Shopping", "Bills", "Health", "Education", "Entertainment", "Other")
INCOME_CATEGORIES = ("Salary", "Scholarship", "Freelance", "Gift", "Other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('income','expense')),
    amount REAL NOT NULL CHECK (amount > 0),
    category TEXT NOT NULL,
    tx_date TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS budgets (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    monthly_limit REAL NOT NULL CHECK (monthly_limit > 0),
    PRIMARY KEY (user_id, category));
CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions(user_id, tx_date);
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def month_shift(year, month, delta):
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def seed_demo(conn):
    """Six months of realistic sample data so the charts look alive on first run."""
    rnd, today = random.Random(7), date.today()
    uid = conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                       ("demo", generate_password_hash("demo123", method="pbkdf2:sha256"), now())).lastrowid
    rows = []
    weights = [("Food", 80, 450, 10), ("Transport", 30, 250, 6), ("Shopping", 300, 2500, 2),
               ("Health", 100, 900, 1), ("Education", 400, 1500, 1), ("Entertainment", 150, 600, 3)]
    for back in range(5, -1, -1):
        y, m = month_shift(today.year, today.month, -back)
        last_day = today.day if back == 0 else 28
        rows.append(("income", 8000, "Scholarship", date(y, m, 1), "Monthly scholarship"))
        if rnd.random() < 0.6 and last_day >= 10:
            rows.append(("income", rnd.randrange(2000, 6000, 500), "Freelance", date(y, m, 10), "Website project"))
        if last_day >= 5:
            rows += [("expense", 299, "Bills", date(y, m, 5), "Mobile recharge"), ("expense", 699, "Bills", date(y, m, 5), "Wi-Fi")]
        for cat, lo, hi, count in weights:
            for _ in range(count if back else max(1, count // 2)):
                rows.append(("expense", rnd.randrange(lo, hi), cat, date(y, m, rnd.randint(1, last_day)), ""))
    t = now()
    conn.executemany("INSERT INTO transactions (user_id,type,amount,category,tx_date,note,created_at) VALUES (?,?,?,?,?,?,?)",
                     [(uid, ty, a, c, d.isoformat(), n, t) for ty, a, c, d, n in rows])
    conn.executemany("INSERT INTO budgets (user_id, category, monthly_limit) VALUES (?,?,?)",
                     [(uid, "Food", 3500), (uid, "Transport", 1200), (uid, "Shopping", 2500), (uid, "Entertainment", 1200)])


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        conn = get_db()
        conn.executescript(SCHEMA)
        if app.config.get("SEED_DEMO") and not conn.execute("SELECT 1 FROM users").fetchone():
            seed_demo(conn)
        conn.commit()
