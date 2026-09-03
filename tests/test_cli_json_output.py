"""JSON reports must survive redirected stdout with a legacy Windows encoding."""

import io
import json

import pytest

from lab28_platform import cli


def test_json_report_preserves_unicode_through_cp1252_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = io.BytesIO()
    output = io.TextIOWrapper(raw, encoding="cp1252")
    payload = {"name": "HTTP → Kafka", "student": "Nguyễn Minh Phương"}
    monkeypatch.setattr(cli.sys, "stdout", output)

    cli._emit(payload)
    output.flush()

    assert json.loads(raw.getvalue().decode("cp1252")) == payload
    assert raw.getvalue().endswith(b"\n")
