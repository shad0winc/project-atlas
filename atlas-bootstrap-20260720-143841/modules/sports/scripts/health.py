#!/usr/bin/env python3
"""Sports module implementation of the Atlas module-health contract."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def check(name: str, healthy: bool, success: str, failure: str, **details):
    return {
        "name": name,
        "status": "healthy" if healthy else "critical",
        "message": success if healthy else failure,
        "details": details,
    }


def container_state(name: str, field: str) -> str:
    result = subprocess.run(
        ["docker", "inspect", "-f", field, name],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "missing"


def endpoint_reachable(url: str) -> bool:
    try:
        with urlopen(url, timeout=5) as response:
            return 200 <= response.status < 300
    except (OSError, URLError):
        return False


def main() -> int:
    checks = []
    for container in ("atlas-sports-feed", "atlas-sports-controller"):
        running = container_state(container, "{{.State.Running}}") == "true"
        checks.append(check(
            f"{container} Running", running,
            f"{container} is running", f"{container} is not running",
            container=container,
        ))
        health = container_state(
            container,
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        )
        checks.append(check(
            f"{container} Health", health == "healthy",
            f"{container} health check is healthy",
            f"{container} health check is {health}",
            container=container, container_health=health,
        ))

    heartbeat = Path("/mnt/storage/configs/sportyfin/state/controller-heartbeat")
    age = int(time.time() - heartbeat.stat().st_mtime) if heartbeat.exists() else None
    checks.append(check(
        "Controller Heartbeat", age is not None and age < 90,
        "Sports controller heartbeat is fresh",
        "Sports controller heartbeat is missing or stale",
        path=str(heartbeat), age_seconds=age,
    ))

    provider_file = Path("/mnt/storage/configs/sportyfin/state/provider-health.json")
    providers_healthy = False
    provider_count = 0
    try:
        providers = json.loads(provider_file.read_text(encoding="utf-8"))
        provider_count = len(providers)
        providers_healthy = provider_count > 0 and all(
            item.get("status") == "healthy" for item in providers.values()
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    checks.append(check(
        "Provider Health", providers_healthy,
        "All configured Sports providers are healthy",
        "Sports provider health is unavailable or degraded",
        path=str(provider_file), provider_count=provider_count,
    ))

    url = "http://127.0.0.1:8097/health"
    checks.append(check(
        "Sports Health Endpoint", endpoint_reachable(url),
        "Sports health endpoint is reachable",
        "Sports health endpoint is unavailable",
        url=url,
    ))

    print(json.dumps({"schema_version": 1, "checks": checks}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
