# Eddy Biegon — Portfolio Website

A full-stack personal portfolio built with **FastAPI, HTML, CSS, JavaScript and SQLite**, featuring the v6 blue/black/red interface, responsive pages, dynamic public content, GitHub activity feed, project filters and quick views, theme switching, and an interactive **Packet Defender** cybersecurity mini-game.

**Live portfolio:** https://eddy-biegon-portfolio.onrender.com/  
**Featured projects:** [NexusDesk](https://nexusdesk-demo.onrender.com/demo/) · [SecureScan](https://securescan-demo.onrender.com/) · [Maison Sanaa](https://maison-sanaa-demo.onrender.com/)

## About this repository

This is the **dedicated source repository** for the portfolio website, migrated from `eddy235/NexusDesk` branch `portfolio/v6-render-hosted` (formerly `portfolio-site/`). NexusDesk itself remains in its own repository. The portfolio source is now in this repository's **root**, with a clean application entry point `app.py`, assets, tests, and deployment configuration.

As of initial import, the public Render URL remains online. **Render may still reference the former NexusDesk repository until the existing Render service's source is changed manually.** See [MIGRATION.md](MIGRATION.md) for cutover and rollback instructions.

## Highlights

- A compact homepage plus projects, experience, about, certifications, Cyber Lab, contact and a dedicated game page.
- Featured NexusDesk and SecureScan project cards, with live demos and GitHub links.
- GitHub activity integration, project search/filtering and quick views.
- Cyber Lab gallery and Packet Defender at `/game.html`, reached from the red pulsing navigation button.
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


## November 2026 usability update
The homepage is a compact introduction with two selected project links, projects/contact buttons and CV access. Detailed capabilities and the GitHub feed remain on About. At the tested desktop viewport, the full homepage fits without vertical scrolling; narrow layouts use responsive cards and a collapsible navigation menu.
Packet Defender is on `/game.html`; `/game` and `/packet-defender` redirect there. The red navigation button pulses gently and stops animating when reduced motion is requested. Explicit SAFE/THREAT text, keyboard controls and a Stop button improve game access.
Contact inputs have visible labels, and the optional email is included in the WhatsApp message draft.


## Services and pricing
`/services.html` (also `/services`) lists business websites from KSh 35,000, internal business tools from KSh 80,000 and Python application support from KSh 25,000. Optional website maintenance is KSh 36,000 per year (12 × the previous KSh 3,000 monthly fee); maintenance tasks retain their existing monthly cadence. USD figures are indicative conversions using the CBK rate of KSh 129.96/USD dated 10 November 2026; update the page's figures and dated source note together when repricing. Package links select the relevant enquiry on Contact, using a fixed list of service identifiers. No enquiry is submitted until the visitor continues on WhatsApp and sends it there.


## Maison Sanaa hospitality suite

The [Maison Sanaa demo](https://maison-sanaa-demo.onrender.com/) is a fictional boutique hotel site, installable mobile restaurant ordering PWA and password-protected staff inventory dashboard. Source and setup: [`hospitality/`](hospitality/README.md). It runs as a separate Render web service from this monorepo. Data on the free demo service is ephemeral.
