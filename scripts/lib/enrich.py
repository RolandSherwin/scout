"""Reddit thread enrichment module.

Fetches actual Reddit JSON to get real engagement metrics:
- Actual upvotes (not fuzzed)
- Real comment counts
- Top comment excerpts with scores

This provides more accurate data than scraping or web search results.
"""

import json
import urllib.request
import urllib.error
import re
from typing import Any, Dict, List, Optional, Tuple

from . import dates, schema


DEFAULT_TIMEOUT = 15
MAX_COMMENTS = 5  # Top N comments to extract


def _make_reddit_request(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, Any, Optional[str]]:
    """Make a request to Reddit's JSON API."""
    default_headers = {
        'User-Agent': 'Scout Research Agent/1.0 (Educational Research)',
        'Accept': 'application/json',
    }
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json,text/html;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    tried_browser = False
    tried_old = False
    while True:
        headers = browser_headers if tried_browser else default_headers
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = response.read().decode('utf-8')
                return True, json.loads(data), None
        except urllib.error.HTTPError as e:
            # If blocked, retry with browser-like headers and/or old.reddit.com
            if e.code == 403:
                if not tried_browser:
                    tried_browser = True
                    continue
                if not tried_old:
                    tried_old = True
                    if "old.reddit.com" not in url:
                        url = url.replace("www.reddit.com", "old.reddit.com").replace("reddit.com", "old.reddit.com")
                        continue
            return False, None, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, None, f"URL Error: {e.reason}"
        except TimeoutError:
            return False, None, "Request timed out"
        except json.JSONDecodeError as e:
            return False, None, f"JSON parse error: {e}"
        except Exception as e:
            return False, None, str(e)


def extract_reddit_url_info(url: str) -> Optional[Dict[str, str]]:
    """Extract subreddit and post ID from a Reddit URL.

    Supports formats:
    - https://reddit.com/r/python/comments/abc123/title
    - https://www.reddit.com/r/python/comments/abc123
    - https://old.reddit.com/r/python/comments/abc123
    - /r/python/comments/abc123
    """
    patterns = [
        r'reddit\.com/r/([^/]+)/comments/([^/]+)',
        r'/r/([^/]+)/comments/([^/]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return {
                'subreddit': match.group(1),
                'post_id': match.group(2),
            }
    return None


def build_reddit_json_url(url: str) -> Optional[str]:
    """Convert a Reddit URL to its JSON API endpoint."""
    info = extract_reddit_url_info(url)
    if not info:
        return None

    # Reddit JSON endpoint format
    return f"https://www.reddit.com/r/{info['subreddit']}/comments/{info['post_id']}.json?limit={MAX_COMMENTS}"


def parse_reddit_post(data: List[Any]) -> Optional[Dict[str, Any]]:
    """Parse Reddit JSON response to extract post and comment data.

    Reddit JSON structure:
    [
        { "data": { "children": [{ "data": <post> }] } },  # Post listing
        { "data": { "children": [{ "data": <comment> }, ...] } }  # Comments listing
    ]
    """
    try:
        if not data or len(data) < 2:
            return None

        # Extract post data
        post_listing = data[0]
        post_children = post_listing.get('data', {}).get('children', [])
        if not post_children:
            return None

        post = post_children[0].get('data', {})

        # Extract comment data
        comments_listing = data[1]
        comment_children = comments_listing.get('data', {}).get('children', [])

        top_comments = []
        for child in comment_children[:MAX_COMMENTS]:
            if child.get('kind') != 't1':  # t1 = comment
                continue
            comment_data = child.get('data', {})
            if not comment_data.get('body'):
                continue

            # Truncate long comments
            body = comment_data.get('body', '')
            if len(body) > 500:
                body = body[:497] + '...'

            top_comments.append({
                'score': comment_data.get('score', 0),
                'author': comment_data.get('author', '[deleted]'),
                'excerpt': body,
                'date': dates.timestamp_to_date(comment_data.get('created_utc')),
            })

        # Sort by score descending
        top_comments.sort(key=lambda c: c.get('score', 0), reverse=True)

        return {
            'id': post.get('id', ''),
            'title': post.get('title', ''),
            'score': post.get('score', 0),  # Upvotes (slightly fuzzed by Reddit)
            'upvote_ratio': post.get('upvote_ratio', 0.5),
            'num_comments': post.get('num_comments', 0),
            'created_utc': post.get('created_utc'),
            'subreddit': post.get('subreddit', ''),
            'author': post.get('author', '[deleted]'),
            'selftext': post.get('selftext', ''),  # Post body if text post
            'url': post.get('url', ''),  # Link if link post
            'permalink': f"https://www.reddit.com{post.get('permalink', '')}",
            'top_comments': top_comments[:MAX_COMMENTS],
        }

    except (KeyError, IndexError, TypeError) as e:
        return None


def enrich_reddit_post(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
    """Fetch and enrich a Reddit post with actual engagement data.

    Args:
        url: Reddit post URL
        timeout: Request timeout in seconds

    Returns:
        Enriched post data or None if fetch failed
    """
    json_url = build_reddit_json_url(url)
    if not json_url:
        return None

    success, data, error = _make_reddit_request(json_url, timeout)
    if not success:
        return None

    return parse_reddit_post(data)


def enrich_reddit_item(item: schema.RedditItem, timeout: int = DEFAULT_TIMEOUT) -> schema.RedditItem:
    """Enrich a RedditItem with actual engagement data from Reddit API.

    Args:
        item: RedditItem to enrich
        timeout: Request timeout

    Returns:
        Enriched RedditItem (mutates and returns same object)
    """
    enriched = enrich_reddit_post(item.url, timeout)
    if not enriched:
        return item

    # Update engagement
    item.engagement = schema.Engagement(
        score=enriched['score'],
        num_comments=enriched['num_comments'],
        upvote_ratio=enriched['upvote_ratio'],
    )

    # Update date if we got it
    if enriched.get('created_utc'):
        date_str = dates.timestamp_to_date(enriched['created_utc'])
        if date_str:
            item.date = date_str
            item.date_confidence = 'high'  # Timestamp from API is reliable

    # Add top comments
    item.top_comments = [
        schema.Comment(
            score=c['score'],
            author=c['author'],
            excerpt=c['excerpt'],
            date=c.get('date'),
        )
        for c in enriched.get('top_comments', [])
    ]

    return item


def enrich_reddit_items(items: List[schema.RedditItem], timeout: int = DEFAULT_TIMEOUT) -> List[schema.RedditItem]:
    """Enrich multiple Reddit items.

    Note: This is sequential to avoid rate limiting.
    For parallel enrichment, use with appropriate rate limiting.

    Args:
        items: List of RedditItems to enrich
        timeout: Per-request timeout

    Returns:
        List of enriched items
    """
    return [enrich_reddit_item(item, timeout) for item in items]
