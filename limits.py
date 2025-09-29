# limits.py — spending and quantity caps persisted to JSON
import json
from pathlib import Path

LIMITS_PATH = Path("limits.json")

def set_limits(max_total_usd: float, max_qty: int):
    data = {"cap": float(max_total_usd), "qty": int(max_qty)}
    LIMITS_PATH.write_text(json.dumps(data, indent=2))
    return data

def get_limits():
    if not LIMITS_PATH.exists():
        # sensible defaults: no spend allowed until set
        return {"cap": 0.0, "qty": 0}
    return json.loads(LIMITS_PATH.read_text())

def enforce(amount_usd: float, qty: int):
    lim = get_limits()
    if amount_usd > lim.get("cap", 0.0):
        return False, f"Amount ${amount_usd:.2f} exceeds cap ${lim.get('cap', 0.0):.2f}"
    if qty > lim.get("qty", 0):
        return False, f"Quantity {qty} exceeds allowed {lim.get('qty', 0)}"
    return True, "ok"
