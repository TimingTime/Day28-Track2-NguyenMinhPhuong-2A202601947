"""Run the original live suite and save its output; external tracing is opt-in."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-langsmith", action="store_true")
    parser.add_argument("--require-gpu", action="store_true")
    args = parser.parse_args()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["LAB28_OTEL_ENABLED"] = "true"
    if args.include_langsmith:
        from dotenv import dotenv_values

        for key, value in dotenv_values(ROOT / ".env").items():
            if value is not None:
                environment.setdefault(key, value)
        environment.setdefault("LANGSMITH_API_KEY", environment.get("LANGCHAIN_API_KEY", ""))
        environment.setdefault(
            "LANGSMITH_PROJECT", environment.get("LANGCHAIN_PROJECT", "lab28-platform")
        )
        if not environment.get("LANGSMITH_API_KEY"):
            parser.error("--include-langsmith requires a key in the environment or .env")

    if args.require_gpu:
        from lab28_platform.llm_client import probe_identity
        from lab28_platform.settings import Settings

        identity = probe_identity(Settings.from_env().vllm)
        if not identity.is_real_vllm:
            parser.error(f"real vLLM required before running: {identity.detail}")

    output = ROOT / "reports/runtime"
    output.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / ".lab28/test-runs" / uuid4().hex
    if not temporary.resolve().is_relative_to(ROOT) or temporary.exists():
        raise ValueError("pytest temporary directory must be new and repository-local")
    command = [sys.executable, "-m", "pytest", "integration-tests", "-q", "-x", "--tb=short"]
    if not args.include_langsmith:
        command += ["-m", "not langsmith"]
    visible_command = ["python", *command[1:]]
    command += [f"--basetemp={temporary}"]
    started = datetime.now(UTC).isoformat()
    log = output / "full-suite.txt"
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            command, cwd=ROOT, env=environment, stdout=stream,
            stderr=subprocess.STDOUT, check=False,
        )
    content = log.read_text(encoding="utf-8").replace(str(ROOT), "<repository>")
    for key in ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "LAB28_VLLM_API_KEY"):
        if secret := environment.get(key):
            content = content.replace(secret, "<redacted>")
    log.write_text(content, encoding="utf-8")
    report = {
        "started_at_utc": started,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "command": visible_command,
        "exit_code": result.returncode,
        "require_gpu": args.require_gpu,
        "include_langsmith": args.include_langsmith,
        "api_url": environment.get("LAB28_API_URL", "http://localhost:8000"),
        "gateway_url": environment.get("LAB28_GATEWAY_URL", "http://localhost:8080"),
        "mlflow_url": environment.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        "scope": "Original live tests; fixtures and environment gates retained",
        "output": "reports/runtime/full-suite.txt",
    }
    (output / "full-suite.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(content[-6500:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
