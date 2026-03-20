"""
Mock search provider for local/prototype use when live web search is unavailable.
Returns structured, explainable mock data with source references.
"""
from __future__ import annotations

from typing import Any

from .search_provider import SearchProvider


class MockSearchProvider(SearchProvider):
    """Mock provider returning structured risk signals for prototype testing."""

    @property
    def is_available(self) -> bool:
        return False  # Indicates mock, not live search

    def search_company_news(self, company_name: str, sector: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "title": f"{company_name} FY24 results announced",
                "snippet": f"Company reported steady performance. Sector outlook {sector or 'mixed'}.",
                "url": "https://mock.example.com/news/1",
                "source": "mock_provider",
                "relevance_score": 0.85,
            },
            {
                "title": f"{company_name} expansion plans",
                "snippet": "Management indicated capacity expansion in pipeline.",
                "url": "https://mock.example.com/news/2",
                "source": "mock_provider",
                "relevance_score": 0.6,
            },
        ]

    def search_promoter_news(self, promoter_names: list[str], company_name: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for name in (promoter_names or [])[:3]:
            results.append({
                "title": f"Profile: {name}",
                "snippet": f"Promoter of {company_name}. No adverse news in mock dataset.",
                "url": "https://mock.example.com/promoter",
                "source": "mock_provider",
                "relevance_score": 0.7,
            })
        if not results:
            results.append({
                "title": f"Promoters of {company_name}",
                "snippet": "No promoter-specific news in mock dataset.",
                "url": "https://mock.example.com/promoters",
                "source": "mock_provider",
                "relevance_score": 0.5,
            })
        return results

    def search_sector_regulatory(self, sector: str) -> list[dict[str, Any]]:
        return [
            {
                "title": f"{sector or 'Industry'} regulatory update",
                "snippet": "New norms may impact compliance costs. Mock regulatory context.",
                "url": "https://mock.example.com/regulatory",
                "source": "mock_provider",
                "relevance_score": 0.75,
            },
        ]

    def search_litigation_reputation(self, company_name: str, promoter_names: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "title": f"Legal search: {company_name}",
                "snippet": "No active litigation found in mock search. Check uploaded documents for disclosed cases.",
                "url": "https://mock.example.com/litigation",
                "source": "mock_provider",
                "relevance_score": 0.8,
            },
        ]
