"""Capture Kubernetes/Argo CD state and gateway responses without credentials."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--kubeconfig", default=".lab28/kubeconfig")
    parser.add_argument("--gateway-url", default="http://localhost:19580")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.label):
        parser.error("label must contain lowercase letters, digits or hyphens")

    def read(*arguments: str) -> Any:
        result = subprocess.run(
            ["kubectl", "--kubeconfig", args.kubeconfig, "--request-timeout=20s",
             *arguments, "-o", "json"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        return json.loads(result.stdout)

    app = read("get", "application", "lab28-platform", "-n", "argocd")
    deployment = read("get", "deployment", "lab28-api", "-n", "lab28")
    config = read("get", "configmap", "lab28-api-config", "-n", "lab28")
    gateway = read("get", "gateway", "lab28", "-n", "lab28")
    route = read("get", "httproute", "lab28-api", "-n", "lab28")
    hpa = read("get", "hpa", "lab28-api", "-n", "lab28")
    pods = read("get", "pods", "-n", "lab28")
    responses = {}
    for path in ("/health", "/ready"):
        try:
            response = httpx.get(args.gateway_url + path, timeout=30.0)
            responses[path] = {
                "status": response.status_code,
                "request_id": response.headers.get("x-request-id"),
                "body": response.json(),
            }
        except (httpx.HTTPError, ValueError) as error:
            responses[path] = {"error": f"{type(error).__name__}: {error}"}

    report = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "label": args.label,
        "scope": "Actual dedicated kind cluster; data dependencies remain in Docker Compose",
        "application": {"source": app["spec"]["source"], "status": app.get("status")},
        "deployment": {"spec": deployment["spec"], "status": deployment.get("status")},
        "demo_revision": config["data"].get("LAB28_DEMO_REVISION"),
        "gateway_status": gateway.get("status"),
        "route_status": route.get("status"),
        "hpa": {"spec": hpa["spec"], "status": hpa.get("status")},
        "pods": [
            {"name": p["metadata"]["name"], "uid": p["metadata"]["uid"],
             "status": p.get("status")}
            for p in pods["items"]
        ],
        "gateway_url": args.gateway_url,
        "responses": responses,
    }
    output = Path("reports/runtime/gitops") / f"{args.label}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output), "revision": app["spec"]["source"]["targetRevision"],
        "sync": app.get("status", {}).get("sync"),
        "health": app.get("status", {}).get("health"),
        "demo_revision": report["demo_revision"],
        "ready_replicas": deployment.get("status", {}).get("readyReplicas", 0),
        "gateway_http": {path: response.get("status") for path, response in responses.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
