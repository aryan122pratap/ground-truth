import hashlib
from urllib.parse import urlparse

from diskcache import Cache

from ground_truth import config
from ground_truth.models import Evidence

_cache = Cache(str(config.CACHE_DIR))


def _domain_of(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def compute_credibility(domain: str) -> float:
    """Heuristic 0-1 credibility score from domain alone. Not ground truth —
    a cheap prior to help the judge weigh sources, documented as such in the README."""
    domain = domain.lower()
    if any(domain.endswith(tld) for tld in config.HIGH_CREDIBILITY_TLDS):
        return 0.9
    if any(domain == d or domain.endswith("." + d) for d in config.HIGH_CREDIBILITY_DOMAINS):
        return 0.8
    if any(domain == d or domain.endswith("." + d) for d in config.MEDIUM_CREDIBILITY_DOMAINS):
        return 0.6
    if any(pattern in domain for pattern in config.LOW_CREDIBILITY_DOMAIN_PATTERNS):
        return 0.3
    return 0.5


def _search_tavily(query: str, max_results: int) -> list[Evidence]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=config.get_secret("TAVILY_API_KEY"))
    response = client.search(query=query, max_results=max_results)
    results = []
    for item in response.get("results", []):
        url = item.get("url", "")
        domain = _domain_of(url)
        results.append(
            Evidence(
                url=url,
                title=item.get("title", ""),
                snippet=(item.get("content", "") or "")[:500],
                source_domain=domain,
                published=item.get("published_date"),
                credibility=compute_credibility(domain),
            )
        )
    return results


def _search_ddgs(query: str, max_results: int) -> list[Evidence]:
    from ddgs import DDGS

    results = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            url = item.get("href", "")
            domain = _domain_of(url)
            results.append(
                Evidence(
                    url=url,
                    title=item.get("title", ""),
                    snippet=(item.get("body", "") or "")[:500],
                    source_domain=domain,
                    published=None,
                    credibility=compute_credibility(domain),
                )
            )
    return results


def search(query: str, max_results: int = config.MAX_SEARCH_RESULTS) -> list[Evidence]:
    cache_key = hashlib.sha256(f"{query}|{max_results}".encode()).hexdigest()
    cached = _cache.get(cache_key)
    if cached is not None:
        return [Evidence.model_validate(item) for item in cached]

    evidence: list[Evidence] = []
    if config.get_secret("TAVILY_API_KEY"):
        try:
            evidence = _search_tavily(query, max_results)
        except Exception:
            evidence = []
    if not evidence:
        try:
            evidence = _search_ddgs(query, max_results)
        except Exception:
            evidence = []

    _cache.set(
        cache_key,
        [e.model_dump() for e in evidence],
        expire=config.CACHE_TTL_SECONDS,
    )
    return evidence
