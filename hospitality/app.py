"""Maison Sanaa hospitality ordering + inventory API. Fictional demo data."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("HOSPITALITY_DB", "/tmp/maison_sanaa_demo.sqlite3"))
ADMIN_PASSWORD = os.getenv("HOSPITALITY_ADMIN_PASSWORD", "")
COOKIE_SECURE = os.getenv("HOSPITALITY_COOKIE_SECURE", "1") != "0"
SECRET = os.getenv("HOSPITALITY_SECRET", "").encode() or secrets.token_bytes(32)
TOKEN_NAME = "maison_staff"
MAX_AGE = 8 * 60 * 60
_attempts: dict[str, list[float]] = {}

app = FastAPI(title="Maison Sanaa Demo", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets", StaticFiles(directory=ROOT / "static"), name="assets")

# Realistic illustrative menu and recipe quantities, not actual hotel data.
INGREDIENTS = [
    ("eggs", "Free-range eggs", "pcs", 70, 15),
    ("bread", "Sourdough bread", "slices", 100, 20),
    ("tomato", "Tomatoes", "kg", 18, 4),
    ("coffee", "Coffee beans", "kg", 8, 2),
    ("flour", "Baking flour", "kg", 18, 3),
    ("milk", "Fresh milk", "L", 35, 8),
    ("banana", "Bananas", "pcs", 45, 10),
    ("honey", "Honey", "kg", 8, 2),
    ("avocado", "Avocados", "pcs", 35, 8),
    ("fish", "Tilapia", "pcs", 24, 6),
    ("rice", "Basmati rice", "kg", 28, 7),
    ("beef", "Beef", "kg", 25, 5),
    ("potato", "Potatoes", "kg", 30, 6),
    ("chicken", "Chicken", "kg", 22, 5),
    ("coconut", "Coconut cream", "L", 18, 4),
    ("pasta", "Pasta", "kg", 15, 3),
    ("cream", "Cooking cream", "L", 15, 3),
    ("chocolate", "Dark chocolate", "kg", 9, 2),
    ("mango", "Mango", "pcs", 30, 7),
    ("passion", "Passion fruit", "pcs", 60, 12),
    ("soda", "Sparkling water", "bottles", 48, 12),
    ("hibiscus", "Hibiscus syrup", "L", 9, 2),
    ("tea", "Kenyan tea", "kg", 6, 1),
    ("orange", "Oranges", "pcs", 45, 10),
]
MENU = [
    ("swahili-breakfast", "Coastal breakfast", "Breakfast", "Eggs, artisan toast, roasted tomato and Kenyan coffee.", 1250, "https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?w=900&q=80", {"eggs": 2, "bread": 2, "tomato": 0.12, "coffee": 0.02}),
    ("tropical-pancakes", "Tropical pancakes", "Breakfast", "Fluffy pancakes, ripe banana and golden honey.", 980, "https://images.unsplash.com/photo-1528207776546-365bb710ee93?w=900&q=80", {"flour": 0.18, "milk": 0.2, "banana": 1, "honey": 0.04}),
    ("avocado-toast", "Avocado sourdough", "Breakfast", "Crushed avocado, soft eggs and toasted sourdough.", 1050, "https://images.unsplash.com/photo-1525351484163-7529414344d8?w=900&q=80", {"avocado": 1, "bread": 2, "eggs": 2}),
    ("grilled-tilapia", "Lake Victoria tilapia", "Mains", "Chargrilled tilapia with fragrant rice and garden relish.", 1950, "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=900&q=80", {"fish": 1, "rice": 0.25, "tomato": 0.1}),
    ("nyama-choma", "Signature nyama choma", "Mains", "Fire-roasted beef, crispy potatoes and fresh kachumbari.", 2450, "https://images.unsplash.com/photo-1544025162-d76694265947?w=900&q=80", {"beef": 0.35, "potato": 0.3, "tomato": 0.12}),
    ("coconut-curry", "Coconut chicken curry", "Mains", "Slow-simmered chicken, coconut cream and steamed rice.", 1850, "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=900&q=80", {"chicken": 0.3, "rice": 0.25, "coconut": 0.2}),
    ("garden-pasta", "Garden pasta", "Mains", "Creamy tomato sauce, fresh herbs and silky pasta.", 1550, "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?w=900&q=80", {"pasta": 0.22, "tomato": 0.2, "cream": 0.15}),
    ("chocolate-fondant", "Chocolate fondant", "Desserts", "Warm dark chocolate centre and a velvety finish.", 950, "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=900&q=80", {"flour": 0.1, "chocolate": 0.15, "milk": 0.1}),
    ("mango-cheesecake", "Mango cheesecake", "Desserts", "A bright tropical mango cheesecake.", 950, "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=900&q=80", {"mango": 1, "cream": 0.15, "flour": 0.07}),
    ("passion-cooler", "Passion fruit cooler", "Cold drinks", "Tangy passion fruit, fresh citrus and soda.", 650, "https://images.unsplash.com/photo-1544145945-f90425340c7e?w=900&q=80", {"passion": 3, "soda": 1}),
    ("hibiscus-spritz", "Hibiscus spritz", "Cold drinks", "Floral hibiscus and sparkling water. Alcohol-free.", 720, "https://images.unsplash.com/photo-1513558161293-cdaf765edfd4?w=900&q=80", {"hibiscus": 0.12, "soda": 1}),
    ("fresh-orange", "Fresh orange juice", "Cold drinks", "Freshly pressed, naturally sweet oranges.", 550, "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=900&q=80", {"orange": 3}),
    ("flat-white", "Flat white", "Hot drinks", "Double espresso with micro-foamed milk.", 480, "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=900&q=80", {"coffee": 0.025, "milk": 0.2}),
    ("masala-chai", "Kenyan masala chai", "Hot drinks", "Spiced Kenyan tea gently brewed with milk.", 420, "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=900&q=80", {"tea": 0.02, "milk": 0.25}),
]

def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    with connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, unit TEXT NOT NULL,
            quantity REAL NOT NULL CHECK(quantity >= 0), minimum REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS menu (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            description TEXT NOT NULL, price INTEGER NOT NULL, image TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recipes (
            menu_id TEXT NOT NULL REFERENCES menu(id),
            ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
            amount REAL NOT NULL CHECK(amount > 0),
            PRIMARY KEY(menu_id, ingredient_id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            guest_name TEXT NOT NULL,
            delivery_type TEXT NOT NULL,
            location TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'received',
            total INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            menu_id TEXT NOT NULL, name TEXT NOT NULL,
            quantity INTEGER NOT NULL, unit_price INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stock_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_id TEXT NOT NULL, delta REAL NOT NULL,
            note TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)
        c.executemany("INSERT OR IGNORE INTO ingredients VALUES(?,?,?,?,?)", INGREDIENTS)
        for ident, name, category, desc, price, image, recipe in MENU:
            c.execute("INSERT OR IGNORE INTO menu VALUES(?,?,?,?,?,?)", (ident, name, category, desc, price, image))
            c.executemany("INSERT OR IGNORE INTO recipes VALUES(?,?,?)",
                          [(ident, ingredient, amount) for ingredient, amount in recipe.items()])

init_db()

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/order")
def order_app():
    return FileResponse(ROOT / "static" / "order.html")

@app.get("/staff")
def staff_app():
    return FileResponse(ROOT / "static" / "staff.html")

@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT / "static" / "manifest.webmanifest", media_type="application/manifest+json")

@app.get("/sw.js")
def service_worker():
    return FileResponse(ROOT / "static" / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})

@app.get("/health")
def health():
    return {"status": "ok", "mode": "fictional-hospitality-demo"}

@app.get("/api/menu")
def menu():
    with connection() as c:
        rows = c.execute("""
        SELECT m.*, NOT EXISTS(
            SELECT 1 FROM recipes r JOIN ingredients i ON i.id = r.ingredient_id
            WHERE r.menu_id = m.id AND i.quantity + 0.000001 < r.amount
        ) AS available FROM menu m ORDER BY
        CASE m.category WHEN 'Breakfast' THEN 1 WHEN 'Mains' THEN 2
        WHEN 'Desserts' THEN 3 WHEN 'Cold drinks' THEN 4 ELSE 5 END, m.rowid
        """).fetchall()
    return [dict(r) for r in rows]

class CartItem(BaseModel):
    id: str = Field(min_length=2, max_length=60)
    quantity: int = Field(ge=1, le=10)

class NewOrder(BaseModel):
    guest_name: str = Field(min_length=2, max_length=80)
    delivery_type: str = Field(min_length=4, max_length=10)
    location: str = Field(min_length=1, max_length=30)
    note: str = Field(default="", max_length=240)
    items: list[CartItem] = Field(min_length=1, max_length=25)

@app.post("/api/orders", status_code=201)
def create_order(payload: NewOrder):
    if len(payload.guest_name.strip()) < 2:
        raise HTTPException(422, "Guest name is required")
    if payload.delivery_type not in ("room", "table", "pickup"):
        raise HTTPException(422, "Choose room, table or pickup")
    if not re.fullmatch(r"[\w -]{1,30}", payload.location, flags=re.UNICODE):
        raise HTTPException(422, "Invalid room or table reference")
    quantities: dict[str, int] = defaultdict(int)
    for item in payload.items:
        quantities[item.id] += item.quantity
    if sum(quantities.values()) > 25 or any(q > 10 for q in quantities.values()):
        raise HTTPException(422, "Maximum 10 of each item and 25 items per order")
    with connection() as c:
        try:
            c.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in quantities)
            products = c.execute("SELECT * FROM menu WHERE id IN (" + placeholders + ")",
                                 tuple(quantities)).fetchall()
            if len(products) != len(quantities):
                raise HTTPException(422, "Invalid menu item")
            needed: dict[str, float] = defaultdict(float)
            for row in c.execute("SELECT menu_id,ingredient_id,amount FROM recipes WHERE menu_id IN (" +
                                 placeholders + ")", tuple(quantities)):
                needed[row["ingredient_id"]] += row["amount"] * quantities[row["menu_id"]]
            for ident, required in needed.items():
                stock = c.execute("SELECT quantity FROM ingredients WHERE id=?", (ident,)).fetchone()
                if stock is None or stock["quantity"] + 0.000001 < required:
                    raise HTTPException(409, "Insufficient stock. Refresh the menu and try again.")
            total = sum(p["price"] * quantities[p["id"]] for p in products)
            code = secrets.token_urlsafe(9)
            cursor = c.execute(
                "INSERT INTO orders(code,guest_name,delivery_type,location,note,total,created_at) VALUES(?,?,?,?,?,?,?)",
                (code, payload.guest_name.strip(), payload.delivery_type, payload.location.strip(),
                 payload.note.strip(), total, utcnow()))
            for p in products:
                c.execute("INSERT INTO order_lines(order_id,menu_id,name,quantity,unit_price) VALUES(?,?,?,?,?)",
                          (cursor.lastrowid, p["id"], p["name"], quantities[p["id"]], p["price"]))
            for ident, amount in needed.items():
                c.execute("UPDATE ingredients SET quantity=ROUND(quantity-?, 4) WHERE id=?",
                          (amount, ident))
                c.execute("INSERT INTO stock_events(ingredient_id,delta,note,created_at) VALUES(?,?,?,?)",
                          (ident, -amount, "Order " + code, utcnow()))
            c.commit()
        except Exception:
            c.rollback()
            raise
    return {"code": code, "total": total, "status": "received", "message": "Demo order received; no actual kitchen or payment is connected."}

@app.get("/api/orders/{code}")
def track_order(code: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,30}", code):
        raise HTTPException(404, "Order not found")
    with connection() as c:
        row = c.execute("SELECT code,status,total,delivery_type,location,created_at FROM orders WHERE code=?",
                        (code,)).fetchone()
        if not row:
            raise HTTPException(404, "Order not found")
        lines = c.execute("SELECT name,quantity,unit_price FROM order_lines WHERE order_id=(SELECT id FROM orders WHERE code=?)",
                          (code,)).fetchall()
    return dict(row) | {"items": [dict(x) for x in lines]}

def sign_session():
    stamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(12)
    value = stamp + "." + nonce
    signature = hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()
    return value + "." + signature

def authenticated(request: Request):
    token = request.cookies.get(TOKEN_NAME, "")
    try:
        stamp, nonce, signature = token.split(".")
        signed = stamp + "." + nonce
        if abs(time.time() - int(stamp)) > MAX_AGE:
            return False
        return hmac.compare_digest(hmac.new(SECRET, signed.encode(), hashlib.sha256).hexdigest(), signature)
    except (ValueError, TypeError):
        return False

def require_staff(request: Request):
    if not authenticated(request):
        raise HTTPException(401, "Staff login required")
    origin = request.headers.get("origin")
    if request.method != "GET" and origin and urlsplit(origin).hostname != request.url.hostname:
        raise HTTPException(403, "Invalid request origin")

class Login(BaseModel):
    password: str = Field(min_length=1, max_length=200)

@app.post("/api/staff/login")
def login(payload: Login, request: Request):
    if not ADMIN_PASSWORD:
        raise HTTPException(503, "Staff login not configured on this deployment")
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = [x for x in _attempts.get(ip, []) if now - x < 300]
    if len(recent) >= 8:
        raise HTTPException(429, "Too many login attempts. Try again later.")
    if not hmac.compare_digest(payload.password.encode(), ADMIN_PASSWORD.encode()):
        _attempts[ip] = recent + [now]
        raise HTTPException(401, "Incorrect staff password")
    _attempts.pop(ip, None)
    response = JSONResponse({"authenticated": True})
    response.set_cookie(TOKEN_NAME, sign_session(), max_age=MAX_AGE, httponly=True,
                        secure=COOKIE_SECURE, samesite="strict", path="/")
    return response

@app.post("/api/staff/logout")
def logout(request: Request):
    require_staff(request)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(TOKEN_NAME, path="/")
    return response

@app.get("/api/staff/snapshot")
def staff_snapshot(request: Request):
    require_staff(request)
    with connection() as c:
        orders = [dict(r) for r in c.execute(
            "SELECT id,code,guest_name,delivery_type,location,note,status,total,created_at FROM orders ORDER BY id DESC LIMIT 100")]
        for o in orders:
            o["items"] = [dict(x) for x in c.execute(
                "SELECT name,quantity FROM order_lines WHERE order_id=?", (o["id"],))]
        stock = [dict(r) for r in c.execute(
            "SELECT id,name,unit,ROUND(quantity,2) AS quantity,minimum FROM ingredients ORDER BY name")]
        stats = c.execute("SELECT COUNT(*) AS count, COALESCE(SUM(total),0) AS revenue, SUM(CASE WHEN status IN ('received','preparing') THEN 1 ELSE 0 END) AS active FROM orders").fetchone()
    return {"orders": orders, "stock": stock,
            "stats": {"orders": stats["count"], "revenue": stats["revenue"],
                      "active": stats["active"] or 0,
                      "low_stock": sum(i["quantity"] <= i["minimum"] for i in stock)}}

class UpdateStatus(BaseModel):
    status: str

@app.post("/api/staff/orders/{order_id}/status")
def update_status(order_id: int, payload: UpdateStatus, request: Request):
    require_staff(request)
    transitions = {"received": "preparing", "preparing": "ready", "ready": "served"}
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown order")
        if transitions.get(row["status"]) != payload.status:
            raise HTTPException(409, "Invalid status transition")
        c.execute("UPDATE orders SET status=? WHERE id=?", (payload.status, order_id))
    return {"id": order_id, "status": payload.status}

class StockAdjustment(BaseModel):
    delta: float = Field(ge=-1000, le=1000)
    reason: str = Field(min_length=3, max_length=100)

@app.post("/api/staff/inventory/{ingredient_id}")
def adjust_stock(ingredient_id: str, payload: StockAdjustment, request: Request):
    require_staff(request)
    if not payload.delta or payload.delta != payload.delta:
        raise HTTPException(422, "Adjustment must be a finite nonzero number")
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT quantity FROM ingredients WHERE id=?", (ingredient_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown ingredient")
        new = round(row["quantity"] + payload.delta, 4)
        if new < 0:
            raise HTTPException(409, "Stock cannot go below zero")
        c.execute("UPDATE ingredients SET quantity=? WHERE id=?", (new, ingredient_id))
        c.execute("INSERT INTO stock_events(ingredient_id,delta,note,created_at) VALUES(?,?,?,?)",
                  (ingredient_id, payload.delta, payload.reason.strip(), utcnow()))
    return {"id": ingredient_id, "quantity": new}
