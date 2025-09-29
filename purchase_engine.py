# purchase_engine.py
from __future__ import annotations
import requests, time
from typing import Dict, Any, Optional, List
from config import Settings
from secure_store import save_cookies, load_cookies

def _apply_cookies(sess: requests.Session, jar_dict: Dict[str, Any]) -> None:
    for d in jar_dict.get("cookies", []):
        sess.cookies.set(d.get("name"), d.get("value"),
                         domain=d.get("domain"), path=d.get("path", "/"))

def _extract_cookies(sess: requests.Session) -> Dict[str, Any]:
    return {"cookies": [
        {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
        for c in sess.cookies
    ]}

def _session_valid(sess: requests.Session, site: str) -> bool:
    # TODO: replace with a lightweight authenticated GET for each site
    return False

def ensure_session(site: str, login_func) -> Optional[requests.Session]:
    sess = requests.Session()
    if Settings.PROXY_URL:
        sess.proxies = {"http": Settings.PROXY_URL, "https": Settings.PROXY_URL}

    jar = load_cookies(site)
    if jar:
        _apply_cookies(sess, jar)
        if _session_valid(sess, site):
            return sess

    if not login_func(sess):
        return None
    save_cookies(site, _extract_cookies(sess))
    return sess

# Target
def login_target(sess: requests.Session) -> bool:
    return bool(Settings.TARGET_USER and Settings.TARGET_PASS)

def add_to_cart_target(sess: requests.Session, product_id: str, qty: int) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "site": "target", "id": product_id, "qty": qty}

def checkout_target(sess: requests.Session, cap_usd: float) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "order": f"SIM-T-{int(time.time())}", "cap": cap_usd}

# BestBuy
def login_bestbuy(sess: requests.Session) -> bool:
    return bool(Settings.BESTBUY_USER and Settings.BESTBUY_PASS)

def add_to_cart_bestbuy(sess: requests.Session, sku: str, qty: int) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "site": "bestbuy", "sku": sku, "qty": qty}

def checkout_bestbuy(sess: requests.Session, cap_usd: float) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "order": f"SIM-BB-{int(time.time())}", "cap": cap_usd}

# Costco
def login_costco(sess: requests.Session) -> bool:
    return bool(Settings.COSTCO_USER and Settings.COSTCO_PASS)

def add_to_cart_costco(sess: requests.Session, item_id: str, qty: int) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "site": "costco", "id": item_id, "qty": qty}

def checkout_costco(sess: requests.Session, cap_usd: float) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "order": f"SIM-C-{int(time.time())}", "cap": cap_usd}

# Sam's Club
def login_sams(sess: requests.Session) -> bool:
    return bool(Settings.SAMS_USER and Settings.SAMS_PASS)

def add_to_cart_sams(sess: requests.Session, item_id: str, qty: int) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "site": "sams", "id": item_id, "qty": qty}

def checkout_sams(sess: requests.Session, cap_usd: float) -> Dict[str, Any]:
    return {"ok": True, "simulated": True, "order": f"SIM-S-{int(time.time())}", "cap": cap_usd}

# Convenience wrappers
def add_to_cart(site: str, product_id: str, qty: int) -> Dict[str, Any]:
    site = site.lower()
    if site == "target":
        sess = ensure_session("target", login_target);  assert sess, "target login failed"
        return add_to_cart_target(sess, product_id, qty)
    if site == "bestbuy":
        sess = ensure_session("bestbuy", login_bestbuy);  assert sess, "bestbuy login failed"
        return add_to_cart_bestbuy(sess, product_id, qty)
    if site == "costco":
        sess = ensure_session("costco", login_costco);  assert sess, "costco login failed"
        return add_to_cart_costco(sess, product_id, qty)
    if site == "sams":
        sess = ensure_session("sams", login_sams);  assert sess, "sams login failed"
        return add_to_cart_sams(sess, product_id, qty)
    raise ValueError(f"unsupported site: {site}")

def checkout(site: str, cap_usd: float) -> Dict[str, Any]:
    site = site.lower()
    if site == "target":
        sess = ensure_session("target", login_target);  assert sess, "target login failed"
        return checkout_target(sess, cap_usd)
    if site == "bestbuy":
        sess = ensure_session("bestbuy", login_bestbuy);  assert sess, "bestbuy login failed"
        return checkout_bestbuy(sess, cap_usd)
    if site == "costco":
        sess = ensure_session("costco", login_costco);  assert sess, "costco login failed"
        return checkout_costco(sess, cap_usd)
    if site == "sams":
        sess = ensure_session("sams", login_sams);  assert sess, "sams login failed"
        return checkout_sams(sess, cap_usd)
    raise ValueError(f"unsupported site: {site}")
