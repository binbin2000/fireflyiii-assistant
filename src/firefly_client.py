"""Firefly III REST API client."""

import requests
from typing import Optional


class FireflyClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> dict:
        r = self.session.get(f"{self.base_url}/api/v1/{path}", params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict) -> dict:
        r = self.session.post(f"{self.base_url}/api/v1/{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()

    def _put(self, path: str, data: dict) -> dict:
        r = self.session.put(f"{self.base_url}/api/v1/{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> None:
        r = self.session.delete(f"{self.base_url}/api/v1/{path}", timeout=30)
        r.raise_for_status()

    # ── Connection ────────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        return self._get("about").get("data", {})

    # ── Transactions ──────────────────────────────────────────────────────────

    def get_transactions(self, limit: int = 100, page: int = 1, tx_type: str = "withdrawal") -> list:
        data = self._get("transactions", {"limit": limit, "page": page, "type": tx_type})
        return self._flatten(data.get("data", []))

    def _flatten(self, raw: list) -> list:
        result = []
        for item in raw:
            gid = item["id"]
            for sp in item.get("attributes", {}).get("transactions", []):
                if sp.get("reconciled"):
                    continue
                result.append({
                    "group_id": gid,
                    "description": sp.get("description", ""),
                    "amount": float(sp.get("amount") or 0),
                    "date": sp.get("date", ""),
                    "type": sp.get("type", "withdrawal"),
                    "category_id": sp.get("category_id"),
                    "category_name": sp.get("category_name") or "",
                    "budget_id": sp.get("budget_id"),
                    "budget_name": sp.get("budget_name") or "",
                    "destination_name": sp.get("destination_name") or "",
                    "source_name": sp.get("source_name") or "",
                    "currency_code": sp.get("currency_code") or "kr",
                    "notes": sp.get("notes") or "",
                    "tags": sp.get("tags") or [],
                    "_raw": sp,
                })
        return result

    def get_uncategorized(self, limit: int = 50) -> list:
        found, page = [], 1
        while len(found) < limit:
            batch = self.get_transactions(limit=100, page=page)
            if not batch:
                break
            found.extend(t for t in batch if not t["category_id"])
            if len(batch) < 100:
                break
            page += 1
            if page > 5:
                break
        return found[:limit]

    def get_categorized(self, limit: int = 100) -> list:
        found, page = [], 1
        per_page = 50
        while len(found) < limit:
            batch = self.get_transactions(limit=per_page, page=page)
            if not batch:
                break
            found.extend(t for t in batch if t["category_id"] and t["category_name"])
            if len(batch) < per_page:
                break
            page += 1
            if page > 6:
                break
        return found[:limit]

    def update_transaction(self, group_id: str, raw: dict,
                           category_name: Optional[str] = None,
                           budget_name: Optional[str] = None,
                           destination_name: Optional[str] = None) -> dict:
        date_str = (raw.get("date") or "")[:10]
        if not date_str:
            raise ValueError("missing date")
        sp: dict = {
            "type": raw.get("type", "withdrawal"),
            "date": date_str,
            "amount": str(raw.get("amount", "")),
            "description": raw.get("description", ""),
        }
        for field in ("source_id", "source_name", "destination_id", "destination_name",
                      "currency_code", "notes", "tags", "category_name", "budget_name"):
            if raw.get(field):
                sp[field] = raw[field]
        if category_name is not None:
            sp["category_name"] = category_name
            sp.pop("category_id", None)
        if budget_name is not None:
            sp["budget_name"] = budget_name
            sp.pop("budget_id", None)
        if destination_name is not None:
            sp["destination_name"] = destination_name
            sp.pop("destination_id", None)
        return self._put(f"transactions/{group_id}", {
            "apply_rules": True, "fire_webhooks": False, "transactions": [sp]
        })

    def delete_transaction(self, group_id: str) -> None:
        self._delete(f"transactions/{group_id}")

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_categories(self) -> list:
        data = self._get("categories", {"limit": 100})
        return [{"id": c["id"], "name": c["attributes"]["name"]} for c in data.get("data", [])]

    def get_budgets(self) -> list:
        data = self._get("budgets", {"limit": 100})
        return [{"id": b["id"], "name": b["attributes"]["name"]}
                for b in data.get("data", []) if b["attributes"].get("active", True)]

    def get_budget_limits(self, budget_id: str, start: str, end: str) -> list:
        data = self._get(f"budgets/{budget_id}/limits", {"start": start, "end": end})
        result = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            result.append({
                "id": item["id"],
                "budget_id": str(attrs.get("budget_id", "")),
                "start": (attrs.get("start") or "")[:10],
                "end": (attrs.get("end") or "")[:10],
                "amount": float(attrs.get("amount") or 0),
                "currency_code": attrs.get("currency_code", ""),
            })
        return result

    def create_budget_limit(self, budget_id: str, start: str, end: str, amount: float) -> dict:
        data = self._post(f"budgets/{budget_id}/limits", {
            "start": start, "end": end, "amount": str(amount), "period": "monthly",
        })
        item = data.get("data", {})
        attrs = item.get("attributes", {})
        return {"id": item.get("id"), "amount": float(attrs.get("amount") or 0)}

    def update_budget_limit(self, limit_id: str, budget_id: str, start: str, end: str, amount: float) -> dict:
        # DELETE + recreate: the PUT /budget-limits/{id} endpoint is absent in some Firefly versions
        self._delete(f"budget-limits/{limit_id}")
        return self.create_budget_limit(budget_id, start, end, amount)

    def delete_budget_limit(self, limit_id: str) -> None:
        self._delete(f"budget-limits/{limit_id}")

    # ── Rules ─────────────────────────────────────────────────────────────────

    def get_rules(self) -> list:
        data = self._get("rules", {"limit": 100})
        return [{"id": r["id"],
                 "title": r["attributes"].get("title", ""),
                 "active": r["attributes"].get("active", False),
                 "trigger": r["attributes"].get("trigger", "")}
                for r in data.get("data", [])]

    def create_rule(self, payload: dict) -> dict:
        return self._post("rules", payload)
