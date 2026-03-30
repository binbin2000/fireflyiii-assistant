"""Local-only fuzzy pattern matcher – no network calls."""

from dataclasses import dataclass
from typing import Optional
from rapidfuzz import fuzz, process


@dataclass
class Suggestion:
    category_name: Optional[str] = None
    budget_name: Optional[str] = None
    destination_name: Optional[str] = None
    confidence: float = 0.0
    source: str = "none"       # none | history | ai_local | ai_cloud | manual
    reasoning: str = ""
    matched_description: str = ""

    def has_any(self) -> bool:
        return any([self.category_name, self.budget_name, self.destination_name])

    def to_dict(self) -> dict:
        return {
            "category_name": self.category_name,
            "budget_name": self.budget_name,
            "destination_name": self.destination_name,
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "reasoning": self.reasoning,
            "matched_description": self.matched_description,
        }

    @staticmethod
    def empty() -> "Suggestion":
        return Suggestion(source="none", reasoning="Ingen matchning")


class HistoryMatcher:
    """Suggest categorization by fuzzy-matching transaction descriptions."""

    def __init__(self, history: list, threshold: int = 75):
        self._threshold = threshold
        self._index: dict = {}
        for t in history:
            desc = (t.get("description") or "").strip().lower()
            if not desc:
                continue
            self._index.setdefault(desc, []).append({
                "category_name": t.get("category_name") or "",
                "budget_name": t.get("budget_name") or "",
                "destination_name": t.get("destination_name") or "",
            })

    def suggest(self, description: str) -> Suggestion:
        if not self._index or not description:
            return Suggestion.empty()
        result = process.extractOne(
            description.lower(), list(self._index.keys()),
            scorer=fuzz.token_set_ratio, score_cutoff=self._threshold,
        )
        if not result:
            return Suggestion.empty()
        key, score, _ = result
        best = self._index[key][-1]
        return Suggestion(
            category_name=best["category_name"] or None,
            budget_name=best["budget_name"] or None,
            destination_name=best["destination_name"] or None,
            confidence=round(score / 100, 2),
            source="history",
            reasoning=f'Matchar "{key}" ({score:.0f}% likhet)',
            matched_description=key,
        )
