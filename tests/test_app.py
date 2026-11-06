"""Unit tests. Run:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app          # noqa: E402

TX = {"type": "expense", "amount": 250, "category": "Food", "tx_date": "2026-03-10", "note": "Lunch"}


class SpendwiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({"DATABASE": os.path.join(self.tmp, "t.db"), "SECRET_KEY": "test", "SEED_DEMO": False, "TESTING": True})
        self.c = self.app.test_client()

    def token(self, client=None):
        client = client or self.c
        with client.session_transaction() as s:
            s["csrf"] = "tok"
        return {"X-CSRF-Token": "tok"}

    def register(self, client, name="asha", pw="secret1"):
        self.token(client)
        return client.post("/register", data={"csrf_token": "tok", "username": name, "password": pw, "confirm": pw})

    def login_client(self, name="asha"):
        cl = self.app.test_client()
        self.register(cl, name)
        return cl, self.token(cl)

    # ---- accounts & security ----
    def test_register_validation_and_duplicates(self):
        self.token()
        bad = self.c.post("/register", data={"csrf_token": "tok", "username": "a!", "password": "123", "confirm": "123"})
        self.assertIn(b"Username must be", bad.data)
        self.assertEqual(self.register(self.app.test_client(), "Asha").status_code, 302)
        self.assertIn(b"already taken", self.register(self.app.test_client(), "ASHA").data)

    def test_login_flow(self):
        self.register(self.app.test_client())
        self.token()
        self.assertIn(b"Incorrect", self.c.post("/login", data={"csrf_token": "tok", "username": "asha", "password": "nope"}).data)
        self.assertEqual(self.c.post("/login", data={"csrf_token": "tok", "username": "asha", "password": "secret1"}).status_code, 302)

    def test_auth_and_csrf_required(self):
        self.assertEqual(self.c.get("/api/summary").status_code, 401)
        self.assertEqual(self.c.get("/").status_code, 302)
        cl, h = self.login_client()
        self.assertEqual(cl.post("/api/transactions", json=TX).status_code, 400)            # no CSRF header
        self.assertEqual(cl.post("/api/transactions", json=TX, headers=h).status_code, 201)

    # ---- transactions ----
    def test_validation(self):
        cl, h = self.login_client()
        for patch in ({"amount": -5}, {"amount": "abc"}, {"category": "Salary"}, {"type": "loan"}, {"tx_date": "2026-13-45"}, {"note": "x" * 201}):
            r = cl.post("/api/transactions", json={**TX, **patch}, headers=h)
            self.assertEqual(r.status_code, 400, patch)

    def test_crud(self):
        cl, h = self.login_client()
        tid = cl.post("/api/transactions", json=TX, headers=h).get_json()["id"]
        self.assertEqual(cl.put(f"/api/transactions/{tid}", json={**TX, "amount": 300}, headers=h).status_code, 200)
        rows = cl.get("/api/transactions?month=2026-03").get_json()
        self.assertEqual((len(rows), rows[0]["amount"]), (1, 300))
        self.assertEqual(len(cl.get("/api/transactions?month=2026-03&q=lunch").get_json()), 1)
        self.assertEqual(len(cl.get("/api/transactions?month=2026-03&type=income").get_json()), 0)
        self.assertEqual(cl.delete(f"/api/transactions/{tid}", headers=h).status_code, 200)
        self.assertEqual(cl.delete(f"/api/transactions/{tid}", headers=h).status_code, 404)

    def test_user_isolation(self):
        a, ha = self.login_client("alice")
        b, hb = self.login_client("bobby")
        tid = a.post("/api/transactions", json=TX, headers=ha).get_json()["id"]
        self.assertEqual(b.get("/api/transactions?month=2026-03").get_json(), [])
        self.assertEqual(b.put(f"/api/transactions/{tid}", json=TX, headers=hb).status_code, 404)
        self.assertEqual(b.delete(f"/api/transactions/{tid}", headers=hb).status_code, 404)
        self.assertEqual(len(a.get("/api/transactions?month=2026-03").get_json()), 1)

    # ---- summary, budgets, export ----
    def test_summary_math_and_budgets(self):
        cl, h = self.login_client()
        for tx in ({"type": "income", "amount": 10000, "category": "Salary"}, {"amount": 2000, "category": "Food"}, {"amount": 500, "category": "Transport"}):
            cl.post("/api/transactions", json={**TX, **tx}, headers=h)
        cl.put("/api/budgets/Food", json={"limit": 2500}, headers=h)
        s = cl.get("/api/summary?month=2026-03").get_json()
        self.assertEqual((s["income"], s["expense"], s["balance"], s["savings_rate"]), (10000, 2500, 7500, 75))
        self.assertEqual(s["by_category"][0], {"category": "Food", "total": 2000})
        self.assertEqual((s["budgets"][0]["pct"], len(s["trend"]), s["trend"][-1]["month"]), (80, 6, "2026-03"))
        self.assertEqual(cl.put("/api/budgets/Food", json={"limit": 0}, headers=h).status_code, 400)
        self.assertEqual(cl.put("/api/budgets/Nope", json={"limit": 5}, headers=h).status_code, 404)
        cl.delete("/api/budgets/Food", headers=h)
        self.assertEqual(cl.get("/api/summary?month=2026-03").get_json()["budgets"], [])

    def test_bad_month_falls_back(self):
        cl, _ = self.login_client()
        self.assertRegex(cl.get("/api/summary?month=hacked").get_json()["month"], r"^\d{4}-\d{2}$")

    def test_csv_export_blocks_formula_injection(self):
        cl, h = self.login_client()
        cl.post("/api/transactions", json={**TX, "note": "=HYPERLINK(\"http://evil\")"}, headers=h)
        body = cl.get("/api/export?month=2026-03").data.decode()
        self.assertIn("'=HYPERLINK", body)
        self.assertTrue(body.startswith("Date,Type,Category,Amount,Note"))


if __name__ == "__main__":
    unittest.main()
