# Monclo Apparel — PyScript + Flask

A responsive, minimalist clothing storefront with a silver-grey design, PHP pricing, cart, Cash on Delivery checkout, saved customer orders, FAQ/support, and an optional protected management panel. **All browser interactivity is written in Python using PyScript** rather than handwritten JavaScript. Flask + SQLite hold real products, order records, and feedback.

## Requirements and start

- Python 3.10 or later, a modern browser and Internet access (for the PyScript runtime, Google Fonts and example Unsplash photos).
- Install dependencies and start the application from this directory:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open **http://127.0.0.1:5000/**. The store works from the Flask server — do **not** double-click `index.html` as a standalone file. Flask creates `instance/monclo.db` and seeds nine editable example apparel products automatically when the database is new.

The storefront defaults to a **₱120 flat delivery fee**; set the same value in `checkout.py` (`DELIVERY_CENTS`) and `static/py/app.py` (`delivery_cents`) before using a real courier. Images are illustrative stock photographs, **not actual Monclo merchandise**; replace them with the real product photos, sizes and pricing before launch.

## Enable the admin panel

The admin panel is accessible at `http://127.0.0.1:5000/#/admin` and **is disabled until both secrets are configured**. Set environment variables in the terminal before starting the server:

```bash
# macOS/Linux example (use YOUR secret values):
export MONCLO_SECRET_KEY="replace-with-a-long-random-32-plus-character-value"
export MONCLO_ADMIN_USERNAME="admin"
export MONCLO_ADMIN_PASSWORD="replace-with-a-strong-unique-admin-password"
export MONCLO_CONTACT_EMAIL="your-team@your-domain.com"
export MONCLO_INSTAGRAM_URL="https://www.instagram.com/your-real-account/"
python server.py
```

On Windows PowerShell use `$env:MONCLO_SECRET_KEY="..."` for each variable instead of `export`. The `.env.example` file lists supported options; this app does **not** automatically read an `.env` file. The admin login is intentionally not enabled without secrets.

Admin users can add, edit and hide products; upload JPG/PNG/WEBP images; update price, sizes, colors, inventory and featured items; view saved customer orders and submitted feedback; and update order fulfillment status. Files are stored in `static/uploads/`. The app restricts admin APIs to authenticated sessions and protects mutations with a CSRF token.

## Running tests

```bash
pytest -q
```

Tests cover inventory checkout, server-calculated totals, order retry idempotency, invalid orders, saved feedback, authentication and product administration.

## How the six commits are organized

Open `COMMITS.md` and run `git log --oneline --reverse`. The download includes six independent Git commits to inspect, cherry-pick or replay using the separate patch-series archive.

## Before taking real customer orders

This is an end-to-end **starter application**, not a fully operated production shop. Before public deployment: configure a secure HTTPS domain and set `MONCLO_HTTPS=1`; use strong secrets; configure actual product photography and accurate shipping rates; back up the SQLite database and uploaded images; add reverse-proxy rate limiting for login, ordering and feedback; establish a real fulfillment and customer-notification process; create your privacy/returns/shipping policies; and consider a managed database when handling higher traffic. SQLite writes are transactional but this starter does not send email or SMS notifications. Keep customer data and database files private. The example footer email/Instagram are only shown when corresponding environment variables are configured.

Never expose the development server directly to the Internet. For deployment, use a production WSGI server (for example, Gunicorn on Linux) behind HTTPS and proper backups, logging and rate limiting.
