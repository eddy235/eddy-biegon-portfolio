from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("PORTFOLIO_DB", BASE_DIR / "portfolio.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "").encode()
COOKIE_NAME = "eddy_cms_session"
# A hosted read-only showcase preserves dynamic public content but disables
# first-run admin takeover and writing to ephemeral hosting storage.
PUBLIC_READONLY = os.getenv("PORTFOLIO_PUBLIC_READONLY", "0") == "1"

app = FastAPI(
    title="Eddy Biegon Portfolio CMS",
    docs_url=None if PUBLIC_READONLY else "/docs",
    redoc_url=None if PUBLIC_READONLY else "/redoc",
    openapi_url=None if PUBLIC_READONLY else "/openapi.json",
)


@app.middleware("http")
async def protect_public_portfolio(request: Request, call_next):
    """Expose only read-only CMS public APIs on public showcase deployment."""
    path = request.url.path
    if PUBLIC_READONLY and (path == "/admin" or path.startswith("/admin/")
                            or path == "/api/admin" or path.startswith("/api/admin/")):
        return Response(status_code=404)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response



@contextmanager
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_b64, digest_b64 = encoded.split("$", 1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def get_secret() -> bytes:
    # For local review only, a stable development secret is generated from the DB path.
    # Production deployments should set SECRET_KEY.
    return SECRET_KEY or hashlib.sha256((str(DB_PATH) + "eddy-portfolio-dev").encode()).digest()


def sign_session(username: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"u": username}).encode()).decode().rstrip("=")
    sig = hmac.new(get_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def unsign_session(token: str) -> Optional[str]:
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(get_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())["u"]
    except Exception:
        return None


def current_admin(request: Request) -> Optional[str]:
    token = request.cookies.get(COOKIE_NAME)
    return unsign_session(token) if token else None


def require_admin(request: Request) -> str:
    username = current_admin(request)
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required")
    return username


def init_db():
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                eyebrow TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                category TEXT DEFAULT 'web',
                tags TEXT DEFAULT '',
                url TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                featured INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 100,
                published INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS certifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                issuer TEXT DEFAULT '',
                date_text TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                credential_url TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 100,
                published INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS cyber_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                activity_type TEXT DEFAULT 'TryHackMe Room',
                summary TEXT DEFAULT '',
                url TEXT DEFAULT '',
                status TEXT DEFAULT 'Completed',
                completed_date TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 100,
                published INTEGER DEFAULT 1
            );
            """
        )
        # Seed admin only when environment variables are explicitly supplied.
        username = os.getenv("ADMIN_USERNAME")
        password = os.getenv("ADMIN_PASSWORD")
        if username and password and not PUBLIC_READONLY:
            con.execute(
                "INSERT OR IGNORE INTO admins(username,password_hash) VALUES(?,?)",
                (username, hash_password(password)),
            )

        # Seed content only when tables are empty.
        if con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO projects(title,eyebrow,summary,category,tags,url,image_url,featured,sort_order) VALUES(?,?,?,?,?,?,?,?,?)",
                [
                    ("KNLS Website", "Web / Infrastructure", "WordPress migration, content cleanup, deployment and server troubleshooting.", "web", "WordPress,Virtualmin,Apache", "https://www.knls.ac.ke/", "https://image.thum.io/get/width/1400/crop/900/https://www.knls.ac.ke/", 1, 10),
                    ("Mint Dental Centre", "Client Website", "Responsive clinic site with booking, WhatsApp and accessibility features.", "web", "HTML,CSS,JavaScript", "https://mintdentalcentre.co.ke/", "https://image.thum.io/get/width/1400/crop/900/https://mintdentalcentre.co.ke/", 1, 20),
                    ("SecureScan — Website Security Auditor", "Cybersecurity / DevSecOps", "FastAPI-based website security auditing platform with risk findings, dashboard insights and a protected public demo. GitHub: github.com/eddy235/SecureScan", "security", "Python,FastAPI,JavaScript,Docker,GitHub Actions,Render", "https://securescan-demo.onrender.com/", "", 1, 30),
                    ("NexusDesk — IT Service Management", "Full-stack / IT Operations", "Django helpdesk covering tickets, SLA tracking, IT assets, role-based controls and technician reporting. Read-only synthetic portfolio demo. GitHub: github.com/eddy235/NexusDesk", "web", "Python,Django,IT Support,Asset Management,SLA,DevOps,GitHub Actions", "https://nexusdesk-demo.onrender.com/demo/", "", 1, 40),
                    ("API Security Risk Analysis", "Cybersecurity", "Authentication, authorisation, exposure, rate limiting and input-validation review.", "security", "Postman,API Security,Risk", "https://github.com/eddy235", "", 0, 50),
                    ("Vulnerability Assessment", "Cybersecurity", "Web testing, risk classification and concise security reporting.", "security", "Nmap,OWASP ZAP,Reporting", "https://github.com/eddy235", "", 0, 60),
                ],
            )
        # Idempotently ensure the two portfolio projects exist in older CMS databases.
        additional = [
            ("SecureScan — Website Security Auditor", "Cybersecurity / DevSecOps", "FastAPI website security auditor with risk findings, dashboards and a safe demo. GitHub: github.com/eddy235/SecureScan", "security", "Python,FastAPI,JavaScript,Docker,GitHub Actions,Render", "https://securescan-demo.onrender.com/", 1, 30),
            ("NexusDesk — IT Service Management", "Full-stack / IT Operations", "Django helpdesk with tickets, SLAs, IT inventory and staff reporting. GitHub: github.com/eddy235/NexusDesk", "web", "Python,Django,IT Support,Asset Management,GitHub Actions,Render", "https://nexusdesk-demo.onrender.com/demo/", 1, 40),
        ]
        for title, eyebrow, summary, category, tags, url, featured, order in additional:
            if not con.execute("SELECT 1 FROM projects WHERE title=? LIMIT 1", (title,)).fetchone():
                con.execute("INSERT INTO projects(title,eyebrow,summary,category,tags,url,image_url,featured,sort_order) VALUES(?,?,?,?,?,?,?,?,?)", (title,eyebrow,summary,category,tags,url,"",featured,order))
        if con.execute("SELECT COUNT(*) FROM certifications").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO certifications(title,issuer,date_text,summary,sort_order) VALUES(?,?,?,?,?)",
                [
                    ("BSc Information Technology", "Kabarak University", "2021–2024", "", 10),
                    ("Cybersecurity Boot Camp", "Moringa School", "2025", "", 20),
                    ("Google Cybersecurity", "Google", "2024–2025", "Foundations, networks, risk, threats and Python automation.", 30),
                    ("Diploma in Information Technology", "Kabarak University", "2019–2021", "", 40),
                    ("Certificate in Information Technology", "Kabarak University", "2018", "", 50),
                    ("Basic Digital Productivity Skills", "ICT Authority", "2023", "", 60),
                ],
            )


init_db()


class ProjectIn(BaseModel):
    title: str
    eyebrow: str = ""
    summary: str = ""
    category: str = "web"
    tags: str = ""
    url: str = ""
    image_url: str = ""
    featured: bool = False
    sort_order: int = 100
    published: bool = True


class CertIn(BaseModel):
    title: str
    issuer: str = ""
    date_text: str = ""
    summary: str = ""
    credential_url: str = ""
    image_url: str = ""
    sort_order: int = 100
    published: bool = True


class ActivityIn(BaseModel):
    title: str
    activity_type: str = "TryHackMe Room"
    summary: str = ""
    url: str = ""
    status: str = "Completed"
    completed_date: str = ""
    sort_order: int = 100
    published: bool = True


def rows(table: str, public_only: bool = True):
    allowed = {"projects", "certifications", "cyber_activities"}
    if table not in allowed:
        raise ValueError("bad table")
    where = "WHERE published=1" if public_only else ""
    with db() as con:
        return [dict(r) for r in con.execute(f"SELECT * FROM {table} {where} ORDER BY sort_order, id").fetchall()]


@app.get("/health")
def health():
    return {"status": "ok", "read_only": PUBLIC_READONLY}


@app.get("/api/projects")
def api_projects(featured: Optional[bool] = None):
    data = rows("projects")
    if featured is not None:
        data = [x for x in data if bool(x["featured"]) == featured]
    return data


@app.get("/api/certifications")
def api_certifications():
    return rows("certifications")


@app.get("/api/cyber-activities")
def api_cyber():
    return rows("cyber_activities")


@app.post("/admin/setup")
def admin_setup(username: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    with db() as con:
        count = con.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
        if count:
            raise HTTPException(status_code=403, detail="Setup is already complete")
        if len(username.strip()) < 3 or len(password) < 10 or password != confirm_password:
            return RedirectResponse("/admin?setup_error=1", status_code=303)
        con.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)", (username.strip(), hash_password(password)))
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(COOKIE_NAME, sign_session(username.strip()), httponly=True, samesite="strict", secure=os.getenv("COOKIE_SECURE", "0") == "1", max_age=60 * 60 * 12)
    return resp


@app.post("/admin/login")
def admin_login(response: Response, username: str = Form(...), password: str = Form(...)):
    with db() as con:
        row = con.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return RedirectResponse("/admin?error=1", status_code=303)
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(COOKIE_NAME, sign_session(username), httponly=True, samesite="strict", secure=os.getenv("COOKIE_SECURE", "0") == "1", max_age=60 * 60 * 12)
    return resp


@app.post("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/admin", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.get("/api/admin/all")
def admin_all(request: Request):
    require_admin(request)
    return {
        "projects": rows("projects", False),
        "certifications": rows("certifications", False),
        "cyber_activities": rows("cyber_activities", False),
    }


def save_item(table: str, data: dict, item_id: Optional[int] = None):
    fields = list(data.keys())
    vals = [int(v) if isinstance(v, bool) else v for v in data.values()]
    with db() as con:
        if item_id is None:
            qs = ",".join("?" for _ in fields)
            cur = con.execute(f"INSERT INTO {table}({','.join(fields)}) VALUES({qs})", vals)
            return cur.lastrowid
        sets = ",".join(f"{f}=?" for f in fields)
        con.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals + [item_id])
        return item_id


@app.post("/api/admin/projects")
def create_project(request: Request, data: ProjectIn):
    require_admin(request)
    return {"id": save_item("projects", data.model_dump())}


@app.put("/api/admin/projects/{item_id}")
def update_project(item_id: int, request: Request, data: ProjectIn):
    require_admin(request)
    return {"id": save_item("projects", data.model_dump(), item_id)}


@app.delete("/api/admin/projects/{item_id}")
def delete_project(item_id: int, request: Request):
    require_admin(request)
    with db() as con:
        con.execute("DELETE FROM projects WHERE id=?", (item_id,))
    return {"ok": True}


@app.post("/api/admin/certifications")
def create_cert(request: Request, data: CertIn):
    require_admin(request)
    return {"id": save_item("certifications", data.model_dump())}


@app.put("/api/admin/certifications/{item_id}")
def update_cert(item_id: int, request: Request, data: CertIn):
    require_admin(request)
    return {"id": save_item("certifications", data.model_dump(), item_id)}


@app.delete("/api/admin/certifications/{item_id}")
def delete_cert(item_id: int, request: Request):
    require_admin(request)
    with db() as con:
        con.execute("DELETE FROM certifications WHERE id=?", (item_id,))
    return {"ok": True}


@app.post("/api/admin/cyber-activities")
def create_activity(request: Request, data: ActivityIn):
    require_admin(request)
    return {"id": save_item("cyber_activities", data.model_dump())}


@app.put("/api/admin/cyber-activities/{item_id}")
def update_activity(item_id: int, request: Request, data: ActivityIn):
    require_admin(request)
    return {"id": save_item("cyber_activities", data.model_dump(), item_id)}


@app.delete("/api/admin/cyber-activities/{item_id}")
def delete_activity(item_id: int, request: Request):
    require_admin(request)
    with db() as con:
        con.execute("DELETE FROM cyber_activities WHERE id=?", (item_id,))
    return {"ok": True}


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, error: Optional[int] = None, setup_error: Optional[int] = None):
    with db() as con:
        admin_count = con.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    if admin_count == 0:
        message = '<p class="error">Use at least 3 characters for the username, a 10+ character password, and matching passwords.</p>' if setup_error else ''
        return HTMLResponse(f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Set up Portfolio CMS</title><link rel='stylesheet' href='/styles.css'><link rel='stylesheet' href='/admin.css'></head>
<body class='admin-body'><main class='login-card'><a class='brand' href='/'>EDDY<span>.</span></a><div class='eyebrow'>First launch</div><h1>Create your admin.</h1><p>This setup screen disappears after the first administrator account is created.</p>{message}
<form action='/admin/setup' method='post' class='admin-form'><label>Username<input name='username' minlength='3' required autocomplete='username'></label><label>Password<input name='password' type='password' minlength='10' required autocomplete='new-password'></label><label>Confirm password<input name='confirm_password' type='password' minlength='10' required autocomplete='new-password'></label><button class='btn primary' type='submit'>Create admin & enter CMS</button></form></main></body></html>""")
    if not current_admin(request):
        message = '<p class="error">Incorrect username or password.</p>' if error else ''
        return HTMLResponse(f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Portfolio CMS Login</title><link rel='stylesheet' href='/styles.css'><link rel='stylesheet' href='/admin.css'></head>
<body class='admin-body'><main class='login-card'><a class='brand' href='/'>EDDY<span>.</span></a><h1>Portfolio CMS</h1><p>Sign in to update your public portfolio.</p>{message}
<form action='/admin/login' method='post' class='admin-form'><label>Username<input name='username' required autocomplete='username'></label><label>Password<input name='password' type='password' required autocomplete='current-password'></label><button class='btn primary' type='submit'>Sign in</button></form></main></body></html>""")
    return FileResponse(BASE_DIR / "admin.html")


# Explicit page routes keep clean root behavior and work locally.
@app.get("/")
def home():
    return FileResponse(BASE_DIR / "index.html")

for page in ["index.html", "about.html", "experience.html", "projects.html", "cyberlab.html", "certifications.html", "contact.html"]:
    path = "/" + page
    app.add_api_route(path, lambda p=page: FileResponse(BASE_DIR / p), methods=["GET"], include_in_schema=False)

# Static assets and downloadable CV.
for name in ["styles.css", "script.js", "admin.css", "admin.js", "EDDY_BIEGON_CV.docx"]:
    path = "/" + name
    app.add_api_route(path, lambda n=name: FileResponse(BASE_DIR / n), methods=["GET"], include_in_schema=False)
