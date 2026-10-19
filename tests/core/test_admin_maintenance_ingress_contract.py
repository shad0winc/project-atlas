"""Narrow privilege and exposure checks for the new maintenance boundary."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_api_gets_only_the_control_socket_directory_not_host_control_files():
    text = (ROOT / 'stack/ingress.yml').read_text()
    # Bound the actual API block using only lines at service indentation.
    import re
    api = re.split(r'\n  [a-z][a-z-]*:\n',text.split('\n  api:\n',1)[1],maxsplit=1)[0]
    assert '/run/atlas-maintenance-control:/run/atlas-maintenance-control:ro' in api
    assert 'ATLAS_MAINTENANCE_CONTROL_SOCKET: "/run/atlas-maintenance-control/control.sock"' in api
    assert '/var/run/docker.sock' not in api and '/run/docker.sock' not in api
    assert '/mnt/storage/configs/atlas/deployments:' not in api
    assert '/mnt/storage/configs/atlas/maintenance:' not in api


def test_control_service_is_a_local_narrow_host_authority():
    text = (ROOT / 'systemd/atlas-maintenance-control.service').read_text()
    assert 'RestrictAddressFamilies=AF_UNIX' in text
    assert 'NoNewPrivileges=true' in text
    assert 'CapabilityBoundingSet=\n' in text
    assert 'ProtectSystem=strict' in text
    assert 'ReadOnlyPaths=/mnt/storage/configs/atlas/deployments' in text
    assert '--allowed-uid 999 --socket-gid 20000' in text
    assert 'RuntimeDirectoryMode=0750' in text
    assert 'docker.sock' not in text


def test_console_uses_external_assets_and_has_a_strict_source_policy():
    site = (ROOT / 'infra/caddy/sites/atlas.caddy').read_text()
    page = (ROOT / 'infra/caddy/site/maintenance/admin.html').read_text()
    assert "script-src 'self'" in site and "connect-src 'self'" in site
    assert 'header Cache-Control "no-store"' in site
    assert '<script src="/maintenance/admin.js" defer></script>' in page
    assert '<script>' not in page
    assert 'role="status" aria-live="polite"' in page


def test_required_proxy_check_cannot_be_downgraded_by_client_header():
    text = (ROOT / 'infra/caddy/snippets/maintenance-auth.caddy').read_text()
    assert 'header_up X-Atlas-Maintenance-Required "1"' in text
    assert 'header_up -X-Atlas-Maintenance-Required' in text
    assert 'copy_headers' not in text
    assert 'uri /_atlas/maintenance/authorize' in text
