"""Unit tests for the Reddit enrichment module."""

import json
import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import enrich, schema


# Mock Reddit JSON response
MOCK_REDDIT_RESPONSE = [
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
                        "body": "Great post! This is really helpful.",
                        "created_utc": 1706400100,
                    }
                },
                {
                    "kind": "t1",
                    "data": {
                        "id": "comment2",
                        "score": 25,
                        "author": "commenter2",
                        "body": "I agree with the above comment.",
                        "created_utc": 1706400200,
                    }
                },
            ]
        }
    }
]


class TestExtractRedditUrlInfo:
    """Tests for URL parsing."""

    def test_standard_url(self):
        url = "https://www.reddit.com/r/python/comments/abc123/test_title"
        result = enrich.extract_reddit_url_info(url)
        assert result == {'subreddit': 'python', 'post_id': 'abc123'}

    def test_old_reddit_url(self):
        url = "https://old.reddit.com/r/programming/comments/xyz789/another_post"
        result = enrich.extract_reddit_url_info(url)
        assert result == {'subreddit': 'programming', 'post_id': 'xyz789'}

    def test_no_www(self):
        url = "https://reddit.com/r/learnpython/comments/def456/question"
        result = enrich.extract_reddit_url_info(url)
        assert result == {'subreddit': 'learnpython', 'post_id': 'def456'}

    def test_relative_url(self):
        url = "/r/test/comments/ghi789/title"
        result = enrich.extract_reddit_url_info(url)
        assert result == {'subreddit': 'test', 'post_id': 'ghi789'}

    def test_invalid_url(self):
        url = "https://example.com/not-reddit"
        result = enrich.extract_reddit_url_info(url)
        assert result is None


class TestBuildRedditJsonUrl:
    """Tests for JSON URL building."""

    def test_standard_url(self):
        url = "https://www.reddit.com/r/python/comments/abc123/test"
        result = enrich.build_reddit_json_url(url)
        assert result == "https://www.reddit.com/r/python/comments/abc123.json?limit=5"

    def test_invalid_url(self):
        url = "https://example.com/not-reddit"
        result = enrich.build_reddit_json_url(url)
        assert result is None


class TestParseRedditPost:
    """Tests for Reddit JSON parsing."""

    def test_valid_response(self):
        result = enrich.parse_reddit_post(MOCK_REDDIT_RESPONSE)

        assert result is not None
        assert result['id'] == 'abc123'
        assert result['title'] == 'Test Reddit Post'
        assert result['score'] == 150
        assert result['upvote_ratio'] == 0.92
        assert result['num_comments'] == 45
        assert result['subreddit'] == 'python'
        assert len(result['top_comments']) == 2

    def test_comments_sorted_by_score(self):
        result = enrich.parse_reddit_post(MOCK_REDDIT_RESPONSE)

        # Comments should be sorted by score descending
        assert result['top_comments'][0]['score'] == 50
        assert result['top_comments'][1]['score'] == 25

    def test_empty_response(self):
        result = enrich.parse_reddit_post([])
        assert result is None

    def test_malformed_response(self):
        result = enrich.parse_reddit_post([{"invalid": "data"}])
        assert result is None


class TestEnrichRedditPost:
    """Tests for the main enrichment function."""

    @patch('lib.enrich._make_reddit_request')
    def test_successful_enrichment(self, mock_request):
        mock_request.return_value = (True, MOCK_REDDIT_RESPONSE, None)

        result, error = enrich.enrich_reddit_post(
            "https://www.reddit.com/r/python/comments/abc123/test"
        )

        assert result is not None
        assert error is None
        assert result['score'] == 150
        assert result['num_comments'] == 45
        mock_request.assert_called_once()

    @patch('lib.enrich._make_reddit_request')
    def test_failed_request(self, mock_request):
        mock_request.return_value = (False, None, "Network error")

        result, error = enrich.enrich_reddit_post(
            "https://www.reddit.com/r/python/comments/abc123/test"
        )

        assert result is None
        assert error == "Network error"

    def test_invalid_url(self):
        result, error = enrich.enrich_reddit_post("https://example.com/not-reddit")
        assert result is None
        assert error == "Invalid Reddit URL"


class TestEnrichRedditItem:
    """Tests for enriching RedditItem objects."""

    @patch('lib.enrich.enrich_reddit_post')
    def test_successful_item_enrichment(self, mock_enrich):
        mock_enrich.return_value = ({
            'score': 200,
            'num_comments': 50,
            'upvote_ratio': 0.95,
            'created_utc': 1706400000,
            'top_comments': [
                {'score': 30, 'author': 'user1', 'excerpt': 'Comment 1', 'date': '2024-01-28'},
            ],
        }, None)

        item = schema.RedditItem(
            id='test123',
            title='Test Post',
            url='https://reddit.com/r/test/comments/test123/title',
            subreddit='test',
        )

        result = enrich.enrich_reddit_item(item)

        assert result.engagement is not None
        assert result.engagement.score == 200
        assert result.engagement.num_comments == 50
        assert result.engagement.upvote_ratio == 0.95
        assert result.date_confidence == 'high'
        assert len(result.top_comments) == 1

    @patch('lib.enrich.enrich_reddit_post')
    def test_failed_enrichment_preserves_item(self, mock_enrich):
        mock_enrich.return_value = (None, "Network error")

        item = schema.RedditItem(
            id='test123',
            title='Test Post',
            url='https://reddit.com/r/test/comments/test123/title',
            subreddit='test',
        )

        result = enrich.enrich_reddit_item(item)

        # Item should be unchanged
        assert result.id == 'test123'
        assert result.title == 'Test Post'


class TestEnrichRedditItems:
    """Tests for batch enrichment."""

    @patch('lib.enrich.enrich_reddit_item')
    def test_batch_enrichment(self, mock_enrich_item):
        mock_enrich_item.side_effect = lambda item, timeout: item

        items = [
            schema.RedditItem(id='1', title='Post 1', url='https://reddit.com/r/test/comments/1/a', subreddit='test'),
            schema.RedditItem(id='2', title='Post 2', url='https://reddit.com/r/test/comments/2/b', subreddit='test'),
        ]

        result = enrich.enrich_reddit_items(items)

        assert len(result) == 2
        assert mock_enrich_item.call_count == 2


class TestCommentTruncation:
    """Tests for long comment handling."""

    def test_long_comment_truncated(self):
        long_comment = "x" * 600  # Over 500 char limit
        response = [
            {
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "id": "test",
                                "title": "Test",
                                "score": 10,
                                "upvote_ratio": 0.9,
                                "num_comments": 1,
                                "subreddit": "test",
                                "permalink": "/r/test/comments/test/",
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
                                "id": "c1",
                                "score": 5,
                                "author": "user",
                                "body": long_comment,
                            }
                        }
                    ]
                }
            }
        ]

        result = enrich.parse_reddit_post(response)

        assert result is not None
        assert len(result['top_comments']) == 1
        # Comment should be truncated with ellipsis
        assert len(result['top_comments'][0]['excerpt']) == 500
        assert result['top_comments'][0]['excerpt'].endswith('...')
