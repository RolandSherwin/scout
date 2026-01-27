"""Near-duplicate detection and removal.

Deduplication strategies:
1. URL normalization (strip tracking params, trailing slashes)
2. Domain + path matching
3. Title/text similarity (Jaccard on character n-grams)

Inspired by last30days-skill's deduplication approach.
"""

import re
from typing import Dict, List, Set, Tuple, Union
from urllib.parse import urlparse, parse_qs, urlencode

from . import schema


# Tracking parameters to strip from URLs
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'ref', 'source', 'fbclid', 'gclid', 'cid', 'mc_cid', 'mc_eid',
    '_ga', '_gl', 'hsCtaTracking', 'mkt_tok', 'trk', 'trkCampaign',
}

# Default similarity threshold
DEFAULT_THRESHOLD = 0.7


def normalize_url(url: str) -> str:
    """Normalize a URL for comparison.

    - Strips tracking parameters
    - Removes trailing slashes
    - Lowercases domain
    - Sorts remaining query params
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        # Parse and filter query params
        params = parse_qs(parsed.query, keep_blank_values=False)
        filtered_params = {
            k: v for k, v in params.items()
            if k.lower() not in TRACKING_PARAMS
        }

        # Sort remaining params for consistency
        sorted_query = urlencode(filtered_params, doseq=True) if filtered_params else ""

        # Normalize path (strip trailing slash, lowercase)
        path = parsed.path.rstrip('/')
        if not path:
            path = '/'

        # Rebuild URL
        normalized = f"{parsed.scheme}://{parsed.netloc.lower()}{path}"
        if sorted_query:
            normalized += f"?{sorted_query}"

        return normalized

    except Exception:
        return url.lower()


def normalize_text(text: str) -> str:
    """Normalize text for comparison.

    - Lowercase
    - Remove punctuation
    - Collapse whitespace
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_ngrams(text: str, n: int = 3) -> Set[str]:
    """Get character n-grams from text."""
    text = normalize_text(text)
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def get_item_text(item: schema.ResearchItem) -> str:
    """Get the primary text from an item for comparison."""
    if hasattr(item, 'title') and item.title:
        return item.title
    if hasattr(item, 'text') and item.text:
        return item.text
    return ""


def get_item_url(item: schema.ResearchItem) -> str:
    """Get the URL from an item."""
    return getattr(item, 'url', '') or ''


def items_match_by_url(item1: schema.ResearchItem, item2: schema.ResearchItem) -> bool:
    """Check if two items have effectively the same URL."""
    url1 = normalize_url(get_item_url(item1))
    url2 = normalize_url(get_item_url(item2))

    if not url1 or not url2:
        return False

    return url1 == url2


def items_similar_by_text(
    item1: schema.ResearchItem,
    item2: schema.ResearchItem,
    threshold: float = DEFAULT_THRESHOLD,
) -> bool:
    """Check if two items have similar text content."""
    text1 = get_item_text(item1)
    text2 = get_item_text(item2)

    if not text1 or not text2:
        return False

    ngrams1 = get_ngrams(text1)
    ngrams2 = get_ngrams(text2)

    similarity = jaccard_similarity(ngrams1, ngrams2)
    return similarity >= threshold


def find_duplicate_pairs(
    items: List[schema.ResearchItem],
    threshold: float = DEFAULT_THRESHOLD,
) -> List[Tuple[int, int]]:
    """Find pairs of items that are likely duplicates.

    Args:
        items: List of items to check
        threshold: Similarity threshold for text comparison

    Returns:
        List of (i, j) index pairs where items are duplicates
    """
    duplicates = []

    # Pre-compute normalized URLs
    normalized_urls = [normalize_url(get_item_url(item)) for item in items]

    # Pre-compute n-grams for text similarity
    ngrams_cache = [get_ngrams(get_item_text(item)) for item in items]

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            # First check URL match (fast, definitive)
            if normalized_urls[i] and normalized_urls[j]:
                if normalized_urls[i] == normalized_urls[j]:
                    duplicates.append((i, j))
                    continue

            # Then check text similarity (slower)
            similarity = jaccard_similarity(ngrams_cache[i], ngrams_cache[j])
            if similarity >= threshold:
                duplicates.append((i, j))

    return duplicates


def dedupe_items(
    items: List[schema.ResearchItem],
    threshold: float = DEFAULT_THRESHOLD,
) -> List[schema.ResearchItem]:
    """Remove near-duplicates, keeping the highest-scored item.

    Args:
        items: List of items (should be pre-sorted by score descending)
        threshold: Similarity threshold

    Returns:
        Deduplicated items
    """
    if len(items) <= 1:
        return items

    # Find duplicate pairs
    dup_pairs = find_duplicate_pairs(items, threshold)

    # Determine which items to remove
    # Keep the higher-scored item in each pair
    to_remove: Set[int] = set()

    for i, j in dup_pairs:
        # Get scores (default to 0 if missing)
        score_i = getattr(items[i], 'score', 0)
        score_j = getattr(items[j], 'score', 0)

        if score_i >= score_j:
            to_remove.add(j)
        else:
            to_remove.add(i)

    # Return items not marked for removal
    return [item for idx, item in enumerate(items) if idx not in to_remove]


def dedupe_by_source(
    items: List[schema.ResearchItem],
    threshold: float = DEFAULT_THRESHOLD,
) -> Dict[str, List[schema.ResearchItem]]:
    """Deduplicate items, grouping by source type.

    Returns a dict with source types as keys.
    """
    # Group by source type
    by_source: Dict[str, List[schema.ResearchItem]] = {}

    for item in items:
        source = getattr(item, 'source_type', 'unknown')
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(item)

    # Dedupe each group
    for source in by_source:
        by_source[source] = dedupe_items(by_source[source], threshold)

    return by_source


def dedupe_across_sources(
    items: List[schema.ResearchItem],
    threshold: float = DEFAULT_THRESHOLD,
) -> List[schema.ResearchItem]:
    """Deduplicate across all sources.

    Same content appearing on Reddit and HN? Keep the higher-scored one.
    """
    return dedupe_items(items, threshold)
