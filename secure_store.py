# secure_store.py
import base64, json
from pathlib import Path
from typing import Optional, Dict, Any
from config import Settings

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception as e:
    raise RuntimeError("cryptography is required: pip install cryptography") from e

COOKIES_DIR = Path("cookies")
COOKIES_DIR.mkdir(parents=True, exist_ok=True)

def _fernet() -> "Fernet":
    key = Settings.COOKIE_ENC_KEY or ""
    if not key.startswith("base64:"):
        raise RuntimeError("COOKIE_ENC_KEY must be set like 'base64:<fernet_key>'")
    b = key.split(":", 1)[1]
    return Fernet(base64.urlsafe_b64decode(b))

def save_cookies(site: str, jar_dict: Dict[str, Any]) -> None:
    f = _fernet()
    blob = f.encrypt(json.dumps(jar_dict).encode("utf-8"))
    (COOKIES_DIR / f"{site}.bin").write_bytes(blob)

def load_cookies(site: str) -> Optional[Dict[str, Any]]:
    p = COOKIES_DIR / f"{site}.bin"
    if not p.exists():
        return None
    try:
        data = _fernet().decrypt(p.read_bytes())
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None
