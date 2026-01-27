# Query Type Detection Patterns

This document describes how the research skill categorizes queries and adapts its behavior accordingly.

## Query Types

### RECOMMENDATIONS

**Purpose:** User wants ranked lists of options with community opinions.

**Trigger Patterns:**
- "best X", "top X"
- "recommend", "what should I use"
- "which X should I", "what's good for"
- "favorite", "popular"

**Examples:**
- "best Python web frameworks"
- "top CI/CD tools for small teams"
- "recommend a database for my project"

**Strategy:**
- Prioritize Reddit and HN for community opinions
- Track mention counts across sources
- Output as ranked list with vote/mention counts
- Higher weight on engagement metrics

**Source Priority:**
1. Reddit (upvotes indicate community preference)
2. HackerNews (tech community validation)
3. Stack Overflow (for tools/library recommendations)
4. Dev.to (developer articles comparing options)

---

### NEWS

**Purpose:** User wants current events and recent developments.

**Trigger Patterns:**
- "what's happening with", "latest"
- "news about", "today", "this week"
- "recent", "announce", "release"

**Examples:**
- "latest Python news"
- "what's happening with Kubernetes"
- "React 19 release news"

**Strategy:**
- Use `freshness: "week"` or `freshness: "day"` in WebSearch
- Prioritize Twitter for real-time updates
- Sort by recency over engagement
- Reduce recency scoring window to 30 days

**Source Priority:**
1. Twitter (real-time updates)
2. HackerNews (tech news aggregation)
3. WebSearch with freshness filter
4. Dev.to (recent articles)

---

### HOW_TO

**Purpose:** User wants tutorials, guides, or implementation help.

**Trigger Patterns:**
- "how to", "tutorial"
- "guide", "learn"
- "implement", "setup", "install", "configure"

**Examples:**
- "how to test async Python code"
- "React hooks tutorial"
- "setup Kubernetes on AWS"

**Strategy:**
- Prioritize Stack Overflow and documentation
- Focus on sources with code examples
- Include step-by-step content in output
- Higher relevance weight for technical accuracy

**Source Priority:**
1. Stack Overflow (Q&A with code)
2. Dev.to (tutorials)
3. Official documentation (via WebSearch)
4. HackerNews (discussion threads with solutions)

---

### COMPARISON

**Purpose:** User wants to evaluate multiple options.

**Trigger Patterns:**
- "vs", "compare"
- "difference between"
- "which is better"
- "pros and cons"

**Examples:**
- "React vs Vue"
- "PostgreSQL vs MySQL comparison"
- "which is better: pytest or unittest"

**Strategy:**
- Find direct comparison posts
- Build pros/cons table from sources
- Include benchmark data if available
- Look for "vs" threads on Reddit/HN

**Source Priority:**
1. Reddit (comparison threads)
2. HackerNews (tech comparisons)
3. Stack Overflow (specific feature comparisons)
4. Dev.to (comparison articles)

---

### GENERAL

**Purpose:** Broad research on a topic (default when no pattern matches).

**Trigger Patterns:**
- Default when no other pattern matches

**Examples:**
- "Python asyncio"
- "microservices architecture"
- "machine learning"

**Strategy:**
- Balanced approach across all sources
- Standard scoring weights
- Include Wikipedia for background
- Comprehensive output format

**Source Priority:**
1. All sources weighted equally
2. Standard scoring: 45% relevance + 25% recency + 30% engagement

---

## Source Priority Tiers

### Tier 1: Engagement Available
- **Reddit**: Real upvotes, comments via JSON API
- **Twitter**: Likes, retweets, reply counts

These sources get full engagement scoring (45/25/30 weights).

### Tier 2: Community Curated
- **HackerNews**: Points, comment counts
- **Stack Overflow**: Votes, accepted answers
- **Lobsters**: Votes, tags

These sources get engagement scoring with a small (-5) tier penalty.

### Tier 3: No Engagement
- **General WebSearch**
- **Dev.to articles** (limited engagement)
- **Blog posts**
- **Documentation**

These sources use the reweighted formula (55/45) with -15 penalty.

---

## Scoring Adjustments by Query Type

| Query Type | Recency Window | Engagement Weight | Special Rules |
|------------|---------------|-------------------|---------------|
| RECOMMENDATIONS | 365 days | High (30%) | Boost Reddit/HN |
| NEWS | 30 days | Medium (20%) | Boost recency to 35% |
| HOW_TO | 365 days | Medium (25%) | Boost SO/docs |
| COMPARISON | 365 days | High (30%) | Look for "vs" content |
| GENERAL | 365 days | Standard (30%) | No adjustments |

---

## Implementation Notes

1. **Query Type Detection** is done in `scripts/research.py:detect_query_type()`
2. **Scoring adjustments** are applied in `scripts/lib/score.py`
3. **Source selection** is handled in `scripts/lib/sources.py:get_sources_for_depth()`
4. The agent can override these defaults based on specific user instructions
