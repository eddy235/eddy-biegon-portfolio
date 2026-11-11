# Maison Sanaa — Hospitality Suite v2

A fictional, full-stack hotel and restaurant portfolio demo by Eddy Biegon.

**Live:** https://maison-sanaa-demo.onrender.com/ · [Mobile ordering](https://maison-sanaa-demo.onrender.com/order) · [Staff / Kitchen](https://maison-sanaa-demo.onrender.com/staff)

## Features

- **Sticky navigation** across hotel, ordering and staff pages.
- **Guest ordering:** 14 mock dishes and drinks, search/categories, basket, room/table/pickup, server-calculated prices, order status, secure unpredictable tracking codes.
- **M-Pesa-ready checkout:** Clicking **Pay with M-Pesa** reserves an order and opens an M-Pesa phone form; submitting asks the backend to initiate STK Push.
- **Demo payment mode (default):** Clearly labeled interactive on-screen mock approval; **does not send an STK prompt, accept a real M-Pesa PIN or collect money**. Real Daraja STK Push requires independently obtained credentials and merchant settings.
- **Manager dashboard:** revenue and volume metrics, inventory and ingredient restocking/write-offs.
- **Kitchen display:** high-contrast active tickets with received → preparing → ready → served transitions, auto-refresh.
- **Individual staff users:** manager can create/deactivate manager, kitchen and server accounts. Password hashes and signed HttpOnly, Secure, SameSite session cookies, login throttling and server-enforced access restrictions.
- **PostgreSQL-ready:** SQLAlchemy-based backend supports managed PostgreSQL via `DATABASE_URL` and local SQLite for development. Ingredient reservations use a transactional write and row locks on PostgreSQL.
- **Installable PWA** for mobile-friendly ordering.

## Persistent PostgreSQL on Render

A free Render PostgreSQL instance called `maison-sanaa-db` was created in Frankfurt on 11 November 2026. **Free databases expire after 30 days: this one expires on December 11, 2026.** Free PostgreSQL databases do not include backups. For long-term hotel data, upgrade to a paid PostgreSQL plan with backups and monitoring before expiration.

A reviewable Blueprint in [`render-hospitality.yaml`](render-hospitality.yaml) links the **existing** `maison-sanaa-demo` service to that **existing** database via:

```yaml
- key: DATABASE_URL
  fromDatabase:
    name: maison-sanaa-db
    property: connectionString
```

**Connection requires a Render Blueprint sync approval:** review [the planned update](https://dashboard.render.com/blueprint/exs-dbq1lm9srm7s73982n7g/sync/exe-dbq1lmpsrm7s73982p10) in Render, then approve it. That plan captures the existing free DB and web service and adds the connection environment variable. It does not create a second instance, and it preserves the existing configured staff password and server secret. **Until the sync is approved, hosting uses local SQLite as an ephemeral fallback**, so do not rely on demo orders surviving redeploys.

After approving, check `https://maison-sanaa-demo.onrender.com/health`: `"database":"postgresql"` means persistent PostgreSQL is connected; `"database":"sqlite"` means it is still using ephemeral storage.

## Real M-Pesa Daraja configuration

**No real M-Pesa PIN is ever entered on this website.** To enable an actual STK prompt, first obtain valid Safaricom Daraja credentials and an approved business shortcode, then configure these secrets on Render (never commit them):

| Environment variable | Purpose |
| --- | --- |
| `MPESA_MODE` | `demo` (no real request), `sandbox` (Daraja testing) or `production` |
| `MPESA_CONSUMER_KEY` | Daraja API app key |
| `MPESA_CONSUMER_SECRET` | Daraja API app secret |
| `MPESA_SHORTCODE` | Registered paybill shortcode |
| `MPESA_PASSKEY` | STK Push passkey |
| `MPESA_CALLBACK_URL` | `https://maison-sanaa-demo.onrender.com/api/payments/mpesa/callback` |
| `MPESA_CALLBACK_TOKEN` | Long random secret appended to callback path |

The app requests OAuth, sends an STK Push request, records the asynchronous checkout reference, processes a protected callback endpoint, and independently queries Daraja before marking a successful payment. For production you must additionally implement idempotent reconciliation, refunds, outstanding-order cleanup, webhook replay protection, monitoring, and staff approval workflows. **Do not enable production payments on this public demo.**

## Local development

Python 3.11+; run from repository root:

```bash
python -m pip install -r requirements.txt
export HOSPITALITY_ADMIN_USERNAME=manager
export HOSPITALITY_ADMIN_PASSWORD='replace-this-with-a-strong-password'
export HOSPITALITY_COOKIE_SECURE=0
uvicorn hospitality.app:app --reload
```

Windows PowerShell: set the three values with `$env:VARIABLE='value'` before running Uvicorn.

You can set `HOSPITALITY_DB=/path/to/local.sqlite3` or `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB`. The local SQLite database is not meant to be a production database.

## Quality checks

GitHub Actions runs `node --check hospitality/static/app.js`, `python -m compileall -q hospitality`, and `python -m unittest hospitality.tests.test_hospitality -v`. Tests cover authentication, role-based access, ordering, stock deductions, invalid orders, order-state transitions and simulated M-Pesa payment.

## Limitations

This is not a commercial hotel booking system or an accredited production POS. It uses fictional property details, mock menus and illustrative prices/images, and does not process room reservations, real payments, deliveries, refunds or guest communications. Do not collect real guest personal data in the public demo.
