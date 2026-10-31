"""Execute the actual API contracts/adapter without production app construction."""
import copy
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import urllib.parse

API = Path(__file__).resolve().parents[1] / 'atlas_api'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


schema = load('curated_fixture_schema', API / 'schemas/sports.py')
service_module = load('curated_fixture_service', API / 'services/sports.py')


class ContractTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.start = now.isoformat()
        self.end = (now + timedelta(days=1)).isoformat()
        self.document = dict(version=1, competition_id='nfl', provider='espn', provider_league_id='football/nfl',
            evaluated_at=self.start, start_at=self.start, end_at=self.end, status='preparing',
            coverage_complete=False, provider_completeness_proven=False, required_buckets=3, fresh_buckets=0,
            retry_after_seconds=0, observed_at=None, expires_at=None, events=[])
        self.client = service_module.SportsWriterBackedAPIService(base_url='http://fixture.invalid', token='fixture')

    def test_preparing_is_valid_but_cannot_claim_empty_complete_schedule(self):
        value = schema.SportsCuratedScheduleResponse.model_validate(self.document)
        self.assertFalse(value.coverage_complete)
        self.document['coverage_complete'] = True
        with self.assertRaises(ValueError):
            schema.SportsCuratedScheduleResponse.model_validate(self.document)

    def test_ready_requires_all_buckets_fresh(self):
        self.document.update(status='ready', coverage_complete=True)
        with self.assertRaises(ValueError):
            schema.SportsCuratedScheduleResponse.model_validate(self.document)
        self.document['fresh_buckets'] = 3
        self.assertTrue(schema.SportsCuratedScheduleResponse.model_validate(self.document).coverage_complete)

    def test_league_mismatch_cannot_pass_same_competition_label(self):
        self.document['provider_league_id'] = 'basketball/nba'
        with self.assertRaises(ValueError):
            schema.SportsCuratedScheduleResponse.model_validate(self.document)

    def test_upstream_completeness_is_never_asserted(self):
        self.document['provider_completeness_proven'] = True
        with self.assertRaises(ValueError):
            schema.SportsCuratedScheduleResponse.model_validate(self.document)

    def test_adapter_uses_only_read_only_writer_route(self):
        with patch.dict(sys.modules, {'atlas_api.schemas.sports': schema}), patch.object(self.client, '_request', return_value=self.document) as request:
            result = self.client.curated_schedule('nfl', self.start, self.end)
        self.assertEqual(result['status'], 'preparing')
        method, url = request.call_args.args
        self.assertEqual(method, 'GET')
        parsed = urllib.parse.urlsplit(url)
        self.assertEqual(parsed.path, '/internal/v1/curated/schedule')
        self.assertEqual(urllib.parse.parse_qs(parsed.query), {'competition': ['nfl'], 'start_at': [self.start], 'end_at': [self.end]})

    def test_adapter_rejects_competition_response_mixup(self):
        with patch.dict(sys.modules, {'atlas_api.schemas.sports': schema}), patch.object(self.client, '_request', return_value=self.document):
            with self.assertRaises(service_module.SportsWriterTransportError):
                self.client.curated_schedule('nba', self.start, self.end)

    def test_adapter_rejects_window_response_mixup(self):
        altered = copy.deepcopy(self.document)
        altered['start_at'] = (datetime.fromisoformat(self.start) + timedelta(seconds=1)).isoformat()
        with patch.dict(sys.modules, {'atlas_api.schemas.sports': schema}), patch.object(self.client, '_request', return_value=altered):
            with self.assertRaises(service_module.SportsWriterTransportError):
                self.client.curated_schedule('nfl', self.start, self.end)

    def test_team_route_ids_are_source_scoped(self):
        document = dict(version=1, competition_id='nfl', provider='espn', provider_league_id='football/nfl',
            evaluated_at=self.start, status='ready', observed_at=self.start, expires_at=self.end,
            retry_after_seconds=0, teams=[{'id': 'football-nfl-1', 'name': 'Fixture'}])
        self.assertEqual(len(schema.SportsCuratedTeamsResponse.model_validate(document).teams), 1)
        document['teams'][0]['id'] = 'basketball-nba-1'
        with self.assertRaises(ValueError):
            schema.SportsCuratedTeamsResponse.model_validate(document)

    def realm_arguments(self):
        return dict(source_id='fixture-source', provider_id='fixture-provider', credential_realm=' fixture-realm ',
            provider_display_name='Fixture', account_display_name='Fixture account',
            server_url='https://fixture.invalid', username='fixture-user', password='fixture-password', max_connections=1)

    def realm_response(self, realm='fixture-realm'):
        return dict(source=dict(source_id='fixture-source', provider_id='fixture-provider',
            credential_realm=realm, enabled=False), account=dict(account_id='fixture-account', name='Fixture account',
            account_type='XC', enabled=False, configured_max_connections=1, credentials_configured=True))

    def test_provider_creation_preserves_explicit_credential_realm(self):
        registry = dict(providers=[], sources=[])
        with patch.object(self.client, '_request', return_value=self.realm_response()) as request, \
             patch.object(self.client, 'get_source_registry', return_value=registry):
            self.assertEqual(self.client.create_provider_account(**self.realm_arguments()), registry)
        self.assertEqual(request.call_args.args[2]['credential_realm'], 'fixture-realm')

    def test_provider_creation_rejects_different_returned_realm(self):
        with patch.object(self.client, '_request', return_value=self.realm_response('other-realm')), \
             patch.object(self.client, 'get_source_registry') as registry:
            with self.assertRaises(service_module.SportsWriterTransportError):
                self.client.create_provider_account(**self.realm_arguments())
        registry.assert_not_called()

    def test_provider_creation_rejects_empty_realm_before_transport(self):
        arguments = self.realm_arguments()
        arguments['credential_realm'] = ' '
        with patch.object(self.client, '_request') as request:
            with self.assertRaises(ValueError):
                self.client.create_provider_account(**arguments)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
