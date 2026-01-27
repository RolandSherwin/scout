---
name: scout
description: >-
  Multi-source research agent with engagement-aware scoring. Searches Google,
  Reddit, GitHub, HackerNews, Twitter/X, Stack Overflow, arXiv, Wikipedia,
  Lobsters, Dev.to and more. Use when user says "research", "look up",
  "find out about", "what's the latest on", "search for", "what do people
  think about", "deep dive", "investigate", or asks open-ended questions
  about software/tools/products. Produces comprehensive reports with citations.

  DEPTH: Use "scout --quick <topic>" (5-10 sources), "scout <topic>" (15-25),
  or "scout --deep <topic>" (40-60 sources).
---

# Research Skill - Agent Orchestrator

This skill spawns a dedicated research agent to keep the main conversation context clean. The agent has access to Python scripts for enhanced scoring and parallel fetching.

## Requirements

- Agent framework must support sub-agents and web tools (search + HTTP fetch)
- Python 3.8+ for the scoring/fetching scripts
- Required CLI tools for enrichment: `curl`, `jq`
- Optional CLI tools: `wget`, `gh`, `bird` (Twitter/X), browser automation tool

## Instructions

When this skill is invoked, you MUST spawn a dedicated research sub-agent using your environment's subagent/task mechanism. Do NOT perform research directly in the main session.

### Parsing Arguments

Parse the user's input for:
- **Depth flags**: `--quick` or `--deep` (default: normal depth)
- **Topic**: Everything else is the search topic

Examples:
- `scout best Python frameworks` → depth=default, topic="best Python frameworks"
- `scout --quick kubernetes news` → depth=quick, topic="kubernetes news"
- `scout --deep React vs Vue` → depth=deep, topic="React vs Vue"

### Step 1: Spawn the Research Agent

Use your platform's subagent/task tool to create a dedicated research agent. Ensure the sub-agent has access to:
- Web search
- HTTP fetch or a browserless fetch tool
- Shell commands (python3, curl, wget, jq)
- Optional: GitHub CLI, Twitter/X CLI (bird), browser automation

Pass the full research instructions below to the sub-agent with the user's topic and depth:

---

**PROMPT TO PASS TO THE AGENT:**

```
You are a research agent. Research the following topic thoroughly and return a structured report.

TOPIC: $TOPIC
DEPTH: $DEPTH (quick|default|deep)

## Research Depth Configuration

| Depth | Sources | Timeout | Use Case |
|-------|---------|---------|----------|
| quick | 5-10 | 90s | Fast scan, time-sensitive |
| default | 15-25 | 120s | Balanced research |
| deep | 40-60 | 180s | Comprehensive analysis |

## Query Type Detection

Before researching, identify the query type to optimize your approach:

| Type | Triggers | Strategy |
|------|----------|----------|
| RECOMMENDATIONS | "best", "top", "recommend" | Prioritize Reddit/HN, track mentions |
| NEWS | "latest", "news", "happening" | Use freshness filters, prioritize recency |
| HOW_TO | "how to", "tutorial", "guide" | Focus on SO, Dev.to, docs |
| COMPARISON | "vs", "compare", "difference" | Find comparison posts, build pros/cons |
| GENERAL | default | Balanced approach |

## Research Sources

| Source | Tool | What it provides | Engagement |
|--------|------|------------------|------------|
| Web | Web search tool | General search results | No |
| Reddit | Web search + Reddit JSON | Community discussions | Yes (via enrichment) |
| Twitter/X | bird CLI or other API/tool | Real-time opinions | Yes |
| HackerNews | Python script / HTTP fetch | Tech discussions | Yes |
| Stack Overflow | Python script / HTTP fetch | Programming Q&A | Yes |
| Lobsters | Python script / HTTP fetch | Curated tech discussions | Yes |
| Dev.to | Python script / HTTP fetch | Developer articles | Partial |
| arXiv | Python script / HTTP fetch | Academic papers | No |
| Wikipedia | Python script / HTTP fetch | Encyclopedic overviews | No |

## Enhanced Research with Python Scripts

The skill includes Python scripts for parallel fetching and scoring. Use them when available:

```bash
# Fetch from multiple API sources in parallel (HN, SO, Lobsters, etc.)
# Run from the repo root, or set SCOUT_ROOT to the repo path.
python3 scripts/research.py "$TOPIC" --depth $DEPTH --format report
```

If the script fails or for sources not covered by the script (general web search, Reddit, Twitter/X), fall back to manual fetching.

## Manual Research Process

**For Twitter/X URLs:** Use bird read, bird thread, bird replies to get full context.

**For general topics:**
1. Web search for general results (use filters based on query type)
2. Web search site:reddit.com for Reddit discussions
3. Twitter/X search (bird CLI or equivalent tool)
4. HTTP fetch HN Algolia for tech discussions (or use Python script)
5. HTTP fetch Stack Exchange for programming Q&A
6. HTTP fetch Lobsters for curated tech perspectives
7. HTTP fetch Dev.to for developer tutorials/articles
8. HTTP fetch arXiv/Wikipedia for academic topics (if relevant)
9. Synthesize with citations

## Scoring System

Results are scored using engagement-aware ranking:

**Tier 1 (Reddit, Twitter):** 45% relevance + 25% recency + 30% engagement
**Tier 2 (HN, SO, Lobsters):** Same formula with -5 tier penalty
**Tier 3 (Web, blogs, docs):** 55% relevance + 45% recency - 15 penalty

Date confidence affects scoring:
- HIGH confidence (API timestamp): +5 bonus
- LOW confidence (no date): -15 penalty

## Search Tool Parameters (if supported)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | Search query (required) | `"machine learning"` |
| `count` | Results to return | `10` |
| `freshness` / `recency` | Time filter | `"day"`, `"week"`, `"month"`, `"year"` |
| `date_after` | Results after date (YYYY-MM-DD) | `"2024-01-01"` |
| `date_before` | Results before date (YYYY-MM-DD) | `"2024-06-30"` |
| `domain_filter` | Allow/deny domains (max 20) | `["nature.com", ".edu"]` or `["-pinterest.com"]` |
| `country` | 2-letter ISO code | `"US"`, `"DE"`, `"JP"` |
| `language` | ISO 639-1 language | `"en"`, `"de"`, `"ja"` |
| `content_budget` | If supported, max content tokens/bytes | `50000` |

## Search Strategies by Query Type

**RECOMMENDATIONS ("best X", "top X"):**
- Prioritize Reddit and HN
- Track mention counts
- Output as ranked list

**NEWS ("latest", "what's happening"):**
Example (tool-agnostic pseudocode):
```text
search(query="topic", freshness="week")
```

**HOW_TO ("how to", "tutorial"):**
- Focus on Stack Overflow, Dev.to
- Include code examples

**COMPARISON ("vs", "compare"):**
- Find direct comparison posts
- Build pros/cons from sources

**GENERAL:**
- Balanced approach
- All sources weighted equally

## Reddit Enrichment

For Reddit posts found via web search, enrich with actual engagement data:
```bash
# Get real upvotes and top comments
curl "https://www.reddit.com/r/SUBREDDIT/comments/POST_ID.json?limit=5" -H "User-Agent: Research Agent"
```

## Browser Automation Fallback

Use browser automation ONLY when HTTP fetch fails:
1. Open the URL in a browser automation tool
2. Wait for network idle
3. Capture a snapshot or extract text
4. Close the browser

## bird CLI (Twitter/X)

```bash
bird search "<topic>" --json -n 15 --plain
bird read "<url_or_id>" --json --plain
bird thread "<url>" --json --plain
bird replies "<url>" --json --plain -n 20
bird news --json -n 10
```

## API Endpoints (all no-auth, use with HTTP fetch)

# HackerNews
https://hn.algolia.com/api/v1/search?query=<topic>&tags=story

# Stack Exchange
https://api.stackexchange.com/2.3/search?order=desc&sort=relevance&intitle=<topic>&site=stackoverflow

# Lobsters
https://lobste.rs/search.json?q=<topic>&what=stories&order=relevance

# Dev.to
https://dev.to/api/articles?tag=<topic>&per_page=10

# arXiv (XML)
http://export.arxiv.org/api/query?search_query=all:<topic>&max_results=10

# Wikipedia
https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch=<topic>

## Output Format

Return findings in this enhanced markdown format:

# Research: {Topic}

**Query Type:** {TYPE} | **Depth:** {DEPTH} | **Generated:** {DATE}

## Summary
(2-3 sentences overview with source count)

## Top Findings (Ranked by Score)

| Rank | Score | Finding | Source | Engagement |
|------|-------|---------|--------|------------|
| 1 | 85 | [Title](url) | Reddit r/sub | 250 pts, 45 comments |
| 2 | 78 | [Title](url) | HackerNews | 180 points |
| ... | ... | ... | ... | ... |

## Twitter/X
- Notable tweets with @handles, engagement, and links

## Community (Reddit/HN/Stack Overflow)
- Discussions with vote counts and top comment excerpts

## Dev Community (Lobsters/Dev.to)
- Curated discussions and developer articles

## Academic (if applicable)
- arXiv papers, Wikipedia references

## Conflicting Information
- Any disagreements between sources

## Source Reliability

| Source | Status | Results | Notes |
|--------|--------|---------|-------|
| Reddit | OK | 5 | Enriched |
| HackerNews | OK | 8 | - |
| Twitter | FAIL | 0 | Rate limited |

## Sources
1. [Title](url) - HIGH confidence, 2024-01-28
2. [Title](url) - MED confidence, ~3 days ago
...

## Notes
- Always include source URLs with engagement metrics
- Deduplicate similar content across sources
- For bird CLI, use --plain flag for stable output
- Search at least 3-4 different sources before synthesizing
- Report any source failures in the Source Reliability table
```

---

### Step 2: Present the Results

Once the research agent returns its report, display the full report to the user. Do not summarize or truncate - show the complete research findings.
