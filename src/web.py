"""FastAPI application – runs on localhost, supports Traefik + Authelia."""

import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .firefly_client import FireflyClient
from .matcher import HistoryMatcher, Suggestion
from .categorizer import ClaudeCategorizer, OllamaCategorizer, _amount_range

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Firefly III Kategoriserare", docs_url=None, redoc_url=None)

# Server-side state (populated on /api/init)
_S: dict = {}


# ── Auth guard ────────────────────────────────────────────────────────────────

@app.middleware("http")
async def auth_guard(request: Request, call_next):
    """When REQUIRE_FORWARDED_AUTH=true, block requests without Remote-User.
    Exempts: /, /static/*, /favicon.ico (so browser can show the UI).
    """
    if os.getenv("REQUIRE_FORWARDED_AUTH", "").lower() == "true":
        p = request.url.path
        if not (p in ("/", "/favicon.ico") or p.startswith("/static/")):
            if not request.headers.get("Remote-User"):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client() -> FireflyClient:
    if "client" not in _S:
        raise HTTPException(503, "Inte initialiserad")
    return _S["client"]

def _raw(group_id: str) -> dict:
    r = _S.get("raws", {}).get(group_id)
    if r is None:
        raise HTTPException(404, f"Okänd transaktion: {group_id}")
    return r

def _safe(txn: dict) -> dict:
    return {k: v for k, v in txn.items() if not k.startswith("_")}

def _examples(n: int = 10) -> list:
    return [{"description": t["description"], "amount_range": _amount_range(t["amount"]),
             "category_name": t.get("category_name", ""), "budget_name": t.get("budget_name", "")}
            for t in _S.get("history", [])[:n] if t.get("category_name")]

def _suggest(txn: dict) -> dict:
    sg: Suggestion = Suggestion.empty()
    if m := _S.get("matcher"):
        sg = m.suggest(txn["description"])
    ai = _S.get("ai")
    if ai and sg.confidence < 0.88:
        ai_sg = ai.suggest(txn, _S.get("categories", []), _S.get("budgets", []), _examples())
        if ai_sg.has_any() and ai_sg.confidence >= sg.confidence:
            sg = ai_sg
    return sg.to_dict()


# ── Models ────────────────────────────────────────────────────────────────────

class UpdateReq(BaseModel):
    group_id: str
    category_name: Optional[str] = None
    budget_name: Optional[str] = None
    destination_name: Optional[str] = None

class BatchUpdateReq(BaseModel):
    updates: list[UpdateReq]

class CreateRulesReq(BaseModel):
    group_ids: list[str]

class ResolveDupReq(BaseModel):
    keep_group_id: str
    delete_group_id: str


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/me")
def me(request: Request):
    return {"user": request.headers.get("Remote-User", ""),
            "name": request.headers.get("Remote-Name", ""),
            "email": request.headers.get("Remote-Email", "")}

@app.post("/api/init")
def init():
    url   = os.getenv("FIREFLY_URL", "").strip()
    token = os.getenv("FIREFLY_TOKEN", "").strip()
    if not url or not token:
        raise HTTPException(400, "FIREFLY_URL eller FIREFLY_TOKEN saknas")
    try:
        fc = FireflyClient(url, token)
        fc.test_connection()
    except Exception as e:
        raise HTTPException(502, f"Anslutningsfel: {e}")
    try:
        categories = fc.get_categories()
        budgets    = fc.get_budgets()
        history    = fc.get_categorized(100)
    except Exception as e:
        raise HTTPException(502, f"Hämtningsfel: {e}")

    ai = None
    if ou := os.getenv("OLLAMA_URL", "").strip():
        ai = OllamaCategorizer(ou, os.getenv("OLLAMA_MODEL", "llama3"))
    elif ak := os.getenv("ANTHROPIC_API_KEY", "").strip():
        ai = ClaudeCategorizer(ak)

    _S.update({"client": fc, "categories": categories, "budgets": budgets,
                "history": history, "matcher": HistoryMatcher(history),
                "ai": ai, "raws": {}})

    ai_type = "local" if isinstance(ai, OllamaCategorizer) else \
              "cloud" if isinstance(ai, ClaudeCategorizer) else "none"
    return {"ok": True, "categories": len(categories), "budgets": len(budgets),
            "history": len(history), "ai_backend": ai_type}

@app.get("/api/metadata")
def metadata():
    destinations = sorted({
        t["destination_name"] for t in _S.get("history", [])
        if t.get("destination_name")
    })
    return {"categories": _S.get("categories", []), "budgets": _S.get("budgets", []),
            "destinations": destinations}

@app.get("/api/transactions")
def transactions(mode: str = "uncategorized", limit: int = 50):
    fc = _client()
    try:
        txns = fc.get_uncategorized(limit) if mode == "uncategorized" \
               else fc.get_transactions(limit=limit)
    except Exception as e:
        raise HTTPException(502, str(e))
    raws = _S.setdefault("raws", {})
    result = []
    for t in txns:
        raws[t["group_id"]] = t["_raw"]
        result.append({"transaction": _safe(t), "suggestion": _suggest(t)})
    return result

@app.post("/api/transactions/batch-update")
def batch_update(req: BatchUpdateReq):
    fc = _client()
    results = []
    for item in req.updates:
        try:
            fc.update_transaction(item.group_id, _raw(item.group_id),
                                  item.category_name, item.budget_name, item.destination_name)
            results.append({"group_id": item.group_id, "ok": True})
        except Exception as e:
            results.append({"group_id": item.group_id, "ok": False, "error": str(e)})
    return results

@app.get("/api/duplicates")
def duplicates(days: int = 30):
    fc = _client()
    try:
        txns = fc.get_transactions(limit=200)
    except Exception as e:
        raise HTTPException(502, str(e))
    raws = _S.setdefault("raws", {})
    for t in txns:
        raws[t["group_id"]] = t["_raw"]
    cutoff = datetime.now() - timedelta(days=days)
    recent = [t for t in txns if t.get("date") and
              datetime.fromisoformat(t["date"][:10]) >= cutoff]
    buckets: dict = defaultdict(list)
    for t in recent:
        buckets[(t.get("source_name", ""), round(t["amount"], 2))].append(t)
    seen, groups = set(), []
    for members in buckets.values():
        if len(members) < 2:
            continue
        ms = sorted(members, key=lambda t: t.get("date", ""))
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                a, b = ms[i], ms[j]
                key = tuple(sorted([a["group_id"], b["group_id"]]))
                if key in seen:
                    continue
                try:
                    delta = abs((datetime.fromisoformat(a["date"][:10]) -
                                 datetime.fromisoformat(b["date"][:10])).days)
                except Exception:
                    continue
                if delta > 3:
                    continue
                seen.add(key)
                same = a["description"].lower() == b["description"].lower()
                conf = "high" if delta == 0 and same else \
                       "medium" if same or delta == 0 else "low"
                groups.append({"confidence": conf, "delta_days": delta,
                                "transactions": [_safe(a), _safe(b)]})
    groups.sort(key=lambda g: {"high": 0, "medium": 1, "low": 2}[g["confidence"]])
    return groups

@app.post("/api/duplicates/resolve")
def resolve_dup(req: ResolveDupReq):
    try:
        _client().delete_transaction(req.delete_group_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(502, str(e))

@app.get("/api/rules")
def rules():
    try:
        return _client().get_rules()
    except Exception as e:
        raise HTTPException(502, str(e))

@app.post("/api/rules/create")
def create_rules(req: CreateRulesReq):
    fc = _client()
    raws = _S.get("raws", {})
    created, skipped, errors = [], [], []
    for gid in req.group_ids:
        raw = raws.get(gid)
        if not raw:
            skipped.append(gid)
            continue
        desc = (raw.get("description") or "").strip()
        actions = []
        if raw.get("category_name"):
            actions.append({"action": "set_category",             "value": raw["category_name"]})
        if raw.get("budget_name"):
            actions.append({"action": "set_budget",               "value": raw["budget_name"]})
        if raw.get("destination_name"):
            actions.append({"action": "set_destination_account",  "value": raw["destination_name"]})
        if not desc or not actions:
            skipped.append(gid)
            continue
        try:
            r = fc.create_rule({"title": f"Auto: {desc[:60]}", "active": True,
                                 "strict": False, "stop_processing": False,
                                 "trigger": "store-journal",
                                 "triggers": [{"type": "description_contains", "value": desc,
                                               "active": True, "stop_processing": False}],
                                 "actions": actions})
            created.append({"group_id": gid, "rule_id": r.get("data", {}).get("id")})
        except Exception as e:
            errors.append({"group_id": gid, "error": str(e)})
    return {"created": created, "skipped": skipped, "errors": errors}


# ── Static / SPA ──────────────────────────────────────────────────────────────

if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    f = STATIC / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8")) if f.exists() \
           else HTMLResponse("<h1>index.html saknas</h1>", status_code=500)
