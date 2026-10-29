"""Non-destructive live-site smoke test: python scripts/verify_live.py https://HOST"""
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check(origin):
    origin = origin.rstrip("/")
    target = urlsplit(origin)
    if target.scheme != "https" or not target.netloc or target.path or target.query or target.fragment:
        raise ValueError("Supply an HTTPS origin without a path or query")

    def get(path):
        try:
            with urlopen(Request(origin+path, headers={"User-Agent": "PortfolioReleaseCheck/1.0"}), timeout=30) as r:
                return r.status, dict(r.headers), r.read(256000)
        except HTTPError as e:
            return e.code, dict(e.headers), e.read(256000)

    status, _, raw = get("/health")
    assert status == 200 and json.loads(raw) == {"status":"ok","read_only":True}, "Incorrect public read-only mode"
    for path in ("/", "/projects.html", "/cyberlab.html", "/styles.css", "/script.js", "/EDDY_BIEGON_CV.docx"):
        status, _, _ = get(path)
        assert status == 200, f"Public page/resource failed: {path} HTTP {status}"
    status, _, raw = get("/api/projects")
    assert status == 200, f"Projects API HTTP {status}"
    projects = json.loads(raw)
    for name in ("NexusDesk","SecureScan","KNLS","Mint Dental"):
        assert any(name in p["title"] for p in projects), f"Missing project: {name}"
    for path in ("/admin","/admin/setup","/admin/login","/api/admin/all"):
        status, _, _ = get(path)
        assert status == 404, f"Exposed admin route: {path} HTTP {status}"
    print("PASS: portfolio pages, assets, featured projects, public read-only mode and admin lockdown")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/verify_live.py https://portfolio.example")
    try:
        check(sys.argv[1])
    except (AssertionError, ValueError, URLError) as e:
        raise SystemExit(f"FAIL: {e}") from e
