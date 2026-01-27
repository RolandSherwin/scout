"""Brave AI Grounding client."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

from . import schema


BRAVE_GROUNDING_ENDPOINT = "https://api.search.brave.com/res/v1/chat/completions"
DEFAULT_TIMEOUT = 60


_CITATION_RE = re.compile(r"<citation>(.*?)</citation>", re.DOTALL)
_USAGE_RE = re.compile(r"<usage>(.*?)</usage>", re.DOTALL)
_ENUM_RE = re.compile(r"</?enum_item>", re.DOTALL)


def _strip_tags(text: str) -> str:
    text = _CITATION_RE.sub("", text)
    text = _USAGE_RE.sub("", text)
    text = _ENUM_RE.sub("", text)
    return text


def _parse_grounding_text(text: str) -> Tuple[str, List[schema.GroundedCitation], Optional[Dict[str, Any]]]:
    citations: List[schema.GroundedCitation] = []
    for raw in _CITATION_RE.findall(text):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        citations.append(schema.GroundedCitation(
            number=payload.get("number"),
            url=payload.get("url", ""),
            snippet=payload.get("snippet", ""),
            start_index=payload.get("start_index"),
            end_index=payload.get("end_index"),
            favicon=payload.get("favicon"),
        ))

    usage: Optional[Dict[str, Any]] = None
    usage_match = _USAGE_RE.search(text)
    if usage_match:
        try:
            usage = json.loads(usage_match.group(1))
        except json.JSONDecodeError:
            usage = None

    cleaned = _strip_tags(text).strip()
    return cleaned, citations, usage


def _build_payload(query: str, depth: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": "brave",
        "stream": True,
        "messages": [
            {"role": "user", "content": query},
        ],
        "enable_citations": True,
    }
    if depth == "deep":
        payload["enable_research"] = True
    return payload


def fetch_brave_grounded_answer(
    query: str,
    depth: str = "default",
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[Optional[schema.GroundedAnswer], schema.SourceStatus]:
    """Fetch a grounded answer from Brave AI Grounding."""
    start = time.time()
    api_key = (os.environ.get("BRAVE_API_KEY") or "").strip()
    if not api_key:
        return None, schema.SourceStatus(
            source_name="brave_grounding",
            success=False,
            error="missing_brave_api_key",
        )

    payload = _build_payload(query, depth)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BRAVE_GROUNDING_ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Subscription-Token": api_key,
        },
        method="POST",
    )

    parts: List[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            for raw in response:
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        payload = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choice = (payload.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        parts.append(content)
                else:
                    # Non-stream fallback
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    choice = (payload.get("choices") or [{}])[0]
                    message = choice.get("message") or {}
                    content = message.get("content")
                    if content:
                        parts.append(content)
        full_text = "".join(parts)
        cleaned, citations, usage = _parse_grounding_text(full_text)
        answer = schema.GroundedAnswer(text=cleaned, citations=citations, usage=usage)
        duration_ms = int((time.time() - start) * 1000)
        return answer, schema.SourceStatus(
            source_name="brave_grounding",
            success=True,
            item_count=len(citations),
            duration_ms=duration_ms,
        )
    except urllib.error.HTTPError as e:
        duration_ms = int((time.time() - start) * 1000)
        return None, schema.SourceStatus(
            source_name="brave_grounding",
            success=False,
            error=f"HTTP {e.code}: {e.reason}",
            duration_ms=duration_ms,
        )
    except urllib.error.URLError as e:
        duration_ms = int((time.time() - start) * 1000)
        return None, schema.SourceStatus(
            source_name="brave_grounding",
            success=False,
            error=f"URL Error: {e.reason}",
            duration_ms=duration_ms,
        )
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return None, schema.SourceStatus(
            source_name="brave_grounding",
            success=False,
            error=str(e),
            duration_ms=duration_ms,
        )
