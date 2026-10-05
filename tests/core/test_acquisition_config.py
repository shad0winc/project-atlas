"""Reviewed routing bytes, no construction side effects, and fail-closed transport."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from atlas.media_requests.providers.acquisition_config import (
    ERROR, MAX_CONFIG_BYTES, _metadata_reader, configured_acquisition_provider,
)
from atlas.media_requests.providers.jellyseerr import default_jellyseerr_media_request_provider
from atlas.media_requests.provider import MediaRequestProviderError
from atlas.media_requests.construction import open_request_repository, validate_default_acquisition_activation
from atlas.media_requests.models import MediaRequest

ROUTES = dict(movie=0, tv=0, anime_movie=1, anime_tv=1)


def config():
    return dict(schema_version=1, categories={category: dict(server_id=server,
        arr_url=f"http://{category}.invalid/api/v3", api_key_env=f"FIXTURE_{category.upper()}_KEY",
        profiles=dict(english_preferred=11, english_required=12, original_subbed=13))
        for category, server in ROUTES.items()})


class RoutingConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reviewed.json"
        self.environment = {
            "ATLAS_ACQUISITION_ROUTING_ENABLED": "1",
            "ATLAS_ACQUISITION_ROUTING_CONFIG": str(self.path),
            "ATLAS_JELLYSEERR_URL": "http://seerr.invalid",
            "ATLAS_JELLYSEERR_API_KEY": "synthetic",
        }
        for category, server in ROUTES.items():
            self.environment[f"FIXTURE_{category.upper()}_KEY"] = "synthetic"
            self.environment[f"ATLAS_JELLYSEERR_{category.upper()}_SERVER_ID"] = str(server)
        self.write(config())
        self.patch = patch.dict(os.environ, self.environment, clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, document=None, *, raw=None):
        if self.path.is_symlink():
            self.path.unlink()
        self.path.write_bytes(raw if raw is not None else json.dumps(document).encode())
        self.path.chmod(0o600)
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.environment['ATLAS_ACQUISITION_ROUTING_SHA256'] = digest
        os.environ['ATLAS_ACQUISITION_ROUTING_SHA256'] = digest

    def assert_blocked(self):
        with self.assertRaises(MediaRequestProviderError) as caught:
            default_jellyseerr_media_request_provider()
        self.assertEqual(ERROR, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_constructs_all_immutable_bindings_without_network_or_file_changes(self):
        before = self.path.read_bytes()
        with patch('atlas.media_requests.providers.acquisition_config.build_opener') as transport:
            provider = default_jellyseerr_media_request_provider()
            transport.assert_not_called()
        self.assertEqual(12, len(provider.audio_profile_ids))
        self.assertEqual(4, len(provider.managed_profile_reader.bindings))
        self.assertEqual(1, provider.anime_tv_server_id)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual({self.path}, set(self.path.parent.iterdir()))
        with self.assertRaises(TypeError):
            provider.audio_profile_ids[('tv', 'english_required')] = 99
        with self.assertRaises(TypeError):
            provider.managed_profile_reader.bindings[('tv', 0)] = None

    def test_default_off_ignores_configuration_and_preserves_legacy_provider(self):
        os.environ['ATLAS_ACQUISITION_ROUTING_ENABLED'] = '0'
        self.path.unlink()
        with patch('atlas.media_requests.providers.acquisition_config._read_config') as read:
            provider = default_jellyseerr_media_request_provider()
            read.assert_not_called()
        self.assertEqual({}, provider.audio_profile_ids)
        self.assertIsNone(provider.managed_profile_reader)
        self.assertEqual(ROUTES, dict(movie=provider.movie_server_id, tv=provider.tv_server_id,
            anime_movie=provider.anime_movie_server_id, anime_tv=provider.anime_tv_server_id))

    def test_invalid_opt_in_fails_before_config_read(self):
        for flag in ('true', 'false', '', '2'):
            with self.subTest(flag=flag), patch.dict(os.environ, {'ATLAS_ACQUISITION_ROUTING_ENABLED': flag}), patch(
                    'atlas.media_requests.providers.acquisition_config._read_config') as read:
                with self.assertRaises(MediaRequestProviderError):
                    default_jellyseerr_media_request_provider()
                read.assert_not_called()

    def test_digest_missing_wrong_or_uppercase_is_rejected(self):
        for digest in ('', '0' * 64, self.environment['ATLAS_ACQUISITION_ROUTING_SHA256'].upper()):
            with self.subTest(digest=digest), patch.dict(os.environ, {'ATLAS_ACQUISITION_ROUTING_SHA256': digest}):
                self.assert_blocked()

    def test_symlink_fifo_hardlink_and_unsafe_modes_are_rejected(self):
        for mode in (0o644, 0o666, 0o400, 0o660, 0o1600):
            self.path.chmod(mode)
            with self.subTest(mode=mode):
                self.assert_blocked()
        self.path.chmod(0o600)
        linked = self.path.parent / 'linked'
        os.link(self.path, linked)
        self.assert_blocked()
        linked.unlink()
        target = self.path.parent / 'target'
        self.path.rename(target)
        self.path.symlink_to(target)
        self.assert_blocked()
        self.path.unlink()
        os.mkfifo(self.path)
        self.assert_blocked()
        self.path.unlink()

    def test_missing_relative_and_symlink_parent_paths_are_rejected(self):
        linked = self.path.parent / 'linkdir'
        linked.symlink_to(self.path.parent, target_is_directory=True)
        for value in ('missing.json', str(self.path.parent/'missing'), str(linked/'reviewed.json')):
            with self.subTest(path=value), patch.dict(os.environ, {'ATLAS_ACQUISITION_ROUTING_CONFIG': value}):
                self.assert_blocked()

    def test_size_duplicate_json_and_nonfinite_values_are_rejected(self):
        for raw in (b' ' * (MAX_CONFIG_BYTES + 1), b'{"schema_version":1,"schema_version":1}', b'{"schema_version": NaN}', b'[]'):
            self.write(raw=raw)
            with self.subTest(size=len(raw)):
                self.assert_blocked()

    def test_incomplete_extra_bool_and_aliased_configuration_fails_without_network(self):
        cases = []
        row = config(); row['schema_version'] = True; cases.append(row)
        row = config(); row['extra'] = 1; cases.append(row)
        row = config(); row['categories'].pop('tv'); cases.append(row)
        row = config(); row['categories']['tv']['extra'] = 1; cases.append(row)
        row = config(); row['categories']['tv']['server_id'] = True; cases.append(row)
        row = config(); row['categories']['tv']['server_id'] = 2; cases.append(row)
        for value in (0, -1, True, '12'):
            row = config(); row['categories']['tv']['profiles']['english_required'] = value; cases.append(row)
        row = config(); row['categories']['tv']['profiles'].pop('original_subbed'); cases.append(row)
        row = config(); row['categories']['tv']['profiles']['english_required'] = 11; cases.append(row)
        row = config(); row['categories']['anime_tv']['arr_url'] = 'http://TV.invalid:80/api/v3/'; cases.append(row)
        row = config(); row['categories']['tv']['api_key_env'] = 'fixture-secret'; cases.append(row)
        for document in cases:
            self.write(document)
            with self.subTest(document=document), patch('atlas.media_requests.providers.acquisition_config.build_opener') as transport:
                self.assert_blocked()
                transport.assert_not_called()

    def test_missing_credentials_or_private_endpoint_errors_are_sanitized(self):
        for endpoint in ('http://user:private-secret@host/api/v3', 'http://host/api/v3?token=private-secret',
                         'http://host:99999/api/v3', 'http://host/../api/v3', 'file:///api/v3', 'http://host/api/v3\n'):
            document = config(); document['categories']['tv']['arr_url'] = endpoint
            self.write(document)
            self.assert_blocked()
        self.write(config())
        with patch.dict(os.environ, {'FIXTURE_TV_KEY': ''}):
            self.assert_blocked()
        with patch.dict(os.environ, {'ATLAS_JELLYSEERR_URL': 'http://user:private-secret@host'}):
            self.assert_blocked()

    def test_configuration_replaced_during_read_is_rejected_even_with_matching_digest(self):
        original_fstat = os.fstat
        calls = 0
        def replace_on_second_stat(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                replacement = self.path.parent / 'replacement'
                replacement.write_bytes(self.path.read_bytes())
                replacement.chmod(0o600)
                os.replace(replacement, self.path)
            return original_fstat(fd)
        with patch('atlas.media_requests.providers.acquisition_config.os.fstat', side_effect=replace_on_second_stat):
            self.assert_blocked()

    def test_stale_environment_server_binding_is_rejected(self):
        with patch.dict(os.environ, {'ATLAS_JELLYSEERR_TV_SERVER_ID': '9'}):
            self.assert_blocked()

    def test_guard_requires_schema_two_and_recovery_without_registry_changes(self):
        registry = self.path.parent/'requests.json'
        for schema, recovery, succeeds in ((1, '0', False), (1, '1', False), (2, '0', False), (2, '1', True), (2, 'true', False)):
            registry.write_text(json.dumps(dict(schema_version=schema, requests={}, **(
                {'submissions': {}, 'submission_outbox': {}} if schema == 2 else {}))))
            before = registry.read_bytes()
            with self.subTest(schema=schema, recovery=recovery), patch.dict(os.environ, {'ATLAS_SUBMISSION_RECOVERY_ENABLED': recovery}):
                repository = open_request_repository(registry.parent)
                if succeeds:
                    validate_default_acquisition_activation(repository)
                else:
                    with self.assertRaises(MediaRequestProviderError):
                        validate_default_acquisition_activation(repository)
            self.assertEqual(before, registry.read_bytes())

    def test_scheduler_enforces_activation_before_provider_construction(self):
        from atlas.media_requests.scheduled_reconcile import build_default_service
        registry = self.path.parent / 'requests.json'
        registry.write_text('{"schema_version":1,"requests":{}}')
        before = registry.read_bytes()
        with patch.dict(os.environ, {'ATLAS_REQUESTS_DIR': str(registry.parent), 'ATLAS_SUBMISSION_RECOVERY_ENABLED': '1'}), patch(
                'atlas.media_requests.scheduled_reconcile.default_jellyseerr_media_request_provider') as provider:
            with self.assertRaises(MediaRequestProviderError):
                build_default_service()
            provider.assert_not_called()
        self.assertEqual(before, registry.read_bytes())

    def test_scheduler_builds_reviewed_schema_two_routing_without_network(self):
        from atlas.media_requests.scheduled_reconcile import build_default_service
        registry = self.path.parent / 'requests.json'
        registry.write_text('{"schema_version":2,"requests":{},"submissions":{},"submission_outbox":{}}')
        before = registry.read_bytes()
        with patch.dict(os.environ, {'ATLAS_REQUESTS_DIR': str(registry.parent), 'ATLAS_SUBMISSION_RECOVERY_ENABLED': '1'}), patch(
                'atlas.media_requests.providers.acquisition_config.build_opener') as transport:
            service = build_default_service()
            transport.assert_not_called()
        self.assertEqual(12, len(service._providers['jellyseerr'].audio_profile_ids))
        self.assertEqual(before, registry.read_bytes())

    def test_verified_tvdb_transport_is_lazy_and_exactly_bound(self):
        provider = default_jellyseerr_media_request_provider()
        response = Mock(status=200)
        response.read.return_value = b'{"id":123,"externalIds":{"tvdbId":456}}'
        context = Mock(); context.__enter__ = Mock(return_value=response); context.__exit__ = Mock(return_value=False)
        opener = Mock(); opener.open.return_value = context
        request = MediaRequest(request_id='fixture', user_id='viewer', media_type='tv', provider='jellyseerr',
            provider_media_id='123', title='Fixture', season_number=1)
        with patch('atlas.media_requests.providers.acquisition_config.build_opener', return_value=opener) as build:
            resolver = provider.managed_profile_reader.resolve_tvdb_id
            self.assertEqual(456, resolver(request, 0))
            self.assertEqual('_NoRedirect', type(build.call_args.args[0]).__name__)
            outgoing = opener.open.call_args.args[0]
            self.assertEqual('GET', outgoing.get_method())
            self.assertEqual('http://seerr.invalid/api/v1/tv/123', outgoing.full_url)
            self.assertEqual(10, opener.open.call_args.kwargs['timeout'])
            response.read.assert_called_once_with(2_000_001)
            with self.assertRaises(MediaRequestProviderError):
                resolver(request, 1)
            self.assertEqual(1, opener.open.call_count)


class MetadataTransportTests(unittest.TestCase):
    def test_unsafe_endpoints_fail_before_transport(self):
        read = _metadata_reader('http://seerr.invalid', 'synthetic')
        for path in ('/api/v1/request/1', '/api/v1/tv/001', '/api/v1/tv/1?secret=x', 'http://other.invalid'):
            with patch('atlas.media_requests.providers.acquisition_config.build_opener') as transport:
                with self.assertRaises(MediaRequestProviderError):
                    read(path)
                transport.assert_not_called()

    def test_failure_oversize_duplicate_and_nonfinite_metadata_are_sanitized(self):
        for payload, status in ((b'x'*2_000_001, 200), (b'{"id":1,"id":2}', 200),
                                (b'{"id":NaN}', 200), (b'{}', 302), (b'private-secret', 200)):
            response = Mock(status=status); response.read.return_value = payload
            context = Mock(); context.__enter__ = Mock(return_value=response); context.__exit__ = Mock(return_value=False)
            opener = Mock(); opener.open.return_value = context
            with patch('atlas.media_requests.providers.acquisition_config.build_opener', return_value=opener):
                with self.assertRaisesRegex(MediaRequestProviderError, '^TV metadata could not be verified$'):
                    _metadata_reader('http://seerr.invalid', 'synthetic')('/api/v1/tv/1')
        with patch('atlas.media_requests.providers.acquisition_config.build_opener', side_effect=RuntimeError('private-secret')):
            with self.assertRaises(MediaRequestProviderError) as caught:
                _metadata_reader('http://seerr.invalid', 'synthetic')('/api/v1/tv/1')
            self.assertTrue(caught.exception.__suppress_context__)
            self.assertNotIn('private-secret', str(caught.exception))
