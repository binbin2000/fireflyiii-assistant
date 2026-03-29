"""FastAPI web application for the Firefly III transaction categorizer.

Runs entirely on localhost – no data leaves your machine unless an external
AI backend (Claude API) is explicitly configured.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .firefly_client import FireflyClient
from .matcher import HistoryMatcher, Suggestion
from .categorizer import ClaudeCategorizer, OllamaCategorizer

STATIC_DIR = Path(__file__).parent / 'static'

app = FastAPI(title='Firefly III Kategoriserare', docs_url=None, redoc_url=None)

# Lazy-initialized singletons (populated on first /api/init request)
_state: dict = {}


# ─── Pydantic models ──────────────────────────────────────────────────────────

class UpdateRequest(BaseModel):
    group_id: str
    raw_split: dict
    category_name: Optional[str] = None
    budget_name: Optional[str] = None
    destination_name: Optional[str] = None


class BatchUpdateRequest(BaseModel):
    updates: list[UpdateRequest]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_client() -> FireflyClient:
    if 'client' not in _state:
        raise HTTPException(503, 'Inte initialiserad – ladda om sidan')
    return _state['client']


def _ai_backend():
    """Return the configured AI backend, or None if not configured."""
    return _state.get('ai_backend')


def _build_history_examples(history: list, n: int = 10) -> list:
    """Pick the most recent categorized transactions as prompt examples."""
    from .categorizer import _amount_range
    examples = []
    for t in history[:n]:
        if t.get('category_name'):
            examples.append({
                'description': t['description'],
                'amount_range': _amount_range(t['amount']),
                'category_name': t.get('category_name', ''),
                'budget_name': t.get('budget_name', ''),
            })
    return examples


def _compute_suggestion(transaction: dict) -> dict:
    """Compute the best suggestion for a transaction (matcher + optional AI)."""
    matcher: HistoryMatcher = _state.get('matcher')
    categories = _state.get('categories', [])
    budgets = _state.get('budgets', [])
    history = _state.get('history', [])

    sg: Suggestion = Suggestion.empty()

    if matcher:
        sg = matcher.suggest(transaction['description'])

    # Use AI only if local matching is weak
    ai = _ai_backend()
    if ai and sg.confidence < 0.88:
        ai_sg = ai.suggest(
            transaction,
            categories,
            budgets,
            _build_history_examples(history),
        )
        if ai_sg.has_any() and ai_sg.confidence >= sg.confidence:
            sg = ai_sg

    return sg.to_dict()


# ─── API routes ───────────────────────────────────────────────────────────────

@app.get('/api/status')
def status():
    """Return the current configuration status."""
    ai_backend = _ai_backend()
    ai_type = 'none'
    if ai_backend:
        ai_type = 'cloud' if isinstance(ai_backend, ClaudeCategorizer) else 'local'

    return {
        'initialized': 'client' in _state,
        'ai_backend': ai_type,
        'categories_count': len(_state.get('categories', [])),
        'budgets_count': len(_state.get('budgets', [])),
        'history_count': len(_state.get('history', [])),
    }


@app.post('/api/init')
def init():
    """Initialize connections and load reference data."""
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

    # Configure AI backend
    ai_backend = None
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    ollama_url = os.getenv('OLLAMA_URL', '').strip()

    if ollama_url:
        model = os.getenv('OLLAMA_MODEL', 'llama3')
        ai_backend = OllamaCategorizer(ollama_url, model)
    elif anthropic_key:
        ai_backend = ClaudeCategorizer(anthropic_key)

    _state.update({
        'client': client,
        'categories': categories,
        'budgets': budgets,
        'history': history,
        'matcher': matcher,
        'ai_backend': ai_backend,
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


@app.get('/api/transactions')
def get_transactions(mode: str = 'uncategorized', limit: int = 50):
    """Return transactions with pre-computed suggestions."""
    client = _get_client()
    try:
        if mode == 'all':
            transactions = client.get_all_recent_transactions(limit=limit)
        else:
            transactions = client.get_uncategorized_transactions(limit=limit)
    except Exception as e:
        raise HTTPException(502, f'Fel vid hämtning: {e}')

    result = []
    for txn in transactions:
        suggestion = _compute_suggestion(txn)
        safe_txn = {k: v for k, v in txn.items() if not k.startswith('_')}
        result.append({'transaction': safe_txn, 'suggestion': suggestion})
    return result


@app.get('/api/metadata')
def get_metadata():
    """Return categories, budgets, and expense accounts for the edit form."""
    return {
        'categories': _state.get('categories', []),
        'budgets': _state.get('budgets', []),
    }


@app.post('/api/transactions/update')
def update_transaction(req: UpdateRequest):
    """Apply categorization to a single transaction."""
    client = _get_client()
    try:
        client.update_transaction(
            group_id=req.group_id,
            raw_split=req.raw_split,
            category_name=req.category_name,
            budget_name=req.budget_name,
            destination_name=req.destination_name,
        )
        return {'ok': True}
    except Exception as e:
        raise HTTPException(502, f'Uppdatering misslyckades: {e}')


@app.post('/api/transactions/batch-update')
def batch_update(req: BatchUpdateRequest):
    """Apply categorization to multiple transactions at once."""
    client = _get_client()
    results = []
    for item in req.updates:
        try:
            client.update_transaction(
                group_id=item.group_id,
                raw_split=item.raw_split,
                category_name=item.category_name,
                budget_name=item.budget_name,
                destination_name=item.destination_name,
            )
            results.append({'group_id': item.group_id, 'ok': True})
        except Exception as e:
            results.append({'group_id': item.group_id, 'ok': False, 'error': str(e)})
    return results


# ─── Static files & SPA ───────────────────────────────────────────────────────

if STATIC_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.get('/', response_class=HTMLResponse)
def index():
    html_file = STATIC_DIR / 'index.html'
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding='utf-8'))
    raise HTTPException(404, 'index.html saknas')
