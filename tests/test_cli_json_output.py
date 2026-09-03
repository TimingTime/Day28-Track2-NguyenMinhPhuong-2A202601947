"""JSON reports must survive redirected stdout with a legacy Windows encoding."""

import io
import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

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


def test_release_keeps_third_party_progress_out_of_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lab28_platform import model_registry

    class RegistryWithProgress:
        def __init__(self, settings: object) -> None:
            pass

        def register(self, spec: object, *, promote: bool) -> SimpleNamespace:
            print("MLflow: view the registered run")
            return SimpleNamespace(
                name="lab28-rag-release", version="1", to_dict=lambda: {"version": "1"}
            )

    monkeypatch.setattr(model_registry, "ReleaseRegistry", RegistryWithProgress)
    monkeypatch.setattr(cli, "_delta_version", lambda _: None)

    result = CliRunner().invoke(cli.app, ["release"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"version": "1"}
    assert "MLflow: view the registered run" in result.stderr
