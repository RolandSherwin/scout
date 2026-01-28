#!/usr/bin/env python3
"""Fetch CLI - Multi-source metadata fetcher.

Scout fetches metadata + engagement from community sources. It does NOT fetch
article content - the agent uses WebFetch for that. The agent makes all decisions
about ranking, scoring, deduplication, and presentation.

Usage:
    python3 fetch.py all "<query>" [--sources hn,so,lobsters] [--limit 10]
    python3 fetch.py hn "<query>" [--limit 10]
    python3 fetch.py so "<query>" [--limit 10]
    python3 fetch.py lobsters "<query>" [--limit 10]
    python3 fetch.py devto "<query>" [--limit 10]
    python3 fetch.py arxiv "<query>" [--limit 10]
    python3 fetch.py wikipedia "<query>" [--limit 5]
    python3 fetch.py enrich-reddit "<url>"
    python3 fetch.py brave "<query>"
    python3 fetch.py list-sources
    python3 fetch.py doctor
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import List, Optional

# Add lib directory to path
sys.path.insert(0, __file__.rsplit('/', 1)[0])

from lib import dates, schema, sources, grounding, doctor, enrich


# Available sources
AVAILABLE_SOURCES = {
    'hn': 'HackerNews - points, num_comments',
    'so': 'Stack Overflow - votes, answer_count, view_count, is_answered',
    'lobsters': 'Lobsters - score, comment_count',
    'devto': 'Dev.to - reactions, comments',
    'arxiv': 'arXiv - academic papers (no engagement)',
    'wikipedia': 'Wikipedia - encyclopedic (no engagement)',
}

DEFAULT_SOURCES = ['hn', 'so', 'lobsters', 'devto']


def fetch_single_source(
    source: str,
    query: str,
    limit: int = 10,
) -> dict:
    """Fetch from a single source and return raw JSON.

    Args:
        source: Source name (hn, so, lobsters, devto, arxiv, wikipedia)
        query: Search query
        limit: Maximum results to return

    Returns:
        Dict with meta, results, and source_status
    """
    response = {
        'meta': {
            'query': query,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'sources_requested': [source],
        },
        'results': {},
        'source_status': [],
    }

    # Map source name to fetch function
    fetch_map = {
        'hn': sources.fetch_hackernews,
        'so': sources.fetch_stackoverflow,
        'lobsters': sources.fetch_lobsters,
        'devto': sources.fetch_devto,
        'arxiv': sources.fetch_arxiv,
        'wikipedia': sources.fetch_wikipedia,
    }

    if source not in fetch_map:
        return {
            'error': f'Unknown source: {source}. Use list-sources to see available sources.',
        }

    fetch_fn = fetch_map[source]
    result = fetch_fn(query, limit=limit)

    # Convert items to dicts
    items = [item.to_dict() for item in result.items]

    response['results'][source] = {
        'success': result.success,
        'item_count': len(items),
        'items': items,
        'error': result.error,
        'duration_ms': result.duration_ms,
    }

    response['source_status'].append({
        'source_name': source,
        'success': result.success,
        'item_count': len(items),
        'error': result.error,
        'duration_ms': result.duration_ms,
    })

    return response


def fetch_all_sources(
    query: str,
    sources_list: Optional[List[str]] = None,
    limit: int = 10,
) -> dict:
    """Fetch from multiple sources in parallel and return raw JSON.

    Args:
        query: Search query
        sources_list: List of source names (default: hn, so, lobsters, devto)
        limit: Maximum results per source

    Returns:
        Dict with meta, results by source, and source_status
    """
    if sources_list is None:
        sources_list = DEFAULT_SOURCES

    response = {
        'meta': {
            'query': query,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'sources_requested': sources_list,
        },
        'results': {},
        'source_status': [],
    }

    # Fetch in parallel using the existing parallel fetch infrastructure
    fetch_results = sources.fetch_parallel(
        query,
        sources=sources_list,
        depth='default',
        limit=limit,
    )

    # Convert results
    for source_name, result in fetch_results.items():
        items = [item.to_dict() for item in result.items]

        response['results'][source_name] = {
            'success': result.success,
            'item_count': len(items),
            'items': items,
            'error': result.error,
            'duration_ms': result.duration_ms,
        }

        response['source_status'].append({
            'source_name': source_name,
            'success': result.success,
            'item_count': len(items),
            'error': result.error,
            'duration_ms': result.duration_ms,
        })

    return response


def fetch_brave_grounding(query: str) -> dict:
    """Fetch grounded answer from Brave API.

    Args:
        query: Search query

    Returns:
        Dict with grounded answer and citations
    """
    response = {
        'meta': {
            'query': query,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'sources_requested': ['brave'],
        },
        'grounded_answer': None,
        'source_status': [],
    }

    answer, status = grounding.fetch_brave_grounded_answer(query)

    if answer:
        response['grounded_answer'] = answer.to_dict()

    if status:
        response['source_status'].append(status.to_dict())

    return response


def enrich_reddit_url(url: str) -> dict:
    """Enrich a Reddit URL with real engagement data.

    Args:
        url: Reddit post URL

    Returns:
        Dict with enriched Reddit data
    """
    response = {
        'meta': {
            'url': url,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'sources_requested': ['reddit-enrich'],
        },
        'result': None,
        'error': None,
    }

    try:
        info = enrich.extract_reddit_url_info(url)
        item = schema.RedditItem(
            id=info['post_id'] if info else url,
            title='',
            url=url,
            subreddit=info['subreddit'] if info else '',
        )
        enriched, error = enrich.enrich_reddit_item_with_error(item)
        response['result'] = enriched.to_dict()
        response['error'] = error
    except Exception as e:
        response['error'] = str(e)

    return response


def list_sources() -> dict:
    """List all available sources with their engagement fields."""
    return {
        'sources': [
            {
                'name': name,
                'description': desc,
            }
            for name, desc in AVAILABLE_SOURCES.items()
        ],
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Multi-source metadata fetcher for AI agent research',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  all           Fetch from multiple sources in parallel
  hn            Fetch from HackerNews
  so            Fetch from Stack Overflow
  lobsters      Fetch from Lobsters
  devto         Fetch from Dev.to
  arxiv         Fetch from arXiv
  wikipedia     Fetch from Wikipedia
  enrich-reddit Enrich a Reddit URL with engagement data
  brave         Fetch grounded answer from Brave API
  list-sources  List available sources
  doctor        Run health checks

Examples:
  python3 fetch.py all "python frameworks" --sources hn,so
  python3 fetch.py hn "machine learning" --limit 20
  python3 fetch.py enrich-reddit "https://reddit.com/r/python/comments/..."
  python3 fetch.py doctor
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # all command
    all_parser = subparsers.add_parser('all', help='Fetch from multiple sources')
    all_parser.add_argument('query', help='Search query')
    all_parser.add_argument('--sources', '-s', help='Comma-separated sources (default: hn,so,lobsters,devto)')
    all_parser.add_argument('--limit', '-l', type=int, default=10, help='Max results per source')

    # Single source commands
    for source in AVAILABLE_SOURCES:
        source_parser = subparsers.add_parser(source, help=f'Fetch from {source}')
        source_parser.add_argument('query', help='Search query')
        source_parser.add_argument('--limit', '-l', type=int, default=10, help='Max results')

    # enrich-reddit command
    enrich_parser = subparsers.add_parser('enrich-reddit', help='Enrich Reddit URL')
    enrich_parser.add_argument('url', help='Reddit post URL')

    # brave command
    brave_parser = subparsers.add_parser('brave', help='Fetch grounded answer from Brave')
    brave_parser.add_argument('query', help='Search query')

    # list-sources command
    subparsers.add_parser('list-sources', help='List available sources')

    # doctor command
    subparsers.add_parser('doctor', help='Run health checks')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == 'doctor':
            exit_code, _ = asyncio.run(doctor.print_report_stream())
            sys.exit(exit_code)

        elif args.command == 'list-sources':
            result = list_sources()

        elif args.command == 'all':
            sources_list = args.sources.split(',') if args.sources else None
            result = fetch_all_sources(args.query, sources_list, args.limit)

        elif args.command == 'enrich-reddit':
            result = enrich_reddit_url(args.url)

        elif args.command == 'brave':
            result = fetch_brave_grounding(args.query)

        elif args.command in AVAILABLE_SOURCES:
            result = fetch_single_source(args.command, args.query, args.limit)

        else:
            parser.print_help()
            sys.exit(1)

        # Output JSON
        print(json.dumps(result, indent=2))

    except KeyboardInterrupt:
        print("\nFetch cancelled.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
