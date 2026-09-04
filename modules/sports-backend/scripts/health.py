#!/usr/bin/env python3
"""Project Atlas Sports Backend health provider."""

from __future__ import annotations

import json
import subprocess


SERVICES = (
    ("atlas-dispatcharr", "Dispatcharr"),
    ("atlas-teamarr", "Teamarr"),
)


def container_state(name: str) -> tuple[str, str]:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            name,
            "--format",
            "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return "missing", ""

    status, _, health = result.stdout.strip().partition("|")
    return status, health


checks = []

for name, display in SERVICES:
    status, health = container_state(name)

    if status == "missing":
        state = "warning"
        message = "container is not installed or running"
    elif status != "running":
        state = "critical"
        message = f"container state is {status}"
    elif health and health != "healthy":
        state = "warning"
        message = f"container health is {health}"
    else:
        state = "healthy"
        message = "container is running"

    checks.append(
        {
            "name": display,
            "status": state,
            "message": message,
            "details": {
                "container": name,
            },
        }
    )

print(json.dumps({"checks": checks}))
