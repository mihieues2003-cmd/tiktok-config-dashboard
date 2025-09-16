"""
Simple Config Dashboard (Flask) for TikTok Watcher Bot
- REST API: GET/POST /api/config  (optional customer_id)
- HTML Form:  GET /config?customer_id=
- Storage:    JSON file on disk (config_store.json)
- Auth:       Optional bearer token (ADMIN_TOKEN). If unset, API is open (not recommended).

Environment:
  PORT=5000
  ADMIN_TOKEN=changeme  # optional but recommended
  DEFAULT_CUSTOMER_ID=DEFAULT

Run local:
  pip install flask waitress python-dotenv
  python server.py

Deploy on Render:
  - Create new Web Service -> Build cmd: pip install -r requirements.txt
  - Start cmd:  python server.py  (or: waitress-serve --port=$PORT server:app)
"""
from __future__ import annotations
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Any

from flask import Flask, request, jsonify, redirect, url_for, render_template_string, abort

APP_ROOT = Path(__file__).parent
STORE_FILE = APP_ROOT / "config_store.json"
DEFAULT_CUSTOMER_ID = os.getenv("DEFAULT_CUSTOMER_ID", "DEFAULT")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # Bearer token for write endpoints

app = Flask(__name__)

# ---------------------------- Model ----------------------------
@dataclass
class Config:
    ratio: float = 1.5
    min_coins: float = 100.0
    min_ratio: float = 1.5
    min_sec_left: int = 20
    alert_enabled: bool = True

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Config":
        base = asdict(cls())
        base.update({k: d.get(k, base[k]) for k in base.keys()})
        # normalize types
        base["ratio"] = float(base["ratio"])
        base["min_coins"] = float(base["min_coins"])
        base["min_ratio"] = float(base["min_ratio"])
        base["min_sec_left"] = int(base["min_sec_left"])
        base["alert_enabled"] = bool(base["alert_enabled"])
        return cls(**base)

# ---------------------------- Storage ----------------------------

def _load_store() -> Dict[str, Dict[str, Any]]:
    if not STORE_FILE.exists():
        return {}
    try:
        return json.loads(STORE_FILE.read_text("utf-8"))
    except Exception:
        return {}


def _save_store(store: Dict[str, Dict[str, Any]]) -> None:
    STORE_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), "utf-8")


def get_cfg(customer_id: str) -> Config:
    store = _load_store()
    raw = store.get(customer_id) or store.get(DEFAULT_CUSTOMER_ID) or {}
    return Config.from_dict(raw)


def set_cfg(customer_id: str, data: Dict[str, Any]) -> Config:
    store = _load_store()
    cfg = Config.from_dict({**store.get(customer_id, {}), **data})
    store[customer_id] = asdict(cfg)
    _save_store(store)
    return cfg

# ---------------------------- Auth ----------------------------

def _require_auth() -> None:
    if not ADMIN_TOKEN:
        return  # open server (not recommended)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        abort(401)
    token = auth.split(" ", 1)[1].strip()
    if token != ADMIN_TOKEN:
        abort(403)

# ---------------------------- API ----------------------------
@app.get("/api/config")
def api_get_config():
    customer_id = request.args.get("customer_id", DEFAULT_CUSTOMER_ID)
    cfg = get_cfg(customer_id)
    return jsonify(asdict(cfg))


@app.post("/api/config")
def api_update_config():
    _require_auth()
    customer_id = request.args.get("customer_id", DEFAULT_CUSTOMER_ID)
    payload = request.get_json(silent=True) or {}
    cfg = set_cfg(customer_id, payload)
    return jsonify({"ok": True, "customer_id": customer_id, "config": asdict(cfg)})

# ---------------------------- HTML ----------------------------
FORM_HTML = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Config Dashboard</title>
  <style>
    body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:720px;margin:24px auto;padding:0 12px}
    .card{border:1px solid #e6e6e6;border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(0,0,0,.04)}
    label{display:block;margin-top:12px;font-weight:600}
    input[type="number"],input[type="text"]{width:100%;padding:10px;border:1px solid #ddd;border-radius:10px}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .btn{background:#111;color:#fff;border:none;border-radius:10px;padding:10px 14px;margin-top:16px;cursor:pointer}
    .muted{color:#666;font-size:13px}
  </style>
</head>
<body>
  <h2>Config Dashboard</h2>
  <div class="card">
  <form method="post" action="{{ save_url }}">
    <input type="hidden" name="customer_id" value="{{ customer_id }}" />
    <label>Alert Enabled
      <input type="text" name="alert_enabled" value="{{ '1' if cfg.alert_enabled else '0' }}" />
      <div class="muted">1 = bật, 0 = tắt</div>
    </label>
    <div class="row">
      <div>
        <label>Ratio</label>
        <input type="number" step="0.1" name="ratio" value="{{ cfg.ratio }}" />
      </div>
      <div>
        <label>Min Ratio</label>
        <input type="number" step="0.1" name="min_ratio" value="{{ cfg.min_ratio }}" />
      </div>
    </div>
    <div class="row">
      <div>
        <label>Min Coins</label>
        <input type="number" step="1" name="min_coins" value="{{ cfg.min_coins }}" />
      </div>
      <div>
        <label>Min Seconds Left</label>
        <input type="number" step="1" name="min_sec_left" value="{{ cfg.min_sec_left }}" />
      </div>
    </div>
    <button class="btn" type="submit">Lưu</button>
    <div class="muted">Customer: <b>{{ customer_id }}</b></div>
  </form>
  </div>
  <p class="muted">API: <code>/api/config?customer_id={{ customer_id }}</code></p>
</body>
</html>
"""

@app.get("/config")
def html_get_form():
    customer_id = request.args.get("customer_id", DEFAULT_CUSTOMER_ID)
    cfg = get_cfg(customer_id)
    return render_template_string(FORM_HTML, cfg=cfg, customer_id=customer_id, save_url=url_for("html_post_form"))


@app.post("/config")
def html_post_form():
    _require_auth()
    form = request.form
    customer_id = form.get("customer_id", DEFAULT_CUSTOMER_ID)
    data = {
        "ratio": form.get("ratio"),
        "min_ratio": form.get("min_ratio"),
        "min_coins": form.get("min_coins"),
        "min_sec_left": form.get("min_sec_left"),
        "alert_enabled": form.get("alert_enabled") in ("1", "true", "True"),
    }
    # loại bỏ None/rỗng
    data = {k: v for k, v in data.items() if v not in (None, "")}
    cfg = set_cfg(customer_id, data)
    return redirect(url_for("html_get_form", customer_id=customer_id))

# ---------------------------- Health ----------------------------
@app.get("/")
def root():
    return redirect(url_for("html_get_form", customer_id=DEFAULT_CUSTOMER_ID))

# ---------------------------- Main ----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
