"""Unit tests for the sources module."""

import json
import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import sources, schema


# Sample API responses for mocking
MOCK_HN_RESPONSE = {
    "hits": [
        {
            "objectID": "12345",
            "title": "Test HN Story",
            "url": "https://example.com/story",
            "author": "testuser",
            "created_at_i": 1706400000,  # 2024-01-28
            "points": 150,
            "num_comments": 45,
        }
    ]
}

MOCK_SO_RESPONSE = {
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
        }
    ]
}

MOCK_LOBSTERS_RESPONSE = [
    {
        "short_id": "abc123",
        "title": "Lobsters Test Story",
        "url": "https://example.com/lobsters",
        "created_at": "2024-01-28T12:00:00Z",
        "score": 30,
        "comment_count": 10,
        "submitter_user": {"username": "lobster_user"},
    }
]

MOCK_DEVTO_RESPONSE = [
    {
        "id": 111222,
        "title": "Dev.to Test Article",
        "url": "https://dev.to/test/article",
        "published_at": "2024-01-28T10:00:00Z",
        "description": "A test article description",
        "positive_reactions_count": 50,
        "comments_count": 5,
        "user": {"username": "devtouser"},
    }
]

MOCK_WIKIPEDIA_RESPONSE = {
    "query": {
        "search": [
            {
                "pageid": 12345,
                "title": "Python (programming language)",
                "snippet": "Python is a high-level programming language...",
            }
        ]
    }
}

MOCK_DDG_RESPONSE = {
    "Heading": "Python",
    "Abstract": "Python is a programming language.",
    "AbstractURL": "https://en.wikipedia.org/wiki/Python",
    "RelatedTopics": [
        {"Text": "Related topic 1", "FirstURL": "https://example.com/1"},
        {"Text": "Related topic 2", "FirstURL": "https://example.com/2"},
    ]
}


class TestMakeRequest:
    """Tests for the HTTP request helper."""

    @patch('urllib.request.urlopen')
    def test_successful_request(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"test": "data"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        success, data, error = sources._make_request("https://example.com/api")
        assert success is True
        assert data == '{"test": "data"}'
        assert error is None

    @patch('urllib.request.urlopen')
    def test_timeout_error(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        success, data, error = sources._make_request("https://example.com/api")
        assert success is False
        assert data is None
        assert "timed out" in error.lower()


class TestFetchHackernews:
    """Tests for HackerNews fetching."""

    @patch('lib.sources._make_request')
    def test_successful_fetch(self, mock_request):
        mock_request.return_value = (True, json.dumps(MOCK_HN_RESPONSE), None)

        result = sources.fetch_hackernews("python", limit=5)

        assert result.success is True
        assert result.source_name == "hackernews"
        assert len(result.items) == 1
        assert isinstance(result.items[0], schema.HNItem)
        assert result.items[0].title == "Test HN Story"
        assert result.items[0].engagement.points == 150

    @patch('lib.sources._make_request')
    def test_failed_fetch(self, mock_request):
        mock_request.return_value = (False, None, "Network error")

        result = sources.fetch_hackernews("python")

        assert result.success is False
        assert result.error == "Network error"
        assert len(result.items) == 0

    @patch('lib.sources._make_request')
    def test_invalid_json(self, mock_request):
        mock_request.return_value = (True, "not valid json", None)

        result = sources.fetch_hackernews("python")

        assert result.success is False
        assert "JSON parse error" in result.error


class TestFetchStackoverflow:
    """Tests for Stack Overflow fetching."""

    @patch('lib.sources._make_request')
    def test_successful_fetch(self, mock_request):
        mock_request.return_value = (True, json.dumps(MOCK_SO_RESPONSE), None)

        result = sources.fetch_stackoverflow("python testing", limit=5)

        assert result.success is True
        assert result.source_name == "stackoverflow"
        assert len(result.items) == 1
        assert isinstance(result.items[0], schema.StackOverflowItem)
        assert result.items[0].title == "How to test Python code?"
        assert result.items[0].engagement.votes == 25
        assert "python" in result.items[0].tags


class TestFetchLobsters:
    """Tests for Lobsters fetching."""

    @patch('lib.sources._make_request')
    def test_successful_fetch(self, mock_request):
        mock_request.return_value = (True, json.dumps(MOCK_LOBSTERS_RESPONSE), None)

        result = sources.fetch_lobsters("rust", limit=5)

        assert result.success is True
        assert result.source_name == "lobsters"
        assert len(result.items) == 1
        assert isinstance(result.items[0], schema.GenericItem)
        assert result.items[0].source_name == "lobsters"
        assert result.items[0].engagement.points == 30


class TestFetchDevto:
    """Tests for Dev.to fetching."""

    @patch('lib.sources._make_request')
    def test_successful_fetch(self, mock_request):
        mock_request.return_value = (True, json.dumps(MOCK_DEVTO_RESPONSE), None)

        result = sources.fetch_devto("python", limit=5)

        assert result.success is True
        assert result.source_name == "devto"
        assert len(result.items) == 1
        assert isinstance(result.items[0], schema.GenericItem)
        assert result.items[0].source_name == "devto"
        assert result.items[0].author == "devtouser"


class TestFetchWikipedia:
    """Tests for Wikipedia fetching."""

    @patch('lib.sources._make_request')
    def test_successful_fetch(self, mock_request):
        mock_request.return_value = (True, json.dumps(MOCK_WIKIPEDIA_RESPONSE), None)

        result = sources.fetch_wikipedia("python", limit=5)

        assert result.success is True
        assert result.source_name == "wikipedia"
        assert len(result.items) == 1
        assert isinstance(result.items[0], schema.GenericItem)
        assert "Python" in result.items[0].title


class TestFetchDuckduckgo:
    """Tests for DuckDuckGo fetching."""

    @patch('lib.sources._make_request')
    def test_successful_fetch(self, mock_request):
        mock_request.return_value = (True, json.dumps(MOCK_DDG_RESPONSE), None)

        result = sources.fetch_duckduckgo("python")

        assert result.success is True
        assert result.source_name == "duckduckgo"
        # Should have abstract + related topics
        assert len(result.items) >= 1


class TestDepthConfiguration:
    """Tests for depth-based configuration."""

    def test_quick_sources(self):
        sources_list = sources.get_sources_for_depth('quick')
        assert 'hackernews' in sources_list
        assert 'stackoverflow' in sources_list
        assert len(sources_list) <= 3

    def test_default_sources(self):
        sources_list = sources.get_sources_for_depth('default')
        assert len(sources_list) >= 3
        assert 'hackernews' in sources_list

    def test_deep_sources(self):
        sources_list = sources.get_sources_for_depth('deep')
        assert len(sources_list) >= 5
        assert 'arxiv' in sources_list

    def test_limits(self):
        assert sources.get_limits_for_depth('quick') == 5
        assert sources.get_limits_for_depth('default') == 10
        assert sources.get_limits_for_depth('deep') == 15

    def test_timeouts(self):
        assert sources.get_timeout_for_depth('quick') == sources.QUICK_TIMEOUT
        assert sources.get_timeout_for_depth('default') == sources.DEFAULT_TIMEOUT
        assert sources.get_timeout_for_depth('deep') == sources.DEEP_TIMEOUT


class TestFetchParallel:
    """Tests for parallel fetching."""

    @patch.object(sources, 'SOURCE_REGISTRY', {
        'hackernews': MagicMock(return_value=sources.FetchResult(
            source_name='hackernews',
            items=[schema.HNItem(id='1', title='HN', url='', hn_url='', author='')],
            success=True,
            duration_ms=100,
        )),
        'stackoverflow': MagicMock(return_value=sources.FetchResult(
            source_name='stackoverflow',
            items=[schema.StackOverflowItem(id='2', title='SO', url='')],
            success=True,
            duration_ms=150,
        )),
    })
    def test_parallel_fetch_success(self):
        results = sources.fetch_parallel(
            "python",
            sources=['hackernews', 'stackoverflow'],
            depth='quick',
        )

        assert 'hackernews' in results
        assert 'stackoverflow' in results
        assert results['hackernews'].success is True
        assert results['stackoverflow'].success is True

    @patch.object(sources, 'SOURCE_REGISTRY', {
        'hackernews': MagicMock(return_value=sources.FetchResult(
            source_name='hackernews',
            items=[],
            success=False,
            error="Network error",
        )),
        'stackoverflow': MagicMock(return_value=sources.FetchResult(
            source_name='stackoverflow',
            items=[schema.StackOverflowItem(id='2', title='SO', url='')],
            success=True,
        )),
    })
    def test_parallel_fetch_partial_failure(self):
        results = sources.fetch_parallel(
            "python",
            sources=['hackernews', 'stackoverflow'],
        )

        # One should fail, one succeed
        assert results['hackernews'].success is False
        assert results['stackoverflow'].success is True


class TestConvertToSourceStatus:
    """Tests for source status conversion."""

    def test_convert_success(self):
        results = {
            'hackernews': sources.FetchResult(
                source_name='hackernews',
                items=[MagicMock(), MagicMock()],  # 2 items
                success=True,
                duration_ms=100,
            ),
        }

        statuses = sources.convert_to_source_status(results)

        assert len(statuses) == 1
        assert statuses[0].source_name == 'hackernews'
        assert statuses[0].success is True
        assert statuses[0].item_count == 2
        assert statuses[0].duration_ms == 100

    def test_convert_failure(self):
        results = {
            'hackernews': sources.FetchResult(
                source_name='hackernews',
                items=[],
                success=False,
                error="Timeout",
                duration_ms=30000,
            ),
        }

        statuses = sources.convert_to_source_status(results)

        assert len(statuses) == 1
        assert statuses[0].success is False
        assert statuses[0].error == "Timeout"
        assert statuses[0].item_count == 0
