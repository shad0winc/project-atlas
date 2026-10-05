from __future__ import annotations

import base64
import importlib.util
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'modules/sports/src'

@pytest.fixture
def verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(SRC))
    spec = importlib.util.spec_from_file_location('atlas_option_auth_test', SRC / 'dispatcharr_admin.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    clock = {'mono': 100.0, 'wall': 1000.0}
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock['mono'])
    monkeypatch.setattr(module.time, 'time', lambda: clock['wall'])
    counts = {'clients': 0, 'logins': 0, 'routes': []}
    class Client:
        def _access_token(self):
            counts['logins'] += 1
            body = base64.urlsafe_b64encode(json.dumps({'exp': clock['wall'] + 120}).encode()).decode().rstrip('=')
            return 'header.' + body + '.signature'
    def create():
        counts['clients'] += 1
        return Client()
    monkeypatch.setattr(module, 'DispatcharrAdminClient', SimpleNamespace(from_environment=create))
    def check(source, option, resources, client):
        counts['routes'].append((source, option))
        return {'option': option}
    monkeypatch.setattr(module, '_verify_option_route', check)
    return module, clock, counts


def test_six_route_checks_share_one_login_and_still_verify_each_route(verifier):
    module, clock, counts = verifier
    for source in ('redzone', 'game'):
        for option in ('primary', 'backup-1', 'backup-2'):
            assert module.verify_configured_playback_option(source, option, []) == {'option': option}
    assert counts['clients'] == counts['logins'] == 1
    assert len(counts['routes']) == 6


def test_expiry_renews_before_jwt_expiration(verifier):
    module, clock, counts = verifier
    module.verify_configured_playback_option('game', 'primary', [])
    clock['mono'] += 89
    module.verify_configured_playback_option('game', 'backup-1', [])
    assert counts['logins'] == 1
    clock['mono'] += 1
    module.verify_configured_playback_option('game', 'backup-2', [])
    assert counts['logins'] == 2


def test_credential_rotation_discards_old_client(verifier, monkeypatch):
    module, clock, counts = verifier
    module.verify_configured_playback_option('game', 'primary', [])
    monkeypatch.setenv('DISPATCHARR_ADMIN_PASSWORD', 'rotated-test-value')
    module.verify_configured_playback_option('game', 'backup-1', [])
    assert counts['clients'] == counts['logins'] == 2


def test_concurrent_checks_do_not_burst_logins(verifier):
    module, clock, counts = verifier
    barrier = threading.Barrier(6)
    def check(index):
        barrier.wait(timeout=5)
        return module.verify_configured_playback_option('game', str(index), [])
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert len(list(pool.map(check, range(6)))) == 6
    assert counts['clients'] == counts['logins'] == 1
    assert len(counts['routes']) == 6


@pytest.mark.parametrize('status,delay', [(429, 45), (401, 10), (403, 10)])
def test_remote_failure_has_cooldown_without_request_retry(verifier, monkeypatch, status, delay):
    module, clock, counts = verifier
    attempts = []
    def failing(*args):
        attempts.append(1)
        raise module.DispatcharrAdminError('safe failure') from HTTPError(
            'http://test.invalid', status, 'failure', {'Retry-After': '45'}, None,
        )
    monkeypatch.setattr(module, '_verify_option_route', failing)
    with pytest.raises(module.DispatcharrAdminError):
        module.verify_configured_playback_option('game', 'primary', [])
    with pytest.raises(module.DispatcharrAdminError):
        module.verify_configured_playback_option('game', 'backup-1', [])
    assert len(attempts) == 1
    clock['mono'] += delay
    with pytest.raises(module.DispatcharrAdminError):
        module.verify_configured_playback_option('game', 'backup-1', [])
    assert len(attempts) == 2
    assert counts['logins'] == (1 if status == 429 else 2)


def test_route_mismatch_never_returns_cached_success(verifier, monkeypatch):
    module, clock, counts = verifier
    module.verify_configured_playback_option('game', 'primary', [])
    def changed(*args):
        raise ValueError('route changed')
    monkeypatch.setattr(module, '_verify_option_route', changed)
    with pytest.raises(ValueError):
        module.verify_configured_playback_option('game', 'primary', [])
    assert counts['logins'] == 1


def test_invalid_token_hint_is_short_lived(verifier):
    module, clock, counts = verifier
    assert module._token_lifetime('opaque') == 60
    assert module._token_lifetime('h.invalid.s') == 60
    body = base64.urlsafe_b64encode(json.dumps({'exp': 999}).encode()).decode()
    assert module._token_lifetime('h.' + body + '.s') == 0


def test_private_route_uses_shared_verifier():
    text = (SRC / 'private_api.py').read_text()
    route = text.split('if parsed.path == "/internal/v1/live-playback-option":', 1)[1].split('\n            if ', 1)[0]
    assert 'verify_configured_playback_option' in route
    assert 'DispatcharrAdminClient.from_environment' not in route


def test_login_throttle_blocks_new_login_attempts(verifier, monkeypatch):
    module, clock, counts = verifier
    attempts = []
    class ThrottledClient:
        def _access_token(self):
            attempts.append(1)
            raise module.DispatcharrAdminError('safe failure') from HTTPError(
                'http://test.invalid', 429, 'failure', {'Retry-After': '60'}, None,
            )
    monkeypatch.setattr(module, 'DispatcharrAdminClient', SimpleNamespace(from_environment=ThrottledClient))
    for option in ('primary', 'backup-1', 'backup-2'):
        with pytest.raises(module.DispatcharrAdminError):
            module.verify_configured_playback_option('game', option, [])
    assert len(attempts) == 1
    clock['mono'] += 60
    with pytest.raises(module.DispatcharrAdminError):
        module.verify_configured_playback_option('game', 'primary', [])
    assert len(attempts) == 2
