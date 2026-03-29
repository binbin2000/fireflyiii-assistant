"""AI-powered suggestion layer (optional).

Supports:
  - Anthropic Claude API  (ANTHROPIC_API_KEY)  – data sent to Anthropic servers
  - Ollama local LLM      (OLLAMA_URL)          – 100% local, no external calls

If neither is configured the caller falls back to local pattern matching only.
"""

import json
import re
from typing import Optional

from .matcher import Suggestion


# ─── Shared prompt builder ────────────────────────────────────────────────────

def _build_prompt(
    description: str,
    amount_range: str,
    categories: list,
    budgets: list,
    examples: list,
) -> str:
    """Build the categorization prompt.

    Privacy note: only description, amount_range (not exact), month/year,
    and your own category/budget names are included. No account names.
    """
    cat_list = '\n'.join(f'  - {c["name"]}' for c in categories)
    budget_list = '\n'.join(f'  - {b["name"]}' for b in budgets)
    example_lines = '\n'.join(
        f'  - "{e["description"]}" ({e.get("amount_range","")}) '
        f'→ {e.get("category_name","-")} / {e.get("budget_name","-")}'
        for e in examples
    )

    return f"""Du är en assistent som kategoriserar hushållstransaktioner.

TRANSAKTION:
  Beskrivning : {description}
  Beloppsintervall: {amount_range}

TILLGÄNGLIGA KATEGORIER:
{cat_list or '  (inga)'}

TILLGÄNGLIGA BUDGETAR:
{budget_list or '  (inga)'}

EXEMPEL FRÅN HISTORIKEN:
{example_lines or '  (inga)'}

Svara ENBART med ett JSON-objekt. Välj ENDAST från kategori/budgetlistorna.
destination_name kan vara ett rimligt leverantörsnamn (du hittar på det baserat på beskrivningen).
Använd null för fält du är osäker på.

{{
  "category_name": "exakt kategorinamn eller null",
  "budget_name": "exakt budgetnamn eller null",
  "destination_name": "leverantörsnamn eller null",
  "confidence": 0.0,
  "reasoning": "kort motivering på svenska"
}}"""


def _amount_range(amount: float) -> str:
    """Coarsen exact amount to a range for privacy."""
    if amount < 50:
        return '<50 kr'
    elif amount < 200:
        return '50–200 kr'
    elif amount < 500:
        return '200–500 kr'
    elif amount < 1000:
        return '500–1000 kr'
    elif amount < 5000:
        return '1000–5000 kr'
    else:
        return '>5000 kr'


def _parse_json_response(text: str) -> dict:
    """Extract and parse JSON from a model response."""
    # Strip markdown fences
    text = re.sub(r'```(?:json)?', '', text).strip('`').strip()
    return json.loads(text)


def _normalize_name(value: Optional[str], lookup_list: list) -> Optional[str]:
    """Return the correctly-cased name if it exists in lookup_list."""
    if not value:
        return None
    lower = value.lower()
    exact = next((item['name'] for item in lookup_list if item['name'].lower() == lower), None)
    if exact:
        return exact
    # Starts-with fallback
    starts = next((item['name'] for item in lookup_list if item['name'].lower().startswith(lower)), None)
    return starts


# ─── Claude API backend ───────────────────────────────────────────────────────

class ClaudeCategorizer:
    """Uses Anthropic Claude API for suggestions.

    Privacy notice: transaction descriptions are sent to Anthropic.
    Exact amounts are replaced with ranges. Account names are NOT sent.
    """

    def __init__(self, api_key: str):
        import anthropic  # Optional dependency
        self.client = anthropic.Anthropic(api_key=api_key)

    def suggest(
        self,
        transaction: dict,
        categories: list,
        budgets: list,
        history_examples: list,
    ) -> Suggestion:
        prompt = _build_prompt(
            description=transaction['description'],
            amount_range=_amount_range(transaction['amount']),
            categories=categories,
            budgets=budgets,
            examples=history_examples,
        )
        try:
            with self.client.messages.stream(
                model='claude-opus-4-6',
                max_tokens=400,
                thinking={'type': 'adaptive'},
                messages=[{'role': 'user', 'content': prompt}],
            ) as stream:
                response = stream.get_final_message()

            text = next((b.text for b in response.content if b.type == 'text'), '')
            data = _parse_json_response(text)

            cat_name = _normalize_name(data.get('category_name'), categories)
            budget_name = _normalize_name(data.get('budget_name'), budgets)

            return Suggestion(
                category_name=cat_name,
                budget_name=budget_name,
                destination_name=data.get('destination_name') or None,
                confidence=float(data.get('confidence', 0.5)),
                source='ai_cloud',
                reasoning=data.get('reasoning', ''),
            )
        except Exception as e:
            return Suggestion(source='ai_cloud', confidence=0.0, reasoning=f'Fel: {e}')


# ─── Ollama backend ───────────────────────────────────────────────────────────

class OllamaCategorizer:
    """Uses a local Ollama LLM for suggestions. Zero external network calls.

    Install: https://ollama.com
    Pull a model: ollama pull llama3
    """

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def suggest(
        self,
        transaction: dict,
        categories: list,
        budgets: list,
        history_examples: list,
    ) -> Suggestion:
        import requests  # Already a dependency

        prompt = _build_prompt(
            description=transaction['description'],
            amount_range=_amount_range(transaction['amount']),
            categories=categories,
            budgets=budgets,
            examples=history_examples,
        )
        try:
            resp = requests.post(
                f'{self.base_url}/api/generate',
                json={'model': self.model, 'prompt': prompt, 'stream': False, 'format': 'json'},
                timeout=60,
            )
            resp.raise_for_status()
            data = _parse_json_response(resp.json().get('response', '{}'))

            cat_name = _normalize_name(data.get('category_name'), categories)
            budget_name = _normalize_name(data.get('budget_name'), budgets)

            return Suggestion(
                category_name=cat_name,
                budget_name=budget_name,
                destination_name=data.get('destination_name') or None,
                confidence=float(data.get('confidence', 0.5)),
                source='ai_local',
                reasoning=data.get('reasoning', ''),
            )
        except Exception as e:
            return Suggestion(source='ai_local', confidence=0.0, reasoning=f'Fel: {e}')
