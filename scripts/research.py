#!/usr/bin/env python3
"""Research CLI - Multi-source research with engagement-aware scoring.

Usage:
    python3 research.py "<query>" [--depth quick|default|deep] [--format report|json|context]

Examples:
    python3 research.py "best Python web frameworks"
    python3 research.py "kubernetes news" --depth quick
    python3 research.py "React vs Vue" --depth deep --format json
"""

import argparse
import asyncio
import re
import sys
from typing import List, Tuple

# Add lib directory to path
sys.path.insert(0, __file__.rsplit('/', 1)[0])

from lib import dates, dedupe, render, schema, score, sources, grounding, doctor


# Query type patterns
QUERY_PATTERNS = {
    'RECOMMENDATIONS': [
        r'\bbest\b', r'\btop\b', r'\brecommend', r'\bwhich\s+\w+\s+should',
        r'\bwhat\s+.*\s+good\s+for', r'\bfavorite\b', r'\bpopular\b',
    ],
    'NEWS': [
        r"\bwhat'?s\s+happening", r'\blatest\b', r'\bnews\b', r'\btoday\b',
        r'\bthis\s+week\b', r'\brecent\b', r'\bannounce', r'\brelease\b',
    ],
    'HOW_TO': [
        r'\bhow\s+to\b', r'\btutorial\b', r'\bguide\b', r'\blearn\b',
        r'\bimplement\b', r'\bsetup\b', r'\binstall\b', r'\bconfigure\b',
    ],
    'COMPARISON': [
        r'\bvs\.?\b', r'\bcompare\b', r'\bdifference\s+between\b',
        r'\bwhich\s+is\s+better\b', r'\bpros\s+and\s+cons\b',
    ],
}


def detect_query_type(query: str) -> str:
    """Detect the type of query based on patterns.

    Returns one of: RECOMMENDATIONS, NEWS, HOW_TO, COMPARISON, GENERAL
    """
    query_lower = query.lower()

    for query_type, patterns in QUERY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                return query_type

    return 'GENERAL'


def extract_core_subject(query: str) -> str:
    """Extract the core subject from a query, stripping noise words."""
    # Remove common noise words
    noise_patterns = [
        r'\bbest\b', r'\btop\b', r'\blatest\b', r'\bhow\s+to\b',
        r'\bwhat\s+is\b', r'\bwhat\s+are\b', r'\btutorial\b',
        r'\bguide\b', r'\bfor\s+beginners?\b', r'\bin\s+\d{4}\b',
    ]

    subject = query.lower()
    for pattern in noise_patterns:
        subject = re.sub(pattern, '', subject)

    # Clean up whitespace
    subject = re.sub(r'\s+', ' ', subject).strip()

    return subject if subject else query


def collect_all_items(fetch_results: dict) -> Tuple[List, List, List, List, List]:
    """Collect and categorize items from fetch results.

    Returns: (reddit, twitter, hn, so, generic)
    """
    reddit_items = []
    twitter_items = []
    hn_items = []
    so_items = []
    generic_items = []

    for source_name, result in fetch_results.items():
        if not result.success:
            continue

        for item in result.items:
            if isinstance(item, schema.HNItem):
                hn_items.append(item)
            elif isinstance(item, schema.StackOverflowItem):
                so_items.append(item)
            elif isinstance(item, schema.GenericItem):
                generic_items.append(item)
            # Note: Reddit and Twitter are typically handled by the agent,
            # not this script. But we support them if passed in.

    return reddit_items, twitter_items, hn_items, so_items, generic_items


def run_research(
    query: str,
    depth: str = 'default',
    output_format: str = 'report',
) -> str:
    """Run a full research query and return formatted results.

    Args:
        query: Search query
        depth: 'quick', 'default', or 'deep'
        output_format: 'report', 'json', or 'context'

    Returns:
        Formatted research results
    """
    # Detect query type
    query_type = detect_query_type(query)

    # Create report
    report = schema.create_report(query, query_type, depth)

    grounded_answer, grounded_status = grounding.fetch_brave_grounded_answer(query, depth=depth)
    if grounded_answer:
        report.grounded_answer = grounded_answer

    # Fetch from all sources in parallel
    fetch_results = sources.fetch_parallel(query, depth=depth)

    # Collect source statuses
    report.source_status = sources.convert_to_source_status(fetch_results)
    if grounded_status:
        report.source_status.append(grounded_status)

    # Collect items by type
    reddit, twitter, hn, so, generic = collect_all_items(fetch_results)

    # Score items by source type
    max_days = 30 if query_type == 'NEWS' else 365

    if hn:
        hn = score.score_hn_items(hn, max_days)
    if so:
        so = score.score_stackoverflow_items(so, max_days)
    if generic:
        generic = score.score_generic_items(generic, max_days)

    # Store in report
    report.hackernews = hn
    report.stackoverflow = so
    report.generic = generic

    # Combine all results
    all_items = reddit + twitter + hn + so + generic

    # Sort by score
    all_items = score.sort_all_items(all_items)

    # Deduplicate
    all_items = dedupe.dedupe_across_sources(all_items)

    report.all_results = all_items

    # Render output
    return render.render_report(report, format=output_format)


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        exit_code, _ = asyncio.run(doctor.print_report_stream())
        sys.exit(exit_code)

    parser = argparse.ArgumentParser(
        description='Multi-source research with engagement-aware scoring',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 research.py "best Python web frameworks"
  python3 research.py "kubernetes news" --depth quick
  python3 research.py "React vs Vue" --depth deep --format json
  python3 research.py doctor
        """
    )
    parser.add_argument('query', help='Search query')
    parser.add_argument(
        '--depth', '-d',
        choices=['quick', 'default', 'deep'],
        default='default',
        help='Research depth (default: default)'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['report', 'json', 'context'],
        default='report',
        help='Output format (default: report)'
    )

    args = parser.parse_args()

    try:
        result = run_research(
            query=args.query,
            depth=args.depth,
            output_format=args.format,
        )
        print(result)
    except KeyboardInterrupt:
        print("\nResearch cancelled.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
