"""Optional AI backends for categorization (Claude API or local Ollama)."""

import json, re
from typing import Optional
from .matcher import Suggestion


def _amount_range(amount: float) -> str:
    if amount < 50:    return "<50 kr"
    if amount < 200:   return "50–200 kr"
    if amount < 500:   return "200–500 kr"
    if amount < 1000:  return "500–1000 kr"
    if amount < 5000:  return "1000–5000 kr"
    return ">5000 kr"


def _build_prompt(description: str, amount_range: str, categories: list,
                  budgets: list, examples: list) -> str:
    cats = "\n".join(f"  - {c['name']}" for c in categories) or "  (inga)"
    buds = "\n".join(f"  - {b['name']}" for b in budgets) or "  (inga)"
    exs  = "\n".join(
        f'  - "{e["description"]}" ({e.get("amount_range","")}) '
        f'→ {e.get("category_name","-")} / {e.get("budget_name","-")}'
        for e in examples
    ) or "  (inga)"
    return f"""Du kategoriserar hushållstransaktioner i Firefly III.

TRANSAKTION:
  Beskrivning: {description}
  Belopp: {amount_range}

KATEGORIER:
{cats}

BUDGETAR:
{buds}

HISTORIK:
{exs}

Svara ENBART med JSON. Välj från kategori/budgetlistorna. destination_name kan vara nytt namn.
{{"category_name":null,"budget_name":null,"destination_name":null,"confidence":0.0,"reasoning":""}}"""


def _parse(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip("`").strip()
    return json.loads(text)


def _normalize(value: Optional[str], lst: list) -> Optional[str]:
    if not value:
        return None
    lower = value.lower()
    for item in lst:
        if item["name"].lower() == lower:
            return item["name"]
    for item in lst:
        if item["name"].lower().startswith(lower):
            return item["name"]
    return None


class ClaudeCategorizer:
    """Sends description (not amounts/account names) to Anthropic Claude API."""

    def __init__(self, api_key: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def suggest(self, txn: dict, categories: list, budgets: list, examples: list) -> Suggestion:
        prompt = _build_prompt(txn["description"], _amount_range(txn["amount"]),
                               categories, budgets, examples)
        try:
            with self._client.messages.stream(
                model="claude-opus-4-6", max_tokens=400,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": prompt}],
            ) as s:
                resp = s.get_final_message()
            text = next((b.text for b in resp.content if b.type == "text"), "")
            d = _parse(text)
            return Suggestion(
                category_name=_normalize(d.get("category_name"), categories),
                budget_name=_normalize(d.get("budget_name"), budgets),
                destination_name=d.get("destination_name") or None,
                confidence=float(d.get("confidence", 0.5)),
                source="ai_cloud",
                reasoning=d.get("reasoning", ""),
            )
        except Exception as e:
            return Suggestion(source="ai_cloud", confidence=0.0, reasoning=f"Fel: {e}")


class OllamaCategorizer:
    """Fully local LLM via Ollama – zero external network calls."""

    def __init__(self, base_url: str, model: str):
        import requests as _r
        self._requests = _r
        self._url = base_url.rstrip("/") + "/api/generate"
        self._model = model

    def suggest(self, txn: dict, categories: list, budgets: list, examples: list) -> Suggestion:
        prompt = _build_prompt(txn["description"], _amount_range(txn["amount"]),
                               categories, budgets, examples)
        try:
            r = self._requests.post(
                self._url, json={"model": self._model, "prompt": prompt,
                                 "stream": False, "format": "json"}, timeout=60)
            r.raise_for_status()
            d = _parse(r.json().get("response", "{}"))
            return Suggestion(
                category_name=_normalize(d.get("category_name"), categories),
                budget_name=_normalize(d.get("budget_name"), budgets),
                destination_name=d.get("destination_name") or None,
                confidence=float(d.get("confidence", 0.5)),
                source="ai_local",
                reasoning=d.get("reasoning", ""),
            )
        except Exception as e:
            return Suggestion(source="ai_local", confidence=0.0, reasoning=f"Fel: {e}")
