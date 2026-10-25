# Six commits: Monclo Apparel

This folder is itself a Git repository with **six commits**. Each commit contains the source changes for one distinct section and builds on the previous commit. `git log --oneline --reverse` shows them in order.

| Commit | What changes | What you can demonstrate |
| --- | --- | --- |
| **01** | Responsive silver-grey layout, homepage, navigation, brand styles, PyScript bootstrap | Responsive Monclo landing page |
| **02** | SQLite product catalog and the PyScript shop, category/size/price filters, search, sorting | Live products loaded from API |
| **03** | Local persistent cart, product variant selection, quantity limits, Buy Now | Add, update and remove merchandise |
| **04** | Server-validated COD checkout, order reference and order storage | Saved order and confirmed total |
| **05** | Support page, feedback database endpoint, FAQ, configurable contact links | Saved support messages |
| **06** | Protected admin area, product CRUD, order statuses, customer feedback dashboard, image uploads, tests, deployment docs | Manage real orders and inventory |

## Commit-by-commit approach

The ZIP containing the **full Git history** can be extracted and used immediately:

```bash
git log --oneline --reverse
git show --stat HEAD~5   # inspect commit 01
git show --stat HEAD~4   # inspect commit 02
# ...
git show --stat HEAD     # inspect commit 06
```

To add these commits to **your own new repository** rather than preserving this repository's history, use the included `git format-patch` files inside `six-commit-patches.zip` (download separately) and run:

```bash
# in a NEW empty Git repository
git am /path/to/patches/*.patch
```

Alternatively, extract the project, remove `.git`, and build each feature yourself following the commit boundaries above.

## Architecture

`templates/index.html` provides the HTML shell. `static/css/style.css` defines the responsive style system. `static/py/app.py` is **PyScript (browser-side Python)** and handles the page routes, DOM events, cart, search, checkout, support and admin interaction. `server.py` initializes Flask. `store.py` owns the SQLite schema and seed catalog. `checkout.py`, `support.py`, and `admin.py` define the server APIs.

The browser cart is stored in `localStorage`; **orders and feedback are only treated as saved after a successful SQLite commit on the server**. The server, not the browser, calculates authoritative prices, validates selections and adjusts stock. Server-side order idempotency prevents repeated charges/orders on retries. No payment gateway or card processing is included; **Cash on Delivery only**.
