#!/usr/bin/env python3
"""Strict, pre-update-only admission for the documented TheSportsDB fault.

No network access, state repair, cooldown reset or health-status mutation.
Only a small sanitized receipt is emitted; raw errors are never printed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

PROVIDER_FILE = Path('/mnt/storage/configs/sportyfin/state/provider-health.json')
PROVIDER_ID = ('module:sports', 'Provider Health')
REQUIRED = {
    ('core', name) for name in (
        'Python Runtime', 'Project Directory', 'Atlas Configuration',
        'Git Working Tree',
    )
} | {
    ('infrastructure', name) for name in (
        'Docker Engine', 'Docker Compose', 'Storage Root', 'Intel GPU',
    )
} | {
    ('services', name) for name in (
        'jellyfin', 'jellyseerr', 'prowlarr', 'sonarr', 'sonarr-anime',
        'radarr', 'radarr-anime', 'gluetun', 'qbittorrent', 'homepage',
    )
} | {
    ('storage', 'Writable: ' + name) for name in (
        'Movies', 'TV', 'Anime Movies', 'Anime TV', 'downloads',
    )
} | {
    ('project', name) for name in (
        'VERSION', 'CHARTER.md', 'ROADMAP.md', 'CHANGELOG.md',
        'docs/BUILD_LOG.md', 'docs/MATURITY.md', 'docs/INDEXERS.md',
    )
} | {
    ('module:sports', name) for name in (
        'atlas-sports-feed Running', 'atlas-sports-feed Health',
        'atlas-sports-controller Running', 'atlas-sports-controller Health',
        'Controller Heartbeat', 'Provider Health', 'Sports Health Endpoint',
    )
}


def require(condition: bool) -> None:
    if not condition:
        raise ValueError('provider recovery contract refused')


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def decode(raw: bytes, maximum: int) -> dict:
    require(0 < len(raw) <= maximum)
    value = json.loads(raw, object_pairs_hook=unique_object)
    require(isinstance(value, dict))
    return value


def recent(value: object, now: datetime, maximum_age: int) -> None:
    require(isinstance(value, str))
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None)
    age = (now - parsed).total_seconds()
    require(0 <= age <= maximum_age)


def read_provider(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        require(0 < info.st_size <= 262144)
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read(262145)
        require(len(raw) <= 262144)
        return raw
    finally:
        os.close(descriptor)


def validate(report_raw: bytes, health_exit_code: int, *,
             now: datetime, provider_path: Path = PROVIDER_FILE) -> dict:
    report = decode(report_raw, 1048576)
    require(type(report.get('schema_version')) is int and report['schema_version'] == 1)
    recent(report.get('generated_at'), now, 30)
    checks = report.get('checks')
    require(isinstance(checks, list) and 0 < len(checks) <= 512)
    observed = {}
    for check in checks:
        require(isinstance(check, dict))
        category, name = check.get('category'), check.get('name')
        require(isinstance(category, str) and isinstance(name, str))
        identity = (category, name)
        require(identity not in observed)
        require(check.get('status') in {'healthy', 'warning', 'critical', 'unknown'})
        require(isinstance(check.get('message'), str))
        require(isinstance(check.get('details'), dict))
        observed[identity] = check
    require(REQUIRED <= observed.keys())
    unhealthy = [key for key, check in observed.items() if check['status'] != 'healthy']
    certificate = {
        'schema_version': 1,
        'scope': 'all',
        'accepted_at': now.isoformat(),
        'check_count': len(checks),
        'report_sha256': hashlib.sha256(report_raw).hexdigest(),
        'post_update_health_required': True,
    }
    if not unhealthy:
        require(health_exit_code == 0 and report.get('status') == 'healthy')
        return {**certificate, 'admission': 'fully-healthy', 'exception_count': 0}
    require(health_exit_code == 1 and report.get('status') == 'critical')
    require(unhealthy == [PROVIDER_ID])
    check = observed[PROVIDER_ID]
    require(check['status'] == 'critical')
    require(check['message'] == 'Sports provider health is unavailable or degraded')
    details = check['details']
    require(details.get('module') == 'sports')
    require(type(details.get('provider_count')) is int and details['provider_count'] == 1)
    require(details.get('path') == str(PROVIDER_FILE))
    raw = read_provider(provider_path)
    providers = decode(raw, 262144)
    require(set(providers) == {'thesportsdb'})
    provider = providers['thesportsdb']
    require(isinstance(provider, dict) and provider.get('status') == 'degraded')
    require(provider.get('last_error') == 'Sports provider is temporarily rate limited.')
    recent(provider.get('last_failure_at'), now, 90)
    return {
        **certificate,
        'admission': 'thesportsdb-rate-limit-only',
        'exception_count': 1,
        'provider_report_sha256': hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--health-exit-code', type=int, choices=(0, 1), required=True)
    args = parser.parse_args()
    try:
        receipt = validate(sys.stdin.buffer.read(1048577), args.health_exit_code,
                           now=datetime.now(timezone.utc))
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        print('ERROR: provider recovery preflight refused; raw details withheld.', file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
