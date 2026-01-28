# Scout

Multi-source metadata fetcher for AI agent research.

## What it does

Scout fetches metadata + engagement metrics from community sources. It does NOT make decisions about ranking or presentation - the AI agent makes those decisions based on the query type it detects.

**Sources:**
- **HackerNews** - Tech discussions with points, num_comments
- **Stack Overflow** - Q&A with votes, answer_count, is_answered
- **Lobsters** - Curated tech discussions with score
- **Dev.to** - Developer articles with reactions
- **arXiv** - Academic papers
- **Wikipedia** - Encyclopedic reference
- **Reddit** - Community discussions (via URL enrichment)
- **Brave** - AI-grounded answers with citations (optional)

## Architecture

```
User Query → [AGENT detects query type] → Scout fetches metadata →
Raw JSON with engagement → [AGENT scores/ranks/formats]
```

Scout provides the data. The agent makes the decisions.

## Installation

```bash
npx skills add RolandSherwin/scout
```

Or install globally:
```bash
npx skills add RolandSherwin/scout -g
```

## Usage

### Fetch from multiple sources
```bash
python3 scripts/fetch.py all "kubernetes" --sources hn,so,lobsters
```

### Fetch from single source
```bash
python3 scripts/fetch.py hn "machine learning" --limit 10
python3 scripts/fetch.py so "python frameworks" --limit 15
```

### Enrich a Reddit URL
```bash
python3 scripts/fetch.py enrich-reddit "https://reddit.com/r/python/comments/..."
```

### Run health checks
```bash
python3 scripts/fetch.py doctor
```

### List available sources
```bash
python3 scripts/fetch.py list-sources
```

## Output Format

All output is JSON:

```json
{
  "meta": {
    "query": "kubernetes",
    "fetched_at": "2026-01-28T10:00:00Z",
    "sources_requested": ["hn", "so"]
  },
  "results": {
    "hn": {
      "success": true,
      "item_count": 10,
      "items": [
        {
          "id": "12345",
          "title": "Show HN: K8s Tool",
          "url": "https://...",
          "date": "2024-01-27",
          "date_confidence": "high",
          "engagement": {
            "points": 450,
            "num_comments": 189
          }
        }
      ]
    }
  }
}
```

## Agent Workflow

The agent (not scout) handles:
1. **Query type detection** - Is this a recommendation, news, how-to, or comparison?
2. **Source selection** - Which sources are best for this query type?
3. **Scoring** - How to weight engagement vs recency based on query type
4. **Deduplication** - Whether to merge similar results
5. **Presentation** - How to format the output for the user

See `SKILL.md` for comprehensive guidance on these decisions.

## Engagement Fields by Source

| Source | Fields |
|--------|--------|
| HackerNews | points, num_comments |
| Stack Overflow | votes, answer_count, view_count, is_answered |
| Lobsters | score, comment_count |
| Dev.to | reactions, comments |
| Reddit | score, upvote_ratio, num_comments |

## Requirements

- Python 3.8+
- Optional: `BRAVE_API_KEY` for AI-grounded answers

## License

MIT
