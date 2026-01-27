import pytest

from lib import doctor


class DummyProc:
    def __init__(self, stdout="", stderr=""):
        self.stdout = stdout
        self.stderr = stderr


def test_check_python_version_fail():
    check = doctor.check_python(version_info=type("V", (), {"major": 3, "minor": 7, "micro": 0})())
    assert check.status == "error"


def test_check_tools_required_missing(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    checks = doctor.check_tools(required=["curl"], optional=[])
    assert checks[0].status == "error"


def test_check_tools_optional_missing(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    checks = doctor.check_tools(required=[], optional=["bird"])
    assert checks[0].status == "warn"


def test_check_tool_version(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *args, **kwargs: DummyProc(stdout="tool 1.2.3\n"),
    )
    checks = doctor.check_tools(required=["curl"], optional=[])
    assert "1.2.3" in checks[0].detail


def test_check_endpoints_json(monkeypatch):
    def fake_get(url, timeout=doctor.DEFAULT_TIMEOUT):
        return True, '{"ok": true}', None

    monkeypatch.setattr(doctor, "_http_get", fake_get)
    monkeypatch.setattr(doctor, "_parse_json", lambda name, payload: None)
    monkeypatch.setattr(doctor, "_parse_xml", lambda name, payload: None)
    checks = doctor.check_endpoints()
    assert all(c.status == "ok" for c in checks)


def test_check_endpoints_error(monkeypatch):
    def fake_get(url, timeout=doctor.DEFAULT_TIMEOUT):
        return False, None, "boom"

    monkeypatch.setattr(doctor, "_http_get", fake_get)
    checks = doctor.check_endpoints()
    assert all(c.status == "error" for c in checks)


def test_brave_grounding_no_key(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    check = doctor.check_brave_grounding()
    assert check.status == "warn"


def test_brave_grounding_with_key(monkeypatch):
    class DummyStatus:
        success = True
        error = None

    monkeypatch.setenv("BRAVE_API_KEY", "x")
    monkeypatch.setattr(doctor.grounding, "fetch_brave_grounded_answer", lambda *args, **kwargs: (None, DummyStatus()))
    check = doctor.check_brave_grounding()
    assert check.status == "ok"
