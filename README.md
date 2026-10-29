# Eddy Biegon — Portfolio Website

A full-stack personal portfolio built with **FastAPI, HTML, CSS, JavaScript and SQLite**, featuring the v6 blue/black/red interface, responsive pages, dynamic public content, GitHub activity feed, project filters and quick views, theme switching, and an interactive **Packet Defender** cybersecurity mini-game.

**Live portfolio:** https://eddy-biegon-portfolio.onrender.com/  
**Featured projects:** [NexusDesk](https://nexusdesk-demo.onrender.com/demo/) · [SecureScan](https://securescan-demo.onrender.com/)

## About this repository

This is the **dedicated source repository** for the portfolio website, migrated from `eddy235/NexusDesk` branch `portfolio/v6-render-hosted` (formerly `portfolio-site/`). NexusDesk itself remains in its own repository. The portfolio source is now in this repository's **root**, with a clean application entry point `app.py`, assets, tests, and deployment configuration.

As of initial import, the public Render URL remains online. **Render may still reference the former NexusDesk repository until the existing Render service's source is changed manually.** See [MIGRATION.md](MIGRATION.md) for cutover and rollback instructions.

## Highlights

- Home, projects, experience, about, certifications, Cyber Lab, and contact pages.
- Featured NexusDesk and SecureScan project cards, with live demos and GitHub links.
- GitHub activity integration, project search/filtering and quick views.
- Cyber Lab gallery and browser-based Packet Defender mini-game.
- Theme switching and mobile-responsive visual design.
- A local, editable CMS supporting projects, certifications and Cyber Lab records.
- Automated regression checks and a read-only public deployment mode.

## Run locally

Requires Python 3.11+.

```bash
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

Visit http://127.0.0.1:8000/. On a **private local installation only**, visit `/admin` to set up CMS login. Local SQLite database (`portfolio.db`) is automatically created. **Never expose first-run admin setup publicly.**

## Run automated tests

```bash
python -m pip install -r requirements.txt httpx
python -m unittest discover -s tests -v
```

## Public deployment on Render

Render runs the portfolio as a **Python web service**, not a static site. Existing hosted configuration:

| Setting | Value |
|---|---|
| Source repository | `eddy235/eddy-biegon-portfolio` (configure on the **existing Render service**) |
| Branch | `main` |
| Root directory | repository root |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Health endpoint | `/health` |
| `PORTFOLIO_PUBLIC_READONLY` | `1` |
| `COOKIE_SECURE` | `1` |
| `SECRET_KEY` | a generated secret, never commit |
| Auto deploy | recommended |

In public read-only mode, CMS admin and write endpoints are disabled. Dynamic public data is seeded from bundled fictional and portfolio project information; ephemeral SQLite storage on Render's free tier must **not** be relied on for private data or editable CMS records.

**Verify after cutover:**

```bash
python scripts/verify_live.py https://eddy-biegon-portfolio.onrender.com
```

The verification checks pages, assets, public project records, health, and admin isolation. It is not a security penetration test.

## Repository files

- `app.py`: FastAPI routes, CMS and public-mode protections
- `index.html`, `projects.html`, other `*.html`: pages
- `styles.css`, `script.js`, `admin.css`, `admin.js`: interface and interactions
- `tests/`: regression tests
- `scripts/verify_live.py`: live site read-only smoke checks
- `render.yaml`, `Dockerfile`: hosting configuration
- `EDDY_BIEGON_CV.docx`: public CV download
- `MIGRATION.md`: existing Render URL preservation and rollback

## Privacy and security

Do not commit `.env`, `portfolio.db`, passwords, or operational data. The public hosted CMS is intentionally **read-only** to prevent account takeover via first-run setup and to avoid persistence risks. The public CV is purposefully downloadable. This is a portfolio application, not a production-hardened multi-user CMS.
