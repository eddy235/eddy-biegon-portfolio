# Maison Sanaa — Hotel & Hospitality Suite

An independent **full-stack hospitality demo** within the Eddy Biegon portfolio repository. Fictional boutique hotel, restaurant, mobile ordering experience and staff inventory dashboard.

## Live experiences
- Hotel landing page: `/`
- Installable ordering web app: `/order`
- Staff dashboard: `/staff` (requires a password supplied in deployment secrets)
- Health endpoint: `/health`

## What works
- Fourteen fictional food and drink menu items, with search and categories.
- Room service, table service and pickup order checkout, a live tracking code, and server-calculated KSh prices.
- Recipe-level ingredient deductions in one SQLite transaction; out-of-stock orders are rejected.
- Password-protected staff dashboard: order pipeline, revenue and low-stock indicators.
- Manual ingredient stock adjustments with audit entries.
- Installable mobile-first Progressive Web App, with offline app-shell support. **Ordering requires connectivity.**
- No real payments, reservations, kitchen dispatch, SMS, or real guests. All data is illustrative.

## Run locally
Use Python 3.11 or newer. From the **repository root**:

```bash
python -m pip install -r requirements.txt
HOSPITALITY_ADMIN_PASSWORD='a-long-random-password' HOSPITALITY_COOKIE_SECURE=0 uvicorn hospitality.app:app --reload
```

Windows PowerShell:

```powershell
$env:HOSPITALITY_ADMIN_PASSWORD='a-long-random-password'
$env:HOSPITALITY_COOKIE_SECURE='0'
uvicorn hospitality.app:app --reload
```

The dev database defaults to `/tmp/maison_sanaa_demo.sqlite3` (set `HOSPITALITY_DB` to override). For production, configure durable database storage before relying on orders. Render free instances use **ephemeral** storage and can reset inventory and orders on restart or redeploy.

## Render deployment
Source: `https://github.com/eddy235/eddy-biegon-portfolio`; branch: `main`.
- Runtime: Python
- Build: `pip install -r requirements.txt`
- Start: `uvicorn hospitality.app:app --host 0.0.0.0 --port $PORT`
- Required secrets: `HOSPITALITY_ADMIN_PASSWORD` and `HOSPITALITY_SECRET` (long, random values)
- Set `HOSPITALITY_COOKIE_SECURE=1` for HTTPS.

## Security and limitations
The demo has staff password authentication, HttpOnly/SameSite session cookies, login throttling, data validation, same-origin mutations, non-enumerable order lookup codes and atomic stock changes. It is **not a production hotel POS**: persistent Postgres storage, individual staff accounts, CSRF tokens, payments, backups, audit retention, privacy/security review and real integrations are needed before a real launch.

## License
A fictional portfolio demo; menu, prices, hotel identity and orders are mock data. Photos are loaded remotely from Unsplash, not stored in this repository.
