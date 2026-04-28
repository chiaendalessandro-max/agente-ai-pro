from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

APOLLO_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_companies/search"


class ApolloProvider:
    def __init__(self, api_key: str, timeout_seconds: int = 5) -> None:
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = max(1, int(timeout_seconds or 5))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_organizations(
        self,
        query: str,
        country: str,
        sector: str,
        limit: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not self.is_configured():
            return [], {"apollo_status": "disabled", "raw_results_count": 0}

        target = max(1, min(int(limit or 10), 50))
        per_page = min(25, target)
        page = 1
        rows: list[dict[str, Any]] = []
        meta: dict[str, Any] = {
            "apollo_status": "ok",
            "raw_results_count": 0,
            "apollo_pages_used": 0,
            "apollo_rate_limited": False,
        }

        while len(rows) < target and page <= 3:
            payload = {
                "api_key": self.api_key,
                "q_organization_name": query or "",
                "person_titles": [],
                "organization_num_employees_ranges": [],
                "page": page,
                "per_page": per_page,
            }
            if country:
                payload["organization_locations"] = [country]
            if sector:
                payload["q_keywords"] = sector

            try:
                response = requests.post(APOLLO_SEARCH_URL, json=payload, timeout=self.timeout_seconds)
                if response.status_code == 429:
                    logger.warning("Apollo rate limit hit (429)")
                    meta["apollo_status"] = "rate_limited"
                    meta["apollo_rate_limited"] = True
                    break
                if response.status_code in {401, 402, 403}:
                    logger.warning("Apollo auth/credits error status=%s", response.status_code)
                    meta["apollo_status"] = "auth_or_credits_error"
                    break
                if response.status_code >= 400:
                    logger.warning("Apollo http error status=%s", response.status_code)
                    meta["apollo_status"] = "http_error"
                    break

                data = response.json() if response.content else {}
                api_rows = data.get("organizations") or data.get("accounts") or []
                if not isinstance(api_rows, list):
                    api_rows = []
                rows.extend([r for r in api_rows if isinstance(r, dict)])
                meta["apollo_pages_used"] = page
                meta["raw_results_count"] = len(rows)
                if not api_rows:
                    break
                page += 1
                time.sleep(0.05)
            except requests.Timeout:
                logger.warning("Apollo timeout after %ss", self.timeout_seconds)
                meta["apollo_status"] = "timeout"
                break
            except Exception as exc:
                logger.warning("Apollo request failed: %s", str(exc)[:200])
                meta["apollo_status"] = "request_error"
                break

        return rows[:target], meta
