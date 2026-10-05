"""API default routing uses the same reviewed schema/recovery configuration."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlas_api.services.requests import build_default_media_requests_api_service, MediaRequestsUnavailableError


class APIAcquisitionConfigurationTests(unittest.TestCase):
    def test_schema_one_and_recovery_off_block_before_provider_construction(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder)/'requests.json'
            for schema, recovery in ((1, '0'), (1, '1'), (2, '0')):
                registry.write_text(json.dumps(dict(schema_version=schema, requests={}, **(
                    dict(submissions={}, submission_outbox={}) if schema == 2 else {}))))
                before = registry.read_bytes()
                with self.subTest(schema=schema, recovery=recovery), patch.dict(os.environ, {
                    'ATLAS_REQUESTS_DIR': folder, 'ATLAS_ACQUISITION_ROUTING_ENABLED': '1',
                    'ATLAS_SUBMISSION_RECOVERY_ENABLED': recovery,
                }), patch('atlas_api.services.requests.default_jellyseerr_media_request_provider') as provider:
                    with self.assertRaises(MediaRequestsUnavailableError):
                        build_default_media_requests_api_service()
                    provider.assert_not_called()
                self.assertEqual(before, registry.read_bytes())
                self.assertEqual({registry}, set(Path(folder).iterdir()))

    def test_api_constructs_all_reviewed_maps_lazily_without_writing_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = root/'requests.json'
            registry.write_text('{"schema_version":2,"requests":{},"submissions":{},"submission_outbox":{}}')
            before = registry.read_bytes()
            routes = dict(movie=0, tv=0, anime_movie=1, anime_tv=1)
            categories = {category: dict(server_id=server, arr_url=f'http://{category}.invalid/api/v3',
                api_key_env=f'FIXTURE_{category.upper()}_KEY', profiles=dict(english_preferred=31, english_required=32, original_subbed=33))
                for category, server in routes.items()}
            config = root/'reviewed.json'
            config.write_text(json.dumps(dict(schema_version=1, categories=categories)))
            config.chmod(0o600)
            config_before = config.read_bytes()
            env = dict(ATLAS_REQUESTS_DIR=folder, ATLAS_ACQUISITION_ROUTING_ENABLED='1',
                ATLAS_SUBMISSION_RECOVERY_ENABLED='1', ATLAS_ACQUISITION_ROUTING_CONFIG=str(config),
                ATLAS_ACQUISITION_ROUTING_SHA256=hashlib.sha256(config_before).hexdigest(),
                ATLAS_JELLYSEERR_URL='http://seerr.invalid', ATLAS_JELLYSEERR_API_KEY='synthetic')
            for category, server in routes.items():
                env[f'ATLAS_JELLYSEERR_{category.upper()}_SERVER_ID'] = str(server)
                env[f'FIXTURE_{category.upper()}_KEY'] = 'synthetic'
            with patch.dict(os.environ, env, clear=True), patch('atlas_api.services.requests.RuntimeEventJournalPublisher.from_environment'), patch(
                    'atlas.media_requests.providers.acquisition_config.build_opener') as transport:
                application = build_default_media_requests_api_service()
                transport.assert_not_called()
            provider = application.requests._providers['jellyseerr']
            self.assertEqual(12, len(provider.audio_profile_ids))
            self.assertEqual(4, len(provider.managed_profile_reader.bindings))
            self.assertEqual(33, provider.audio_profile_ids[('anime_tv', 'original_subbed')])
            self.assertEqual(0, provider.tv_server_id)
            self.assertEqual(1, provider.anime_tv_server_id)
            self.assertEqual(before, registry.read_bytes())
            self.assertEqual(config_before, config.read_bytes())
            self.assertEqual({registry, config}, set(root.iterdir()))

    def test_invalid_opt_in_is_sanitized_before_provider_construction(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder)/'requests.json'
            registry.write_text('{"schema_version":1,"requests":{}}')
            before = registry.read_bytes()
            with patch.dict(os.environ, {'ATLAS_REQUESTS_DIR': folder, 'ATLAS_ACQUISITION_ROUTING_ENABLED': 'invalid'}), patch(
                    'atlas_api.services.requests.default_jellyseerr_media_request_provider') as provider:
                with self.assertRaises(MediaRequestsUnavailableError):
                    build_default_media_requests_api_service()
                provider.assert_not_called()
            self.assertEqual(before, registry.read_bytes())
