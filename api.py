"""JSON API used by the dashboard. Every query is scoped to the logged-in user."""
import csv
import io
import re
import sqlite3
from datetime import date

from flask import Blueprint, Response, g, jsonify, request

from auth import login_required
from db import EXPENSE_CATEGORIES, INCOME_CATEGORIES, get_db, month_shift, now

bp = Blueprint("api", __name__, url_prefix="/api")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def current_month():
    t = date.today()
    return f"{t.year}-{t.month:02d}"


def month_arg():
    m = request.args.get("month", "")
    return m if MONTH_RE.match(m) else current_month()


def clean_tx(d):
    """Validate a transaction payload. Returns (data, error)."""
    try:
        kind = d.get("type")
        amount = round(float(d.get("amount")), 2)
        tx_date = date.fromisoformat(str(d.get("tx_date", ""))).isoformat()
    except (TypeError, ValueError):
        return None, "Enter a valid amount and date"
    cats = EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES if kind == "income" else None
    if cats is None:
        return None, "Type must be income or expense"
    if d.get("category") not in cats:
        return None, "Choose a valid category"
    if not 0 < amount <= 1_000_000_000:
        return None, "Amount must be greater than 0"
    if not 2000 <= int(tx_date[:4]) <= 2100:
        return None, "Date must be between 2000 and 2100"
    note = str(d.get("note", "")).strip()
    if len(note) > 200:
        return None, "Note can be at most 200 characters"
    return {"type": kind, "amount": amount, "category": d["category"], "tx_date": tx_date, "note": note}, None


@bp.get("/meta")
@login_required
def meta():
    return jsonify(expense=EXPENSE_CATEGORIES, income=INCOME_CATEGORIES, month=current_month())


@bp.get("/summary")
@login_required
def summary():
    db, uid, month = get_db(), g.user["id"], month_arg()
    totals = dict(db.execute("SELECT type, SUM(amount) FROM transactions WHERE user_id=? AND substr(tx_date,1,7)=? GROUP BY type", (uid, month)).fetchall())
    income, expense = round(totals.get("income") or 0, 2), round(totals.get("expense") or 0, 2)
    cats = [{"category": r[0], "total": round(r[1], 2)} for r in db.execute(
        """SELECT category, SUM(amount) t FROM transactions WHERE user_id=? AND type='expense' AND substr(tx_date,1,7)=?
           GROUP BY category ORDER BY t DESC""", (uid, month))]
    y, m = int(month[:4]), int(month[5:])
    months = [f"{a}-{b:02d}" for a, b in (month_shift(y, m, -i) for i in range(5, -1, -1))]
    trend = {k: {"month": k, "income": 0, "expense": 0} for k in months}
    for k, ty, total in db.execute("""SELECT substr(tx_date,1,7), type, SUM(amount) FROM transactions
                                      WHERE user_id=? AND substr(tx_date,1,7) BETWEEN ? AND ? GROUP BY 1, 2""", (uid, months[0], months[-1])):
        trend[k][ty] = round(total, 2)
    spent = {c["category"]: c["total"] for c in cats}
    budgets = [{"category": r["category"], "limit": r["monthly_limit"], "spent": spent.get(r["category"], 0),
                "pct": round(spent.get(r["category"], 0) / r["monthly_limit"] * 100)}
               for r in db.execute("SELECT category, monthly_limit FROM budgets WHERE user_id=? ORDER BY category", (uid,))]
    return jsonify(month=month, income=income, expense=expense, balance=round(income - expense, 2),
                   savings_rate=round((income - expense) / income * 100) if income else 0,
                   by_category=cats, trend=list(trend.values()), budgets=budgets)


def tx_query():
    a = request.args
    sql, args = "SELECT id,type,amount,category,tx_date,note FROM transactions WHERE user_id=? AND substr(tx_date,1,7)=?", [g.user["id"], month_arg()]
    if a.get("type") in ("income", "expense"):
        sql += " AND type=?"; args.append(a["type"])
    if a.get("category"):
        sql += " AND category=?"; args.append(a["category"])
    if a.get("q", "").strip():
        sql += " AND (note LIKE ? OR category LIKE ?)"; args += [f"%{a['q'].strip()}%"] * 2
    return sql + " ORDER BY tx_date DESC, id DESC", args


@bp.get("/transactions")
@login_required
def list_tx():
    sql, args = tx_query()
    return jsonify([dict(r) for r in get_db().execute(sql + " LIMIT 300", args)])


@bp.post("/transactions")
@login_required
def add_tx():
    data, err = clean_tx(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    db = get_db()
    tid = db.execute("INSERT INTO transactions (user_id,type,amount,category,tx_date,note,created_at) VALUES (?,?,?,?,?,?,?)",
                     (g.user["id"], data["type"], data["amount"], data["category"], data["tx_date"], data["note"], now())).lastrowid
    db.commit()
    return jsonify(id=tid), 201


@bp.put("/transactions/<int:tid>")
@login_required
def edit_tx(tid):
    data, err = clean_tx(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    db = get_db()
    cur = db.execute("UPDATE transactions SET type=?,amount=?,category=?,tx_date=?,note=? WHERE id=? AND user_id=?",
                     (data["type"], data["amount"], data["category"], data["tx_date"], data["note"], tid, g.user["id"]))
    db.commit()
    return (jsonify(ok=True), 200) if cur.rowcount else (jsonify(error="Transaction not found"), 404)


@bp.delete("/transactions/<int:tid>")
@login_required
def delete_tx(tid):
    db = get_db()
    cur = db.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tid, g.user["id"]))
    db.commit()
    return (jsonify(ok=True), 200) if cur.rowcount else (jsonify(error="Transaction not found"), 404)


@bp.put("/budgets/<category>")
@login_required
def set_budget(category):
    if category not in EXPENSE_CATEGORIES:
        return jsonify(error="Unknown category"), 404
    try:
        limit = round(float((request.get_json(silent=True) or {}).get("limit")), 2)
    except (TypeError, ValueError):
        return jsonify(error="Enter a valid limit"), 400
    if not 0 < limit <= 1_000_000_000:
        return jsonify(error="Limit must be greater than 0"), 400
    db = get_db()
    db.execute("INSERT INTO budgets (user_id, category, monthly_limit) VALUES (?,?,?) "
               "ON CONFLICT(user_id, category) DO UPDATE SET monthly_limit=excluded.monthly_limit", (g.user["id"], category, limit))
    db.commit()
    return jsonify(ok=True)


@bp.delete("/budgets/<category>")
@login_required
def remove_budget(category):
    db = get_db()
    db.execute("DELETE FROM budgets WHERE user_id=? AND category=?", (g.user["id"], category))
    db.commit()
    return jsonify(ok=True)


@bp.get("/export")
@login_required
def export():
    def safe(v):                       # stop spreadsheet formula injection
        v = str(v)
        return "'" + v if v[:1] in "=+-@" else v
    sql, args = tx_query()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Type", "Category", "Amount", "Note"])
    for r in get_db().execute(sql, args):
        w.writerow([r["tx_date"], r["type"], safe(r["category"]), r["amount"], safe(r["note"])])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=spendwise-{month_arg()}.csv"})
