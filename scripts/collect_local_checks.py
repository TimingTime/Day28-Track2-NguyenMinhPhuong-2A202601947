"""Save reproducible local validation output without claiming live integration success."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "local-checks"


def run_check(name: str, arguments: list[str]) -> dict[str, Any]:
    started = time.monotonic()
    if arguments[1:3] == ["-m", "pytest"]:
        # Each run owns a fresh temp directory, including when Windows users differ.
        temporary = ROOT / ".lab28" / "test-runs" / uuid4().hex
        if not temporary.resolve().is_relative_to(ROOT.resolve()) or temporary.exists():
            raise ValueError("pytest temporary directory must be new and inside the repository")
        temporary.parent.mkdir(parents=True, exist_ok=True)
        arguments = [*arguments, f"--basetemp={temporary}"]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["LAB28_OTEL_ENABLED"] = "false"
    try:
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
        )
        output = result.stdout + result.stderr
        returncode = result.returncode
    except (OSError, subprocess.TimeoutExpired) as error:
        output = f"{type(error).__name__}: {error}\n"
        returncode = 124 if isinstance(error, subprocess.TimeoutExpired) else 127
    # Keep reports portable; no user-specific interpreter/workspace paths are needed.
    output = output.replace(str(ROOT), "<repository>").replace(str(Path.home()), "<user>")
    path = OUTPUT / f"{name}.txt"
    path.write_text(output or "Command completed successfully without output.\n", encoding="utf-8")
    command = [
        "python" if part == sys.executable else part.replace(str(ROOT), "<repository>")
        for part in arguments
    ]
    record = {
        "name": name,
        "command": command,
        "exit_code": returncode,
        "status": "PASS" if returncode == 0 else "FAIL",
        "duration_seconds": round(time.monotonic() - started, 3),
        "output": path.relative_to(ROOT).as_posix(),
    }
    print(f"{record['status']}: {name}", flush=True)
    return record


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    checks = [
        ("fast-suite", [python, "-m", "pytest", "starter-tests", "tests", "-q", "--tb=short"]),
        ("ruff", [python, "-m", "ruff", "check", "."]),
        ("integration-matrix", [python, "scripts/verify_matrix.py"]),
        ("portability", [python, "scripts/check_portability.py"]),
        ("manifests", [python, "scripts/validate_manifests.py"]),
        (
            "offline-integration",
            [python, "-m", "pytest", "integration-tests", "-m", "offline", "-q", "--tb=short"],
        ),
        (
            "compose-basic",
            ["docker", "compose", "--env-file", "ports.template", "config", "--quiet"],
        ),
        (
            "compose-full",
            [
                "docker", "compose", "--env-file", "ports.template", "--profile", "full",
                "config", "--quiet",
            ],
        ),
        (
            "preflight",
            [python, "-c", "from lab28_platform.cli import main; main()", "preflight"],
        ),
    ]
    records = [run_check(name, arguments) for name, arguments in checks]
    passed = all(record["exit_code"] == 0 for record in records)
    report = {
        "schema_version": "1",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Local code, static configuration and environment checks only",
        "python": platform.python_version(),
        "platform": platform.system(),
        "all_checks_passed": passed,
        "live_integration_verified": False,
        "checks": records,
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
