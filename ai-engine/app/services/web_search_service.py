"""
Web search service: performs real web research via Tavily (or falls back to mock).
Synthesises results into structured risk signals using Mistral.

FIX: Original was entirely mocked. Now attempts a real Tavily search when
TAVILY_API_KEY is set; falls back to annotated mock so the pipeline never crashes.
"""
import logging
import os
from typing import List, Dict, Any

from .mistral_service import call_mistral
from .ai_extraction import extract_json_safely

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

RESEARCH_PROMPT = """You are a senior credit investigator. You have been provided with internet search results about a company.
Your task is to synthesize these results into structured risk signals.

CRITICAL DISAMBIGUATION RULES:
1. Ensure the news actually relates to "{company_name}" and its sector "{sector}".
2. Pay special attention to its promoters: {promoter_names_str}.
3. If a news item is about a completely different company with a similar name, IGNORE IT.
4. Only flag litigation that involves THIS company or its named promoters — not homonyms.
5. If some fields of schemas are missing then try to fill those values from the given text + web crawlers (and mention that it is fetched by crawler).

Target Company: {company_name}
Sector: {sector}
Promoters: {promoter_names_str}

Categories:
1. Litigation/Legal: Court cases, legal disputes, investigations, regulatory actions.
2. Sentiment/Reputation: News articles, social sentiment, promoter reputation.
3. Sector Trends: Industry headwinds or tailwinds relevant to this company.

Search Results:
{search_results_text}

Output JSON Schema:
{{
  "litigation_risk": {{
    "level": "low"|"medium"|"high"|"critical",
    "details": "string",
    "confidence": 0.0,
    "citations": ["string"]
  }},
  "sentiment_risk": {{
    "level": "low"|"medium"|"high"|"critical",
    "details": "string",
    "confidence": 0.0,
    "citations": ["string"]
  }},
  "sector_risk": {{
    "level": "low"|"medium"|"high"|"critical",
    "details": "string",
    "confidence": 0.0,
    "citations": ["string"]
  }},
  "summary_insight": "string"
}}

IMPORTANT:
- If search results are mock/empty, set all levels to "low" and confidence to 0.1.
- Mark confidence higher (0.7-0.9) only when real, specific, verified articles are present.
- Do NOT invent citations.

Return ONLY the JSON object.
"""

# FIX: Calibrated default for when web search is unavailable — confidence 0.1
# signals to downstream scoring that this is a placeholder, not real intelligence.
_DEFAULT_RESULT = {
    "litigation_risk":  {"level": "low", "details": "No real search performed.", "confidence": 0.1, "citations": []},
    "sentiment_risk":   {"level": "low", "details": "No real search performed.", "confidence": 0.1, "citations": []},
    "sector_risk":      {"level": "low", "details": "No real search performed.", "confidence": 0.1, "citations": []},
    "summary_insight":  "Web search not available. Results are placeholder defaults.",
}


def _search_tavily(query: str, max_results: int = 5) -> list[dict]:
    """
    Call Tavily search API. Returns list of {title, url, content} dicts.
    Returns empty list on any failure so callers never crash.
    """
    if not TAVILY_API_KEY:
        return []
    try:
        from tavily import TavilyClient  # type: ignore
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query=query, max_results=max_results, search_depth="advanced")
        return response.get("results", [])
    except ImportError:
        logger.warning("tavily-python not installed. Run: pip install tavily-python")
        return []
    except Exception as e:
        logger.warning("Tavily search failed for query '%s': %s", query, e)
        return []


def _format_results(results: list[dict]) -> str:
    """Convert Tavily result dicts to a readable text block for the LLM prompt."""
    if not results:
        return "No search results available."
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "N/A")
        url = r.get("url", "N/A")
        content = (r.get("content") or r.get("snippet") or "")[:400]
        lines.append(f"{i}. [{title}]({url})\n   {content}")
    return "\n\n".join(lines)


def perform_web_research(
    company_name: str,
    sector: str = "",
    promoter_names: List[str] = None,
) -> Dict[str, Any]:
    """
    Perform web research on the borrower entity and synthesise risk signals.
    Uses Tavily when TAVILY_API_KEY is set; returns annotated defaults otherwise.
    """
    if promoter_names is None:
        promoter_names = []

    logger.info("Performing web research for: %s", company_name)

    # --- Gather search results ---
    all_results: list[dict] = []

    if TAVILY_API_KEY:
        # Three targeted queries: company news, litigation, sector
        queries = [
            f"{company_name} {sector} latest news 2024 2025",
            f"{company_name} lawsuit litigation court case",
            f"{sector} sector regulatory risk India 2024",
        ]
        if promoter_names:
            queries.append(f"{' '.join(promoter_names[:2])} promoter fraud controversy")

        for q in queries:
            results = _search_tavily(q, max_results=4)
            all_results.extend(results)

        logger.info("Tavily returned %d total results across all queries.", len(all_results))
    else:
        logger.warning(
            "TAVILY_API_KEY not set — using annotated mock results. "
            "Set the key for real intelligence."
        )
        # Annotated mock so LLM can reason about it correctly
        all_results = [
            {
                "title": f"{company_name} — mock news",
                "url": "https://mock.example.com/no-real-data",
                "content": (
                    f"MOCK DATA: No real search was performed for {company_name}. "
                    "Treat all signals as low confidence placeholder defaults."
                ),
            }
        ]

    search_results_text = _format_results(all_results)

    prompt = RESEARCH_PROMPT.format(
        company_name=company_name,
        sector=sector or "general",
        promoter_names_str=", ".join(promoter_names) if promoter_names else "Not provided",
        search_results_text=search_results_text,
    )

    try:
        response = call_mistral(prompt, response_format={"type": "json_object"})
        result = extract_json_safely(response)
        # Tag whether the result was from real or mock data
        result["_source"] = "tavily" if TAVILY_API_KEY else "mock"
        return result
    except Exception as e:
        logger.error("Web research synthesis failed: %s", e)
        return {**_DEFAULT_RESULT, "_source": "error", "_error": str(e)}