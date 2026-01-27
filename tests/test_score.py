"""Unit tests for the scoring module."""

import pytest
import math
from datetime import datetime, timedelta, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import schema, score


class TestLog1pSafe:
    """Tests for log1p_safe function."""

    def test_positive_value(self):
        assert score.log1p_safe(10) == pytest.approx(math.log1p(10))

    def test_zero(self):
        assert score.log1p_safe(0) == 0.0

    def test_none(self):
        assert score.log1p_safe(None) == 0.0

    def test_negative(self):
        assert score.log1p_safe(-5) == 0.0


class TestNormalizeTo100:
    """Tests for normalize_to_100 function."""

    def test_basic_normalization(self):
        values = [0.0, 50.0, 100.0]
        result = score.normalize_to_100(values)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(50.0)
        assert result[2] == pytest.approx(100.0)

    def test_with_none_values(self):
        values = [0.0, None, 100.0]
        result = score.normalize_to_100(values)
        assert result[0] == pytest.approx(0.0)
        assert result[1] is None
        assert result[2] == pytest.approx(100.0)

    def test_all_none(self):
        values = [None, None, None]
        result = score.normalize_to_100(values)
        assert all(v is None for v in result)

    def test_single_value(self):
        values = [50.0]
        result = score.normalize_to_100(values)
        assert result[0] == pytest.approx(50.0)  # No range, defaults to 50

    def test_same_values(self):
        values = [10.0, 10.0, 10.0]
        result = score.normalize_to_100(values)
        # All same, no range, should return 50 for all
        assert all(v == pytest.approx(50.0) for v in result)


class TestComputeRedditEngagementRaw:
    """Tests for Reddit engagement calculation."""

    def test_with_full_engagement(self):
        eng = schema.Engagement(score=100, num_comments=50, upvote_ratio=0.9)
        result = score.compute_reddit_engagement_raw(eng)
        assert result is not None
        # 0.55*log1p(100) + 0.40*log1p(50) + 0.05*(0.9*10)
        expected = 0.55 * math.log1p(100) + 0.40 * math.log1p(50) + 0.05 * 9
        assert result == pytest.approx(expected)

    def test_with_none_engagement(self):
        result = score.compute_reddit_engagement_raw(None)
        assert result is None

    def test_with_missing_fields(self):
        eng = schema.Engagement()  # All None
        result = score.compute_reddit_engagement_raw(eng)
        assert result is None


class TestComputeTwitterEngagementRaw:
    """Tests for Twitter engagement calculation."""

    def test_with_full_engagement(self):
        eng = schema.Engagement(likes=100, reposts=20, replies=30, quotes=5)
        result = score.compute_twitter_engagement_raw(eng)
        assert result is not None
        expected = (0.55 * math.log1p(100) + 0.25 * math.log1p(20) +
                   0.15 * math.log1p(30) + 0.05 * math.log1p(5))
        assert result == pytest.approx(expected)

    def test_with_none_engagement(self):
        result = score.compute_twitter_engagement_raw(None)
        assert result is None


class TestComputeHNEngagementRaw:
    """Tests for HackerNews engagement calculation."""

    def test_with_engagement(self):
        eng = schema.Engagement(points=200, num_comments=50)
        result = score.compute_hn_engagement_raw(eng)
        assert result is not None
        expected = 0.60 * math.log1p(200) + 0.40 * math.log1p(50)
        assert result == pytest.approx(expected)


class TestComputeStackOverflowEngagementRaw:
    """Tests for Stack Overflow engagement calculation."""

    def test_with_full_engagement(self):
        eng = schema.Engagement(votes=50, answer_count=5, view_count=10000, is_accepted=True)
        result = score.compute_stackoverflow_engagement_raw(eng)
        assert result is not None
        expected = (0.40 * math.log1p(50) + 0.30 * math.log1p(5) +
                   0.20 * math.log1p(100) + 0.10 * 10)  # view_count/100, is_accepted=10
        assert result == pytest.approx(expected)

    def test_without_accepted(self):
        eng = schema.Engagement(votes=50, answer_count=5, view_count=10000, is_accepted=False)
        result = score.compute_stackoverflow_engagement_raw(eng)
        assert result is not None
        expected = (0.40 * math.log1p(50) + 0.30 * math.log1p(5) +
                   0.20 * math.log1p(100) + 0.10 * 0)
        assert result == pytest.approx(expected)


class TestScoreRedditItems:
    """Tests for scoring Reddit items."""

    def test_single_item_with_engagement(self):
        item = schema.RedditItem(
            id="abc123",
            title="Test post",
            url="https://reddit.com/r/test/abc123",
            subreddit="test",
            date=(datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
            date_confidence="high",
            engagement=schema.Engagement(score=100, num_comments=50, upvote_ratio=0.9),
            relevance=0.8,
        )
        result = score.score_reddit_items([item])
        assert len(result) == 1
        assert result[0].score > 0
        assert result[0].score <= 100
        assert result[0].subs.relevance == 80  # 0.8 * 100
        assert result[0].subs.recency > 0  # Recent post

    def test_multiple_items_ranking(self):
        # High engagement, recent
        item1 = schema.RedditItem(
            id="1", title="High engagement", url="https://reddit.com/1",
            subreddit="test",
            date=(datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
            date_confidence="high",
            engagement=schema.Engagement(score=1000, num_comments=200),
            relevance=0.9,
        )
        # Low engagement, old
        item2 = schema.RedditItem(
            id="2", title="Low engagement", url="https://reddit.com/2",
            subreddit="test",
            date=(datetime.now(timezone.utc) - timedelta(days=300)).date().isoformat(),
            date_confidence="med",
            engagement=schema.Engagement(score=10, num_comments=5),
            relevance=0.5,
        )
        result = score.score_reddit_items([item1, item2])
        assert result[0].score > result[1].score

    def test_empty_list(self):
        result = score.score_reddit_items([])
        assert result == []


class TestScoreGenericItems:
    """Tests for scoring generic items (Tier 3)."""

    def test_item_without_engagement(self):
        item = schema.GenericItem(
            id="gen1",
            title="Blog post",
            url="https://example.com/blog/post",
            source_name="blog",
            date=(datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat(),
            date_confidence="high",
            relevance=0.7,
        )
        result = score.score_generic_items([item])
        assert len(result) == 1
        # Should have penalty applied
        assert result[0].subs.engagement == 0
        # Verify the penalty is applied by checking against theoretical max
        # Max would be: 55% * 70 (relevance) + 45% * 98 (recency) + 5 (high conf) - 15 (no eng) = 72.6
        # So score should be around 72-73, verify penalty was applied
        expected_no_penalty = 0.55 * 70 + 0.45 * result[0].subs.recency + 5  # high conf bonus
        expected_with_penalty = expected_no_penalty - 15
        assert result[0].score == pytest.approx(expected_with_penalty, abs=2)

    def test_item_with_engagement(self):
        # Lobsters has engagement (points)
        item = schema.GenericItem(
            id="lob1",
            title="Lobsters post",
            url="https://lobste.rs/s/abc123",
            source_name="lobsters",
            date=(datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat(),
            date_confidence="high",
            engagement=schema.Engagement(points=50),
            relevance=0.8,
        )
        result = score.score_generic_items([item])
        assert len(result) == 1
        assert result[0].subs.engagement > 0  # Has engagement


class TestDateConfidenceAdjustment:
    """Tests for date confidence score adjustments."""

    def test_high_confidence_bonus(self):
        item = schema.RedditItem(
            id="1", title="Test", url="https://reddit.com/1",
            subreddit="test",
            date=(datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
            date_confidence="high",
            engagement=schema.Engagement(score=100, num_comments=50),
            relevance=0.5,
        )
        result = score.score_reddit_items([item])
        base_item = result[0]

        # Same item with low confidence
        item_low = schema.RedditItem(
            id="2", title="Test", url="https://reddit.com/2",
            subreddit="test",
            date=item.date,
            date_confidence="low",
            engagement=schema.Engagement(score=100, num_comments=50),
            relevance=0.5,
        )
        result_low = score.score_reddit_items([item_low])

        # High confidence should score higher than low confidence
        assert base_item.score > result_low[0].score


class TestSortAllItems:
    """Tests for sorting all items."""

    def test_sort_by_score(self):
        item1 = schema.RedditItem(
            id="1", title="Low score", url="https://reddit.com/1",
            subreddit="test", relevance=0.3,
        )
        item1.score = 30

        item2 = schema.RedditItem(
            id="2", title="High score", url="https://reddit.com/2",
            subreddit="test", relevance=0.9,
        )
        item2.score = 90

        result = score.sort_all_items([item1, item2])
        assert result[0].score == 90
        assert result[1].score == 30

    def test_sort_by_source_priority_when_tied(self):
        reddit_item = schema.RedditItem(
            id="1", title="Reddit", url="https://reddit.com/1",
            subreddit="test", relevance=0.5,
        )
        reddit_item.score = 50
        reddit_item.date = "2024-01-15"

        generic_item = schema.GenericItem(
            id="2", title="Generic", url="https://example.com/1",
            source_name="blog", relevance=0.5,
        )
        generic_item.score = 50
        generic_item.date = "2024-01-15"

        result = score.sort_all_items([generic_item, reddit_item])
        # Reddit should come first due to source priority
        assert isinstance(result[0], schema.RedditItem)
        assert isinstance(result[1], schema.GenericItem)

    def test_empty_list(self):
        result = score.sort_all_items([])
        assert result == []


class TestScoringFormulas:
    """Tests to verify the scoring formulas match the spec."""

    def test_tier1_weights(self):
        """Verify Tier 1 (Reddit/Twitter) uses 45/25/30 weights."""
        assert score.WEIGHT_RELEVANCE == pytest.approx(0.45)
        assert score.WEIGHT_RECENCY == pytest.approx(0.25)
        assert score.WEIGHT_ENGAGEMENT == pytest.approx(0.30)

    def test_tier3_weights(self):
        """Verify Tier 3 (no engagement) uses 55/45 weights with penalty."""
        assert score.NO_ENGAGEMENT_WEIGHT_RELEVANCE == pytest.approx(0.55)
        assert score.NO_ENGAGEMENT_WEIGHT_RECENCY == pytest.approx(0.45)
        assert score.NO_ENGAGEMENT_SOURCE_PENALTY == 15

    def test_score_bounds(self):
        """Verify scores are bounded 0-100."""
        # Create item that might score very high
        item = schema.RedditItem(
            id="1", title="Max score test", url="https://reddit.com/1",
            subreddit="test",
            date=datetime.now(timezone.utc).date().isoformat(),
            date_confidence="high",
            engagement=schema.Engagement(score=100000, num_comments=10000, upvote_ratio=1.0),
            relevance=1.0,
        )
        result = score.score_reddit_items([item])
        assert result[0].score <= 100

        # Create item that might score very low
        item_low = schema.GenericItem(
            id="2", title="Min score test", url="https://example.com/1",
            source_name="blog",
            date="2000-01-01",  # Very old
            date_confidence="low",
            relevance=0.0,
        )
        result_low = score.score_generic_items([item_low])
        assert result_low[0].score >= 0
