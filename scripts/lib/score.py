"""Engagement-aware scoring for research skill.

Scoring formula (inspired by last30days-skill):
- With engagement data: 45% relevance + 25% recency + 30% engagement
- Without engagement: 55% relevance + 45% recency - 15 point penalty

Source tiers:
- Tier 1: Reddit, Twitter (engagement available) - no penalty
- Tier 2: HN, Stack Overflow, Lobsters (community curated) - small penalty
- Tier 3: Generic web sources (no engagement) - full penalty
"""

import math
from typing import List, Optional

from . import dates, schema


# Score weights for sources with engagement (Tier 1)
WEIGHT_RELEVANCE = 0.45
WEIGHT_RECENCY = 0.25
WEIGHT_ENGAGEMENT = 0.30

# Score weights for sources without engagement (Tier 3)
NO_ENGAGEMENT_WEIGHT_RELEVANCE = 0.55
NO_ENGAGEMENT_WEIGHT_RECENCY = 0.45
NO_ENGAGEMENT_SOURCE_PENALTY = 15

# Tier 2 sources (HN, SO, Lobsters) - partial engagement
TIER2_PENALTY = 5

# Date confidence adjustments
HIGH_CONFIDENCE_BONUS = 5
LOW_CONFIDENCE_PENALTY = 15
MED_CONFIDENCE_PENALTY = 0

# Unknown engagement penalty
UNKNOWN_ENGAGEMENT_PENALTY = 10
DEFAULT_ENGAGEMENT = 35


def log1p_safe(x: Optional[int]) -> float:
    """Safe log1p that handles None and negative values."""
    if x is None or x < 0:
        return 0.0
    return math.log1p(x)


def compute_reddit_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """Compute raw engagement score for Reddit item.

    Formula: 0.55*log1p(score) + 0.40*log1p(num_comments) + 0.05*(upvote_ratio*10)
    """
    if engagement is None:
        return None

    if engagement.score is None and engagement.num_comments is None:
        return None

    score = log1p_safe(engagement.score)
    comments = log1p_safe(engagement.num_comments)
    ratio = (engagement.upvote_ratio or 0.5) * 10

    return 0.55 * score + 0.40 * comments + 0.05 * ratio


def compute_twitter_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """Compute raw engagement score for Twitter item.

    Formula: 0.55*log1p(likes) + 0.25*log1p(reposts) + 0.15*log1p(replies) + 0.05*log1p(quotes)
    """
    if engagement is None:
        return None

    if engagement.likes is None and engagement.reposts is None:
        return None

    likes = log1p_safe(engagement.likes)
    reposts = log1p_safe(engagement.reposts)
    replies = log1p_safe(engagement.replies)
    quotes = log1p_safe(engagement.quotes)

    return 0.55 * likes + 0.25 * reposts + 0.15 * replies + 0.05 * quotes


def compute_hn_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """Compute raw engagement score for HackerNews item.

    Formula: 0.60*log1p(points) + 0.40*log1p(num_comments)
    """
    if engagement is None:
        return None

    if engagement.points is None and engagement.num_comments is None:
        return None

    points = log1p_safe(engagement.points)
    comments = log1p_safe(engagement.num_comments)

    return 0.60 * points + 0.40 * comments


def compute_stackoverflow_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """Compute raw engagement score for Stack Overflow item.

    Formula: 0.40*log1p(votes) + 0.30*log1p(answer_count) + 0.20*log1p(view_count/100) + 0.10*is_accepted
    """
    if engagement is None:
        return None

    if engagement.votes is None and engagement.answer_count is None:
        return None

    votes = log1p_safe(engagement.votes)
    answers = log1p_safe(engagement.answer_count)
    views = log1p_safe((engagement.view_count or 0) // 100)  # Scale down view count
    accepted = 10 if engagement.is_accepted else 0

    return 0.40 * votes + 0.30 * answers + 0.20 * views + 0.10 * accepted


def compute_generic_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """Compute raw engagement score for generic items (Lobsters, Dev.to, etc.).

    Uses points/votes if available, otherwise returns None.
    """
    if engagement is None:
        return None

    # Try points (Lobsters, Dev.to)
    if engagement.points is not None:
        return log1p_safe(engagement.points)

    # Try votes
    if engagement.votes is not None:
        return log1p_safe(engagement.votes)

    return None


def normalize_to_100(values: List[Optional[float]], default: float = 50) -> List[Optional[float]]:
    """Normalize a list of values to 0-100 scale.

    Args:
        values: Raw values (None values are preserved)
        default: Default value for empty lists

    Returns:
        Normalized values with None preserved
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return [None if v is None else default for v in values]

    min_val = min(valid)
    max_val = max(valid)
    range_val = max_val - min_val

    if range_val == 0:
        return [None if v is None else 50.0 for v in values]

    result = []
    for v in values:
        if v is None:
            result.append(None)
        else:
            normalized = ((v - min_val) / range_val) * 100
            result.append(normalized)

    return result


def _apply_date_confidence_adjustment(score: float, date_confidence: str) -> float:
    """Apply score adjustment based on date confidence."""
    if date_confidence == "high":
        return score + HIGH_CONFIDENCE_BONUS
    elif date_confidence == "low":
        return score - LOW_CONFIDENCE_PENALTY
    else:  # med
        return score - MED_CONFIDENCE_PENALTY


def score_reddit_items(items: List[schema.RedditItem], max_days: int = 365) -> List[schema.RedditItem]:
    """Compute scores for Reddit items.

    Args:
        items: List of Reddit items
        max_days: Max age for recency scoring

    Returns:
        Items with updated scores
    """
    if not items:
        return items

    # Compute raw engagement scores
    eng_raw = [compute_reddit_engagement_raw(item.engagement) for item in items]

    # Normalize engagement to 0-100
    eng_normalized = normalize_to_100(eng_raw)

    for i, item in enumerate(items):
        # Relevance subscore (0-100)
        rel_score = int(item.relevance * 100)

        # Recency subscore
        rec_score = dates.recency_score(item.date, max_days)

        # Engagement subscore
        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT

        # Store subscores
        item.subs = schema.SubScores(
            relevance=rel_score,
            recency=rec_score,
            engagement=eng_score,
        )

        # Compute overall score
        overall = (
            WEIGHT_RELEVANCE * rel_score +
            WEIGHT_RECENCY * rec_score +
            WEIGHT_ENGAGEMENT * eng_score
        )

        # Apply penalty for unknown engagement
        if eng_raw[i] is None:
            overall -= UNKNOWN_ENGAGEMENT_PENALTY

        # Apply date confidence adjustment
        overall = _apply_date_confidence_adjustment(overall, item.date_confidence)

        item.score = max(0, min(100, int(overall)))

    return items


def score_twitter_items(items: List[schema.TwitterItem], max_days: int = 365) -> List[schema.TwitterItem]:
    """Compute scores for Twitter items."""
    if not items:
        return items

    eng_raw = [compute_twitter_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)

    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date, max_days)

        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT

        item.subs = schema.SubScores(
            relevance=rel_score,
            recency=rec_score,
            engagement=eng_score,
        )

        overall = (
            WEIGHT_RELEVANCE * rel_score +
            WEIGHT_RECENCY * rec_score +
            WEIGHT_ENGAGEMENT * eng_score
        )

        if eng_raw[i] is None:
            overall -= UNKNOWN_ENGAGEMENT_PENALTY

        overall = _apply_date_confidence_adjustment(overall, item.date_confidence)
        item.score = max(0, min(100, int(overall)))

    return items


def score_hn_items(items: List[schema.HNItem], max_days: int = 365) -> List[schema.HNItem]:
    """Compute scores for HackerNews items (Tier 2)."""
    if not items:
        return items

    eng_raw = [compute_hn_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)

    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date, max_days)

        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT

        item.subs = schema.SubScores(
            relevance=rel_score,
            recency=rec_score,
            engagement=eng_score,
        )

        overall = (
            WEIGHT_RELEVANCE * rel_score +
            WEIGHT_RECENCY * rec_score +
            WEIGHT_ENGAGEMENT * eng_score
        )

        if eng_raw[i] is None:
            overall -= UNKNOWN_ENGAGEMENT_PENALTY

        # Tier 2 penalty
        overall -= TIER2_PENALTY

        overall = _apply_date_confidence_adjustment(overall, item.date_confidence)
        item.score = max(0, min(100, int(overall)))

    return items


def score_stackoverflow_items(items: List[schema.StackOverflowItem], max_days: int = 365) -> List[schema.StackOverflowItem]:
    """Compute scores for Stack Overflow items (Tier 2)."""
    if not items:
        return items

    eng_raw = [compute_stackoverflow_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)

    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date, max_days)

        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT

        item.subs = schema.SubScores(
            relevance=rel_score,
            recency=rec_score,
            engagement=eng_score,
        )

        overall = (
            WEIGHT_RELEVANCE * rel_score +
            WEIGHT_RECENCY * rec_score +
            WEIGHT_ENGAGEMENT * eng_score
        )

        if eng_raw[i] is None:
            overall -= UNKNOWN_ENGAGEMENT_PENALTY

        # Tier 2 penalty
        overall -= TIER2_PENALTY

        overall = _apply_date_confidence_adjustment(overall, item.date_confidence)
        item.score = max(0, min(100, int(overall)))

    return items


def score_generic_items(items: List[schema.GenericItem], max_days: int = 365) -> List[schema.GenericItem]:
    """Compute scores for generic items (Tier 3 - no engagement).

    Uses reweighted formula: 55% relevance + 45% recency - 15pt source penalty.
    """
    if not items:
        return items

    eng_raw = [compute_generic_engagement_raw(item.engagement) for item in items]
    has_any_engagement = any(e is not None for e in eng_raw)

    if has_any_engagement:
        eng_normalized = normalize_to_100(eng_raw)
    else:
        eng_normalized = [None] * len(items)

    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date, max_days)

        # For generic items, engagement is often unavailable
        if eng_normalized[i] is not None:
            # Has engagement (e.g., Lobsters, Dev.to)
            eng_score = int(eng_normalized[i])
            item.subs = schema.SubScores(
                relevance=rel_score,
                recency=rec_score,
                engagement=eng_score,
            )
            overall = (
                WEIGHT_RELEVANCE * rel_score +
                WEIGHT_RECENCY * rec_score +
                WEIGHT_ENGAGEMENT * eng_score
            )
            # Tier 2-like penalty for partial engagement
            overall -= TIER2_PENALTY
        else:
            # No engagement (Tier 3)
            item.subs = schema.SubScores(
                relevance=rel_score,
                recency=rec_score,
                engagement=0,
            )
            overall = (
                NO_ENGAGEMENT_WEIGHT_RELEVANCE * rel_score +
                NO_ENGAGEMENT_WEIGHT_RECENCY * rec_score
            )
            # Full penalty for no engagement
            overall -= NO_ENGAGEMENT_SOURCE_PENALTY

        overall = _apply_date_confidence_adjustment(overall, item.date_confidence)
        item.score = max(0, min(100, int(overall)))

    return items


def sort_all_items(items: List[schema.ResearchItem]) -> List[schema.ResearchItem]:
    """Sort all items by score (descending), then date, then source priority.

    Source priority: Reddit > Twitter > HN > SO > Generic
    """
    def get_source_priority(item: schema.ResearchItem) -> int:
        if isinstance(item, schema.RedditItem):
            return 0
        elif isinstance(item, schema.TwitterItem):
            return 1
        elif isinstance(item, schema.HNItem):
            return 2
        elif isinstance(item, schema.StackOverflowItem):
            return 3
        else:
            return 4

    def get_title(item: schema.ResearchItem) -> str:
        if hasattr(item, 'title'):
            return item.title
        elif hasattr(item, 'text'):
            return item.text
        return ""

    def sort_key(item: schema.ResearchItem):
        # Primary: score descending
        score = -item.score

        # Secondary: date descending (recent first)
        date = item.date or "0000-00-00"
        date_key = -int(date.replace("-", "")) if date != "0000-00-00" else 0

        # Tertiary: source priority
        source_priority = get_source_priority(item)

        # Quaternary: title for stability
        title = get_title(item)

        return (score, date_key, source_priority, title)

    return sorted(items, key=sort_key)
