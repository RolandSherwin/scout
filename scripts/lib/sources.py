"""Source fetching module with parallel execution.

Supports fetching from multiple sources in parallel using ThreadPoolExecutor:
- HackerNews (Algolia API)
- Stack Overflow (Stack Exchange API)
- Lobsters API
- Dev.to API
- arXiv API
- Wikipedia API
- DuckDuckGo Instant Answer API
- Reddit (via URL enrichment)

Note: Web search, Twitter/X (bird CLI), and direct Reddit search are handled
by the agent itself, not this module. This module handles the no-auth APIs.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from xml.etree import ElementTree

from . import dates, schema


# Timeouts in seconds
DEFAULT_TIMEOUT = 30
QUICK_TIMEOUT = 15
DEEP_TIMEOUT = 60


@dataclass
class FetchResult:
    """Result of a source fetch operation."""
    source_name: str
    items: List[Any]
    success: bool
    error: Optional[str] = None
    duration_ms: int = 0


def _make_request(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, Any, Optional[str]]:
    """Make an HTTP request and return (success, data, error)."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Scout Research Agent/1.0',
                'Accept': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            return True, data, None
    except urllib.error.HTTPError as e:
        return False, None, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, None, f"URL Error: {e.reason}"
    except TimeoutError:
        return False, None, "Request timed out"
    except Exception as e:
        return False, None, str(e)


def fetch_hackernews(query: str, limit: int = 10, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch stories from HackerNews Algolia API.

    API: https://hn.algolia.com/api/v1/search?query=<topic>&tags=story
    """
    start = time.time()
    source_name = "hackernews"

    encoded_query = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={encoded_query}&tags=story&hitsPerPage={limit}"

    success, data, error = _make_request(url, timeout)
    duration_ms = int((time.time() - start) * 1000)

    if not success:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=error, duration_ms=duration_ms)

    try:
        parsed = json.loads(data)
        items = []

        for hit in parsed.get('hits', [])[:limit]:
            # Convert created_at_i (unix timestamp) to date
            created_at = hit.get('created_at_i')
            date_str = dates.timestamp_to_date(created_at) if created_at else None

            engagement = schema.Engagement(
                points=hit.get('points'),
                num_comments=hit.get('num_comments'),
            )

            item = schema.HNItem(
                id=str(hit.get('objectID', '')),
                title=hit.get('title', ''),
                url=hit.get('url', ''),
                hn_url=f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                author=hit.get('author', ''),
                date=date_str,
                date_confidence=dates.get_date_confidence(date_str),
                engagement=engagement,
                relevance=0.7,  # Default relevance for API results
            )
            items.append(item)

        return FetchResult(source_name=source_name, items=items, success=True,
                          duration_ms=duration_ms)

    except json.JSONDecodeError as e:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=f"JSON parse error: {e}", duration_ms=duration_ms)


def fetch_stackoverflow(query: str, limit: int = 10, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch questions from Stack Overflow API.

    API: https://api.stackexchange.com/2.3/search?order=desc&sort=relevance&intitle=<topic>&site=stackoverflow
    """
    start = time.time()
    source_name = "stackoverflow"

    encoded_query = urllib.parse.quote(query)
    url = (f"https://api.stackexchange.com/2.3/search?"
           f"order=desc&sort=relevance&intitle={encoded_query}&site=stackoverflow&pagesize={limit}")

    success, data, error = _make_request(url, timeout)
    duration_ms = int((time.time() - start) * 1000)

    if not success:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=error, duration_ms=duration_ms)

    try:
        parsed = json.loads(data)
        items = []

        for q in parsed.get('items', [])[:limit]:
            # Convert creation_date (unix timestamp) to date
            created_at = q.get('creation_date')
            date_str = dates.timestamp_to_date(created_at) if created_at else None

            engagement = schema.Engagement(
                votes=q.get('score'),
                answer_count=q.get('answer_count'),
                is_accepted=q.get('is_answered', False),
                view_count=q.get('view_count'),
            )

            item = schema.StackOverflowItem(
                id=str(q.get('question_id', '')),
                title=q.get('title', ''),
                url=q.get('link', ''),
                date=date_str,
                date_confidence=dates.get_date_confidence(date_str),
                engagement=engagement,
                tags=q.get('tags', []),
                relevance=0.7,
            )
            items.append(item)

        return FetchResult(source_name=source_name, items=items, success=True,
                          duration_ms=duration_ms)

    except json.JSONDecodeError as e:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=f"JSON parse error: {e}", duration_ms=duration_ms)


def fetch_lobsters(query: str, limit: int = 10, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch stories from Lobsters API.

    Note: Lobsters doesn't have a search API, so we fetch hottest stories
    and filter client-side by matching query terms in title/tags.
    """
    start = time.time()
    source_name = "lobsters"

    # Lobsters only supports feed endpoints, not search
    url = "https://lobste.rs/hottest.json"

    success, data, error = _make_request(url, timeout)
    duration_ms = int((time.time() - start) * 1000)

    if not success:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=error, duration_ms=duration_ms)

    try:
        parsed = json.loads(data)
        items = []

        stories = parsed if isinstance(parsed, list) else parsed.get('results', [])

        # Filter stories by query terms (case-insensitive)
        query_terms = query.lower().split()
        filtered_stories = []
        for story in stories:
            title = story.get('title', '').lower()
            tags = [t.lower() for t in story.get('tags', [])]
            if any(term in title or term in tags for term in query_terms):
                filtered_stories.append(story)

        for story in filtered_stories[:limit]:
            # Parse date from created_at
            created_at = story.get('created_at', '')
            date_str = None
            if created_at:
                dt = dates.parse_date(created_at)
                if dt:
                    date_str = dt.date().isoformat()

            engagement = schema.Engagement(
                points=story.get('score'),
                num_comments=story.get('comment_count'),
            )

            item = schema.GenericItem(
                id=story.get('short_id', ''),
                title=story.get('title', ''),
                url=story.get('url', '') or f"https://lobste.rs/s/{story.get('short_id', '')}",
                source_name="lobsters",
                author=story.get('submitter_user', {}).get('username', '') if isinstance(story.get('submitter_user'), dict) else '',
                date=date_str,
                date_confidence=dates.get_date_confidence(date_str),
                engagement=engagement,
                relevance=0.7,
            )
            items.append(item)

        return FetchResult(source_name=source_name, items=items, success=True,
                          duration_ms=duration_ms)

    except json.JSONDecodeError as e:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=f"JSON parse error: {e}", duration_ms=duration_ms)


def fetch_devto(query: str, limit: int = 10, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch articles from Dev.to API.

    API: https://dev.to/api/articles?tag=<topic>&per_page=10
    Note: Dev.to uses tags, not free-text search. We try the query as a tag.
    """
    start = time.time()
    source_name = "devto"

    # Clean query for use as tag (lowercase, no spaces)
    tag = query.lower().replace(' ', '').replace('-', '')
    encoded_tag = urllib.parse.quote(tag)
    url = f"https://dev.to/api/articles?tag={encoded_tag}&per_page={limit}"

    success, data, error = _make_request(url, timeout)
    duration_ms = int((time.time() - start) * 1000)

    if not success:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=error, duration_ms=duration_ms)

    try:
        parsed = json.loads(data)
        items = []

        for article in parsed[:limit]:
            # Parse date from published_at
            published_at = article.get('published_at', '')
            date_str = None
            if published_at:
                dt = dates.parse_date(published_at)
                if dt:
                    date_str = dt.date().isoformat()

            engagement = schema.Engagement(
                points=article.get('positive_reactions_count'),
                num_comments=article.get('comments_count'),
            )

            item = schema.GenericItem(
                id=str(article.get('id', '')),
                title=article.get('title', ''),
                url=article.get('url', ''),
                source_name="devto",
                snippet=article.get('description', ''),
                author=article.get('user', {}).get('username', ''),
                date=date_str,
                date_confidence=dates.get_date_confidence(date_str),
                engagement=engagement,
                relevance=0.6,  # Slightly lower for tag-based search
            )
            items.append(item)

        return FetchResult(source_name=source_name, items=items, success=True,
                          duration_ms=duration_ms)

    except json.JSONDecodeError as e:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=f"JSON parse error: {e}", duration_ms=duration_ms)


def fetch_arxiv(query: str, limit: int = 10, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch papers from arXiv API.

    API: http://export.arxiv.org/api/query?search_query=all:<topic>&max_results=10
    Returns XML.
    """
    start = time.time()
    source_name = "arxiv"

    encoded_query = urllib.parse.quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results={limit}"

    success, data, error = _make_request(url, timeout)
    duration_ms = int((time.time() - start) * 1000)

    if not success:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=error, duration_ms=duration_ms)

    try:
        # Parse XML
        root = ElementTree.fromstring(data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        items = []
        for entry in root.findall('atom:entry', ns)[:limit]:
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ''

            # Get abstract/summary
            summary_elem = entry.find('atom:summary', ns)
            summary = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ''

            # Get URL (prefer PDF link)
            url = ''
            for link in entry.findall('atom:link', ns):
                if link.get('type') == 'application/pdf':
                    url = link.get('href', '')
                    break
                elif link.get('rel') == 'alternate':
                    url = link.get('href', '')

            # Get published date
            published_elem = entry.find('atom:published', ns)
            date_str = None
            if published_elem is not None and published_elem.text:
                dt = dates.parse_date(published_elem.text)
                if dt:
                    date_str = dt.date().isoformat()

            # Get authors
            authors = []
            for author in entry.findall('atom:author', ns):
                name_elem = author.find('atom:name', ns)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text)

            item = schema.GenericItem(
                id=entry.find('atom:id', ns).text if entry.find('atom:id', ns) is not None else '',
                title=title,
                url=url,
                source_name="arxiv",
                snippet=summary[:500] if summary else '',
                author=', '.join(authors[:3]),
                date=date_str,
                date_confidence=dates.get_date_confidence(date_str),
                relevance=0.7,
            )
            items.append(item)

        return FetchResult(source_name=source_name, items=items, success=True,
                          duration_ms=duration_ms)

    except ElementTree.ParseError as e:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=f"XML parse error: {e}", duration_ms=duration_ms)


def fetch_wikipedia(query: str, limit: int = 5, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch search results from Wikipedia API.

    API: https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch=<topic>
    """
    start = time.time()
    source_name = "wikipedia"

    encoded_query = urllib.parse.quote(query)
    url = (f"https://en.wikipedia.org/w/api.php?"
           f"action=query&format=json&list=search&srsearch={encoded_query}&srlimit={limit}")

    success, data, error = _make_request(url, timeout)
    duration_ms = int((time.time() - start) * 1000)

    if not success:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=error, duration_ms=duration_ms)

    try:
        parsed = json.loads(data)
        items = []

        for result in parsed.get('query', {}).get('search', [])[:limit]:
            page_id = result.get('pageid', '')
            title = result.get('title', '')

            # Build Wikipedia URL
            url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"

            # Snippet (strip HTML)
            snippet = result.get('snippet', '')
            # Basic HTML tag removal
            import re
            snippet = re.sub(r'<[^>]+>', '', snippet)

            item = schema.GenericItem(
                id=str(page_id),
                title=title,
                url=url,
                source_name="wikipedia",
                snippet=snippet,
                relevance=0.6,  # Wikipedia is reference, not discussion
            )
            items.append(item)

        return FetchResult(source_name=source_name, items=items, success=True,
                          duration_ms=duration_ms)

    except json.JSONDecodeError as e:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=f"JSON parse error: {e}", duration_ms=duration_ms)


def fetch_duckduckgo(query: str, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch instant answer from DuckDuckGo API.

    API: https://api.duckduckgo.com/?q=<topic>&format=json
    Note: This is instant answers only, not full search results.
    """
    start = time.time()
    source_name = "duckduckgo"

    encoded_query = urllib.parse.quote(query)
    url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"

    success, data, error = _make_request(url, timeout)
    duration_ms = int((time.time() - start) * 1000)

    if not success:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=error, duration_ms=duration_ms)

    try:
        parsed = json.loads(data)
        items = []

        # Check for abstract (main answer)
        if parsed.get('Abstract'):
            item = schema.GenericItem(
                id='ddg_abstract',
                title=parsed.get('Heading', query),
                url=parsed.get('AbstractURL', ''),
                source_name="duckduckgo",
                snippet=parsed.get('Abstract', ''),
                relevance=0.5,  # Instant answers are supplementary
            )
            items.append(item)

        # Related topics
        for topic in parsed.get('RelatedTopics', [])[:3]:
            if isinstance(topic, dict) and topic.get('Text'):
                item = schema.GenericItem(
                    id=f"ddg_topic_{len(items)}",
                    title=topic.get('Text', '')[:100],
                    url=topic.get('FirstURL', ''),
                    source_name="duckduckgo",
                    snippet=topic.get('Text', ''),
                    relevance=0.4,
                )
                items.append(item)

        return FetchResult(source_name=source_name, items=items, success=True,
                          duration_ms=duration_ms)

    except json.JSONDecodeError as e:
        return FetchResult(source_name=source_name, items=[], success=False,
                          error=f"JSON parse error: {e}", duration_ms=duration_ms)


# Source registry: maps source name to fetch function
SOURCE_REGISTRY: Dict[str, Callable] = {
    'hackernews': fetch_hackernews,
    'stackoverflow': fetch_stackoverflow,
    'lobsters': fetch_lobsters,
    'devto': fetch_devto,
    'arxiv': fetch_arxiv,
    'wikipedia': fetch_wikipedia,
    'duckduckgo': fetch_duckduckgo,
}

# Default sources by depth
QUICK_SOURCES = ['hackernews', 'stackoverflow']
DEFAULT_SOURCES = ['hackernews', 'stackoverflow', 'lobsters', 'devto', 'wikipedia']
DEEP_SOURCES = ['hackernews', 'stackoverflow', 'lobsters', 'devto', 'arxiv', 'wikipedia', 'duckduckgo']


def get_sources_for_depth(depth: str) -> List[str]:
    """Get list of sources for a given depth level."""
    if depth == 'quick':
        return QUICK_SOURCES
    elif depth == 'deep':
        return DEEP_SOURCES
    else:
        return DEFAULT_SOURCES


def get_limits_for_depth(depth: str) -> int:
    """Get item limit per source for a given depth level."""
    if depth == 'quick':
        return 5
    elif depth == 'deep':
        return 15
    else:
        return 10


def get_timeout_for_depth(depth: str) -> int:
    """Get timeout per source for a given depth level."""
    if depth == 'quick':
        return QUICK_TIMEOUT
    elif depth == 'deep':
        return DEEP_TIMEOUT
    else:
        return DEFAULT_TIMEOUT


def fetch_parallel(
    query: str,
    sources: Optional[List[str]] = None,
    depth: str = 'default',
    max_workers: int = 5,
) -> Dict[str, FetchResult]:
    """Fetch from multiple sources in parallel.

    Args:
        query: Search query
        sources: List of source names (defaults based on depth)
        depth: 'quick', 'default', or 'deep'
        max_workers: Max concurrent fetches

    Returns:
        Dict mapping source name to FetchResult
    """
    if sources is None:
        sources = get_sources_for_depth(depth)

    limit = get_limits_for_depth(depth)
    timeout = get_timeout_for_depth(depth)

    results: Dict[str, FetchResult] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        futures = {}
        for source in sources:
            if source in SOURCE_REGISTRY:
                fetch_fn = SOURCE_REGISTRY[source]
                future = executor.submit(fetch_fn, query, limit, timeout)
                futures[future] = source

        # Collect results as they complete
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                results[source] = result
            except Exception as e:
                results[source] = FetchResult(
                    source_name=source,
                    items=[],
                    success=False,
                    error=str(e),
                )

    return results


def convert_to_source_status(results: Dict[str, FetchResult]) -> List[schema.SourceStatus]:
    """Convert fetch results to source status list for reporting."""
    statuses = []
    for source_name, result in results.items():
        statuses.append(schema.SourceStatus(
            source_name=source_name,
            success=result.success,
            item_count=len(result.items),
            error=result.error,
            duration_ms=result.duration_ms,
        ))
    return statuses
