# config.py
import os

def _get(name: str, required: bool=True, default=None):
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return val

class Settings:
    TARGET_USER = os.getenv("TARGET_USER", "")
    TARGET_PASS = os.getenv("TARGET_PASS", "")
    BESTBUY_USER = os.getenv("BESTBUY_USER", "")
    BESTBUY_PASS = os.getenv("BESTBUY_PASS", "")
    COSTCO_USER = os.getenv("COSTCO_USER", "")
    COSTCO_PASS = os.getenv("COSTCO_PASS", "")
    SAMS_USER   = os.getenv("SAMS_USER", "")
    SAMS_PASS   = os.getenv("SAMS_PASS", "")

    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    INBOUND_SIGNATURE_SECRET = os.getenv("INBOUND_SIGNATURE_SECRET", "")

    COOKIE_ENC_KEY = os.getenv("COOKIE_ENC_KEY", "")

    PROXY_URL = os.getenv("PROXY_URL", None)
