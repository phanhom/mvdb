"""
DuckDuckGo search engine wrapper — performs web searches without API keys.
Supports both legacy duckduckgo_search and new ddgs packages.
"""

import logging

logger = logging.getLogger(__name__)

DDGS = None
HAS_DDGS = False

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDGS = True
    except ImportError:
        pass


def search(
    query: str,
    max_results: int = 15,
    region: str = "wt-wt",
    safesearch: str = "off",
    timeout: int = 15,
) -> list[dict]:
    """
    Search DuckDuckGo for `query`.
    Returns list of dicts with keys: title, href, body.
    """
    if not HAS_DDGS:
        raise ImportError(
            "Search library not installed. Run: pip install ddgs"
        )

    logger.info(f"Searching: {query!r} (max={max_results})")
    results = []

    try:
        with DDGS(timeout=timeout) as ddgs:
            for r in ddgs.text(query, region=region, safesearch=safesearch, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "href": r.get("href", ""),
                    "body": r.get("body", ""),
                })
    except Exception as e:
        logger.warning(f"Search error for {query!r}: {e}")

    logger.info(f"Found {len(results)} results for {query!r}")
    return results


def search_multi(
    queries: list[str],
    max_results_per: int = 10,
    timeout: int = 15,
) -> dict[str, list[dict]]:
    """
    Run multiple search queries in sequence and return combined results.
    Returns dict mapping query -> list of results.
    """
    all_results = {}
    for q in queries:
        all_results[q] = search(q, max_results=max_results_per, timeout=timeout)
    return all_results
