"""Tulia Care: fictional mobile self-check-in and receptionist queue dashboard.

Demo-only: intentionally excludes patient identifiers, contact details, medical records
and symptoms. Local SQLite is ephemeral on free Render; NOT clinical production software.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("CLINIC_DB", "/tmp/tulia_care_demo.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
ADMIN_PASSWORD = os.getenv("CLINIC_STAFF_PASSWORD", "")
SECRET = (os.getenv("CLINIC_SECRET") or secrets.token_urlsafe(40)).encode()
COOKIE_SECURE = os.getenv("CLINIC_COOKIE_SECURE", "1") != "0"
COOKIE = "tulia_staff"
SESSION_SECONDS = 8 * 60 * 60
ATTEMPTS: dict[str, list[float]] = defaultdict(list)
SERVICES = [
    {"id":"general","code":"GEN","name":"General consultation","icon":"heart-pulse","description":"Everyday health concerns and routine consultations.","tone":"mint"},
    {"id":"dental","code":"DEN","name":"Dental care","icon":"smile","description":"Check-ups, dental hygiene and assessment.","tone":"peach"},
    {"id":"pediatrics","code":"PED","name":"Paediatric care","icon":"baby","description":"Friendly care and consultations for children.","tone":"lilac"},
    {"id":"lab","code":"LAB","name":"Laboratory services","icon":"flask","description":"Sample collection and routine laboratory visits.","tone":"sky"},
    {"id":"physio","code":"PHY","name":"Physiotherapy","icon":"activity","description":"Mobility, rehabilitation and wellness visits.","tone":"sand"},
    {"id":"wellness","code":"WEL","name":"Wellness clinic","icon":"flower","description":"Preventive care and general wellness checks.","tone":"rose"},
]
SERVICE_MAP = {v["id"]:v for v in SERVICES}

@contextmanager
def db(write=False):
    con=sqlite3.connect(DB_PATH,timeout=15,check_same_thread=False)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    try:
        if write:con.execute("BEGIN IMMEDIATE")
        yield con
        if write:con.commit()
    except Exception:
        if write:con.rollback()
        raise
    finally:con.close()

def utc_now(): return datetime.now(timezone.utc).isoformat(timespec="microseconds")
def local_today(): return datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y-%m-%d")
def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def asdict(rows): return [dict(r) for r in rows]
def throttle(bucket:str,request:Request,limit:int,period:int=3600):
    addr=request.client.host if request.client else "unknown"
    key=bucket+":"+addr
    current=time.monotonic()
    ATTEMPTS[key]=[t for t in ATTEMPTS[key] if current-t<period]
    if len(ATTEMPTS[key])>=limit: raise HTTPException(429,"Too many demo requests. Please try again later.")
    ATTEMPTS[key].append(current)

def init_db():
    with db(write=True) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          public_id TEXT NOT NULL UNIQUE,
          token_hash TEXT NOT NULL UNIQUE,
          display_name TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visits(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_id INTEGER NOT NULL REFERENCES patients(id),
          service_id TEXT NOT NULL,
          ticket TEXT NOT NULL,
          day TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('prechecked','waiting','called','completed','missed')),
          created_at TEXT NOT NULL,
          arrived_at TEXT,
          updated_at TEXT NOT NULL,
          called_at TEXT,
          completed_at TEXT,
          UNIQUE(day,service_id,ticket)
        );
        CREATE INDEX IF NOT EXISTS idx_visits_day_service_status ON visits(day,service_id,status,id);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_visit_per_patient
          ON visits(patient_id) WHERE status IN ('prechecked','waiting','called');
        """)
        if os.getenv("CLINIC_SEED_DEMO","1")=="1" and not con.execute("SELECT 1 FROM patients LIMIT 1").fetchone():
            # Only invented aliases; no contact information or medical data.
            for name,service in [("Demo visitor A","general"),("Demo visitor B","general"),
                                 ("Demo visitor C","dental"),("Demo visitor D","lab"),
                                 ("Demo visitor E","pediatrics"),("Demo visitor F","physio")]:
                token=secrets.token_urlsafe(32)
                pid=con.execute("INSERT INTO patients(public_id,token_hash,display_name,created_at) VALUES(?,?,?,?)",
                    (secrets.token_hex(6),digest(token),name,utc_now())).lastrowid
                count=con.execute("SELECT COUNT(*) FROM visits WHERE day=? AND service_id=?",(local_today(),service)).fetchone()[0]
                ticket=SERVICE_MAP[service]["code"]+"-"+str(count+1).zfill(3)
                current=utc_now()
                con.execute("""INSERT INTO visits(patient_id,service_id,ticket,day,status,created_at,arrived_at,updated_at)
                             VALUES(?,?,?,?,?,?,?,?)""",
                             (pid,service,ticket,local_today(),"waiting",current,current,current))
init_db()

app=FastAPI(title="Tulia Care — Fictional Queue Demo",docs_url=None,redoc_url=None,openapi_url=None)
app.mount("/assets",StaticFiles(directory=ROOT/"static"),name="assets")

@app.middleware("http")
async def headers(request:Request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    if request.url.path.startswith("/api/"):response.headers["Cache-Control"]="no-store"
    return response

@app.get("/")
def home():return FileResponse(ROOT/"static/index.html")
@app.get("/register")
def register_page():return FileResponse(ROOT/"static/register.html")
@app.get("/my-visit")
def visit_page():return FileResponse(ROOT/"static/visit.html")
@app.get("/reception")
def reception_page():return FileResponse(ROOT/"static/reception.html")
@app.get("/manifest.webmanifest")
def manifest():return FileResponse(ROOT/"static/manifest.webmanifest",media_type="application/manifest+json")
@app.get("/sw.js")
def service_worker():return FileResponse(ROOT/"static/sw.js",media_type="application/javascript",headers={"Service-Worker-Allowed":"/"})
@app.get("/health")
def health():return {"status":"ok","storage":"demo-sqlite","production_ready":False}

@app.get("/api/services")
def get_services():
    today=local_today()
    with db() as con:
        counts=asdict(con.execute("""SELECT service_id,status,COUNT(*) AS n FROM visits
                                  WHERE day=? GROUP BY service_id,status""",(today,)).fetchall())
    grouped=defaultdict(dict)
    for r in counts:grouped[r["service_id"]][r["status"]]=r["n"]
    return [{**s,"waiting":grouped[s["id"]].get("waiting",0),
             "being_seen":grouped[s["id"]].get("called",0)} for s in SERVICES]

class Register(BaseModel):
    display_name:str=Field(min_length=2,max_length=42)
    accepted_demo_terms:bool
@app.post("/api/patients",status_code=201)
def create_patient(body:Register,request:Request):
    throttle("register",request,18)
    name=" ".join(body.display_name.strip().split())
    if not body.accepted_demo_terms:raise HTTPException(422,"You must acknowledge this is a fictional demo")
    if len(name)<2 or not re.fullmatch(r"[\w .'-]{2,42}",name,re.UNICODE):
        raise HTTPException(422,"Enter a short display name without contact or medical details")
    token=secrets.token_urlsafe(32)
    public=secrets.token_urlsafe(8)
    with db(write=True) as con:
        con.execute("INSERT INTO patients(public_id,token_hash,display_name,created_at) VALUES(?,?,?,?)",
                    (public,digest(token),name,utc_now()))
    return {"patient_id":public,"access_token":token,"display_name":name,
            "message":"Demo profile saved on this device. It is not an actual hospital registration."}

def patient_for_token(token:str|None):
    if not token or len(token)<24 or len(token)>128:raise HTTPException(401,"Demo access key required")
    with db() as con:
        row=con.execute("SELECT * FROM patients WHERE token_hash=?",(digest(token),)).fetchone()
    if not row:raise HTTPException(401,"Demo profile not found. It may have reset.")
    return dict(row)

def safe_visit(con,patient_id):
    row=con.execute("SELECT * FROM visits WHERE patient_id=? ORDER BY id DESC LIMIT 1",(patient_id,)).fetchone()
    if not row:return None
    result=dict(row)
    service=SERVICE_MAP.get(result["service_id"])
    result["service_name"]=service["name"] if service else result["service_id"]
    if result["status"]=="waiting":
        # Queue position must use the same arrival-time ordering as staff call-next,
        # including when reception restores an earlier missed ticket at the end.
        ahead=con.execute("""SELECT COUNT(*) FROM visits WHERE day=? AND service_id=? AND status='waiting'
                              AND (arrived_at<? OR (arrived_at=? AND id<?))""",
            (result["day"],result["service_id"],result["arrived_at"],
             result["arrived_at"],result["id"])).fetchone()[0]
        result["people_ahead"]=ahead
        result["position"]=ahead+1
    else:
        result["people_ahead"]=None
        result["position"]=None
    # Do not disclose internal database IDs or other patients.
    return {k:result[k] for k in ("ticket","service_id","service_name","status","created_at",
            "arrived_at","called_at","completed_at","people_ahead","position")}

@app.get("/api/me")
def me(x_patient_token:str|None=Header(default=None)):
    patient=patient_for_token(x_patient_token)
    with db() as con:visit=safe_visit(con,patient["id"])
    return {"patient_id":patient["public_id"],"display_name":patient["display_name"],"visit":visit}

class NewVisit(BaseModel):
    service_id:str
    onsite:bool=False
@app.post("/api/visits",status_code=201)
def start_visit(body:NewVisit,request:Request,x_patient_token:str|None=Header(default=None)):
    throttle("checkin",request,40)
    patient=patient_for_token(x_patient_token)
    if body.service_id not in SERVICE_MAP:raise HTTPException(422,"Unknown clinic service")
    day=local_today()
    with db(write=True) as con:
        existing=con.execute("""SELECT id FROM visits WHERE patient_id=? AND
                                status IN ('prechecked','waiting','called')""",(patient["id"],)).fetchone()
        if existing:raise HTTPException(409,"You already have an active demo visit")
        count=con.execute("SELECT COUNT(*) FROM visits WHERE day=? AND service_id=?",
                          (day,body.service_id)).fetchone()[0]
        ticket=SERVICE_MAP[body.service_id]["code"]+"-"+str(count+1).zfill(3)
        current=utc_now()
        status="waiting" if body.onsite else "prechecked"
        con.execute("""INSERT INTO visits(patient_id,service_id,ticket,day,status,created_at,arrived_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (patient["id"],body.service_id,ticket,day,status,current,
                     current if body.onsite else None,current))
        visit=safe_visit(con,patient["id"])
    return {"visit":visit,"message":"You joined the demo queue." if body.onsite
            else "Pre-check-in complete. Tap 'I have arrived' once at the clinic."}

@app.post("/api/visits/arrive")
def mark_arrived(x_patient_token:str|None=Header(default=None)):
    patient=patient_for_token(x_patient_token)
    with db(write=True) as con:
        row=con.execute("""SELECT * FROM visits WHERE patient_id=? ORDER BY id DESC LIMIT 1""",
                        (patient["id"],)).fetchone()
        if not row:raise HTTPException(404,"No visit found")
        if row["day"]!=local_today():raise HTTPException(409,"Your ticket is from another day. Please ask reception for assistance.")
        if row["status"]!="prechecked":raise HTTPException(409,"This visit is already checked in or closed")
        current=utc_now()
        con.execute("UPDATE visits SET status='waiting',arrived_at=?,updated_at=? WHERE id=?",
                    (current,current,row["id"]))
        visit=safe_visit(con,patient["id"])
    return {"visit":visit,"message":"Arrival confirmed. You are in the demo queue."}

def make_session():
    stamp=str(int(time.time()))
    nonce=secrets.token_urlsafe(15)
    data=stamp+"."+nonce
    return data+"."+hmac.new(SECRET,data.encode(),"sha256").hexdigest()

def require_staff(request:Request,mutation=False):
    token=request.cookies.get(COOKIE,"")
    try:
        stamp,nonce,signature=token.split(".",2)
        data=stamp+"."+nonce
        age=time.time()-int(stamp)
        valid=0<=age<SESSION_SECONDS and hmac.compare_digest(signature,hmac.new(SECRET,data.encode(),"sha256").hexdigest())
    except (ValueError,TypeError):
        valid=False
    if not valid:raise HTTPException(401,"Staff sign-in required")
    if mutation:
        origin=request.headers.get("origin","")
        if origin and urlsplit(origin).hostname!=request.url.hostname:raise HTTPException(403,"Invalid request origin")
        if request.headers.get("sec-fetch-site")=="cross-site":raise HTTPException(403,"Cross-site action blocked")
    return True

class StaffLogin(BaseModel):
    password:str=Field(min_length=1,max_length=200)
@app.post("/api/staff/login")
def staff_login(body:StaffLogin,request:Request):
    throttle("staff-login",request,10,600)
    if not ADMIN_PASSWORD or not hmac.compare_digest(body.password,ADMIN_PASSWORD):
        raise HTTPException(401,"Invalid staff password")
    response=JSONResponse({"signed_in":True})
    response.set_cookie(COOKIE,make_session(),max_age=SESSION_SECONDS,
                        secure=COOKIE_SECURE,httponly=True,samesite="strict",path="/")
    return response

@app.post("/api/staff/logout")
def staff_logout(request:Request):
    require_staff(request,True)
    response=JSONResponse({"signed_in":False})
    response.delete_cookie(COOKIE,path="/")
    return response

@app.get("/api/staff/overview")
def staff_overview(request:Request):
    require_staff(request)
    day=local_today()
    with db() as con:
        results=asdict(con.execute("""SELECT v.id,v.ticket,v.day,v.service_id,v.status,v.created_at,
                                    v.arrived_at,v.called_at,v.updated_at,p.display_name
                                    FROM visits v JOIN patients p ON p.id=v.patient_id
                                    WHERE v.day=? ORDER BY v.id ASC""",(day,)).fetchall())
    counts=defaultdict(lambda:defaultdict(int))
    for v in results:counts[v["service_id"]][v["status"]]+=1
    services=[{**s,"waiting":counts[s["id"]]["waiting"],"called":counts[s["id"]]["called"],
                "completed":counts[s["id"]]["completed"],"prechecked":counts[s["id"]]["prechecked"]} for s in SERVICES]
    return {"services":services,"visits":results,
            "totals":{"registered_today":len(results),
                      "waiting":sum(s["waiting"] for s in services),
                      "called":sum(s["called"] for s in services),
                      "completed":sum(s["completed"] for s in services),
                      "prechecked":sum(s["prechecked"] for s in services)}}

class CallNext(BaseModel):
    service_id:str
@app.post("/api/staff/call-next")
def call_next(body:CallNext,request:Request):
    require_staff(request,True)
    if body.service_id not in SERVICE_MAP:raise HTTPException(422,"Unknown service")
    with db(write=True) as con:
        active=con.execute("""SELECT id FROM visits WHERE day=? AND service_id=? AND status='called'
                              LIMIT 1""",(local_today(),body.service_id)).fetchone()
        if active:raise HTTPException(409,"Finish the current consultation before calling the next visitor")
        row=con.execute("""SELECT id,ticket FROM visits WHERE day=? AND service_id=?
                           AND status='waiting' ORDER BY arrived_at,id LIMIT 1""",
                       (local_today(),body.service_id)).fetchone()
        if not row:raise HTTPException(404,"No waiting visitors in this service")
        current=utc_now()
        con.execute("UPDATE visits SET status='called',called_at=?,updated_at=? WHERE id=?",
                    (current,current,row["id"]))
    return {"ticket":row["ticket"],"status":"called"}

class ChangeVisit(BaseModel):
    status:str
@app.post("/api/staff/visits/{visit_id}/status")
def change_visit(visit_id:int,body:ChangeVisit,request:Request):
    require_staff(request,True)
    allowed={"waiting":{"missed"},"called":{"completed","missed"},"missed":{"waiting"}}
    with db(write=True) as con:
        row=con.execute("SELECT * FROM visits WHERE id=? AND day=?",(visit_id,local_today())).fetchone()
        if not row:raise HTTPException(404,"Today's visit not found")
        if body.status not in allowed.get(row["status"],set()):raise HTTPException(409,"Invalid queue status transition")
        if body.status=="waiting":
            current=utc_now()
            con.execute("UPDATE visits SET status='waiting',arrived_at=?,updated_at=? WHERE id=?",
                        (current,current,row["id"]))
        elif body.status=="completed":
            current=utc_now()
            con.execute("UPDATE visits SET status='completed',completed_at=?,updated_at=? WHERE id=?",
                        (current,current,row["id"]))
        else:
            con.execute("UPDATE visits SET status='missed',updated_at=? WHERE id=?",
                        (utc_now(),row["id"]))
    return {"ticket":row["ticket"],"status":body.status}

@app.get("/api/public/queue")
def public_queue():
    day=local_today()
    with db() as con:
        stats=asdict(con.execute("""SELECT service_id,
                                   SUM(CASE WHEN status='waiting' THEN 1 ELSE 0 END) waiting,
                                   MAX(CASE WHEN status='called' THEN ticket ELSE NULL END) currently_called
                                   FROM visits WHERE day=? GROUP BY service_id""",(day,)).fetchall())
    mapping={v["service_id"]:v for v in stats}
    return [{"id":service["id"],"name":service["name"],
             "waiting":int(mapping.get(service["id"],{}).get("waiting") or 0),
             "called_ticket":mapping.get(service["id"],{}).get("currently_called")}
            for service in SERVICES]
