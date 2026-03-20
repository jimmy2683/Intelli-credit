"""
Pluggable search provider interface for secondary research.
Implement this interface to provide live web search or mock data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SearchProvider(ABC):
    """Abstract interface for secondary research search."""

    @abstractmethod
    def search_company_news(self, company_name: str, sector: str | None = None) -> list[dict[str, Any]]:
        """Search for company-related news. Returns list of {title, snippet, url, source, relevance_score}."""
        pass

    @abstractmethod
    def search_promoter_news(self, promoter_names: list[str], company_name: str) -> list[dict[str, Any]]:
        """Search for promoter-related news."""
        pass

    @abstractmethod
    def search_sector_regulatory(self, sector: str) -> list[dict[str, Any]]:
        """Search for sector and regulatory developments."""
        pass

    @abstractmethod
    def search_litigation_reputation(self, company_name: str, promoter_names: list[str]) -> list[dict[str, Any]]:
        """Search for litigation or reputation issues."""
        pass

    @property
    def is_available(self) -> bool:
        """Whether live search is available (vs mock)."""
        return False
