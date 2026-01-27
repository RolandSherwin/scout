"""Integration tests that hit real APIs/CLIs to verify sources are working.

Run with: pytest tests/test_integration.py -v
These are intended for local/debug runs and will hit live services.
"""

import pytest
import sys
import os
import subprocess
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import sources, enrich, grounding


pytestmark = pytest.mark.integration


class TestHackerNewsAPI:
    """Test HackerNews Algolia API."""

    def test_fetch_returns_results(self):
        result = sources.fetch_hackernews("python", limit=5)

        assert result.success, f"HackerNews fetch failed: {result.error}"
        assert result.source_name == "hackernews"
        assert len(result.items) > 0, "No results returned"

    def test_result_has_expected_fields(self):
        result = sources.fetch_hackernews("javascript", limit=3)

        assert result.success, f"HackerNews fetch failed: {result.error}"
        item = result.items[0]

        assert item.id is not None
        assert item.title is not None
        assert len(item.title) > 0
        assert item.hn_url is not None
        assert "news.ycombinator.com" in item.hn_url


class TestStackOverflowAPI:
    """Test Stack Exchange API."""

    def test_fetch_returns_results(self):
        result = sources.fetch_stackoverflow("python list comprehension", limit=5)

        assert result.success, f"StackOverflow fetch failed: {result.error}"
        assert result.source_name == "stackoverflow"
        assert len(result.items) > 0, "No results returned"

    def test_result_has_expected_fields(self):
        result = sources.fetch_stackoverflow("async await", limit=3)

        assert result.success, f"StackOverflow fetch failed: {result.error}"
        item = result.items[0]

        assert item.id is not None
        assert item.title is not None
        assert item.url is not None
        assert "stackoverflow.com" in item.url


class TestLobstersAPI:
    """Test Lobsters API.

    Note: Lobsters doesn't have a search API, so we fetch hottest stories
    and filter client-side. Results depend on current hot stories.
    """

    def test_fetch_succeeds(self):
        # Use a broad term likely to match hot stories
        result = sources.fetch_lobsters("linux", limit=10)

        assert result.success, f"Lobsters fetch failed: {result.error}"
        assert result.source_name == "lobsters"
        # May have 0 results if no hot stories match the query

    def test_result_has_expected_fields_when_results_exist(self):
        # Fetch with a very broad term
        result = sources.fetch_lobsters("code", limit=10)

        assert result.success, f"Lobsters fetch failed: {result.error}"
        if len(result.items) > 0:
            item = result.items[0]
            assert item.id is not None
            assert item.title is not None
            assert item.url is not None


class TestDevtoAPI:
    """Test Dev.to API."""

    def test_fetch_returns_results(self):
        result = sources.fetch_devto("python", limit=5)

        assert result.success, f"Dev.to fetch failed: {result.error}"
        assert result.source_name == "devto"
        assert len(result.items) > 0, "No results returned"

    def test_result_has_expected_fields(self):
        result = sources.fetch_devto("javascript", limit=3)

        assert result.success, f"Dev.to fetch failed: {result.error}"
        item = result.items[0]

        assert item.id is not None
        assert item.title is not None
        assert item.url is not None
        assert "dev.to" in item.url


class TestWikipediaAPI:
    """Test Wikipedia API."""

    def test_fetch_returns_results(self):
        result = sources.fetch_wikipedia("Python programming language", limit=5)

        assert result.success, f"Wikipedia fetch failed: {result.error}"
        assert result.source_name == "wikipedia"
        assert len(result.items) > 0, "No results returned"

    def test_result_has_expected_fields(self):
        result = sources.fetch_wikipedia("machine learning", limit=3)

        assert result.success, f"Wikipedia fetch failed: {result.error}"
        item = result.items[0]

        assert item.id is not None
        assert item.title is not None
        assert item.url is not None
        assert "wikipedia.org" in item.url


class TestArxivAPI:
    """Test arXiv API."""

    def test_fetch_returns_results(self):
        # Check if arxiv is implemented
        if not hasattr(sources, 'fetch_arxiv'):
            pytest.skip("arXiv fetch not implemented")

        result = sources.fetch_arxiv("neural networks", limit=5)

        assert result.success, f"arXiv fetch failed: {result.error}"
        assert result.source_name == "arxiv"
        assert len(result.items) > 0, "No results returned"


class TestDuckDuckGoAPI:
    """Test DuckDuckGo Instant Answer API."""

    def test_fetch_returns_results(self):
        result = sources.fetch_duckduckgo("Python programming")

        assert result.success, f"DuckDuckGo fetch failed: {result.error}"
        assert result.source_name == "duckduckgo"
        # DDG may return empty for some queries, just verify no error


class TestParallelFetch:
    """Test parallel fetching of multiple sources."""

    def test_fetch_multiple_sources(self):
        results = sources.fetch_parallel(
            "python web framework",
            sources=['hackernews', 'stackoverflow', 'lobsters'],
            depth='quick',
        )

        # At least some sources should succeed
        successful = [name for name, r in results.items() if r.success]
        assert len(successful) >= 2, f"Too many failures. Results: {results}"

    def test_handles_mixed_success_failure(self):
        # Include a source that might fail or be slow
        results = sources.fetch_parallel(
            "kubernetes",
            sources=['hackernews', 'devto'],
            depth='quick',
        )

        # Should return results for all requested sources
        assert 'hackernews' in results
        assert 'devto' in results


class TestSourceRegistry:
    """Test that all registered sources are functional."""

    @pytest.mark.parametrize("source_name", [
        'hackernews',
        'stackoverflow',
        'lobsters',
        'devto',
        'wikipedia',
    ])
    def test_registered_source_works(self, source_name):
        if source_name not in sources.SOURCE_REGISTRY:
            pytest.skip(f"{source_name} not in SOURCE_REGISTRY")

        fetch_fn = sources.SOURCE_REGISTRY[source_name]
        result = fetch_fn("test query", limit=3)

        assert result.source_name == source_name
        # We don't assert success since APIs can have transient failures
        # But we verify the structure is correct
        assert hasattr(result, 'success')
        assert hasattr(result, 'items')
        assert hasattr(result, 'error')

    def test_duckduckgo_registered_source_works(self):
        """DDG doesn't take a limit parameter."""
        if 'duckduckgo' not in sources.SOURCE_REGISTRY:
            pytest.skip("duckduckgo not in SOURCE_REGISTRY")

        fetch_fn = sources.SOURCE_REGISTRY['duckduckgo']
        result = fetch_fn("python programming")

        assert result.source_name == 'duckduckgo'
        assert hasattr(result, 'success')
        assert hasattr(result, 'items')


class TestResearchCLILive:
    """Smoke test for research CLI using live APIs."""

    def test_research_cli_quick_report(self):
        # Use a short query to reduce load/time
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'research.py'),
             "python web frameworks", "--depth", "quick", "--format", "report"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"research.py failed: {result.stderr}"
        assert "Research:" in result.stdout
        assert "Top Findings" in result.stdout


class TestCliToolsLive:
    """Smoke tests for optional CLI integrations."""

    def test_bird_cli_search(self):
        if shutil.which("bird") is None:
            pytest.skip("bird CLI not installed")
        result = subprocess.run(
            ["bird", "search", "python", "--json", "-n", "1", "--plain"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"bird CLI failed: {result.stderr}"

    def test_gh_cli_api(self):
        if shutil.which("gh") is None:
            pytest.skip("gh CLI not installed")
        result = subprocess.run(
            ["gh", "api", "rate_limit"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"gh CLI failed: {result.stderr}"


class TestBraveGroundingLive:
    """Smoke test for Brave AI Grounding."""

    def test_brave_grounding(self):
        if not os.environ.get("BRAVE_API_KEY"):
            pytest.skip("BRAVE_API_KEY not set")

        answer, status = grounding.fetch_brave_grounded_answer("python programming", depth="quick")
        assert status.success is True, f"Brave grounding failed: {status.error}"
        assert answer is not None
        assert len(answer.text) > 0
        assert len(answer.citations) > 0
class TestRedditEnrichmentLive:
    """Test Reddit enrichment against live Reddit JSON."""

    def test_enriches_live_post(self):
        # Fetch a live listing to obtain a real post permalink
        listing_url = "https://old.reddit.com/r/python/new.json?limit=1"
        success, data, error = enrich._make_reddit_request(listing_url)
        assert success, f"Reddit listing fetch failed: {error}"

        # Extract the first permalink and build a post URL
        if isinstance(data, dict):
            children = data.get('data', {}).get('children', [])
        elif isinstance(data, list) and data:
            children = data[0].get('data', {}).get('children', [])
        else:
            children = []
        assert len(children) > 0, "No posts returned from Reddit listing"

        post = children[0].get('data', {}) if isinstance(children[0], dict) else {}
        permalink = post.get('permalink')
        assert permalink, "Reddit listing missing permalink"

        post_url = f"https://www.reddit.com{permalink}"
        enriched = enrich.enrich_reddit_post(post_url)

        assert enriched is not None, "Reddit enrichment returned None"
        assert enriched.get('id'), "Missing post id"
        assert enriched.get('title'), "Missing title"
        assert enriched.get('num_comments') is not None, "Missing comment count"
