"""Date utilities for research skill."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import re


def get_date_range(days: int = 30) -> Tuple[str, str]:
    """Get the date range for the last N days.

    Returns:
        Tuple of (from_date, to_date) as YYYY-MM-DD strings
    """
    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=days)
    return from_date.isoformat(), today.isoformat()


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a date string in various formats.

    Supports: YYYY-MM-DD, ISO 8601, Unix timestamp
    """
    if not date_str:
        return None

    # Try Unix timestamp (from Reddit, HN)
    try:
        ts = float(date_str)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError):
        pass

    # Try ISO formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None


def timestamp_to_date(ts: Optional[float]) -> Optional[str]:
    """Convert Unix timestamp to YYYY-MM-DD string."""
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.date().isoformat()
    except (ValueError, TypeError, OSError):
        return None


def extract_date_from_url(url: str) -> Optional[str]:
    """Try to extract a date from a URL path.

    Common patterns:
    - /2024/01/15/article-title
    - /2024-01-15-article-title
    - /posts/2024-01-15
    """
    patterns = [
        r'/(\d{4})/(\d{2})/(\d{2})/',  # /2024/01/15/
        r'/(\d{4})-(\d{2})-(\d{2})',   # /2024-01-15
        r'(\d{4})(\d{2})(\d{2})',       # 20240115 (in path)
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            try:
                year, month, day = match.groups()
                dt = datetime(int(year), int(month), int(day))
                # Sanity check: not in future, not too old
                if 2010 <= dt.year <= datetime.now().year + 1:
                    return dt.date().isoformat()
            except ValueError:
                continue

    return None


def get_date_confidence(
    date_str: Optional[str],
    url: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> str:
    """Determine confidence level for a date.

    Args:
        date_str: The date to check (YYYY-MM-DD or None)
        url: Optional URL to check for date patterns
        from_date: Start of valid range (YYYY-MM-DD)
        to_date: End of valid range (YYYY-MM-DD)

    Returns:
        'high', 'med', or 'low'
    """
    if not date_str:
        # Check if URL contains a date
        if url:
            url_date = extract_date_from_url(url)
            if url_date:
                return 'med'  # URL-derived dates are medium confidence
        return 'low'

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()

        # Future date is suspicious
        if dt > today:
            return 'low'

        # If we have a range to check against
        if from_date and to_date:
            start = datetime.strptime(from_date, "%Y-%m-%d").date()
            end = datetime.strptime(to_date, "%Y-%m-%d").date()

            if start <= dt <= end:
                return 'high'
            else:
                return 'med'  # Outside range but valid date

        # If URL confirms the date, high confidence
        if url:
            url_date = extract_date_from_url(url)
            if url_date == date_str:
                return 'high'

        return 'med'

    except ValueError:
        return 'low'


def days_ago(date_str: Optional[str]) -> Optional[int]:
    """Calculate how many days ago a date is.

    Returns None if date is invalid or missing.
    """
    if not date_str:
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()
        delta = today - dt
        return delta.days
    except ValueError:
        return None


def recency_score(date_str: Optional[str], max_days: int = 365) -> int:
    """Calculate recency score (0-100).

    0 days ago = 100, max_days ago = 0, clamped.
    Default max_days is 365 (for general research, not just last 30 days).
    """
    age = days_ago(date_str)
    if age is None:
        return 0  # Unknown date gets worst score

    if age < 0:
        return 100  # Future date (treat as today)
    if age >= max_days:
        return 0

    return int(100 * (1 - age / max_days))


def format_relative_date(date_str: Optional[str]) -> str:
    """Format a date as relative time (e.g., '3 days ago', '2 weeks ago')."""
    age = days_ago(date_str)
    if age is None:
        return "unknown date"
    if age == 0:
        return "today"
    if age == 1:
        return "yesterday"
    if age < 7:
        return f"{age} days ago"
    if age < 30:
        weeks = age // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    if age < 365:
        months = age // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    years = age // 365
    return f"{years} year{'s' if years > 1 else ''} ago"
