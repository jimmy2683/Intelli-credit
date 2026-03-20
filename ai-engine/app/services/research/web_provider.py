"""
Optional live web search provider.
Falls back to MockSearchProvider when dependencies or API keys are unavailable.
"""
from __future__ import annotations

import logging
from typing import Any

from .mock_provider import MockSearchProvider
from .search_provider import SearchProvider

logger = logging.getLogger(__name__)


def get_search_provider() -> SearchProvider:
    """
    Return live search provider if available, else mock.
    Set env SEARCH_PROVIDER=mock to force mock. Set SEARCH_PROVIDER=live to attempt live.
    """
    import os

    if os.environ.get("SEARCH_PROVIDER", "").lower() == "mock":
        return MockSearchProvider()

    try:
        # Placeholder: add duckduckgo-search or similar when needed
        # from duckduckgo_search import DDGS
        # return LiveSearchProvider(DDGS())
        pass
    except ImportError:
        pass

    return MockSearchProvider()


class LiveSearchProvider(SearchProvider):
    """Stub for future live search. Extend with DDGS or news API."""

    @property
    def is_available(self) -> bool:
        return True

    def search_company_news(self, company_name: str, sector: str | None = None) -> list[dict[str, Any]]:
        return MockSearchProvider().search_company_news(company_name, sector)

    def search_promoter_news(self, promoter_names: list[str], company_name: str) -> list[dict[str, Any]]:
        return MockSearchProvider().search_promoter_news(promoter_names, company_name)

    def search_sector_regulatory(self, sector: str) -> list[dict[str, Any]]:
        return MockSearchProvider().search_sector_regulatory(sector)

    def search_litigation_reputation(self, company_name: str, promoter_names: list[str]) -> list[dict[str, Any]]:
        return MockSearchProvider().search_litigation_reputation(company_name, promoter_names)
