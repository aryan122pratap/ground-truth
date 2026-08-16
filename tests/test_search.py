from ground_truth import search
from ground_truth.models import Evidence


def test_compute_credibility_gov_domain():
    assert search.compute_credibility("nih.gov") == 0.9


def test_compute_credibility_wire_domain():
    assert search.compute_credibility("reuters.com") == 0.8


def test_compute_credibility_wikipedia():
    assert search.compute_credibility("en.wikipedia.org") == 0.6


def test_compute_credibility_default():
    assert search.compute_credibility("some-random-blog.example") == 0.5


def test_search_falls_back_to_ddgs_when_tavily_unavailable(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(
        search,
        "_search_ddgs",
        lambda query, max_results: [
            Evidence(
                url="https://example.gov/x",
                title="t",
                snippet="s",
                source_domain="example.gov",
                credibility=0.9,
            )
        ],
    )
    search._cache.clear()
    results = search.search("some unique query for fallback test", max_results=3)
    assert len(results) == 1
    assert results[0].source_domain == "example.gov"


def test_search_uses_cache_on_second_call(monkeypatch):
    calls = {"n": 0}

    def fake_ddgs(query, max_results):
        calls["n"] += 1
        return [Evidence(url="https://x.com/a", title="t", snippet="s", source_domain="x.com")]

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(search, "_search_ddgs", fake_ddgs)
    search._cache.clear()

    search.search("a cacheable unique query", max_results=3)
    search.search("a cacheable unique query", max_results=3)
    assert calls["n"] == 1


def test_search_falls_back_to_ddgs_when_tavily_raises(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")

    def broken_tavily(query, max_results):
        raise RuntimeError("tavily down")

    def fake_ddgs(query, max_results):
        return [Evidence(url="https://y.com/a", title="t", snippet="s", source_domain="y.com")]

    monkeypatch.setattr(search, "_search_tavily", broken_tavily)
    monkeypatch.setattr(search, "_search_ddgs", fake_ddgs)
    search._cache.clear()

    results = search.search("a query that triggers tavily failure", max_results=3)
    assert len(results) == 1
    assert results[0].source_domain == "y.com"
