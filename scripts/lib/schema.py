"""Data schemas for research skill.

Defines dataclasses for research results from various sources:
- RedditItem: Reddit posts/discussions
- TwitterItem: Twitter/X posts
- HNItem: HackerNews stories
- StackOverflowItem: Stack Overflow Q&A
- GenericItem: Other web sources (Dev.to, Lobsters, blogs, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Engagement:
    """Engagement metrics (varies by source type)."""
    # Reddit
    score: Optional[int] = None
    num_comments: Optional[int] = None
    upvote_ratio: Optional[float] = None

    # Twitter/X
    likes: Optional[int] = None
    reposts: Optional[int] = None
    replies: Optional[int] = None
    quotes: Optional[int] = None

    # HackerNews
    points: Optional[int] = None

    # Stack Overflow
    votes: Optional[int] = None
    is_accepted: Optional[bool] = None
    answer_count: Optional[int] = None
    view_count: Optional[int] = None

    def to_dict(self) -> Optional[Dict[str, Any]]:
        d = {}
        for key in ['score', 'num_comments', 'upvote_ratio', 'likes', 'reposts',
                    'replies', 'quotes', 'points', 'votes', 'is_accepted',
                    'answer_count', 'view_count']:
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        return d if d else None


@dataclass
class SubScores:
    """Component scores for transparency."""
    relevance: int = 0
    recency: int = 0
    engagement: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            'relevance': self.relevance,
            'recency': self.recency,
            'engagement': self.engagement,
        }


@dataclass
class Comment:
    """Top comment/answer excerpt."""
    score: int
    author: str
    excerpt: str
    url: str = ""
    date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'author': self.author,
            'excerpt': self.excerpt,
            'url': self.url,
            'date': self.date,
        }


@dataclass
class RedditItem:
    """Reddit post."""
    id: str
    title: str
    url: str
    subreddit: str
    date: Optional[str] = None
    date_confidence: str = "low"  # high/med/low
    engagement: Optional[Engagement] = None
    top_comments: List[Comment] = field(default_factory=list)
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    source_type: str = "reddit"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_type': self.source_type,
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'subreddit': self.subreddit,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'top_comments': [c.to_dict() for c in self.top_comments],
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }


@dataclass
class TwitterItem:
    """Twitter/X post."""
    id: str
    text: str
    url: str
    author_handle: str
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    source_type: str = "twitter"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_type': self.source_type,
            'id': self.id,
            'text': self.text,
            'url': self.url,
            'author_handle': self.author_handle,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }


@dataclass
class HNItem:
    """HackerNews story."""
    id: str
    title: str
    url: str
    hn_url: str  # Link to HN discussion
    author: str
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None  # points, num_comments
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    source_type: str = "hackernews"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_type': self.source_type,
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'hn_url': self.hn_url,
            'author': self.author,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }


@dataclass
class StackOverflowItem:
    """Stack Overflow question."""
    id: str
    title: str
    url: str
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None  # votes, answer_count, is_accepted
    top_answers: List[Comment] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    source_type: str = "stackoverflow"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_type': self.source_type,
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'top_answers': [a.to_dict() for a in self.top_answers],
            'tags': self.tags,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }


@dataclass
class GenericItem:
    """Generic web item (Dev.to, Lobsters, arXiv, Wikipedia, blogs, etc.)."""
    id: str
    title: str
    url: str
    source_name: str  # e.g., "devto", "lobsters", "arxiv", "wikipedia"
    snippet: str = ""
    author: str = ""
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None  # May have points for Lobsters/Dev.to
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    source_type: str = "generic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_type': self.source_type,
            'source_name': self.source_name,
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet,
            'author': self.author,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }


# Type alias for any research item
ResearchItem = RedditItem | TwitterItem | HNItem | StackOverflowItem | GenericItem


@dataclass
class SourceStatus:
    """Status of a source fetch."""
    source_name: str
    success: bool
    item_count: int = 0
    error: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            'source_name': self.source_name,
            'success': self.success,
            'item_count': self.item_count,
        }
        if self.error:
            d['error'] = self.error
        if self.duration_ms:
            d['duration_ms'] = self.duration_ms
        return d


@dataclass
class ResearchReport:
    """Full research report."""
    topic: str
    query_type: str  # RECOMMENDATIONS, NEWS, HOW_TO, COMPARISON, GENERAL
    depth: str  # quick, default, deep
    generated_at: str

    # Results by source
    reddit: List[RedditItem] = field(default_factory=list)
    twitter: List[TwitterItem] = field(default_factory=list)
    hackernews: List[HNItem] = field(default_factory=list)
    stackoverflow: List[StackOverflowItem] = field(default_factory=list)
    generic: List[GenericItem] = field(default_factory=list)

    # Combined sorted results
    all_results: List[ResearchItem] = field(default_factory=list)

    # Source status tracking
    source_status: List[SourceStatus] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'topic': self.topic,
            'query_type': self.query_type,
            'depth': self.depth,
            'generated_at': self.generated_at,
            'reddit': [r.to_dict() for r in self.reddit],
            'twitter': [t.to_dict() for t in self.twitter],
            'hackernews': [h.to_dict() for h in self.hackernews],
            'stackoverflow': [s.to_dict() for s in self.stackoverflow],
            'generic': [g.to_dict() for g in self.generic],
            'all_results': [r.to_dict() for r in self.all_results],
            'source_status': [s.to_dict() for s in self.source_status],
        }


def create_report(topic: str, query_type: str, depth: str) -> ResearchReport:
    """Create a new research report."""
    return ResearchReport(
        topic=topic,
        query_type=query_type,
        depth=depth,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
