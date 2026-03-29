"""FastAPI web application for the Firefly III transaction categorizer.

Runs entirely on localhost unless explicitly configured otherwise.
When deployed behind Traefik + Authelia, set REQUIRE_FORWARDED_AUTH=true
to enforce that every request must carry the Remote-User header injected
by Authelia.  Without that header the app returns 401.
"""

import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .firefly_client import FireflyClient
from .matcher import HistoryMatcher, Suggestion
from .categorizer import ClaudeCategorizer, OllamaCategorizer

STATIC_DIR = Path(__file__).parent / 'static'

app = FastAPI(title='Firefly III Kategoriserare', docs_url=None, redoc_url=None)

# ── Shared server-side state ──────────────────────────────────────────────────
# Populated on POST /api/init, reused for all subsequent requests.
_state: dict = {}


# ── Auth middleware ───────────────────────────────────────────────────────────

@app.middleware('http')
async def forwarded_auth_guard(request: Request, call_next):
    """Block requests that lack the Authelia-injected Remote-User header.

    Only active when REQUIRE_FORWARDED_AUTH=true (production behind Traefik).
    Static assets and the root HTML are let through so the browser can render
    a useful error page instead of a blank screen.
    """
    if os.getenv('REQUIRE_FORWARDED_AUTH', '').lower() == 'true':
        path = request.url.path
        exempt = path in ('/', '/favicon.ico') or path.startswith('/static/')
        if not exempt and not request.headers.get('Remote-User'):
            return JSONResponse({'detail': 'Unauthorized'}, status_code=401)
    return await call_next(request)


# ── Pydantic models ───────────────────────────────────────────────────────────

class UpdateRequest(BaseModel):
    group_id: str
    category_name: Optional[str] = None
    budget_name: Optional[str] = None
    destination_name: Optional[str] = None


class BatchUpdateRequest(BaseModel):
    updates: list[UpdateRequest]


class CreateRulesRequest(BaseModel):
    group_ids: list[str]   # create Firefly III rules for these transactions


class ResolveDuplicateRequest(BaseModel):
    keep_group_id: str
    delete_group_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client() -> FireflyClient:
    if 'client' not in _state:
        raise HTTPException(503, 'Inte initialiserad – ladda om sidan')
    return _state['client']


def _get_raw_split(group_id: str) -> dict:
    split = _state.get('raw_splits', {}).get(group_id)
    if split is None:
        raise HTTPException(404, f'Okänd transaktion: {group_id}')
    return split


def _ai_backend():
    return _state.get('ai_backend')


def _build_history_examples(n: int = 10) -> list:
    from .categorizer import _amount_range
    examples = []
    for t in _state.get('history', [])[:n]:
        if t.get('category_name'):
            examples.append({
                'description': t['description'],
                'amount_range': _amount_range(t['amount']),
                'category_name': t.get('category_name', ''),
                'budget_name': t.get('budget_name', ''),
            })
    return examples


def _compute_suggestion(transaction: dict) -> dict:
    matcher: Optional[HistoryMatcher] = _state.get('matcher')
    categories = _state.get('categories', [])
    budgets = _state.get('budgets', [])

    sg: Suggestion = Suggestion.empty()

    if matcher:
        sg = matcher.suggest(transaction['description'])

    ai = _ai_backend()
    if ai and sg.confidence < 0.88:
        ai_sg = ai.suggest(transaction, categories, budgets, _build_history_examples())
        if ai_sg.has_any() and ai_sg.confidence >= sg.confidence:
            sg = ai_sg

    return sg.to_dict()


def _safe_txn(txn: dict) -> dict:
    """Return a client-safe view of a transaction (no internal keys)."""
    return {k: v for k, v in txn.items() if not k.startswith('_')}


# ── Status & init ─────────────────────────────────────────────────────────────

@app.get('/api/status')
def status():
    ai = _ai_backend()
    ai_type = 'none'
    if isinstance(ai, OllamaCategorizer):
        ai_type = 'local'
    elif isinstance(ai, ClaudeCategorizer):
        ai_type = 'cloud'
    return {
        'initialized': 'client' in _state,
        'ai_backend': ai_type,
        'categories_count': len(_state.get('categories', [])),
        'budgets_count': len(_state.get('budgets', [])),
        'history_count': len(_state.get('history', [])),
    }


@app.get('/api/me')
def me(request: Request):
    """Return the currently authenticated user (from Authelia headers)."""
    return {
        'user': request.headers.get('Remote-User', ''),
        'name': request.headers.get('Remote-Name', ''),
        'email': request.headers.get('Remote-Email', ''),
        'groups': request.headers.get('Remote-Groups', ''),
    }


@app.post('/api/init')
def init():
    """Connect to Firefly III and pre-load reference data."""
    firefly_url = os.getenv('FIREFLY_URL', '').strip()
    firefly_token = os.getenv('FIREFLY_TOKEN', '').strip()

    if not firefly_url or not firefly_token:
        raise HTTPException(400, 'FIREFLY_URL eller FIREFLY_TOKEN saknas i .env')

    try:
        client = FireflyClient(firefly_url, firefly_token)
        client.test_connection()
    except Exception as e:
        raise HTTPException(502, f'Kan inte ansluta till Firefly III: {e}')

    try:
        categories = client.get_categories()
        budgets = client.get_budgets()
        history = client.get_recent_categorized_transactions(limit=300)
    except Exception as e:
        raise HTTPException(502, f'Fel vid hämtning av data: {e}')

    matcher = HistoryMatcher(history)

    ai_backend = None
    ollama_url = os.getenv('OLLAMA_URL', '').strip()
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    if ollama_url:
        ai_backend = OllamaCategorizer(ollama_url, os.getenv('OLLAMA_MODEL', 'llama3'))
    elif anthropic_key:
        ai_backend = ClaudeCategorizer(anthropic_key)

    _state.update({
        'client': client,
        'categories': categories,
        'budgets': budgets,
        'history': history,
        'matcher': matcher,
        'ai_backend': ai_backend,
        'raw_splits': {},   # populated as transactions are fetched
    })

    ai_type = 'none'
    if isinstance(ai_backend, OllamaCategorizer):
        ai_type = 'local'
    elif isinstance(ai_backend, ClaudeCategorizer):
        ai_type = 'cloud'

    return {
        'ok': True,
        'categories_count': len(categories),
        'budgets_count': len(budgets),
        'history_count': len(history),
        'ai_backend': ai_type,
    }


# ── Transactions ──────────────────────────────────────────────────────────────

@app.get('/api/transactions')
def get_transactions(mode: str = 'uncategorized', limit: int = 50):
    """Return transactions with suggestions. Raw splits are cached server-side."""
    client = _get_client()
    try:
        if mode == 'all':
            transactions = client.get_all_recent_transactions(limit=limit)
        else:
            transactions = client.get_uncategorized_transactions(limit=limit)
    except Exception as e:
        raise HTTPException(502, f'Fel vid hämtning: {e}')

    raw_splits: dict = _state.setdefault('raw_splits', {})
    result = []
    for txn in transactions:
        raw_splits[txn['group_id']] = txn['_raw_split']
        suggestion = _compute_suggestion(txn)
        result.append({'transaction': _safe_txn(txn), 'suggestion': suggestion})
    return result


@app.get('/api/metadata')
def get_metadata():
    return {
        'categories': _state.get('categories', []),
        'budgets': _state.get('budgets', []),
    }


@app.post('/api/transactions/update')
def update_transaction(req: UpdateRequest):
    client = _get_client()
    raw_split = _get_raw_split(req.group_id)
    try:
        client.update_transaction(
            group_id=req.group_id,
            raw_split=raw_split,
            category_name=req.category_name,
            budget_name=req.budget_name,
            destination_name=req.destination_name,
        )
        return {'ok': True}
    except Exception as e:
        raise HTTPException(502, f'Uppdatering misslyckades: {e}')


@app.post('/api/transactions/batch-update')
def batch_update(req: BatchUpdateRequest):
    client = _get_client()
    results = []
    for item in req.updates:
        try:
            raw_split = _get_raw_split(item.group_id)
            client.update_transaction(
                group_id=item.group_id,
                raw_split=raw_split,
                category_name=item.category_name,
                budget_name=item.budget_name,
                destination_name=item.destination_name,
            )
            results.append({'group_id': item.group_id, 'ok': True})
        except Exception as e:
            results.append({'group_id': item.group_id, 'ok': False, 'error': str(e)})
    return results


# ── Firefly III Rule Automation ───────────────────────────────────────────────

@app.post('/api/rules/create')
def create_rules(req: CreateRulesRequest):
    """Create Firefly III rules that auto-categorize future matching transactions.

    For each saved transaction, a rule is created that:
      - Trigger: transaction description contains the key words
      - Actions: set category, budget, and/or destination account
    """
    client = _get_client()
    raw_splits = _state.get('raw_splits', {})
    created, skipped, errors = [], [], []

    for gid in req.group_ids:
        split = raw_splits.get(gid)
        if not split:
            skipped.append(gid)
            continue

        description = split.get('description', '').strip()
        category_name = split.get('category_name', '').strip()
        budget_name = split.get('budget_name', '').strip()
        destination_name = split.get('destination_name', '').strip()

        if not description:
            skipped.append(gid)
            continue

        # Build actions list – only include fields that are actually set
        actions = []
        if category_name:
            actions.append({'action': 'set_category', 'value': category_name})
        if budget_name:
            actions.append({'action': 'set_budget', 'value': budget_name})
        if destination_name:
            actions.append({'action': 'set_destination_account', 'value': destination_name})

        if not actions:
            skipped.append(gid)
            continue

        rule_payload = {
            'title': f'Auto: {description[:60]}',
            'description': f'Skapad automatiskt av Firefly Kategoriserare från transaktion {gid}',
            'order': 0,
            'active': True,
            'strict': False,
            'stop_processing': False,
            'trigger': 'store-journal',
            'triggers': [
                {
                    'type': 'description_contains',
                    'value': description,
                    'active': True,
                    'stop_processing': False,
                }
            ],
            'actions': actions,
        }

        try:
            result = client.create_rule(rule_payload)
            created.append({'group_id': gid, 'rule_id': result.get('data', {}).get('id')})
        except Exception as e:
            errors.append({'group_id': gid, 'error': str(e)})

    return {'created': created, 'skipped': skipped, 'errors': errors}


@app.get('/api/rules')
def list_rules():
    """Return existing Firefly III rules."""
    client = _get_client()
    try:
        return client.get_rules()
    except Exception as e:
        raise HTTPException(502, f'Fel vid hämtning av regler: {e}')


# ── Duplicate detection ───────────────────────────────────────────────────────

@app.get('/api/duplicates')
def find_duplicates(days: int = 30, amount_tolerance: float = 0.01):
    """Detect likely duplicate transactions.

    Two transactions are considered potential duplicates when:
      - They share the same amount (within tolerance)
      - Their dates are within 3 days of each other
      - They have the same source account

    Returns groups of suspect transactions with a suggested action.
    """
    client = _get_client()
    try:
        # Fetch a broader window to catch cross-month duplicates
        end = date.today()
        start = end - timedelta(days=days)
        transactions = client.get_transactions(
            limit=500,
            transaction_type='withdrawal',
        )
    except Exception as e:
        raise HTTPException(502, f'Fel vid hämtning: {e}')

    # Cache raw splits for later resolution
    raw_splits: dict = _state.setdefault('raw_splits', {})
    for txn in transactions:
        raw_splits[txn['group_id']] = txn['_raw_split']

    # Group by (source_account, rounded_amount) for O(n) grouping
    buckets: dict = defaultdict(list)
    for txn in transactions:
        amt_key = round(txn['amount'] / (amount_tolerance + 1e-9)) * (amount_tolerance + 1e-9)
        amt_key = round(txn['amount'], 2)
        key = (txn.get('source_name', ''), amt_key)
        buckets[key].append(txn)

    groups = []
    for (source, amount), members in buckets.items():
        if len(members) < 2:
            continue
        # Within a bucket, find pairs whose dates are within 3 days
        members_sorted = sorted(members, key=lambda t: t.get('date', ''))
        for i in range(len(members_sorted)):
            for j in range(i + 1, len(members_sorted)):
                a, b = members_sorted[i], members_sorted[j]
                try:
                    da = datetime.fromisoformat(a['date'][:10])
                    db = datetime.fromisoformat(b['date'][:10])
                    delta = abs((da - db).days)
                except Exception:
                    continue
                if delta <= 3:
                    # Score: 0 days apart + same description = very likely duplicate
                    same_desc = a['description'].lower() == b['description'].lower()
                    confidence = 'high' if (delta == 0 and same_desc) else ('medium' if same_desc or delta == 0 else 'low')
                    suggestion = (
                        'Troligen dubblett – överväg att ta bort en av dem'
                        if confidence == 'high' else
                        'Möjlig dubblett – granska manuellt'
                    )
                    groups.append({
                        'confidence': confidence,
                        'suggestion': suggestion,
                        'delta_days': delta,
                        'transactions': [_safe_txn(a), _safe_txn(b)],
                    })

    # Deduplicate groups (A-B and B-A are the same)
    seen = set()
    unique_groups = []
    for g in groups:
        key = tuple(sorted(t['group_id'] for t in g['transactions']))
        if key not in seen:
            seen.add(key)
            unique_groups.append(g)

    # Sort by confidence: high first
    order = {'high': 0, 'medium': 1, 'low': 2}
    unique_groups.sort(key=lambda g: order.get(g['confidence'], 9))
    return unique_groups


@app.post('/api/duplicates/resolve')
def resolve_duplicate(req: ResolveDuplicateRequest):
    """Delete the duplicate transaction, keeping the specified one."""
    client = _get_client()
    try:
        client.delete_transaction(req.delete_group_id)
        return {'ok': True, 'deleted': req.delete_group_id, 'kept': req.keep_group_id}
    except Exception as e:
        raise HTTPException(502, f'Borttagning misslyckades: {e}')


# ── Static files & SPA ────────────────────────────────────────────────────────

if STATIC_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.get('/', response_class=HTMLResponse)
def index():
    html_file = STATIC_DIR / 'index.html'
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding='utf-8'))
    raise HTTPException(404, 'index.html saknas')
