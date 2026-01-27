"""Output rendering module for research results.

Supports multiple output formats:
- report: Full markdown report (default)
- json: JSON output for programmatic use
- context: Compact snippet for embedding in other skills
"""

import json
from typing import List, Optional

from . import dates, schema


def render_engagement(item: schema.ResearchItem) -> str:
    """Render engagement metrics as a compact string."""
    eng = getattr(item, 'engagement', None)
    if not eng:
        return "-"

    parts = []

    # Reddit/Lobsters
    if eng.score is not None:
        parts.append(f"{eng.score:,} pts")
    if eng.num_comments is not None:
        parts.append(f"{eng.num_comments} comments")

    # Twitter
    if eng.likes is not None:
        parts.append(f"{eng.likes:,} likes")
    if eng.reposts is not None:
        parts.append(f"{eng.reposts:,} reposts")

    # HackerNews
    if eng.points is not None and eng.score is None:  # Avoid duplication
        parts.append(f"{eng.points} points")

    # Stack Overflow
    if eng.votes is not None:
        parts.append(f"{eng.votes} votes")
    if eng.answer_count is not None:
        parts.append(f"{eng.answer_count} answers")

    return ", ".join(parts) if parts else "-"


def render_source_badge(item: schema.ResearchItem) -> str:
    """Render a source badge for an item."""
    if isinstance(item, schema.RedditItem):
        return f"Reddit r/{item.subreddit}"
    elif isinstance(item, schema.TwitterItem):
        return f"Twitter @{item.author_handle}"
    elif isinstance(item, schema.HNItem):
        return "HackerNews"
    elif isinstance(item, schema.StackOverflowItem):
        return "Stack Overflow"
    elif isinstance(item, schema.GenericItem):
        return item.source_name.title()
    return "Unknown"


def get_item_title(item: schema.ResearchItem) -> str:
    """Get the title/text from an item."""
    if hasattr(item, 'title') and item.title:
        return item.title
    if hasattr(item, 'text') and item.text:
        return item.text[:100] + ('...' if len(item.text) > 100 else '')
    return "(no title)"


def get_item_url(item: schema.ResearchItem) -> str:
    """Get the best URL for an item."""
    url = getattr(item, 'url', '')
    # For HN items, prefer the HN discussion URL
    if isinstance(item, schema.HNItem) and item.hn_url:
        return item.hn_url
    return url


def render_findings_table(items: List[schema.ResearchItem], max_items: int = 15) -> str:
    """Render a scored findings table."""
    if not items:
        return "*No findings*\n"

    lines = ["| Rank | Score | Finding | Source | Engagement |",
             "|------|-------|---------|--------|------------|"]

    for i, item in enumerate(items[:max_items], 1):
        title = get_item_title(item)
        url = get_item_url(item)

        # Truncate long titles
        if len(title) > 60:
            title = title[:57] + "..."

        # Escape pipe characters in title
        title = title.replace("|", "\\|")

        source = render_source_badge(item)
        engagement = render_engagement(item)
        score = getattr(item, 'score', 0)

        # Create markdown link
        finding = f"[{title}]({url})" if url else title

        lines.append(f"| {i} | {score} | {finding} | {source} | {engagement} |")

    return "\n".join(lines) + "\n"


def render_source_status(statuses: List[schema.SourceStatus]) -> str:
    """Render source reliability table."""
    if not statuses:
        return ""

    lines = ["\n## Source Reliability\n",
             "| Source | Status | Results | Duration | Notes |",
             "|--------|--------|---------|----------|-------|"]

    for status in statuses:
        status_emoji = "OK" if status.success else "FAIL"
        duration = f"{status.duration_ms}ms" if status.duration_ms else "-"
        notes = status.error if status.error else "-"

        lines.append(
            f"| {status.source_name.title()} | {status_emoji} | "
            f"{status.item_count} | {duration} | {notes} |"
        )

    return "\n".join(lines) + "\n"


def render_grounded_answer_section(answer: Optional[schema.GroundedAnswer]) -> str:
    """Render grounded answer section."""
    if not answer or not answer.text:
        return ""

    lines = ["\n## Grounded Answer\n", answer.text.strip(), ""]

    if answer.citations:
        lines.append("**Citations:**")
        for c in answer.citations:
            label = f"[{c.number}]" if c.number is not None else "-"
            snippet = c.snippet.replace("\n", " ").strip()
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            lines.append(f"- {label} {c.url} — {snippet}")
        lines.append("")

    return "\n".join(lines)


def render_comments(item: schema.ResearchItem, max_comments: int = 3) -> str:
    """Render top comments for an item."""
    comments = getattr(item, 'top_comments', []) or []
    if not comments:
        return ""

    lines = []
    for c in comments[:max_comments]:
        score = c.score
        author = c.author
        excerpt = c.excerpt[:200] + ('...' if len(c.excerpt) > 200 else '')
        lines.append(f"  - **{author}** ({score} pts): {excerpt}")

    return "\n".join(lines)


def render_reddit_section(items: List[schema.RedditItem]) -> str:
    """Render Reddit findings section."""
    if not items:
        return ""

    lines = ["\n### Reddit\n"]

    for item in items[:10]:
        title = item.title
        url = item.url
        subreddit = item.subreddit
        eng = render_engagement(item)
        date_str = dates.format_relative_date(item.date)

        lines.append(f"- [{title}]({url}) (r/{subreddit}, {eng}, {date_str})")

        # Add top comments if available
        comments = render_comments(item)
        if comments:
            lines.append(comments)

    return "\n".join(lines) + "\n"


def render_twitter_section(items: List[schema.TwitterItem]) -> str:
    """Render Twitter findings section."""
    if not items:
        return ""

    lines = ["\n### Twitter/X\n"]

    for item in items[:10]:
        text = item.text[:150] + ('...' if len(item.text) > 150 else '')
        url = item.url
        author = item.author_handle
        eng = render_engagement(item)
        date_str = dates.format_relative_date(item.date)

        lines.append(f"- **@{author}**: \"{text}\" ([link]({url}), {eng}, {date_str})")

    return "\n".join(lines) + "\n"


def render_community_section(
    hn_items: List[schema.HNItem],
    so_items: List[schema.StackOverflowItem],
) -> str:
    """Render HackerNews and Stack Overflow section."""
    if not hn_items and not so_items:
        return ""

    lines = ["\n### Community (HN/Stack Overflow)\n"]

    if hn_items:
        lines.append("**HackerNews:**\n")
        for item in hn_items[:5]:
            title = item.title
            hn_url = item.hn_url
            eng = render_engagement(item)
            date_str = dates.format_relative_date(item.date)
            lines.append(f"- [{title}]({hn_url}) ({eng}, {date_str})")

    if so_items:
        if hn_items:
            lines.append("")
        lines.append("**Stack Overflow:**\n")
        for item in so_items[:5]:
            title = item.title
            url = item.url
            eng = render_engagement(item)
            tags = ", ".join(item.tags[:3]) if item.tags else ""
            lines.append(f"- [{title}]({url}) ({eng}, tags: {tags})")

    return "\n".join(lines) + "\n"


def render_generic_section(items: List[schema.GenericItem]) -> str:
    """Render generic items (Lobsters, Dev.to, Wikipedia, etc.)."""
    if not items:
        return ""

    # Group by source
    by_source = {}
    for item in items:
        source = item.source_name
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(item)

    lines = ["\n### Other Sources\n"]

    for source, source_items in by_source.items():
        lines.append(f"**{source.title()}:**\n")
        for item in source_items[:5]:
            title = item.title
            url = item.url
            eng = render_engagement(item)
            date_str = dates.format_relative_date(item.date)
            lines.append(f"- [{title}]({url}) ({eng}, {date_str})")
        lines.append("")

    return "\n".join(lines)


def render_markdown_report(report: schema.ResearchReport) -> str:
    """Render a full markdown research report."""
    lines = [
        f"# Research: {report.topic}\n",
        f"**Query Type:** {report.query_type} | **Depth:** {report.depth} | "
        f"**Generated:** {report.generated_at[:10]}\n",
    ]

    # Summary section
    lines.append("\n## Summary\n")
    total_items = (len(report.reddit) + len(report.twitter) +
                   len(report.hackernews) + len(report.stackoverflow) +
                   len(report.generic))
    successful_sources = sum(1 for s in report.source_status if s.success)
    total_sources = len(report.source_status)
    lines.append(f"Found {total_items} results from {successful_sources}/{total_sources} sources.\n")

    grounded_section = render_grounded_answer_section(report.grounded_answer)
    if grounded_section:
        lines.append(grounded_section)

    # Top findings table
    lines.append("\n## Top Findings (Ranked by Score)\n")
    lines.append(render_findings_table(report.all_results))

    # Detailed sections
    lines.append(render_reddit_section(report.reddit))
    lines.append(render_twitter_section(report.twitter))
    lines.append(render_community_section(report.hackernews, report.stackoverflow))
    lines.append(render_generic_section(report.generic))

    # Source status
    lines.append(render_source_status(report.source_status))

    # Sources list
    lines.append("\n## All Sources\n")
    seen_urls = set()
    source_num = 1
    for item in report.all_results[:30]:
        url = get_item_url(item)
        if url and url not in seen_urls:
            seen_urls.add(url)
            title = get_item_title(item)
            confidence = getattr(item, 'date_confidence', 'low')
            date = getattr(item, 'date', '') or 'unknown'
            lines.append(f"{source_num}. [{title}]({url}) - {confidence} confidence, {date}")
            source_num += 1

    return "\n".join(lines)


def render_json(report: schema.ResearchReport) -> str:
    """Render report as JSON."""
    return json.dumps(report.to_dict(), indent=2)


def render_context_snippet(report: schema.ResearchReport) -> str:
    """Render a compact context snippet for embedding.

    Designed for other skills to consume without re-researching.
    """
    top_findings = []
    for item in report.all_results[:10]:
        top_findings.append({
            'text': get_item_title(item),
            'source': render_source_badge(item),
            'url': get_item_url(item),
            'score': getattr(item, 'score', 0),
            'engagement': render_engagement(item),
        })

    successful = sum(1 for s in report.source_status if s.success)

    context = {
        'topic': report.topic,
        'query_type': report.query_type,
        'timestamp': report.generated_at,
        'top_findings': top_findings,
        'sources_searched': len(report.source_status),
        'sources_successful': successful,
    }

    return json.dumps(context, indent=2)


def render_report(
    report: schema.ResearchReport,
    format: str = 'report',
) -> str:
    """Render report in the specified format.

    Args:
        report: Research report to render
        format: 'report' (markdown), 'json', or 'context'

    Returns:
        Formatted output string
    """
    if format == 'json':
        return render_json(report)
    elif format == 'context':
        return render_context_snippet(report)
    else:
        return render_markdown_report(report)
