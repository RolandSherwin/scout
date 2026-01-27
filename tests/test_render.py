"""Unit tests for the render module."""

import json
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import render, schema


def create_sample_reddit_item() -> schema.RedditItem:
    """Create a sample Reddit item for testing."""
    item = schema.RedditItem(
        id='r1',
        title='Test Reddit Post',
        url='https://reddit.com/r/python/comments/r1/test',
        subreddit='python',
        date='2024-01-28',
        engagement=schema.Engagement(score=150, num_comments=45),
    )
    item.score = 75
    return item


def create_sample_twitter_item() -> schema.TwitterItem:
    """Create a sample Twitter item for testing."""
    item = schema.TwitterItem(
        id='t1',
        text='This is a test tweet about Python programming.',
        url='https://twitter.com/user/status/t1',
        author_handle='testuser',
        date='2024-01-27',
        engagement=schema.Engagement(likes=100, reposts=20),
    )
    item.score = 70
    return item


def create_sample_hn_item() -> schema.HNItem:
    """Create a sample HN item for testing."""
    item = schema.HNItem(
        id='hn1',
        title='Test HN Story',
        url='https://example.com/story',
        hn_url='https://news.ycombinator.com/item?id=hn1',
        author='hnuser',
        date='2024-01-26',
        engagement=schema.Engagement(points=200, num_comments=80),
    )
    item.score = 80
    return item


def create_sample_report() -> schema.ResearchReport:
    """Create a sample report for testing."""
    report = schema.ResearchReport(
        topic='Python testing',
        query_type='HOW_TO',
        depth='default',
        generated_at='2024-01-28T12:00:00Z',
    )
    report.reddit = [create_sample_reddit_item()]
    report.twitter = [create_sample_twitter_item()]
    report.hackernews = [create_sample_hn_item()]
    report.all_results = report.reddit + report.twitter + report.hackernews
    report.source_status = [
        schema.SourceStatus(source_name='reddit', success=True, item_count=1, duration_ms=100),
        schema.SourceStatus(source_name='twitter', success=True, item_count=1, duration_ms=150),
        schema.SourceStatus(source_name='hackernews', success=True, item_count=1, duration_ms=200),
    ]
    return report


class TestRenderEngagement:
    """Tests for engagement rendering."""

    def test_reddit_engagement(self):
        item = create_sample_reddit_item()
        result = render.render_engagement(item)
        assert "150" in result
        assert "45" in result
        assert "pts" in result or "comments" in result

    def test_twitter_engagement(self):
        item = create_sample_twitter_item()
        result = render.render_engagement(item)
        assert "100" in result
        assert "likes" in result

    def test_no_engagement(self):
        item = schema.GenericItem(id='1', title='Test', url='', source_name='test')
        result = render.render_engagement(item)
        assert result == "-"


class TestRenderSourceBadge:
    """Tests for source badge rendering."""

    def test_reddit_badge(self):
        item = create_sample_reddit_item()
        badge = render.render_source_badge(item)
        assert "Reddit" in badge
        assert "python" in badge

    def test_twitter_badge(self):
        item = create_sample_twitter_item()
        badge = render.render_source_badge(item)
        assert "Twitter" in badge
        assert "testuser" in badge

    def test_hn_badge(self):
        item = create_sample_hn_item()
        badge = render.render_source_badge(item)
        assert "HackerNews" in badge


class TestRenderFindingsTable:
    """Tests for findings table rendering."""

    def test_renders_table(self):
        items = [create_sample_reddit_item(), create_sample_twitter_item()]
        result = render.render_findings_table(items)

        # Should be markdown table format
        assert "|" in result
        assert "Rank" in result
        assert "Score" in result
        assert "Finding" in result

    def test_empty_items(self):
        result = render.render_findings_table([])
        assert "No findings" in result

    def test_limits_items(self):
        # Create many items
        items = [create_sample_reddit_item() for _ in range(20)]
        result = render.render_findings_table(items, max_items=5)

        # Count data rows (not header rows)
        data_rows = [line for line in result.split('\n')
                     if line.startswith('|') and 'Rank' not in line and '---' not in line]
        assert len(data_rows) == 5


class TestRenderSourceStatus:
    """Tests for source status rendering."""

    def test_renders_status_table(self):
        statuses = [
            schema.SourceStatus(source_name='reddit', success=True, item_count=5, duration_ms=100),
            schema.SourceStatus(source_name='twitter', success=False, item_count=0, error='Timeout'),
        ]
        result = render.render_source_status(statuses)

        assert "Reddit" in result
        assert "OK" in result
        assert "Twitter" in result
        assert "FAIL" in result
        assert "Timeout" in result

    def test_empty_statuses(self):
        result = render.render_source_status([])
        assert result == ""


class TestRenderRedditSection:
    """Tests for Reddit section rendering."""

    def test_renders_section(self):
        items = [create_sample_reddit_item()]
        result = render.render_reddit_section(items)

        assert "Reddit" in result
        assert "Test Reddit Post" in result
        assert "r/python" in result

    def test_empty_items(self):
        result = render.render_reddit_section([])
        assert result == ""


class TestRenderTwitterSection:
    """Tests for Twitter section rendering."""

    def test_renders_section(self):
        items = [create_sample_twitter_item()]
        result = render.render_twitter_section(items)

        assert "Twitter" in result
        assert "@testuser" in result

    def test_empty_items(self):
        result = render.render_twitter_section([])
        assert result == ""


class TestRenderMarkdownReport:
    """Tests for full markdown report rendering."""

    def test_renders_full_report(self):
        report = create_sample_report()
        result = render.render_markdown_report(report)

        # Check main sections
        assert "# Research: Python testing" in result
        assert "Query Type:" in result
        assert "Summary" in result
        assert "Top Findings" in result
        assert "All Sources" in result

    def test_includes_topic(self):
        report = create_sample_report()
        result = render.render_markdown_report(report)
        assert "Python testing" in result


class TestRenderJson:
    """Tests for JSON rendering."""

    def test_renders_valid_json(self):
        report = create_sample_report()
        result = render.render_json(report)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed['topic'] == 'Python testing'
        assert parsed['query_type'] == 'HOW_TO'


class TestRenderContextSnippet:
    """Tests for context snippet rendering."""

    def test_renders_context(self):
        report = create_sample_report()
        result = render.render_context_snippet(report)

        parsed = json.loads(result)
        assert parsed['topic'] == 'Python testing'
        assert 'top_findings' in parsed
        assert 'sources_searched' in parsed
        assert 'sources_successful' in parsed

    def test_limits_findings(self):
        report = create_sample_report()
        # Add many items
        report.all_results = [create_sample_reddit_item() for _ in range(20)]
        result = render.render_context_snippet(report)

        parsed = json.loads(result)
        assert len(parsed['top_findings']) <= 10


class TestRenderReport:
    """Tests for the main render_report function."""

    def test_default_is_markdown(self):
        report = create_sample_report()
        result = render.render_report(report)

        # Should be markdown (starts with #)
        assert result.startswith("# Research:")

    def test_json_format(self):
        report = create_sample_report()
        result = render.render_report(report, format='json')

        # Should be valid JSON
        parsed = json.loads(result)
        assert 'topic' in parsed

    def test_context_format(self):
        report = create_sample_report()
        result = render.render_report(report, format='context')

        parsed = json.loads(result)
        assert 'top_findings' in parsed
