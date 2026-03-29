"""Local pattern-matching engine for transaction categorization.

All computation is done against your own Firefly III history.
No data is sent anywhere.
"""

from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz, process


@dataclass
class Suggestion:
    category_name: Optional[str] = None
    budget_name: Optional[str] = None
    destination_name: Optional[str] = None
    confidence: float = 0.0
    source: str = 'none'           # 'history', 'ai_local', 'ai_cloud', 'manual'
    reasoning: str = ''
    matched_description: str = ''

    def has_any(self) -> bool:
        return any([self.category_name, self.budget_name, self.destination_name])

    def to_dict(self) -> dict:
        return {
            'category_name': self.category_name,
            'budget_name': self.budget_name,
            'destination_name': self.destination_name,
            'confidence': round(self.confidence, 2),
            'source': self.source,
            'reasoning': self.reasoning,
            'matched_description': self.matched_description,
        }

    @staticmethod
    def empty() -> 'Suggestion':
        return Suggestion(source='none', reasoning='Ingen matchning hittades')


class HistoryMatcher:
    """Suggest categorization by fuzzy-matching against historical transactions.

    100% local – no network calls.
    """

    def __init__(self, history: list, fuzzy_threshold: int = 75):
        self.fuzzy_threshold = fuzzy_threshold
        self._index: dict = {}  # normalized_description -> list of categorizations
        self._build_index(history)

    def _build_index(self, history: list):
        for txn in history:
            desc = (txn.get('description') or '').strip().lower()
            if not desc:
                continue
            if desc not in self._index:
                self._index[desc] = []
            self._index[desc].append({
                'category_name': txn.get('category_name') or '',
                'budget_name': txn.get('budget_name') or '',
                'destination_name': txn.get('destination_name') or '',
            })

    def suggest(self, description: str) -> Suggestion:
        if not self._index or not description:
            return Suggestion.empty()

        desc_lower = description.lower()
        history_keys = list(self._index.keys())

        result = process.extractOne(
            desc_lower,
            history_keys,
            scorer=fuzz.token_set_ratio,
            score_cutoff=self.fuzzy_threshold,
        )
        if not result:
            return Suggestion.empty()

        matched_key, score, _ = result
        entries = self._index[matched_key]
        if not entries:
            return Suggestion.empty()

        # Use the most recent matching entry
        best = entries[-1]
        return Suggestion(
            category_name=best['category_name'] or None,
            budget_name=best['budget_name'] or None,
            destination_name=best['destination_name'] or None,
            confidence=round(score / 100.0, 2),
            source='history',
            reasoning=f'Matchar "{matched_key}" ({score:.0f}% likhet)',
            matched_description=matched_key,
        )

    def top_matches(self, description: str, n: int = 5) -> list:
        """Return the top-n fuzzy matches with their categorization data."""
        if not self._index or not description:
            return []
        results = process.extract(
            description.lower(),
            list(self._index.keys()),
            scorer=fuzz.token_set_ratio,
            limit=n,
            score_cutoff=40,
        )
        out = []
        for key, score, _ in results:
            entry = self._index[key][-1]
            out.append({
                'description': key,
                'score': score,
                **entry,
            })
        return out
