# Migration to a standalone GitHub repository

## Source and destination

- Prior source: `eddy235/NexusDesk` branch `portfolio/v6-render-hosted`, subdirectory `portfolio-site/`.
- New source: **`eddy235/eddy-biegon-portfolio` branch `main`, repository root**.
- Existing Render service: [eddy-biegon-portfolio](https://dashboard.render.com/web/srv-dbhh0jh42hec73ceso40).
- Public URL to preserve: https://eddy-biegon-portfolio.onrender.com/

The new repository includes the verified v6 site source, NexusDesk and SecureScan links, pages, CV, Packet Defender, public project APIs and automated tests.

## Current Render source switch

The GitHub repository migration and the Render source switch are separate operations. **The live site does not automatically follow the new repository just because the code moved.** On the **existing** Render service (do not create a replacement service if you want to retain the same URL):

1. Open [Render service settings](https://dashboard.render.com/web/srv-dbhh0jh42hec73ceso40).
2. Change the connected repository/source from `eddy235/NexusDesk` to **`eddy235/eddy-biegon-portfolio`**, branch **`main`**. If the repository does not appear, give Render access to it using its GitHub connection controls.
3. Keep the service type **Python web service** and clear any old repository subdirectory/root directory setting.
4. Set **Build Command**: `pip install -r requirements.txt`.
5. Set **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
6. Preserve `PORTFOLIO_PUBLIC_READONLY=1`, `COOKIE_SECURE=1`, and the existing generated `SECRET_KEY`. Keep HTTPS and automatic deployments on.
7. Deploy the new commit and confirm the status is **Live**.
8. Run `python scripts/verify_live.py https://eddy-biegon-portfolio.onrender.com` and confirm the project pages and CSS load, and `/admin` stays inaccessible.

**Do not delete the old source branch before the new deployment is verified.**

## Rollback

If the new deployment fails, restore the previous source on Render:
- Repository: `eddy235/NexusDesk`
- Branch: `portfolio/v6-render-hosted`
- Build: `pip install -r portfolio-site/requirements.txt`
- Start: `cd portfolio-site && uvicorn app:app --host 0.0.0.0 --port $PORT`.

Keep `PORTFOLIO_PUBLIC_READONLY=1` and do not publish any editable admin setup on the public service.

## Limitations

The public Render free service has an ephemeral filesystem. It serves public data only and does not provide persistent CMS editing. For a writable private CMS, move to persistent storage, proper secret management, and authentication hardening first. Automated smoke tests do not constitute a penetration test.
