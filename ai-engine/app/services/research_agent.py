"""
Research agent: secondary research on borrower.
Searches company news, promoter news, sector/regulatory, litigation; outputs structured risk signals.
"""
from __future__ import annotations

from typing import Any

from .research.search_provider import SearchProvider
from .research.web_provider import get_search_provider


def _aggregate_sentiment(results: list[dict], default: str = "neutral") -> tuple[str, list[str]]:
    """Derive sentiment and source refs from search results. Mock uses default."""
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
        return "medium", 0.7, refs, "Negative signals detected in research. Verify with primary documents."
    return default, 0.6, refs, "No significant negative signals in mock research. Primary documents take precedence."


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
    Output: news_sentiment, litigation_risk, regulatory_risk, promoter_reputation_risk, sector_headwind_risk.
    Each with: level, confidence, source_refs, summary.
    """
    prov = provider or get_search_provider()

    company_news = prov.search_company_news(company_name, sector)
    promoter_news = prov.search_promoter_news(promoter_names or [], company_name)
    sector_reg = prov.search_sector_regulatory(sector or "general")
    litigation_news = prov.search_litigation_reputation(company_name, promoter_names or [])

    news_sentiment_val, news_refs = _aggregate_sentiment(company_news, "neutral")
    news_sentiment = {
        "level": news_sentiment_val,
        "confidence": 0.65,
        "source_refs": news_refs,
        "summary": f"Aggregated from {len(company_news)} company news items. Mock provider yields neutral default.",
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
        "summary": f"Sector {sector or 'general'} regulatory scan. {len(sector_reg)} items. Mock default: low risk.",
    }

    prom_level, prom_conf, prom_refs, _ = _risk_level_from_results(promoter_news, default="low")
    promoter_reputation_risk = {
        "level": prom_level,
        "confidence": prom_conf,
        "source_refs": prom_refs,
        "summary": f"Promoter search for {len(promoter_names or [])} names. No adverse news in mock dataset.",
    }

    sector_level, sector_conf, sector_refs, _ = _risk_level_from_results(sector_reg, default="low")
    sector_headwind_risk = {
        "level": sector_level,
        "confidence": sector_conf,
        "source_refs": sector_refs,
        "summary": f"Sector {sector or 'general'} headwinds. Mock: low. Verify with domain experts.",
    }

    return {
        "news_sentiment": news_sentiment,
        "litigation_risk": litigation_risk,
        "regulatory_risk": regulatory_risk,
        "promoter_reputation_risk": promoter_reputation_risk,
        "sector_headwind_risk": sector_headwind_risk,
        "search_provider": "mock" if not prov.is_available else "live",
        "results_count": {
            "company_news": len(company_news),
            "promoter_news": len(promoter_news),
            "sector_regulatory": len(sector_reg),
            "litigation_reputation": len(litigation_news),
        },
    }
