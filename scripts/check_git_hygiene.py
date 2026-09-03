"""Check submission visibility and reject generated or sensitive files in Git."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    ".dockerignore",
    ".gitignore",
    ".github/workflows/ci.yml",
    "README.md",
    "REPORT.md",
    "ANSWERS.md",
    "integration-report.json",
    "pyproject.toml",
    "uv.lock",
    "ports.template",
    "compose.yaml",
    "compose.gpu.yaml",
    "data/documents.jsonl",
    "data/feedback.jsonl",
    "src/lab28_platform/cli.py",
    "src/lab28_platform/event_bus.py",
    "src/lab28_platform/integration_tasks.py",
    "scripts/check_git_hygiene.py",
    "scripts/collect_local_checks.py",
    "starter-tests/test_integration_tasks.py",
    "tests/test_integration_edge_cases.py",
    "tests/test_cli_json_output.py",
    "tests/test_kafka_batch_polling.py",
    "compose.gpu.8gb.yaml",
    "load-tests/run_ask_profile.py",
    "docs/submission-architecture.md",
    "evidence/README.md",
    "reports/local-checks/summary.json",
    "reports/local-checks/fast-suite.txt",
}
PRIVATE = {
    ".env",
    ".env.local",
    ".venv/pyvenv.cfg",
    ".lab28/airflow/simple-auth-passwords.json",
    ".pytest_cache/state",
    ".ruff_cache/state",
    "runtime.db",
    "runtime.sqlite3",
    "weights/model.safetensors",
    "weights/model.onnx",
    "private.pem",
    "private.key",
    "evidence/raw-capture.json",
}
SECRET = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|"
    rb"AKIA[0-9A-Z]{16}|sk-proj-[A-Za-z0-9_-]{40,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def git(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *arguments],
        cwd=ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def main() -> int:
    matrix = yaml.safe_load(
        (ROOT / "contracts/integration-matrix.yaml").read_text(encoding="utf-8")
    )
    evidence = {
        name
        for point in matrix["points"]
        for name in re.findall(r"evidence/[A-Za-z0-9._-]+", point["demo_evidence"])
    }
    tracked_result = git("ls-files", "-z")
    candidates_result = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    if tracked_result.returncode or candidates_result.returncode:
        raise RuntimeError("Cannot inspect the Git index")
    tracked = set(filter(None, tracked_result.stdout.split("\0")))
    candidates = set(filter(None, candidates_result.stdout.split("\0")))
    paths = REQUIRED | evidence | PRIVATE | tracked
    ignored_result = git(
        "check-ignore", "--no-index", "--stdin", "-z", input_text="\0".join(sorted(paths)) + "\0"
    )
    if ignored_result.returncode not in {0, 1}:
        raise RuntimeError(ignored_result.stderr)
    ignored = set(filter(None, ignored_result.stdout.split("\0")))
    problems = [
        f"Required file missing: {path}" for path in sorted(REQUIRED) if not (ROOT / path).is_file()
    ]
    problems += [
        f"Submission file ignored: {path}" for path in sorted((REQUIRED | evidence) & ignored)
    ]
    problems += [f"Private path not ignored: {path}" for path in sorted(PRIVATE - ignored)]
    problems += [
        f"Generated/private file already tracked: {path}" for path in sorted(tracked & ignored)
    ]
    for path in sorted(candidates):
        item = ROOT / path
        if not item.is_file():
            continue
        if item.stat().st_size > 10 * 1024 * 1024:
            problems.append(f"Review large file before upload: {path}")
        elif SECRET.search(item.read_bytes()):
            problems.append(f"Possible credential detected: {path}")
    report = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "status": "PASS" if not problems else "FAIL",
        "scope": "File visibility, generated-file exclusions and common credential patterns",
        "candidate_files_checked": len(candidates),
        "required_files": sorted(REQUIRED),
        "required_evidence_paths_are_not_ignored": not bool(evidence & ignored),
        "live_evidence_not_yet_present": sorted(
            path for path in evidence if not (ROOT / path).is_file()
        ),
        "problems": problems,
    }
    output = ROOT / "reports/git-hygiene.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"{report['status']}: {len(candidates)} candidate files checked; "
        f"{len(evidence)} evidence paths visible"
    )
    for problem in problems:
        print(problem)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
