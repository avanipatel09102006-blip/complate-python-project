# Spendwise: Personal Finance Tracker (Flask + SQLite)

A complete Python project: accounts, REST API, database, responsive dashboard with charts, tests.

## Run
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000  (demo login: demo / demo123, six months of sample data are created on first run)

## Test
    python -m unittest discover -s tests -v

## Features
- Register / login (hashed passwords, sessions), every user sees only their own data
- Add, edit, delete income and expenses; search and filter; export a month to CSV
- Dashboard: income, expenses, balance, savings rate, category donut chart, 6-month trend chart (pure SVG)
- Monthly budgets per category with progress bars (amber at 80%, red when over)
- Responsive layout (tables become cards on mobile), light print-friendly theme

## Project structure
    app.py        application factory, CSRF protection, error handlers
    auth.py       register / login / logout, login_required
    api.py        JSON API (transactions, budgets, summary, export) + validation
    db.py         schema, connection handling, demo data
    templates/    Jinja pages (login, register, dashboard)
    static/       style.css, app.js (fetch, SVG charts, dialogs)
    tests/        unittest suite

## Database
users (1) -> (many) transactions, users (1) -> (many) budgets (composite key user + category), CHECK constraints, ON DELETE CASCADE, index on (user_id, tx_date)
