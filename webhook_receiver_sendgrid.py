from flask import Flask, request, jsonify, Response
from pathlib import Path
import json, os, re, datetime, base64, html, time, threading

from purchase_engine import add_to_cart, checkout
from limits import set_limits, get_limits, enforce

app = Flask(__name__)

DECISIONS_DIR = Path(os.getenv("DECISIONS_DIR", "decisions"))
PURCHASES_DIR = Path(os.getenv("PURCHASES_DIR", "purchases"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", "logs"))
for d in (DECISIONS_DIR, PURCHASES_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

ADMIN_USER = os.getenv("ADMIN_USER", "")
ADMIN_PASS = os.getenv("ADMIN_PASS", "")

TOKEN_RE = re.compile(r"(?i)token\s*:\s*([a-f0-9]{6,32})")

_metrics_lock = threading.Lock()
_metrics = {
    "http_requests_total": {},
    "decisions_total": 0,
    "purchases_total": 0,
    "purchases_amount_usd": 0.0
}
def _inc_http(method, path, status):
    with _metrics_lock:
        key = (method, path, int(status))
        _metrics["http_requests_total"][key] = _metrics["http_requests_total"].get(key, 0) + 1
def _inc_decision():
    with _metrics_lock:
        _metrics["decisions_total"] += 1
def _inc_purchase(amount):
    with _metrics_lock:
        _metrics["purchases_total"] += 1
        try:
            _metrics["purchases_amount_usd"] += float(amount or 0.0)
        except Exception:
            pass

@app.after_request
def _after(resp):
    try:
        _inc_http(request.method, request.path, resp.status_code)
    finally:
        return resp

def _prometheus_exposition():
    lines = []
    with _metrics_lock:
        lines.append("# HELP pokebot_decisions_total Total number of decisions stored")
        lines.append("# TYPE pokebot_decisions_total counter")
        lines.append(f"pokebot_decisions_total {_metrics['decisions_total']}")
        lines.append("# HELP pokebot_purchases_total Total number of purchases stored")
        lines.append("# TYPE pokebot_purchases_total counter")
        lines.append(f"pokebot_purchases_total {_metrics['purchases_total']}")
        lines.append("# HELP pokebot_purchases_amount_usd Sum of purchase amounts in USD")
        lines.append("# TYPE pokebot_purchases_amount_usd counter")
        lines.append(f"pokebot_purchases_amount_usd {_metrics['purchases_amount_usd']:.2f}")
        lines.append("# HELP pokebot_http_requests_total HTTP requests by method, path and status")
        lines.append("# TYPE pokebot_http_requests_total counter")
        for (method, path, status), count in sorted(_metrics["http_requests_total"].items()):
            plabel = path.replace('\\', '\\\\').replace('"', '\"')
            lines.append(f'pokebot_http_requests_total{{method="{method}",path="{plabel}",status="{status}"}} {count}')
    return "\n".join(lines) + "\n"

def _now():
    return datetime.datetime.utcnow().isoformat() + "Z"

def _log_json(line: dict, file_name="server.log"):
    p = LOGS_DIR / file_name
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _list_json(dirpath: Path, limit=200):
    files = sorted(dirpath.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:limit]:
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            pass
    return out

def _check_basic_auth(auth_header: str) -> bool:
    if not ADMIN_USER or not ADMIN_PASS:
        return True
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        b64 = auth_header.split(" ", 1)[1].strip()
        userpass = base64.b64decode(b64).decode("utf-8")
        user, pw = userpass.split(":", 1)
        return user == ADMIN_USER and pw == ADMIN_PASS
    except Exception:
        return False

@app.route("/", methods=["GET"])
def root():
    return jsonify({"ok": True, "msg": "PokeBot receiver alive"}), 200

@app.route("/healthz", methods=["GET"])
def healthz():
    decs = sorted(DECISIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    purs = sorted(PURCHASES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest_dec = decs[0].stat().st_mtime if decs else 0
    latest_pur = purs[0].stat().st_mtime if purs else 0
    return jsonify({
        "ok": True,
        "decisions_count": len(decs),
        "purchases_count": len(purs),
        "latest_decision_ts": datetime.datetime.utcfromtimestamp(latest_dec).isoformat() + "Z" if latest_dec else None,
        "latest_purchase_ts": datetime.datetime.utcfromtimestamp(latest_pur).isoformat() + "Z" if latest_pur else None
    }), 200

@app.route("/metrics", methods=["GET"])
def metrics():
    text = _prometheus_exposition()
    return Response(text, mimetype="text/plain; version=0.0.4; charset=utf-8")

@app.route("/admin/logs", methods=["GET"])
def admin_logs():
    auth = request.headers.get("Authorization", "")
    if not _check_basic_auth(auth):
        return Response("Unauthorized", status=401, headers={"WWW-Authenticate": "Basic realm='PokeBot Admin'"})
    try:
        n = int(request.args.get("n", "200"))
    except Exception:
        n = 200
    n = max(1, min(n, 5000))
    fmt = (request.args.get("format", "jsonl") or "jsonl").lower()
    path = LOGS_DIR / "server.log"
    if not path.exists():
        return Response("", mimetype="text/plain" if fmt == "txt" else "application/x-ndjson")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    body = "\n".join(lines) + ("\n" if lines else "")
    return Response(body, mimetype="text/plain; charset=utf-8" if fmt == "txt" else "application/x-ndjson")

# ----- Inbound decisions (email webhook) -----
@app.route("/inbound", methods=["POST"])
def inbound():
    frm = request.form.get("from", "")
    to = request.form.get("to", "")
    subject = request.form.get("subject", "")
    text = request.form.get("text", "") or ""
    html_body = request.form.get("html", "") or ""

    token_match = TOKEN_RE.search(text) or TOKEN_RE.search(html_body)
    if not token_match:
        _log_json({"ts": _now(), "type": "inbound", "ok": False, "reason": "no_token"})
        return jsonify({"ok": False, "error": "TOKEN not found in message body"}), 200

    token = token_match.group(1)
    decision = None
    body = text.strip() or html_body
    for line in body.splitlines():
        stripped = line.strip()
        if stripped == "1":
            decision = "1"; break
        if stripped == "2":
            decision = "2"; break
    if decision is None:
        if "1" in body and "2" not in body:
            decision = "1"
        elif "2" in body and "1" not in body:
            decision = "2"

    if decision not in ("1", "2"):
        _log_json({"ts": _now(), "type": "inbound", "ok": False, "token": token, "reason": "no_decision"})
        return jsonify({"ok": False, "error": "Decision (1/2) not found"}), 200

    record = {"token": token, "decision": decision, "from": frm, "to": to, "subject": subject, "ts": _now()}
    (DECISIONS_DIR / f"{token}.json").write_text(json.dumps(record, indent=2))
    _inc_decision()
    _log_json({"ts": _now(), "type": "decision_store", "ok": True, "token": token, "decision": decision})
    return jsonify({"ok": True, "stored": record}), 200

@app.route("/decision/<token>", methods=["GET"])
def get_decision(token: str):
    p = DECISIONS_DIR / f"{token}.json"
    if not p.exists():
        return jsonify({"ok": False, "status": "pending"}), 200
    try:
        data = json.loads(p.read_text())
        return jsonify({"ok": True, "status": "found", "data": data}), 200
    except Exception as e:
        return jsonify({"ok": False, "status": "error", "error": str(e)}), 500

# ----- Purchases JSON / dashboards -----
def _list_purchases(limit=200):
    files = sorted(PURCHASES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for p in files:
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            pass
    return out

@app.route("/purchases.json", methods=["GET"])
def purchases_json():
    auth = request.headers.get("Authorization", "")
    if not _check_basic_auth(auth):
        return Response("Unauthorized", status=401, headers={"WWW-Authenticate": "Basic realm='PokeBot Admin'"})
    items = _list_purchases()
    total = 0.0
    for it in items:
        try:
            total += float(it.get("amount", 0.0))
        except Exception:
            pass
    return jsonify({"ok": True, "total": total, "items": items}), 200

# ----- New: Limits endpoints -----
@app.route("/limits", methods=["GET"])
def get_limits_ep():
    return jsonify({"ok": True, "limits": get_limits()}), 200

@app.route("/limits", methods=["POST"])
def set_limits_ep():
    data = request.get_json(force=True, silent=True) or {}
    cap = float(data.get("cap", 0.0))
    qty = int(data.get("qty", 0))
    result = set_limits(cap, qty)
    _log_json({"ts": _now(), "type": "limits_set", "data": result})
    return jsonify({"ok": True, "limits": result}), 200

# ----- New: Order flow endpoints (simulate real merchant calls) -----
@app.route("/order/add", methods=["POST"])
def order_add():
    data = request.get_json(force=True, silent=True) or {}
    site = (data.get("site") or "").lower()
    product_id = data.get("product_id") or data.get("sku") or ""
    qty = int(data.get("qty") or 1)
    price = float(data.get("price_usd") or 0.0)

    ok, why = enforce(price * qty, qty)
    if not ok:
        return jsonify({"ok": False, "error": why}), 400

    try:
        res = add_to_cart(site, product_id, qty)
    except Exception as e:
        _log_json({"ts": _now(), "type": "add_to_cart_error", "site": site, "err": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 500

    _log_json({"ts": _now(), "type": "add_to_cart", "site": site, "product_id": product_id, "qty": qty, "result": res})
    return jsonify({"ok": True, "result": res}), 200

@app.route("/order/checkout", methods=["POST"])
def order_checkout():
    data = request.get_json(force=True, silent=True) or {}
    site = (data.get("site") or "").lower()
    decision_token = data.get("decision_token") or ""
    total_cap = float(data.get("cap_usd") or 0.0)
    # optional: require prior email approval
    if decision_token:
        p = DECISIONS_DIR / f"{decision_token}.json"
        if not p.exists():
            return jsonify({"ok": False, "error": "approval not found"}), 403
        try:
            rec = json.loads(p.read_text())
            if rec.get("decision") != "1":
                return jsonify({"ok": False, "error": "approval denied"}), 403
        except Exception:
            return jsonify({"ok": False, "error": "approval read error"}), 500

    try:
        res = checkout(site, total_cap)
    except Exception as e:
        _log_json({"ts": _now(), "type": "checkout_error", "site": site, "err": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 500

    # persist purchase
    record = {
        "ts": _now(),
        "site": site,
        "order": res.get("order", f"SIM-{int(time.time())}"),
        "amount": float(total_cap),
        "items": data.get("items", [])
    }
    (PURCHASES_DIR / f"purchase_{int(time.time()*1000)}.json").write_text(json.dumps(record, indent=2))
    _inc_purchase(record["amount"])
    _log_json({"ts": _now(), "type": "purchase_store", "data": record})
    return jsonify({"ok": True, "purchase": record, "result": res}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
