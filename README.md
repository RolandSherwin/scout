# Scout

Multi-source research agent with engagement-aware scoring.

## What it does

Scout searches across multiple platforms simultaneously and ranks results by relevance, recency, and engagement:

- **Google** - General web results
- **Reddit** - Community discussions with upvotes/comments
- **HackerNews** - Tech discussions with points
- **Twitter/X** - Real-time opinions via bird CLI
- **Stack Overflow** - Programming Q&A with vote counts
- **Lobsters** - Curated tech discussions
- **Dev.to** - Developer articles
- **arXiv** - Academic papers
- **Wikipedia** - Encyclopedic overviews

## Installation

```bash
npx skills add RolandSherwin/scout
```

Or install globally:
```bash
npx skills add RolandSherwin/scout -g
```

## Usage

```
/scout best Python web frameworks
/scout --quick kubernetes news
/scout --deep React vs Vue comparison
```

### Depth Options

| Flag | Sources | Use Case |
|------|---------|----------|
| `--quick` | 5-10 | Fast scan, time-sensitive queries |
| *(default)* | 15-25 | Balanced research |
| `--deep` | 40-60 | Comprehensive analysis |

## Features

- **Engagement-aware scoring** - Weighs upvotes, comments, and points
- **Query type detection** - Optimizes strategy for recommendations, news, how-to, comparisons
- **Parallel fetching** - Searches multiple sources concurrently
- **Deduplication** - Removes similar content across sources
- **Advanced filtering** - Domain allowlist/denylist, freshness, date ranges
- **Source reliability tracking** - Reports which sources succeeded/failed

## Output Format

Scout returns a structured report with:

- Summary with source count
- Top findings ranked by score with engagement metrics
- Categorized results (Twitter, Community, Dev, Academic)
- Conflicting information highlighted
- Source reliability table
- Full citations with confidence levels

## How Scoring Works

Results are scored using a tiered system:

| Tier | Sources | Formula |
|------|---------|---------|
| 1 | Reddit, Twitter | 45% relevance + 25% recency + 30% engagement |
| 2 | HN, SO, Lobsters | Same formula with -5 tier penalty |
| 3 | Web, blogs, docs | 55% relevance + 45% recency - 15 penalty |

## Requirements

- Any agent runner that supports sub-agents and web tools (search + HTTP fetch)
- Python 3.8+ (for enhanced scoring scripts)
- Required CLI tools: `curl`, `jq`
- Optional CLI tools: `wget`, `gh`, [bird CLI](https://github.com/steipete/bird) (Twitter/X)

## Full Config (APIs)

To unlock all features, set the following API key(s):

- `BRAVE_API_KEY` — Brave AI Grounding (grounded answer with citations)

## License

MIT
