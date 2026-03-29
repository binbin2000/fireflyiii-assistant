"""Firefly III API client."""

import requests
from typing import Optional


class FireflyClient:
    """Client for the Firefly III REST API."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })

    def test_connection(self) -> dict:
        """Verify API connectivity and token validity."""
        data = self._get('about')
        return data.get('data', {})

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.base_url}/api/v1/{endpoint}"
        resp = self.session.get(url, params=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _put(self, endpoint: str, data: dict) -> dict:
        url = f"{self.base_url}/api/v1/{endpoint}"
        resp = self.session.put(url, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_transactions(
        self,
        limit: int = 50,
        page: int = 1,
        transaction_type: str = 'withdrawal',
    ) -> list:
        """Fetch transactions and return list of flattened splits."""
        params = {'limit': limit, 'page': page, 'type': transaction_type}
        data = self._get('transactions', params)
        return self._flatten_transactions(data.get('data', []))

    def _flatten_transactions(self, raw: list) -> list:
        """Flatten grouped transaction entries into individual splits."""
        result = []
        for item in raw:
            group_id = item['id']
            attrs = item.get('attributes', {})
            for split in attrs.get('transactions', []):
                if split.get('reconciled'):
                    continue
                result.append({
                    'group_id': group_id,
                    'journal_id': split.get('transaction_journal_id'),
                    'description': split.get('description', ''),
                    'amount': float(split.get('amount', 0) or 0),
                    'date': split.get('date', ''),
                    'type': split.get('type', 'withdrawal'),
                    'category_id': split.get('category_id'),
                    'category_name': split.get('category_name') or '',
                    'budget_id': split.get('budget_id'),
                    'budget_name': split.get('budget_name') or '',
                    'destination_id': split.get('destination_id'),
                    'destination_name': split.get('destination_name') or '',
                    'source_id': split.get('source_id'),
                    'source_name': split.get('source_name') or '',
                    'notes': split.get('notes') or '',
                    'tags': split.get('tags') or [],
                    'currency_code': split.get('currency_code') or '',
                    '_raw_split': split,
                })
        return result

    def get_uncategorized_transactions(self, limit: int = 50) -> list:
        """Get withdrawal transactions that have no category assigned."""
        # Fetch more pages if needed to find enough uncategorized ones
        result = []
        page = 1
        while len(result) < limit:
            batch = self.get_transactions(limit=100, page=page)
            if not batch:
                break
            result.extend(t for t in batch if not t['category_id'])
            if len(batch) < 100:
                break
            page += 1
            if page > 5:
                break
        return result[:limit]

    def get_all_recent_transactions(self, limit: int = 50) -> list:
        """Get recent transactions (all, including categorized)."""
        return self.get_transactions(limit=limit)

    def get_recent_categorized_transactions(self, limit: int = 300) -> list:
        """Get recent transactions that have categories (for pattern learning)."""
        transactions = self.get_transactions(limit=limit)
        return [t for t in transactions if t['category_id'] and t['category_name']]

    def get_categories(self) -> list:
        """Fetch all categories."""
        data = self._get('categories', {'limit': 100})
        return [
            {'id': c['id'], 'name': c['attributes']['name']}
            for c in data.get('data', [])
        ]

    def get_budgets(self) -> list:
        """Fetch all active budgets."""
        data = self._get('budgets', {'limit': 100})
        return [
            {'id': b['id'], 'name': b['attributes']['name']}
            for b in data.get('data', [])
            if b['attributes'].get('active', True)
        ]

    def get_expense_accounts(self) -> list:
        """Fetch expense accounts (vendors/stores)."""
        data = self._get('accounts', {'limit': 200, 'type': 'expense'})
        return [
            {'id': a['id'], 'name': a['attributes']['name']}
            for a in data.get('data', [])
        ]

    def update_transaction(
        self,
        group_id: str,
        raw_split: dict,
        category_name: Optional[str] = None,
        budget_name: Optional[str] = None,
        destination_name: Optional[str] = None,
    ) -> dict:
        """Update a transaction split with new categorization data."""
        date_str = (raw_split.get('date') or '')[:10] or None
        if not date_str:
            raise ValueError('Transaction is missing date')

        update_split: dict = {
            'type': raw_split.get('type', 'withdrawal'),
            'date': date_str,
            'amount': str(raw_split.get('amount', '')),
            'description': raw_split.get('description', ''),
        }

        # Source account
        if raw_split.get('source_id'):
            update_split['source_id'] = raw_split['source_id']
        elif raw_split.get('source_name'):
            update_split['source_name'] = raw_split['source_name']

        # Destination / vendor
        if destination_name:
            update_split['destination_name'] = destination_name
        elif raw_split.get('destination_id'):
            update_split['destination_id'] = raw_split['destination_id']
        elif raw_split.get('destination_name'):
            update_split['destination_name'] = raw_split['destination_name']

        # Category
        if category_name:
            update_split['category_name'] = category_name
        elif raw_split.get('category_name'):
            update_split['category_name'] = raw_split['category_name']

        # Budget
        if budget_name:
            update_split['budget_name'] = budget_name
        elif raw_split.get('budget_name'):
            update_split['budget_name'] = raw_split['budget_name']

        # Preserve other metadata
        if raw_split.get('currency_code'):
            update_split['currency_code'] = raw_split['currency_code']
        if raw_split.get('notes'):
            update_split['notes'] = raw_split['notes']
        if raw_split.get('tags'):
            update_split['tags'] = raw_split['tags']

        payload = {
            'apply_rules': True,
            'fire_webhooks': False,
            'transactions': [update_split],
        }
        return self._put(f'transactions/{group_id}', payload)

    def delete_transaction(self, group_id: str) -> None:
        """Permanently delete a transaction group."""
        url = f"{self.base_url}/api/v1/transactions/{group_id}"
        resp = self.session.delete(url, timeout=30)
        resp.raise_for_status()

    # ── Rules (automations) ───────────────────────────────────────────────────

    def get_rules(self) -> list:
        """Fetch all existing rules."""
        data = self._get('rules', {'limit': 100})
        return [
            {
                'id': r['id'],
                'title': r['attributes'].get('title', ''),
                'active': r['attributes'].get('active', False),
                'description': r['attributes'].get('description', ''),
                'trigger': r['attributes'].get('trigger', ''),
            }
            for r in data.get('data', [])
        ]

    def create_rule(self, payload: dict) -> dict:
        """Create a new rule.

        payload must follow the Firefly III rule schema:
        {
          title, trigger, triggers: [{type, value, active, stop_processing}],
          actions: [{action, value}], active, strict, stop_processing
        }
        """
        url = f"{self.base_url}/api/v1/rules"
        resp = self.session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
