---
name: scout
description: >-
  Multi-source research agent with engagement-aware scoring. Searches Google, Reddit,
  GitHub, HackerNews, Twitter/X, Stack Overflow, arXiv, Wikipedia, Lobsters, Dev.to
  and more. Use when user says "research", "look up", "find out about", "what's the
  latest on", "search for", "what do people think about", "deep dive", "investigate",
  or asks open-ended questions about software/tools/products. Produces comprehensive
  reports with citations.
  DEPTH: Use "scout --quick <topic>" (5-10 sources), "scout <topic>" (15-25), or
  "scout --deep <topic>" (40-60 sources).
argument-hint: "<query>" or "--quick <query>" or "--deep <query>"
---

# Scout - Community Metadata Fetcher

Scout fetches metadata + engagement from community sources. It does NOT fetch article
content - use WebFetch for that. Reddit requires URL enrichment. YOU make all decisions
about ranking and presentation.

## What Scout Does vs What You Do

| Scout Does (Deterministic) | You Do (Judgment) |
|---------------------------|-------------------|
| Call HN/SO/Lobsters/etc APIs | Decide which sources to query |
| Parse JSON responses | Detect query type (RECOMMENDATIONS, NEWS, etc.) |
| Return engagement metrics | Score/rank results based on query type |
| Reddit enrichment for engagement | Deduplicate if needed |
| | Decide which URLs to fetch with WebFetch |
| | Format output for user |

---

## NEVER Do

- **NEVER call scout for single-source lookups** - Use WebFetch directly for a known URL
- **NEVER call scout for real-time data** - Twitter/X results may be minutes old; use the twitter skill instead
- **NEVER trust Reddit engagement without enrichment** - Web search results lack real scores; always enrich Reddit URLs
- **NEVER skip query type detection** - Different queries need different source weights; detect FIRST, then fetch
- **NEVER present raw JSON to users** - Always synthesize, rank, and format results appropriately
- **NEVER call scout repeatedly for the same query** - Use WebFetch on URLs you already have
- **NEVER use scout when user provides specific URLs** - Just fetch those URLs directly with WebFetch

---

## CRITICAL: Parse User Intent First

Before calling scout, analyze the user's query to determine the best approach:

### Step 1: Detect Query Type

| Type | Trigger Patterns | Your Strategy |
|------|-----------------|---------------|
| RECOMMENDATIONS | "best X", "top X", "recommend", "which should I use" | Weight engagement higher (points, votes) |
| NEWS | "what's happening with X", "latest", "news", "today" | Weight recency higher (date) |
| HOW_TO | "how to X", "tutorial", "guide", "implement" | Weight is_answered, answer_count (SO) |
| COMPARISON | "X vs Y", "compare", "difference between" | Aggregate mentions across sources |
| GENERAL | anything else | Balanced approach |

### Step 2: Select Sources Based on Query Type

| Query Type | Best Sources | Why |
|------------|--------------|-----|
| RECOMMENDATIONS | hn, lobsters, reddit (via web search) | Community discussion, upvotes indicate quality |
| NEWS | hn, lobsters | Tech news aggregators |
| HOW_TO | so, devto | Has is_answered, code examples |
| COMPARISON | hn, so, lobsters | Discussion threads with pros/cons |
| ACADEMIC | arxiv, wikipedia | Academic papers, encyclopedic |
| GENERAL | hn, so, lobsters, devto | Balanced coverage |

**Store these for later:**
- `QUERY_TYPE` = [detected type]
- `TOPIC` = [core topic extracted]
- `SELECTED_SOURCES` = [sources to query]

> **For advanced query patterns**: Read [`references/query_patterns.md`](references/query_patterns.md) for detailed trigger patterns, scoring adjustments by query type, and source priority tiers.

---

## Quick Reference

```bash
python3 scripts/fetch.py all "<query>"                    # All sources
python3 scripts/fetch.py all "<query>" --sources hn,so    # Specific sources
python3 scripts/fetch.py enrich-reddit "<reddit-url>"     # Get real Reddit engagement
python3 scripts/fetch.py brave "<query>"                  # AI grounded answer (needs BRAVE_API_KEY)
python3 scripts/fetch.py doctor                           # Health check
```

---

## Available Sources

| Source | Command | Engagement Fields | Notes |
|--------|---------|-------------------|-------|
| HackerNews | `hn` | points, num_comments | Tech discussions, high signal |
| Stack Overflow | `so` | votes, answer_count, view_count, is_answered | Q&A, has accepted answers |
| Lobsters | `lobsters` | score, comment_count | Curated tech, smaller community |
| Dev.to | `devto` | reactions, comments | Developer tutorials/articles |
| arXiv | `arxiv` | (none) | Academic papers |
| Wikipedia | `wikipedia` | (none) | Encyclopedic reference |
| DuckDuckGo | `duckduckgo` | (none) | Instant answers/related topics |
| Reddit | `enrich-reddit <url>` | score, upvote_ratio, num_comments, top_comments | Requires URL |
| Brave | `brave` | (grounded answer) | AI-generated with citations |

---

## Output Schema

JSON with `meta`, `results` (by source), and `source_status`. Key fields per item:
- `title`, `url`, `author`, `date`, `date_confidence` ("high"/"med"/"low")
- `engagement`: source-specific metrics (see table below)

Check `source_status` for failures - continue with successful sources.

---

## Fields Available for Your Scoring

Each source returns different engagement metrics. Use these to rank results based on your detected query type.

### Engagement Metrics by Source

| Source | Field | What It Means | Good For |
|--------|-------|---------------|----------|
| HackerNews | `points` | Community upvotes | Quality signal |
| HackerNews | `num_comments` | Discussion activity | Controversial/interesting |
| Stack Overflow | `votes` | Answer quality | Technical accuracy |
| Stack Overflow | `answer_count` | Number of solutions | Well-answered questions |
| Stack Overflow | `view_count` | Popularity | Common problems |
| Stack Overflow | `is_answered` | Has accepted answer | Solved problems |
| Lobsters | `score` | Community votes | Quality signal |
| Lobsters | `comment_count` | Discussion depth | Nuanced topics |
| Dev.to | `reactions` | Reader engagement | Popular articles |
| Dev.to | `comments` | Discussion | Active topics |
| Reddit | `score` | Net upvotes | Community agreement |
| Reddit | `upvote_ratio` | Controversy indicator | Low = divisive |
| Reddit | `num_comments` | Discussion activity | Hot topics |

### Date Fields

Every item includes:
- `date`: ISO date string (e.g., "2024-01-27")
- `date_confidence`: "high" | "med" | "low"

**Scoring tip:** Weight items with "high" date_confidence more reliably for recency scoring. "low" confidence means the date is uncertain or missing.

---

## Suggested Scoring Strategies

You decide weights based on query type. Here are suggested approaches:

### For RECOMMENDATIONS ("best X", "top X")

```
Score = (engagement_weight * normalized_engagement) + (recency_weight * recency_score)

Suggested weights:
- engagement_weight = 0.7 (high - community validated)
- recency_weight = 0.3 (moderate - still want recent)

Also:
- Count mentions across sources (FastAPI mentioned 5x = higher confidence)
- Check comment count (high comments = active discussion)
```

### For NEWS ("what's happening with X")

```
Score = (recency_weight * recency_score) + (engagement_weight * normalized_engagement)

Suggested weights:
- recency_weight = 0.6 (high - freshness matters)
- engagement_weight = 0.4 (moderate - still check engagement)

Also:
- Prefer items with date_confidence = "high"
- Filter to last 30 days if possible
```

### For HOW_TO ("how to X")

```
Score = (answered_bonus * is_answered) + (votes_weight * votes) + (recency_weight * recency)

Suggested weights:
- answered_bonus = 20 points if is_answered = true
- votes_weight = 0.5
- recency_weight = 0.3

Also:
- Prioritize SO results (has is_answered, answer_count)
- Check answer_count > 1 for multiple perspectives
```

### For COMPARISON ("X vs Y")

```
Approach:
1. Search for "X vs Y" directly
2. Also search for "X" and "Y" separately
3. Count mentions of each option
4. Look for direct comparison posts (title contains "vs")
5. Aggregate pros/cons from comments

Present as:
- Side-by-side comparison
- Mention counts
- Community sentiment
```

---

## Iterative Research Workflow

Scout returns metadata. You decide what to do next. Follow this workflow:

### Step 1: Initial Fetch

```bash
python3 scripts/fetch.py all "your query" --sources hn,so,lobsters
```

### Step 2: Evaluate Results

Look at the returned JSON and evaluate:

1. **Engagement signals:**
   - High points/votes = community-validated
   - High comments = active discussion
   - is_answered = true = solved problem

2. **Date signals:**
   - Recent date + high confidence = fresh, reliable
   - Old date = may be outdated (but classics can still be relevant)

3. **Coverage:**
   - Did all sources return results?
   - Are there different perspectives across sources?

### Step 3: Decide Next Action

**If results look promising:**
- Use WebFetch to read the top 2-3 URLs with highest engagement
- Focus on URLs where you want more detail
- Synthesize what you learn

**If results are sparse:**
- Try a refined query (more specific or more general)
- Try different sources (e.g., add arxiv for academic topics)
- Try alternative phrasings

**If you need more depth:**
- Call scout again with a narrower query
- Fetch more URLs from the initial results

### Step 4: Synthesize and Present

After gathering metadata and fetching key URLs:

1. Combine insights from metadata + fetched content
2. Apply your scoring based on query type
3. Present in format appropriate to user's question:
   - Ranked list for recommendations
   - Timeline for news
   - Step-by-step for how-to
   - Comparison table for vs queries

---

## Concrete Examples

### Example 1: Recommendation Query

**User:** "What are the best Python web frameworks?"

**Your analysis:**
- Query type: RECOMMENDATIONS
- Topic: "Python web frameworks"
- Best sources: hn, so (high engagement, community discussion)

**Step 1: Fetch**
```bash
python3 scripts/fetch.py all "python web frameworks" --sources hn,so
```

**Step 2: Evaluate results**
```
Results show:
- FastAPI: 450 points, 189 comments on HN
- Django: 320 points, 95 comments on HN; 125 votes on SO
- Flask: 180 points on HN
```

**Step 3: Decide**
- FastAPI has highest engagement - fetch its URL for details
- Multiple frameworks mentioned - this is a comparison

**Step 4: Use WebFetch on top results**
- Fetch FastAPI article to understand why it's popular
- Fetch Django comparison thread

**Step 5: Synthesize**
```
Based on community engagement across HackerNews and Stack Overflow:

1. FastAPI (450 pts, 189 comments) - Modern, async, fast
2. Django (320 pts + 125 SO votes) - Full-featured, mature
3. Flask (180 pts) - Lightweight, flexible

FastAPI is trending with highest recent engagement...
```

---

### Example 2: How-To Query

**User:** "How do I handle authentication in Next.js?"

**Your analysis:**
- Query type: HOW_TO
- Topic: "nextjs authentication"
- Best sources: so, devto (has is_answered, code examples)

**Step 1: Fetch**
```bash
python3 scripts/fetch.py all "nextjs authentication" --sources so,hn,devto
```

**Step 2: Evaluate results**
```
SO results:
- "NextAuth.js vs Clerk" - 45 votes, is_answered=true
- "JWT auth in Next.js" - 32 votes, is_answered=true

HN results:
- "Show HN: Auth.js 5.0" - 120 comments
```

**Step 3: Decide**
- SO item with is_answered=true and 45 votes is high quality
- HN discussion has 120 comments - likely good debate
- Fetch both for comprehensive answer

**Step 4: Use WebFetch**
- Fetch SO accepted answer for implementation details
- Fetch HN discussion for community opinions

**Step 5: Synthesize**
```
For Next.js authentication, the community recommends:

1. NextAuth.js (Auth.js) - Most mentioned (8x across sources)
   - 45 votes on accepted SO answer
   - 120 comments on HN launch thread

2. Clerk - Mentioned 5x, rising in popularity

Implementation steps from the SO accepted answer:
[Include code from fetched content]
```

---

### Example 3: News Query

**User:** "What's happening with AI coding assistants?"

**Your analysis:**
- Query type: NEWS
- Topic: "AI coding assistants"
- Best sources: hn, lobsters (tech news)

**Step 1: Fetch**
```bash
python3 scripts/fetch.py all "AI coding assistants" --sources hn,lobsters
```

**Step 2: Evaluate results**
- Sort by date (prefer recent)
- Check date_confidence (prefer "high")
- Note high-engagement items even if older

**Step 3: Present timeline**
```
Recent developments in AI coding assistants:

This week:
- [Title] - 230 points, 89 comments (Jan 27)
- [Title] - 180 points (Jan 26)

Last month:
- [Title] - 450 points (major announcement)

Key themes: ...
```

---

## When to Call Scout Again

Scout can be called multiple times in a research session. Call it again when:

1. **Initial results are sparse** - Try different query phrasing
2. **You need a specific source** - Query just that source with narrower terms
3. **User asks follow-up** - New aspect of the topic
4. **Comparison needs both sides** - Fetch each option separately

**Don't call again when:**
- You already have good results - just use WebFetch on URLs
- The question is about content you already fetched
- Simple clarification doesn't need new data

---

## Reddit Research (Special Case)

Scout doesn't search Reddit directly (no public search API). Instead:

1. Use your WebSearch tool with `site:reddit.com` to find Reddit posts
2. When you find a Reddit URL, enrich it:
   ```bash
   python3 scripts/fetch.py enrich-reddit "https://reddit.com/r/python/comments/abc123"
   ```
3. This returns real engagement data: score, upvote_ratio, top_comments

---

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `BRAVE_API_KEY` | Enable Brave AI Grounding (optional) |

---

## Summary

1. **Analyze the query** - Detect type (RECOMMENDATIONS, NEWS, HOW_TO, etc.)
2. **Select sources** - Choose based on query type
3. **Fetch metadata** - Use scout to get engagement data
4. **Evaluate results** - Look at engagement, dates, coverage
5. **Fetch content** - Use WebFetch on promising URLs
6. **Synthesize** - Combine insights, apply scoring, present appropriately

Scout gives you the data. You make the decisions.
