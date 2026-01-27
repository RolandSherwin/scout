"""Unit tests for the deduplication module."""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import dedupe, schema


class TestNormalizeUrl:
    """Tests for URL normalization."""

    def test_strips_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        result = dedupe.normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert result == "https://example.com/article"

    def test_strips_trailing_slash(self):
        url = "https://example.com/article/"
        result = dedupe.normalize_url(url)
        assert result == "https://example.com/article"

    def test_lowercases_domain(self):
        url = "https://EXAMPLE.COM/Article"
        result = dedupe.normalize_url(url)
        assert "example.com" in result

    def test_preserves_non_tracking_params(self):
        url = "https://example.com/search?q=python&page=2"
        result = dedupe.normalize_url(url)
        assert "q=python" in result
        assert "page=2" in result

    def test_handles_empty_url(self):
        result = dedupe.normalize_url("")
        assert result == ""

    def test_handles_invalid_url(self):
        url = "not-a-valid-url"
        result = dedupe.normalize_url(url)
        # Should return something (may include protocol artifacts from urlparse)
        # The important thing is it doesn't raise an exception
        assert result is not None
        assert "not-a-valid-url" in result


class TestNormalizeText:
    """Tests for text normalization."""

    def test_lowercases(self):
        result = dedupe.normalize_text("HELLO World")
        assert result == "hello world"

    def test_removes_punctuation(self):
        result = dedupe.normalize_text("Hello, World! How are you?")
        assert result == "hello world how are you"

    def test_collapses_whitespace(self):
        result = dedupe.normalize_text("Hello    World\n\tTest")
        assert result == "hello world test"


class TestGetNgrams:
    """Tests for n-gram generation."""

    def test_basic_ngrams(self):
        ngrams = dedupe.get_ngrams("hello")
        # With n=3: "hel", "ell", "llo"
        assert "hel" in ngrams
        assert "ell" in ngrams
        assert "llo" in ngrams

    def test_short_text(self):
        ngrams = dedupe.get_ngrams("hi")
        # Text shorter than n, return text itself
        assert ngrams == {"hi"}

    def test_empty_text(self):
        ngrams = dedupe.get_ngrams("")
        assert ngrams == set()


class TestJaccardSimilarity:
    """Tests for Jaccard similarity."""

    def test_identical_sets(self):
        set1 = {"a", "b", "c"}
        set2 = {"a", "b", "c"}
        assert dedupe.jaccard_similarity(set1, set2) == 1.0

    def test_disjoint_sets(self):
        set1 = {"a", "b", "c"}
        set2 = {"x", "y", "z"}
        assert dedupe.jaccard_similarity(set1, set2) == 0.0

    def test_partial_overlap(self):
        set1 = {"a", "b", "c"}
        set2 = {"b", "c", "d"}
        # Intersection: {b, c} = 2
        # Union: {a, b, c, d} = 4
        # Jaccard: 2/4 = 0.5
        assert dedupe.jaccard_similarity(set1, set2) == 0.5

    def test_empty_set(self):
        assert dedupe.jaccard_similarity(set(), {"a"}) == 0.0
        assert dedupe.jaccard_similarity({"a"}, set()) == 0.0
        assert dedupe.jaccard_similarity(set(), set()) == 0.0


class TestItemsMatchByUrl:
    """Tests for URL-based matching."""

    def test_same_url(self):
        item1 = schema.GenericItem(id='1', title='Test', url='https://example.com/post', source_name='test')
        item2 = schema.GenericItem(id='2', title='Test', url='https://example.com/post', source_name='test')
        assert dedupe.items_match_by_url(item1, item2) is True

    def test_same_url_with_tracking(self):
        item1 = schema.GenericItem(id='1', title='Test', url='https://example.com/post?utm_source=twitter', source_name='test')
        item2 = schema.GenericItem(id='2', title='Test', url='https://example.com/post?utm_source=reddit', source_name='test')
        assert dedupe.items_match_by_url(item1, item2) is True

    def test_different_urls(self):
        item1 = schema.GenericItem(id='1', title='Test', url='https://example.com/post1', source_name='test')
        item2 = schema.GenericItem(id='2', title='Test', url='https://example.com/post2', source_name='test')
        assert dedupe.items_match_by_url(item1, item2) is False

    def test_empty_url(self):
        item1 = schema.GenericItem(id='1', title='Test', url='', source_name='test')
        item2 = schema.GenericItem(id='2', title='Test', url='https://example.com/post', source_name='test')
        assert dedupe.items_match_by_url(item1, item2) is False


class TestItemsSimilarByText:
    """Tests for text-based similarity."""

    def test_identical_titles(self):
        item1 = schema.RedditItem(id='1', title='Python is great', url='', subreddit='test')
        item2 = schema.RedditItem(id='2', title='Python is great', url='', subreddit='test')
        assert dedupe.items_similar_by_text(item1, item2) is True

    def test_very_similar_titles(self):
        item1 = schema.RedditItem(id='1', title='Python is great for beginners', url='', subreddit='test')
        item2 = schema.RedditItem(id='2', title='Python is great for beginner developers', url='', subreddit='test')
        # Very similar, should exceed threshold
        assert dedupe.items_similar_by_text(item1, item2, threshold=0.5) is True

    def test_different_titles(self):
        item1 = schema.RedditItem(id='1', title='Python programming tutorial', url='', subreddit='test')
        item2 = schema.RedditItem(id='2', title='JavaScript web development', url='', subreddit='test')
        assert dedupe.items_similar_by_text(item1, item2) is False


class TestFindDuplicatePairs:
    """Tests for finding duplicate pairs."""

    def test_finds_url_duplicates(self):
        items = [
            schema.GenericItem(id='1', title='Post A', url='https://example.com/post', source_name='test'),
            schema.GenericItem(id='2', title='Post B', url='https://example.com/other', source_name='test'),
            schema.GenericItem(id='3', title='Post C', url='https://example.com/post?ref=twitter', source_name='test'),  # Duplicate of 1
        ]
        pairs = dedupe.find_duplicate_pairs(items)
        assert (0, 2) in pairs

    def test_finds_text_duplicates(self):
        items = [
            schema.RedditItem(id='1', title='Python is awesome', url='https://reddit.com/1', subreddit='test'),
            schema.RedditItem(id='2', title='Python is awesome', url='https://reddit.com/2', subreddit='test'),  # Identical title
        ]
        pairs = dedupe.find_duplicate_pairs(items)
        assert (0, 1) in pairs

    def test_no_duplicates(self):
        items = [
            schema.RedditItem(id='1', title='Python tutorial', url='https://example.com/1', subreddit='test'),
            schema.RedditItem(id='2', title='JavaScript guide', url='https://example.com/2', subreddit='test'),
        ]
        pairs = dedupe.find_duplicate_pairs(items)
        assert len(pairs) == 0


class TestDedupeItems:
    """Tests for item deduplication."""

    def test_keeps_higher_scored(self):
        item1 = schema.RedditItem(id='1', title='Same title', url='https://example.com/a', subreddit='test')
        item1.score = 80

        item2 = schema.RedditItem(id='2', title='Same title', url='https://example.com/b', subreddit='test')
        item2.score = 50

        result = dedupe.dedupe_items([item1, item2])

        assert len(result) == 1
        assert result[0].id == '1'  # Higher score kept

    def test_empty_list(self):
        result = dedupe.dedupe_items([])
        assert result == []

    def test_single_item(self):
        item = schema.RedditItem(id='1', title='Only one', url='https://example.com', subreddit='test')
        result = dedupe.dedupe_items([item])
        assert len(result) == 1

    def test_no_duplicates_preserved(self):
        items = [
            schema.RedditItem(id='1', title='First post', url='https://example.com/1', subreddit='test'),
            schema.RedditItem(id='2', title='Second different post', url='https://example.com/2', subreddit='test'),
        ]
        result = dedupe.dedupe_items(items)
        assert len(result) == 2


class TestDedupeAcrossSources:
    """Tests for cross-source deduplication."""

    def test_dedupes_across_sources(self):
        reddit_item = schema.RedditItem(
            id='r1',
            title='Python 4.0 released',
            url='https://python.org/news/v4',
            subreddit='python',
        )
        reddit_item.score = 80

        hn_item = schema.HNItem(
            id='hn1',
            title='Python 4.0 released',
            url='https://python.org/news/v4',
            hn_url='https://news.ycombinator.com/item?id=123',
            author='user',
        )
        hn_item.score = 60

        result = dedupe.dedupe_across_sources([reddit_item, hn_item])

        # Same URL, keep higher-scored one
        assert len(result) == 1
        assert result[0].id == 'r1'
