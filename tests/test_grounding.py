"""Unit tests for Brave grounding parsing."""

import json

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import grounding


def test_parse_grounding_text_extracts_citations_and_usage():
    citation_payload = {
        "number": 1,
        "url": "https://example.com",
        "snippet": "Example snippet",
        "start_index": 0,
        "end_index": 10,
    }
    usage_payload = {"prompt_tokens": 10, "completion_tokens": 20}

    text = (
        "Answer text "
        f"<citation>{json.dumps(citation_payload)}</citation>"
        " more text "
        f"<usage>{json.dumps(usage_payload)}</usage>"
    )

    cleaned, citations, usage = grounding._parse_grounding_text(text)

    assert "citation" not in cleaned
    assert "usage" not in cleaned
    assert cleaned.startswith("Answer text")
    assert len(citations) == 1
    assert citations[0].url == "https://example.com"
    assert usage == usage_payload


def test_strip_tags_removes_enum_item():
    text = "Test <enum_item>Item</enum_item> end"
    cleaned, citations, usage = grounding._parse_grounding_text(text)
    assert cleaned == "Test Item end"
    assert citations == []
    assert usage is None
