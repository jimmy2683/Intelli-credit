"""
Research agent: secondary research on borrower.
Searches company news, promoter news, sector/regulatory, litigation; outputs structured risk signals.

FIX: The original code imported from `.research.search_provider` and `.research.web_provider`
which are not present in the uploaded codebase. A self-contained MockSearchProvider is defined
here as a drop-in fallback so the module loads correctly. Replace with a real provider
(e.g. Tavily, Serper) by implementing the SearchProvider protocol below.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# SearchProvider protocol — implement this to plug in a real search backend
# ---------------------------------------------------------------------------

@runtime_checkable
class SearchProvider(Protocol):
    """Minimum interface that any search backend must satisfy."""

    @property
    def is_available(self) -> bool:
        ...

    def search_company_news(self, company_name: str, sector: str | None) -> list[dict]:
        ...

    def search_promoter_news(self, promoter_names: list[str], company_name: str) -> list[dict]:
        ...

    def search_sector_regulatory(self, sector: str) -> list[dict]:
        ...

    def search_litigation_reputation(self, company_name: str, promoter_names: list[str]) -> list[dict]:
        ...


class MockSearchProvider:
    """
    Deterministic stub used when no live search backend is configured.
    Returns empty result sets so downstream code always receives a list.
    """

    @property
    def is_available(self) -> bool:
        return False

    def search_company_news(self, company_name: str, sector: str | None) -> list[dict]:
        return []

    def search_promoter_news(self, promoter_names: list[str], company_name: str) -> list[dict]:
        return []

    def search_sector_regulatory(self, sector: str) -> list[dict]:
        return []

    def search_litigation_reputation(self, company_name: str, promoter_names: list[str]) -> list[dict]:
        return []


def get_search_provider() -> SearchProvider:
    """
    Factory: try to import a real provider; fall back to MockSearchProvider.
    To use a live backend, install it and adjust the import path below.
    """
    try:
        # Attempt to import a real provider if the sub-package exists.
        from .research.web_provider import get_search_provider as _real_factory  # type: ignore
        return _real_factory()
    except ImportError:
        return MockSearchProvider()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _aggregate_sentiment(results: list[dict], default: str = "neutral") -> tuple[str, list[str]]:
    refs = [r.get("url", r.get("source", "unknown")) for r in results if r]
    return default, refs


def _risk_level_from_results(
    results: list[dict],
    has_negative_keywords: bool = False,
    default: str = "low",
) -> tuple[str, float, list[str], str]:
    """Return (level, confidence, source_refs, summary)."""
    refs = [r.get("url", r.get("source", "unknown")) for r in results if r]
    if has_negative_keywords:
        return (
            "medium", 0.7, refs,
            "Negative signals detected in research. Verify with primary documents.",
        )
    return (
        default, 0.6, refs,
        "No significant negative signals detected. Primary documents take precedence.",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_research_agent(
    company_name: str,
    sector: str | None,
    promoter_names: list[str],
    provider: SearchProvider | None = None,
    document_litigation_hint: bool = False,
    document_auditor_concern: bool = False,
) -> dict[str, Any]:
    """
    Run secondary research and return structured risk signals.
    Output keys: news_sentiment, litigation_risk, regulatory_risk,
                 promoter_reputation_risk, sector_headwind_risk, web_research_summary.
    Each sub-dict has: level, confidence, source_refs, summary.
    """
    from .web_search_service import perform_web_research  # local import to avoid circular

    prov: SearchProvider = provider or get_search_provider()

    company_news = prov.search_company_news(company_name, sector)
    promoter_news = prov.search_promoter_news(promoter_names or [], company_name)
    sector_reg = prov.search_sector_regulatory(sector or "general")
    litigation_news = prov.search_litigation_reputation(company_name, promoter_names or [])

    news_sentiment_val, news_refs = _aggregate_sentiment(company_news, "neutral")
    news_sentiment = {
        "level": news_sentiment_val,
        "confidence": 0.65,
        "source_refs": news_refs,
        "summary": (
            f"Aggregated from {len(company_news)} company news items. "
            + ("Live provider." if prov.is_available else "Mock provider — neutral default.")
        ),
    }

    lit_level, lit_conf, lit_refs, lit_summary = _risk_level_from_results(
        litigation_news,
        has_negative_keywords=document_litigation_hint,
        default="low",
    )
    litigation_risk = {
        "level": lit_level,
        "confidence": lit_conf,
        "source_refs": lit_refs,
        "summary": lit_summary,
    }

    reg_level, reg_conf, reg_refs, _ = _risk_level_from_results(sector_reg, default="low")
    regulatory_risk = {
        "level": reg_level,
        "confidence": reg_conf,
        "source_refs": reg_refs,
        "summary": f"Sector '{sector or 'general'}' regulatory scan — {len(sector_reg)} items.",
    }

    prom_level, prom_conf, prom_refs, _ = _risk_level_from_results(promoter_news, default="low")
    promoter_reputation_risk = {
        "level": prom_level,
        "confidence": prom_conf,
        "source_refs": prom_refs,
        "summary": f"Promoter search for {len(promoter_names or [])} name(s).",
    }

    sector_level, sector_conf, sector_refs, _ = _risk_level_from_results(sector_reg, default="low")
    sector_headwind_risk = {
        "level": sector_level,
        "confidence": sector_conf,
        "source_refs": sector_refs,
        "summary": f"Sector '{sector or 'general'}' headwinds. Verify with domain experts.",
    }

    # Deep AI synthesis via web research module
    web_research_summary = perform_web_research(
        company_name=company_name,
        sector=sector or "",
        promoter_names=promoter_names or [],
    )

    return {
        "news_sentiment": news_sentiment,
        "litigation_risk": litigation_risk,
        "regulatory_risk": regulatory_risk,
        "promoter_reputation_risk": promoter_reputation_risk,
        "sector_headwind_risk": sector_headwind_risk,
        "web_research_summary": web_research_summary,
        "search_provider": "live" if prov.is_available else "mock",
        "results_count": {
            "company_news": len(company_news),
            "promoter_news": len(promoter_news),
            "sector_regulatory": len(sector_reg),
            "litigation_reputation": len(litigation_news),
        },
    }