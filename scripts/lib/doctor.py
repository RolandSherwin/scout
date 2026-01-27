"""Doctor checks for Scout CLI."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree

from . import grounding


DEFAULT_TIMEOUT = 10


@dataclass
class DoctorCheck:
    name: str
    status: str  # "ok", "warn", "error"
    detail: str
    duration_ms: int = 0


def _http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, Optional[str], Optional[str]]:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Scout Doctor/1.0",
                "Accept": "application/json, application/xml, text/xml, */*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode("utf-8", errors="replace")
            return True, data, None
    except urllib.error.HTTPError as e:
        return False, None, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, None, f"URL Error: {e.reason}"
    except TimeoutError:
        return False, None, "Request timed out"
    except Exception as e:
        return False, None, str(e)


def check_python(min_version: Tuple[int, int] = (3, 8), version_info=None) -> DoctorCheck:
    start = time.time()
    v = version_info or sys.version_info
    ok = (v.major, v.minor) >= min_version
    detail = f"Python {v.major}.{v.minor}.{v.micro}"
    status = "ok" if ok else "error"
    if not ok:
        detail += f" (requires >= {min_version[0]}.{min_version[1]})"
    duration_ms = int((time.time() - start) * 1000)
    return DoctorCheck(name="python", status=status, detail=detail, duration_ms=duration_ms)


def _check_tool(name: str, required: bool) -> DoctorCheck:
    start = time.time()
    path = shutil.which(name)
    if not path:
        status = "error" if required else "warn"
        detail = "missing"
        duration_ms = int((time.time() - start) * 1000)
        return DoctorCheck(name=f"tool:{name}", status=status, detail=detail, duration_ms=duration_ms)

    version_detail = "present"
    try:
        result = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        output = (result.stdout or result.stderr or "").strip()
        if output:
            version_detail = output.splitlines()[0]
    except Exception:
        version_detail = "present (version check failed)"

    duration_ms = int((time.time() - start) * 1000)
    return DoctorCheck(name=f"tool:{name}", status="ok", detail=version_detail, duration_ms=duration_ms)


def check_tools(required: Iterable[str], optional: Iterable[str]) -> List[DoctorCheck]:
    checks: List[DoctorCheck] = []
    for tool in required:
        checks.append(_check_tool(tool, required=True))
    for tool in optional:
        checks.append(_check_tool(tool, required=False))
    return checks


def _parse_json(name: str, payload: str) -> Optional[str]:
    try:
        json.loads(payload)
        return None
    except json.JSONDecodeError as e:
        return f"{name} JSON parse error: {e}"


def _parse_xml(name: str, payload: str) -> Optional[str]:
    try:
        ElementTree.fromstring(payload)
        return None
    except ElementTree.ParseError as e:
        return f"{name} XML parse error: {e}"


def check_endpoints() -> List[DoctorCheck]:
    checks: List[DoctorCheck] = []
    endpoints: List[Tuple[str, str, str]] = [
        ("hackernews", "json", "https://hn.algolia.com/api/v1/search?query=python&tags=story&hitsPerPage=1"),
        ("stackoverflow", "json", "https://api.stackexchange.com/2.3/search?order=desc&sort=relevance&intitle=python&site=stackoverflow&pagesize=1"),
        ("lobsters", "json", "https://lobste.rs/hottest.json"),
        ("devto", "json", "https://dev.to/api/articles?tag=python&per_page=1"),
        ("arxiv", "xml", "http://export.arxiv.org/api/query?search_query=all:python&max_results=1"),
        ("wikipedia", "json", "https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch=python&srlimit=1"),
        ("duckduckgo", "json", "https://api.duckduckgo.com/?q=python&format=json&no_html=1"),
    ]

    for name, kind, url in endpoints:
        start = time.time()
        success, data, error = _http_get(url)
        duration_ms = int((time.time() - start) * 1000)
        if not success or data is None:
            checks.append(DoctorCheck(name=f"endpoint:{name}", status="error",
                                      detail=error or "request failed", duration_ms=duration_ms))
            continue

        parse_error = _parse_json(name, data) if kind == "json" else _parse_xml(name, data)
        if parse_error:
            checks.append(DoctorCheck(name=f"endpoint:{name}", status="error",
                                      detail=parse_error, duration_ms=duration_ms))
        else:
            checks.append(DoctorCheck(name=f"endpoint:{name}", status="ok",
                                      detail="ok", duration_ms=duration_ms))

    return checks


def check_brave_grounding() -> DoctorCheck:
    start = time.time()
    api_key = (os.environ.get("BRAVE_API_KEY") or "").strip()
    if not api_key:
        duration_ms = int((time.time() - start) * 1000)
        return DoctorCheck(
            name="brave_grounding",
            status="warn",
            detail="BRAVE_API_KEY not set (optional)",
            duration_ms=duration_ms,
        )

    _, status = grounding.fetch_brave_grounded_answer("python", depth="quick")
    duration_ms = int((time.time() - start) * 1000)
    if status.success:
        return DoctorCheck(
            name="brave_grounding",
            status="ok",
            detail="ok",
            duration_ms=duration_ms,
        )
    return DoctorCheck(
        name="brave_grounding",
        status="warn",
        detail=status.error or "request failed",
        duration_ms=duration_ms,
    )


def run_doctor() -> Tuple[int, List[DoctorCheck]]:
    checks: List[DoctorCheck] = []
    checks.append(check_python())
    checks.extend(check_tools(required=["curl", "jq"], optional=["wget", "gh", "bird"]))
    checks.extend(check_endpoints())
    checks.append(check_brave_grounding())

    exit_code = 0
    for check in checks:
        if check.status == "error":
            exit_code = 1
            break
    return exit_code, checks


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _color(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _status_label(status: str) -> str:
    label = status.upper()
    if status == "ok":
        return _color(f"[{label}]", "32")  # green
    if status == "warn":
        return _color(f"[{label}]", "33")  # yellow
    return _color(f"[{label}]", "31")  # red


def _summary_line(checks: List[DoctorCheck]) -> str:
    errors = sum(1 for c in checks if c.status == "error")
    warns = sum(1 for c in checks if c.status == "warn")
    return f"Checks: {len(checks)} | Errors: {errors} | Warnings: {warns}"


def _format_check_line(check: DoctorCheck) -> str:
    duration = f"{check.duration_ms}ms"
    label = _status_label(check.status)
    return f"{label} {check.name}: {check.detail} ({duration})"


def render_report_lines(checks: List[DoctorCheck], summary_last: bool = False) -> List[str]:
    lines: List[str] = []
    header = _color("Scout Doctor", "1")
    lines.append(header)
    if not summary_last:
        lines.append(_summary_line(checks))
    for check in checks:
        lines.append(_format_check_line(check))
    if summary_last:
        lines.append(_summary_line(checks))
    return lines


def render_report(checks: List[DoctorCheck]) -> str:
    return "\n".join(render_report_lines(checks))


async def print_report_async(checks: List[DoctorCheck]) -> None:
    for line in render_report_lines(checks):
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
        await asyncio.sleep(0)


def iter_checks() -> Iterable[DoctorCheck]:
    yield check_python()
    for check in check_tools(required=["curl", "jq"], optional=["wget", "gh", "bird"]):
        yield check
    for check in check_endpoints():
        yield check
    yield check_brave_grounding()


async def print_report_stream() -> Tuple[int, List[DoctorCheck]]:
    checks: List[DoctorCheck] = []
    header = _color("Scout Doctor", "1")
    sys.stdout.write(header + "\n")
    sys.stdout.flush()

    exit_code = 0
    for check in iter_checks():
        checks.append(check)
        if check.status == "error":
            exit_code = 1
        sys.stdout.write(_format_check_line(check) + "\n")
        sys.stdout.flush()
        await asyncio.sleep(0)

    sys.stdout.write(_summary_line(checks) + "\n")
    sys.stdout.flush()
    return exit_code, checks
