"""Shared pytest fixtures for research skill tests."""

import pytest
from datetime import datetime, timedelta, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import schema


@pytest.fixture
def sample_reddit_item():
    """Create a sample Reddit item."""
    item = schema.RedditItem(
        id='reddit123',
        title='Test Reddit Post About Python',
        url='https://reddit.com/r/python/comments/reddit123/test',
        subreddit='python',
        date=(datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat(),
        date_confidence='high',
        engagement=schema.Engagement(score=250, num_comments=45, upvote_ratio=0.92),
        relevance=0.85,
    )
    item.score = 75
    return item


@pytest.fixture
def sample_twitter_item():
    """Create a sample Twitter item."""
    item = schema.TwitterItem(
        id='tweet456',
        text='Just released a new Python library for data processing! Check it out.',
        url='https://twitter.com/pythondev/status/tweet456',
        author_handle='pythondev',
        date=(datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
        date_confidence='high',
        engagement=schema.Engagement(likes=500, reposts=120, replies=35),
        relevance=0.8,
    )
    item.score = 72
    return item


@pytest.fixture
def sample_hn_item():
    """Create a sample HackerNews item."""
    item = schema.HNItem(
        id='hn789',
        title='Show HN: A New Python Testing Framework',
        url='https://github.com/example/testframework',
        hn_url='https://news.ycombinator.com/item?id=hn789',
        author='hnuser',
        date=(datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat(),
        date_confidence='high',
        engagement=schema.Engagement(points=350, num_comments=120),
        relevance=0.9,
    )
    item.score = 82
    return item


@pytest.fixture
def sample_stackoverflow_item():
    """Create a sample Stack Overflow item."""
    item = schema.StackOverflowItem(
        id='so101112',
        title='How to properly test async Python code?',
        url='https://stackoverflow.com/questions/so101112',
        date=(datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat(),
        date_confidence='high',
        engagement=schema.Engagement(votes=75, answer_count=5, is_accepted=True, view_count=15000),
        tags=['python', 'async', 'testing'],
        relevance=0.88,
    )
    item.score = 70
    return item


@pytest.fixture
def sample_generic_item():
    """Create a sample generic item (Lobsters/Dev.to style)."""
    item = schema.GenericItem(
        id='lobsters131415',
        title='Understanding Python Decorators',
        url='https://lobste.rs/s/lobsters131415',
        source_name='lobsters',
        snippet='A deep dive into how Python decorators work under the hood...',
        author='lobsteruser',
        date=(datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat(),
        date_confidence='high',
        engagement=schema.Engagement(points=45),
        relevance=0.75,
    )
    item.score = 65
    return item


@pytest.fixture
def sample_research_report(sample_reddit_item, sample_hn_item, sample_generic_item):
    """Create a sample research report with multiple items."""
    report = schema.ResearchReport(
        topic='Python testing best practices',
        query_type='HOW_TO',
        depth='default',
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    report.reddit = [sample_reddit_item]
    report.hackernews = [sample_hn_item]
    report.generic = [sample_generic_item]
    report.all_results = [sample_hn_item, sample_reddit_item, sample_generic_item]  # Pre-sorted by score
    report.source_status = [
        schema.SourceStatus(source_name='reddit', success=True, item_count=1, duration_ms=150),
        schema.SourceStatus(source_name='hackernews', success=True, item_count=1, duration_ms=200),
        schema.SourceStatus(source_name='lobsters', success=True, item_count=1, duration_ms=180),
    ]
    return report


@pytest.fixture
def mock_hn_api_response():
    """Mock HackerNews API response."""
    return {
        "hits": [
            {
                "objectID": "12345",
                "title": "Test HN Story",
                "url": "https://example.com/story",
                "author": "testuser",
                "created_at_i": 1706400000,
                "points": 150,
                "num_comments": 45,
            },
            {
                "objectID": "12346",
                "title": "Another HN Story",
                "url": "https://example.com/another",
                "author": "anotheruser",
                "created_at_i": 1706300000,
                "points": 80,
                "num_comments": 20,
            },
        ]
    }


@pytest.fixture
def mock_stackoverflow_api_response():
    """Mock Stack Overflow API response."""
    return {
        "items": [
            {
                "question_id": 67890,
                "title": "How to test Python code?",
                "link": "https://stackoverflow.com/q/67890",
                "creation_date": 1706400000,
                "score": 25,
                "answer_count": 3,
                "is_answered": True,
                "view_count": 5000,
                "tags": ["python", "testing"],
            },
        ]
    }


@pytest.fixture
def mock_reddit_json_response():
    """Mock Reddit JSON API response."""
    return [
        {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "abc123",
                            "title": "Test Reddit Post",
                            "score": 150,
                            "upvote_ratio": 0.92,
                            "num_comments": 45,
                            "created_utc": 1706400000,
                            "subreddit": "python",
                            "author": "testuser",
                            "selftext": "This is the post body",
                            "url": "https://example.com/link",
                            "permalink": "/r/python/comments/abc123/test_post/",
                        }
                    }
                ]
            }
        },
        {
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "id": "comment1",
                            "score": 50,
                            "author": "commenter1",
                            "body": "Great post!",
                            "created_utc": 1706400100,
                        }
                    },
                ]
            }
        }
    ]
