"""Maison Sanaa v2 — persistent hotel demo, per-staff permissions and M-Pesa STK workflow.

M-Pesa defaults to an explicitly simulated experience; real requests require separately
configured Safaricom Daraja sandbox/production credentials and callback secret.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import (Boolean, Column, Float, ForeignKey, Integer, MetaData,
                        String, Table, Text, create_engine, func, insert, select, update)
from sqlalchemy.exc import IntegrityError

from hospitality.catalog import INGREDIENTS, MENU

ROOT = Path(__file__).resolve().parent
url = os.getenv("DATABASE_URL") or "sqlite:///" + os.getenv("HOSPITALITY_DB", "/tmp/maison_sanaa_demo.sqlite3")
if url.startswith("postgres://"):
    url = "postgresql://" + url[len("postgres://"):]
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
if url.startswith("sqlite:///"):
    Path(url.removeprefix("sqlite:///")).expanduser().parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread":False} if url.startswith("sqlite:") else {})
schema = MetaData()
ingredients = Table("ingredients", schema,
    Column("id", String(70), primary_key=True), Column("name", String(140), nullable=False),
    Column("unit", String(30), nullable=False), Column("quantity", Float, nullable=False),
    Column("minimum", Float, nullable=False))
menu_items = Table("menu", schema,
    Column("id", String(70), primary_key=True), Column("name", String(140), nullable=False),
    Column("category", String(60), nullable=False), Column("description", Text, nullable=False),
    Column("price", Integer, nullable=False), Column("image", Text, nullable=False))
recipes = Table("recipes", schema,
    Column("menu_id", String(70), ForeignKey("menu.id"), primary_key=True),
    Column("ingredient_id", String(70), ForeignKey("ingredients.id"), primary_key=True),
    Column("amount", Float, nullable=False))
orders = Table("orders", schema,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(48), unique=True, nullable=False),
    Column("guest_name", String(80), nullable=False),
    Column("delivery_type", String(10), nullable=False),
    Column("location", String(30), nullable=False), Column("note", Text, nullable=False, default=""),
    Column("status", String(20), nullable=False, default="received"),
    Column("payment_status", String(24), nullable=False, default="awaiting_payment"),
    Column("total", Integer, nullable=False),
    Column("created_at", String(40), nullable=False))
order_lines = Table("order_lines", schema,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("order_id", Integer, ForeignKey("orders.id"), nullable=False),
    Column("menu_id", String(70), nullable=False),
    Column("name", String(140), nullable=False),
    Column("quantity", Integer, nullable=False), Column("unit_price", Integer, nullable=False))
stock_events = Table("stock_events", schema,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ingredient_id", String(70), nullable=False), Column("delta", Float, nullable=False),
    Column("note", String(200), nullable=False), Column("created_at", String(40), nullable=False))
staff_users = Table("staff_users", schema,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(80), unique=True, nullable=False),
    Column("password_hash", String(180), nullable=False),
    Column("role", String(20), nullable=False), Column("active", Boolean, nullable=False, default=True),
    Column("created_at", String(40), nullable=False))
payments = Table("payments", schema,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("order_id", Integer, ForeignKey("orders.id"), nullable=False),
    Column("method", String(30), nullable=False, default="mpesa"),
    Column("mode", String(16), nullable=False),
    Column("status", String(28), nullable=False),
    Column("phone_last4", String(4), nullable=False),
    Column("checkout_id", String(160), unique=True, nullable=True),
    Column("merchant_id", String(160), nullable=True),
    Column("receipt", String(80), nullable=True),
    Column("created_at", String(40), nullable=False))
BOOTSTRAP_USER = os.getenv("HOSPITALITY_ADMIN_USERNAME", "manager").strip().lower()
BOOTSTRAP_PASSWORD = os.getenv("HOSPITALITY_ADMIN_PASSWORD", "")
SECRET = (os.getenv("HOSPITALITY_SECRET") or secrets.token_urlsafe(40)).encode()
COOKIE_SECURE = os.getenv("HOSPITALITY_COOKIE_SECURE", "1") != "0"
MPESA_MODE = os.getenv("MPESA_MODE", "demo").strip().lower()
if MPESA_MODE not in ("demo", "sandbox", "production"):
    raise RuntimeError("MPESA_MODE must be demo, sandbox, or production")
MPESA_CALLBACK_TOKEN = os.getenv("MPESA_CALLBACK_TOKEN", "")
COOKIE = "maison_staff_v2"
SESSION_AGE = 8 * 3600
_attempts: dict[str, list[float]] = {}
_payment_attempts: dict[str, list[float]] = {}

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(20)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 340_000)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()

def check_password(password, stored):
    try:
        salt64, hash64 = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt64), 340_000)
        return hmac.compare_digest(actual, base64.b64decode(hash64))
    except (ValueError, TypeError):
        return False

def initialize():
    schema.create_all(engine)
    # Add payment status for an existing local SQLite v1 demo DB, if any.
    if url.startswith("sqlite:"):
        from sqlalchemy import text
        with engine.begin() as conn:
            columns = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(orders)")}
            if "payment_status" not in columns:
                conn.execute(text("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(24) NOT NULL DEFAULT 'awaiting_payment'"))
    with engine.begin() as conn:
        for ident, name, unit, quantity, minimum in INGREDIENTS:
            if not conn.execute(select(ingredients.c.id).where(ingredients.c.id == ident)).first():
                conn.execute(insert(ingredients).values(id=ident, name=name, unit=unit, quantity=quantity, minimum=minimum))
        for ident, name, category, description, price, image, recipe in MENU:
            if not conn.execute(select(menu_items.c.id).where(menu_items.c.id == ident)).first():
                conn.execute(insert(menu_items).values(id=ident, name=name, category=category, description=description, price=price, image=image))
            for ing, amount in recipe.items():
                if not conn.execute(select(recipes.c.ingredient_id).where(recipes.c.menu_id == ident, recipes.c.ingredient_id == ing)).first():
                    conn.execute(insert(recipes).values(menu_id=ident, ingredient_id=ing, amount=amount))
        if BOOTSTRAP_PASSWORD and not conn.execute(select(staff_users.c.id).limit(1)).first():
            conn.execute(insert(staff_users).values(username=BOOTSTRAP_USER, password_hash=hash_password(BOOTSTRAP_PASSWORD), role="manager", active=True, created_at=now()))

initialize()
app = FastAPI(title="Maison Sanaa Hospitality", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets", StaticFiles(directory=ROOT / "static"), name="assets")

@app.middleware("http")
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/")
def home(): return FileResponse(ROOT / "static/index.html")
@app.get("/order")
def order_page(): return FileResponse(ROOT / "static/order.html")
@app.get("/staff")
def staff_page(): return FileResponse(ROOT / "static/staff.html")
@app.get("/manifest.webmanifest")
def manifest(): return FileResponse(ROOT / "static/manifest.webmanifest", media_type="application/manifest+json")
@app.get("/sw.js")
def sw(): return FileResponse(ROOT / "static/sw.js", media_type="application/javascript", headers={"Service-Worker-Allowed":"/"})
@app.get("/health")
def health(): return {"status":"ok", "database":"postgresql" if url.startswith("postgresql+") else "sqlite", "mpesa_mode":MPESA_MODE}

def rows(result): return [dict(row) for row in result.mappings().all()]

@app.get("/api/menu")
def menu():
    with engine.connect() as conn:
        stock = {r["id"]:r["quantity"] for r in rows(conn.execute(select(ingredients)))}
        recipe_rows = rows(conn.execute(select(recipes)))
        product_rows = rows(conn.execute(select(menu_items)))
    mapping: dict[str, list[dict]] = defaultdict(list)
    for line in recipe_rows: mapping[line["menu_id"]].append(line)
    category_order = {"Breakfast":0,"Mains":1,"Desserts":2,"Cold drinks":3,"Hot drinks":4}
    return [dict(product, available=int(all(stock.get(x["ingredient_id"],0)+1e-7>=x["amount"] for x in mapping[product["id"]])))
            for product in sorted(product_rows, key=lambda p:(category_order.get(p["category"],9),next((n for n,m in enumerate(MENU) if m[0]==p["id"]),99)))]

class CartItem(BaseModel):
    id: str = Field(min_length=2,max_length=70)
    quantity: int = Field(ge=1,le=10)
class NewOrder(BaseModel):
    guest_name: str = Field(min_length=2,max_length=80)
    delivery_type: str = Field(min_length=4,max_length=10)
    location: str = Field(min_length=1,max_length=30)
    note: str = Field(default="",max_length=240)
    items: list[CartItem] = Field(min_length=1,max_length=25)

@app.post("/api/orders",status_code=201)
def create_order(payload:NewOrder):
    if len(payload.guest_name.strip()) < 2: raise HTTPException(422,"Guest name is required")
    if payload.delivery_type not in ("room","table","pickup"): raise HTTPException(422,"Invalid service type")
    if not re.fullmatch(r"[\w -]{1,30}",payload.location,re.UNICODE): raise HTTPException(422,"Invalid room or table reference")
    quantities = defaultdict(int)
    for item in payload.items: quantities[item.id]+=item.quantity
    if sum(quantities.values())>25 or any(q>10 for q in quantities.values()): raise HTTPException(422,"Basket exceeds limits")
    with engine.begin() as conn:
        product_rows = rows(conn.execute(select(menu_items).where(menu_items.c.id.in_(list(quantities)))))
        if len(product_rows)!=len(quantities): raise HTTPException(422,"Invalid menu item")
        needed = defaultdict(float)
        for line in rows(conn.execute(select(recipes).where(recipes.c.menu_id.in_(list(quantities))))):
            needed[line["ingredient_id"]] += line["amount"] * quantities[line["menu_id"]]
        # Lock inventory rows consistently across competing orders on PostgreSQL.
        stock_query = select(ingredients).where(ingredients.c.id.in_(sorted(needed))).order_by(ingredients.c.id)
        if url.startswith("postgresql+"): stock_query = stock_query.with_for_update()
        stock = {i["id"]:i for i in rows(conn.execute(stock_query))}
        for ident,amount in needed.items():
            if ident not in stock or stock[ident]["quantity"] + 1e-7 < amount:
                raise HTTPException(409,"Insufficient stock. Refresh the menu and try again.")
        total = sum(p["price"]*quantities[p["id"]] for p in product_rows)
        code=secrets.token_urlsafe(12)
        order_id=conn.execute(insert(orders).values(code=code,guest_name=payload.guest_name.strip(),
            delivery_type=payload.delivery_type,location=payload.location.strip(),note=payload.note.strip(),
            status="received",payment_status="awaiting_payment",total=total,created_at=now())).inserted_primary_key[0]
        for p in product_rows:
            conn.execute(insert(order_lines).values(order_id=order_id,menu_id=p["id"],name=p["name"],
                           quantity=quantities[p["id"]],unit_price=p["price"]))
        for ident,amount in needed.items():
            conn.execute(update(ingredients).where(ingredients.c.id==ident).values(quantity=round(stock[ident]["quantity"]-amount,4)))
            conn.execute(insert(stock_events).values(ingredient_id=ident,delta=-amount,note="Reserved for order "+code,created_at=now()))
    return {"code":code,"total":total,"status":"received","payment_status":"awaiting_payment",
            "message":"Demo order created. Complete the M-Pesa checkout flow to continue."}

@app.get("/api/orders/{code}")
def track_order(code:str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,45}",code): raise HTTPException(404,"Order not found")
    with engine.connect() as conn:
        order=conn.execute(select(orders).where(orders.c.code==code)).mappings().first()
        if not order: raise HTTPException(404,"Order not found")
        lines=rows(conn.execute(select(order_lines.c.name,order_lines.c.quantity,order_lines.c.unit_price)
                                .where(order_lines.c.order_id==order["id"])))
    return {k:order[k] for k in ("code","status","payment_status","total","delivery_type","location","created_at")} | {"items":lines}

def sign_session(uid:int):
    token=str(uid)+"."+str(int(time.time()))+"."+secrets.token_urlsafe(10)
    sig=hmac.new(SECRET,token.encode(),"sha256").hexdigest()
    return token+"."+sig

def current_user(request:Request):
    try:
        raw=request.cookies.get(COOKIE,"")
        uid,stamp,nonce,sig=raw.split(".",3)
        signed=".".join((uid,stamp,nonce))
        if not hmac.compare_digest(sig,hmac.new(SECRET,signed.encode(),"sha256").hexdigest()): return None
        age=time.time()-int(stamp)
        if age < 0 or age>SESSION_AGE: return None
        with engine.connect() as conn:
            user=conn.execute(select(staff_users).where(staff_users.c.id==int(uid),staff_users.c.active==True)).mappings().first()
        return dict(user) if user else None
    except (ValueError,TypeError): return None

def require_staff(request:Request, role=None):
    user=current_user(request)
    if not user: raise HTTPException(401,"Staff login required")
    if role and user["role"] not in role: raise HTTPException(403,"Insufficient staff permission")
    if request.method not in ("GET","HEAD"):
        origin=request.headers.get("origin")
        if origin and urlsplit(origin).hostname != request.url.hostname:
            raise HTTPException(403,"Invalid request origin")
        # Strict SameSite cookie protects cross-site requests; reject explicit cross-site Fetch Metadata.
        if request.headers.get("sec-fetch-site")=="cross-site":
            raise HTTPException(403,"Cross-site request denied")
    return user

def throttle(bucket:dict, ip:str, limit:int, period=300):
    current=time.monotonic()
    recent=[t for t in bucket.get(ip,[]) if current-t<period]
    if len(recent)>=limit: raise HTTPException(429,"Too many requests; try again later")
    bucket[ip]=recent+[current]

class Login(BaseModel):
    username: str = Field(default="manager",min_length=2,max_length=80)
    password: str = Field(min_length=1,max_length=200)

@app.post("/api/staff/login")
def login(payload:Login,request:Request):
    throttle(_attempts,request.client.host if request.client else "unknown",8)
    with engine.connect() as conn:
        user=conn.execute(select(staff_users).where(staff_users.c.username==payload.username.strip().lower())).mappings().first()
    if not user or not user["active"] or not check_password(payload.password,user["password_hash"]):
        raise HTTPException(401,"Incorrect username or password")
    response=JSONResponse({"authenticated":True,"username":user["username"],"role":user["role"]})
    response.set_cookie(COOKIE,sign_session(user["id"]),max_age=SESSION_AGE,httponly=True,
                        secure=COOKIE_SECURE,samesite="strict",path="/")
    return response

@app.post("/api/staff/logout")
def logout(request:Request):
    require_staff(request)
    response=JSONResponse({"authenticated":False})
    response.delete_cookie(COOKIE,path="/")
    return response

@app.get("/api/staff/snapshot")
def snapshot(request:Request):
    user=require_staff(request)
    with engine.connect() as conn:
        all_orders=rows(conn.execute(select(orders).order_by(orders.c.id.desc()).limit(100)))
        for entry in all_orders:
            entry["items"]=rows(conn.execute(select(order_lines.c.name,order_lines.c.quantity)
                .where(order_lines.c.order_id==entry["id"])))
        stock=rows(conn.execute(select(ingredients).order_by(ingredients.c.name)))
        stats=conn.execute(select(func.count(orders.c.id).label("count"),
                func.coalesce(func.sum(orders.c.total),0).label("revenue"))).mappings().one()
    return {"user":{"id":user["id"],"username":user["username"],"role":user["role"]},
            "orders":all_orders,"stock":[dict(i,quantity=round(i["quantity"],2)) for i in stock],
            "stats":{"orders":stats["count"],"revenue":stats["revenue"],
                     "active":sum(o["status"] in ("received","preparing") for o in all_orders),
                     "low_stock":sum(i["quantity"]<=i["minimum"] for i in stock)}}

class UpdateStatus(BaseModel):
    status:str
@app.post("/api/staff/orders/{order_id}/status")
def order_status(order_id:int,payload:UpdateStatus,request:Request):
    require_staff(request,role=("manager","kitchen","server"))
    transitions={"received":"preparing","preparing":"ready","ready":"served"}
    with engine.begin() as conn:
        query=select(orders).where(orders.c.id==order_id)
        if url.startswith("postgresql+"):query=query.with_for_update()
        row=conn.execute(query).mappings().first()
        if not row:raise HTTPException(404,"Unknown order")
        if transitions.get(row["status"])!=payload.status:raise HTTPException(409,"Invalid status transition")
        if MPESA_MODE!="demo" and row["payment_status"]!="paid":
            raise HTTPException(409,"Payment not verified for this order")
        conn.execute(update(orders).where(orders.c.id==order_id).values(status=payload.status))
    return {"id":order_id,"status":payload.status}

class StockAdjustment(BaseModel):
    delta:float = Field(ge=-1000,le=1000)
    reason:str = Field(min_length=3,max_length=100)
@app.post("/api/staff/inventory/{ingredient_id}")
def adjust_stock(ingredient_id:str,payload:StockAdjustment,request:Request):
    require_staff(request,role=("manager",))
    if not payload.delta or payload.delta!=payload.delta:raise HTTPException(422,"Adjustment must be finite and nonzero")
    with engine.begin() as conn:
        query=select(ingredients).where(ingredients.c.id==ingredient_id)
        if url.startswith("postgresql+"): query=query.with_for_update()
        item=conn.execute(query).mappings().first()
        if not item: raise HTTPException(404,"Unknown ingredient")
        remaining=round(item["quantity"]+payload.delta,4)
        if remaining < 0: raise HTTPException(409,"Stock cannot go below zero")
        conn.execute(update(ingredients).where(ingredients.c.id==ingredient_id).values(quantity=remaining))
        conn.execute(insert(stock_events).values(ingredient_id=ingredient_id,delta=payload.delta,
                    note=payload.reason.strip(),created_at=now()))
    return {"id":ingredient_id,"quantity":remaining}

class NewStaff(BaseModel):
    username:str = Field(min_length=3,max_length=80)
    password:str = Field(min_length=12,max_length=128)
    role:str = Field(default="kitchen")
@app.get("/api/staff/users")
def list_users(request:Request):
    require_staff(request,role=("manager",))
    with engine.connect() as conn:
        return rows(conn.execute(select(staff_users.c.id,staff_users.c.username,staff_users.c.role,staff_users.c.active,staff_users.c.created_at).order_by(staff_users.c.id)))

@app.post("/api/staff/users",status_code=201)
def add_staff(payload:NewStaff,request:Request):
    require_staff(request,role=("manager",))
    username=payload.username.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,80}",username):raise HTTPException(422,"Username may contain letters, digits, ., _, -")
    if payload.role not in ("manager","kitchen","server"):raise HTTPException(422,"Unknown role")
    try:
        with engine.begin() as conn:
            new_id=conn.execute(insert(staff_users).values(username=username,password_hash=hash_password(payload.password),
                role=payload.role,active=True,created_at=now())).inserted_primary_key[0]
    except IntegrityError:
        raise HTTPException(409,"Username already exists")
    return {"id":new_id,"username":username,"role":payload.role}

class ToggleStaff(BaseModel):
    active:bool
@app.post("/api/staff/users/{user_id}/active")
def toggle_staff(user_id:int,payload:ToggleStaff,request:Request):
    manager=require_staff(request,role=("manager",))
    if user_id==manager["id"] and not payload.active:raise HTTPException(409,"You cannot deactivate your own account")
    with engine.begin() as conn:
        row=conn.execute(select(staff_users.c.id).where(staff_users.c.id==user_id)).first()
        if not row:raise HTTPException(404,"Staff member not found")
        conn.execute(update(staff_users).where(staff_users.c.id==user_id).values(active=payload.active))
    return {"id":user_id,"active":payload.active}

class ChangePassword(BaseModel):
    current_password:str = Field(min_length=1,max_length=128)
    new_password:str = Field(min_length=12,max_length=128)
@app.post("/api/staff/password")
def change_password(payload:ChangePassword,request:Request):
    user=require_staff(request)
    if not check_password(payload.current_password,user["password_hash"]):
        raise HTTPException(401,"Current password incorrect")
    with engine.begin() as conn:
        conn.execute(update(staff_users).where(staff_users.c.id==user["id"]).values(password_hash=hash_password(payload.new_password)))
    return {"changed":True}

def normalized_phone(phone:str):
    cleaned=re.sub(r"[\s-]","",phone)
    if cleaned.startswith("+254"):cleaned=cleaned[1:]
    if cleaned.startswith("0"):cleaned="254"+cleaned[1:]
    if not re.fullmatch(r"254[17]\d{8}",cleaned):raise HTTPException(422,"Enter a valid Kenyan M-Pesa number (07/01...)")
    return cleaned

def daraja_api(path:str,payload:dict|None=None):
    if MPESA_MODE=="demo":raise HTTPException(503,"Real M-Pesa credentials not configured")
    key=os.getenv("MPESA_CONSUMER_KEY","")
    secret=os.getenv("MPESA_CONSUMER_SECRET","")
    if not key or not secret:raise HTTPException(503,"Missing Daraja credentials")
    base="https://api.safaricom.co.ke" if MPESA_MODE=="production" else "https://sandbox.safaricom.co.ke"
    try:
        with httpx.Client(timeout=12.0) as client:
            oauth=client.get(base+"/oauth/v1/generate",params={"grant_type":"client_credentials"},auth=(key,secret))
            oauth.raise_for_status()
            bearer=oauth.json().get("access_token")
            if not bearer:raise ValueError("Missing OAuth token")
            answer=client.post(base+path,json=payload,headers={"Authorization":"Bearer "+bearer})
            answer.raise_for_status()
            return answer.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(502,"M-Pesa provider unavailable; please try again") from exc

def daraja_password():
    shortcode=os.getenv("MPESA_SHORTCODE","")
    passkey=os.getenv("MPESA_PASSKEY","")
    callback=os.getenv("MPESA_CALLBACK_URL","")
    if not all([shortcode,passkey,callback,MPESA_CALLBACK_TOKEN]):
        raise HTTPException(503,"M-Pesa merchant configuration incomplete")
    if not callback.startswith("https://"):raise HTTPException(503,"Callback must be HTTPS")
    stamp=datetime.now().strftime("%Y%m%d%H%M%S")
    pwd=base64.b64encode((shortcode+passkey+stamp).encode()).decode()
    return shortcode,stamp,pwd,callback.rstrip("/")+"/"+MPESA_CALLBACK_TOKEN

class InitiatePayment(BaseModel):
    code:str = Field(min_length=12,max_length=45)
    phone:str = Field(min_length=9,max_length=24)

@app.get("/api/payments/config")
def payment_configuration():
    configured = MPESA_MODE!="demo" and all(os.getenv(k) for k in (
        "MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET", "MPESA_SHORTCODE",
        "MPESA_PASSKEY", "MPESA_CALLBACK_URL", "MPESA_CALLBACK_TOKEN"))
    return {"mode":MPESA_MODE,"real_prompt_available":bool(configured)}

@app.post("/api/payments/mpesa/initiate")
def initiate_mpesa(payload:InitiatePayment,request:Request):
    throttle(_payment_attempts,request.client.host if request.client else "unknown",12,600)
    phone=normalized_phone(payload.phone)
    with engine.begin() as conn:
        query=select(orders).where(orders.c.code==payload.code)
        if url.startswith("postgresql+"):query=query.with_for_update()
        order=conn.execute(query).mappings().first()
        if not order:raise HTTPException(404,"Order not found")
        if order["payment_status"] in ("paid","demo_paid"):
            raise HTTPException(409,"Order payment already completed")
        count=conn.execute(select(func.count(payments.c.id)).where(payments.c.order_id==order["id"])).scalar_one()
        if count>=3:raise HTTPException(429,"Maximum payment attempts reached for this order")
        # Payment request state stored before contacting provider; final receipt is asynchronous.
        payment_id=conn.execute(insert(payments).values(order_id=order["id"],mode=MPESA_MODE,method="mpesa",
            status="initiating",phone_last4=phone[-4:],created_at=now())).inserted_primary_key[0]
        conn.execute(update(orders).where(orders.c.id==order["id"]).values(payment_status="pending"))
        total=order["total"]
    if MPESA_MODE=="demo":
        with engine.begin() as conn:
            conn.execute(update(payments).where(payments.c.id==payment_id).values(status="demo_pending"))
        return {"mode":"demo","payment_id":payment_id,"status":"demo_pending","total":total,
                "message":"This is an on-screen M-Pesa demonstration. NO prompt was sent to the phone and NO money was collected."}
    try:
        shortcode,stamp,password,callback=daraja_password()
        answer=daraja_api("/mpesa/stkpush/v1/processrequest",{
            "BusinessShortCode":shortcode,"Password":password,"Timestamp":stamp,
            "TransactionType":"CustomerPayBillOnline","Amount":total,
            "PartyA":phone,"PartyB":shortcode,"PhoneNumber":phone,
            "CallBackURL":callback,"AccountReference":payload.code[:12],
            "TransactionDesc":"Maison Sanaa order"
        })
        if str(answer.get("ResponseCode"))!="0" or not answer.get("CheckoutRequestID"):
            raise HTTPException(502,"M-Pesa declined the prompt request")
        with engine.begin() as conn:
            conn.execute(update(payments).where(payments.c.id==payment_id).values(
                status="pending",checkout_id=answer["CheckoutRequestID"],merchant_id=answer.get("MerchantRequestID")))
        return {"mode":MPESA_MODE,"payment_id":payment_id,"status":"pending","total":total,
                "message":"M-Pesa request submitted. Check your phone for an STK PIN prompt; payment is not confirmed yet."}
    except HTTPException:
        with engine.begin() as conn:
            conn.execute(update(payments).where(payments.c.id==payment_id).values(status="failed"))
            conn.execute(update(orders).where(orders.c.id==order["id"]).values(payment_status="failed"))
        raise

class ConfirmDemo(BaseModel):
    code:str = Field(min_length=12,max_length=45)
    payment_id:int
@app.post("/api/payments/mpesa/confirm-demo")
def confirm_demo(payload:ConfirmDemo):
    if MPESA_MODE!="demo":raise HTTPException(404,"Demo confirmation disabled")
    with engine.begin() as conn:
        order=conn.execute(select(orders).where(orders.c.code==payload.code)).mappings().first()
        if not order:raise HTTPException(404,"Order not found")
        target=conn.execute(select(payments).where(payments.c.id==payload.payment_id,payments.c.order_id==order["id"])).mappings().first()
        if not target or target["status"]!="demo_pending":raise HTTPException(409,"No pending demo payment")
        conn.execute(update(payments).where(payments.c.id==payload.payment_id).values(status="demo_paid"))
        conn.execute(update(orders).where(orders.c.id==order["id"]).values(payment_status="demo_paid"))
    return {"payment_status":"demo_paid","message":"Demo payment simulated. No actual M-Pesa transaction occurred."}

@app.post("/api/payments/mpesa/callback/{token}")
async def mpesa_callback(token:str,request:Request):
    if MPESA_MODE=="demo" or not MPESA_CALLBACK_TOKEN or not secrets.compare_digest(token,MPESA_CALLBACK_TOKEN):
        raise HTTPException(404,"Not found")
    try:
        payload=await request.json()
        result=payload["Body"]["stkCallback"]
        checkout=str(result["CheckoutRequestID"])
        code=int(result["ResultCode"])
    except (KeyError,ValueError,TypeError):
        raise HTTPException(422,"Invalid M-Pesa callback")
    with engine.begin() as conn:
        pay=conn.execute(select(payments).where(payments.c.checkout_id==checkout)).mappings().first()
        if not pay:return {"ResultCode":0,"ResultDesc":"Acknowledged"}
        if pay["status"] in ("paid","failed"):return {"ResultCode":0,"ResultDesc":"Already processed"}
        order=conn.execute(select(orders).where(orders.c.id==pay["order_id"])).mappings().first()
        if code!=0:
            conn.execute(update(payments).where(payments.c.id==pay["id"]).values(status="failed"))
            conn.execute(update(orders).where(orders.c.id==order["id"]).values(payment_status="failed"))
            return {"ResultCode":0,"ResultDesc":"Failure recorded"}
    # Reject any positive-result callback that cannot be independently confirmed via Daraja query.
    try:
        shortcode,stamp,password,_=daraja_password()
        query=daraja_api("/mpesa/stkpushquery/v1/query",{
            "BusinessShortCode":shortcode,"Password":password,
            "Timestamp":stamp,"CheckoutRequestID":checkout})
        verified=str(query.get("ResultCode"))=="0"
    except HTTPException:
        verified=False
    metadata=result.get("CallbackMetadata",{}).get("Item",[]) or []
    values={str(i.get("Name")):i.get("Value") for i in metadata if isinstance(i,dict)}
    try:
        amount_matches=Decimal(str(values.get("Amount"))) == Decimal(str(order["total"]))
    except (InvalidOperation, TypeError):
        amount_matches=False
    receipt=str(values.get("MpesaReceiptNumber","")).strip()
    if not verified or not amount_matches or not receipt:
        # Leave payment pending until reconciled, rather than trusting unverified webhook data.
        return {"ResultCode":0,"ResultDesc":"Pending reconciliation"}
    with engine.begin() as conn:
        conn.execute(update(payments).where(payments.c.id==pay["id"]).values(status="paid",receipt=receipt))
        conn.execute(update(orders).where(orders.c.id==order["id"]).values(payment_status="paid"))
    return {"ResultCode":0,"ResultDesc":"Payment verified"}

@app.get("/api/payments/mpesa/status/{code}")
def payment_status(code:str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,45}",code):raise HTTPException(404,"Order not found")
    with engine.connect() as conn:
        row=conn.execute(select(orders.c.id,orders.c.payment_status).where(orders.c.code==code)).mappings().first()
        if not row:raise HTTPException(404,"Order not found")
        latest=conn.execute(select(payments.c.status,payments.c.mode).where(payments.c.order_id==row["id"]).order_by(payments.c.id.desc()).limit(1)).mappings().first()
    return {"payment_status":row["payment_status"],"payment_attempt":dict(latest) if latest else None}
