# Receiver Extensions
New endpoints added to wire purchase engine + limits:

- `GET /limits` → current caps
- `POST /limits` → `{ "cap": 200.0, "qty": 2 }`
- `POST /order/add` → `{ "site": "target", "product_id": "94300072", "qty": 1, "price_usd": 19.99 }`
- `POST /order/checkout` → `{ "site": "target", "cap_usd": 50.0, "decision_token": "a1b2c3" }`

These call into `purchase_engine.py` (currently simulated). Replace stubs with live retailer flows when ready.
