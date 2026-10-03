"""Behavioral protection and isolated episode timing review contracts."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from atlas.favorites import FavoriteStore
from atlas.dislikes import DislikeStore
from atlas.policies import PolicyService
from atlas.policies.providers import PolicyProviders
from atlas.retention import RetentionService
from atlas.cleanup.service import CleanupService
from atlas.cleanup.scanner import CleanupScanner
from atlas.cleanup.execution_service import CleanupExecutionService
from atlas.cleanup.default_executor import DefaultCleanupExecutor
from atlas.cleanup.deletion_intent_repository import JsonCleanupDeletionIntentRepository
from atlas.cleanup.audit import JsonlCleanupAuditWriter
from atlas.media.jellyfin import JellyfinProvider

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
USER = 'usr_' + 'a' * 32
OTHER = 'usr_' + 'b' * 32

def stamp(days):
    return (NOW - timedelta(days=days)).isoformat()

class Users:
    def list_users(self):
        return [{'status': 'active', 'jellyfin_user_id': name} for name in ('one', 'two')]

class Provider:
    def __init__(self):
        self.kind = 'episode'
        self.series_id = 'series'
        self.fail = False
        self.created = {'old': stamp(40), 'new': stamp(1)}
        self.positions = (0, 0)
        self.last = None
    def get_retention_context(self, identity):
        if self.fail:
            raise RuntimeError('lookup failed')
        return {'item_type': self.kind, 'series_id': self.series_id}
    def get_retention_state(self, identity, *, user_ids):
        return {
            'media_type': 'tv' if self.kind == 'episode' else 'movie',
            'date_created': self.created.get(identity, stamp(40)),
            'users': tuple({
                'jellyfin_user_id': user, 'played': False,
                'runtime_ticks': 1000, 'playback_position_ticks': position,
                'last_played_at': (self.last[user] if isinstance(self.last, dict) else self.last) if position else None,
            } for user, position in zip(user_ids, self.positions)),
        }

class EpisodeRetentionSafety(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.favorites = FavoriteStore(self.root / 'favorites')
        self.dislikes = DislikeStore(self.root / 'dislikes', clock=lambda: NOW-timedelta(days=2))
        self.provider = Provider()
    def service(self, enabled=True):
        return RetentionService(
            PolicyService(PolicyProviders(favorites=self.favorites)),
            media_providers={'jellyfin': self.provider}, user_store=Users(),
            dislike_store=self.dislikes, clock=lambda: NOW,
            episode_retention_enabled=enabled,
        )
    def favorite(self, identity, user=USER):
        self.favorites.add(user, 'jellyfin', identity, media_type='tv', title=identity)
    def test_sibling_episode_clocks_are_independent(self):
        service=self.service()
        old, new=(service.evaluate('jellyfin', identity) for identity in ('old', 'new'))
        self.assertTrue(old.eligible)
        self.assertFalse(new.eligible)
        self.assertNotEqual(old.lifecycle.delete_at, new.lifecycle.delete_at)
    def test_series_favorite_from_another_user_protects_episode(self):
        self.favorite('series', OTHER)
        result=self.service().evaluate('jellyfin', 'old')
        self.assertFalse(result.eligible)
        self.assertTrue(result.policy.protected)
        self.assertEqual(result.policy.item_id, 'old')
        self.assertEqual(result.policy.reasons[0].metadata['inherited_from_series_id'], 'series')
    def test_direct_episode_favorite_protects_on_parent_outage(self):
        self.favorite('old')
        self.provider.fail=True
        self.assertTrue(self.service().evaluate('jellyfin', 'old').policy.protected)
    def test_parent_failure_retains_even_disliked_episode(self):
        self.dislikes.add(USER, 'jellyfin', 'old', media_type='tv', title='old')
        self.provider.fail=True
        self.assertFalse(self.service().evaluate('jellyfin', 'old').eligible)
    def test_missing_parent_retains(self):
        self.provider.series_id=None
        self.assertFalse(self.service().evaluate('jellyfin', 'old').eligible)
    def test_series_and_season_dislikes_do_not_delete_containers(self):
        self.dislikes.add(USER, 'jellyfin', 'old', media_type='tv', title='old')
        for kind in ('series', 'season'):
            with self.subTest(kind=kind):
                self.provider.kind=kind
                self.assertFalse(self.service().evaluate('jellyfin', 'old').eligible)
    def test_episode_retention_disabled_by_default(self):
        self.assertFalse(self.service(False).evaluate('jellyfin', 'old').eligible)
        service=RetentionService(media_providers={'jellyfin': self.provider}, user_store=Users())
        self.assertFalse(service.episode_retention_enabled)
    def test_disabled_episode_dislike_does_not_bypass_gate(self):
        self.dislikes.add(USER, 'jellyfin', 'old', media_type='tv', title='old')
        self.assertFalse(self.service(False).evaluate('jellyfin', 'old').eligible)
    def test_favorite_protects_disliked_episode(self):
        self.dislikes.add(USER, 'jellyfin', 'old', media_type='tv', title='old')
        self.favorite('series')
        self.assertTrue(self.service().evaluate('jellyfin', 'old').policy.protected)
    def test_movie_timing_still_works_when_episode_gate_off(self):
        self.provider.kind='movie'
        self.assertTrue(self.service(False).evaluate('jellyfin', 'old').eligible)
    def test_latest_completed_user_sets_episode_clock(self):
        self.provider.positions=(950, 980)
        self.provider.last={'one': stamp(4), 'two': stamp(5)}
        self.assertTrue(self.service().evaluate('jellyfin', 'old').eligible)
        self.provider.last={'one': stamp(4), 'two': stamp(1)}
        self.assertFalse(self.service().evaluate('jellyfin', 'old').eligible)
    def test_partial_viewer_retains_episode(self):
        self.provider.positions=(950, 500)
        self.provider.last=stamp(4)
        self.assertFalse(self.service().evaluate('jellyfin', 'old').eligible)
    def test_invalid_activation_rejected(self):
        with self.assertRaises(TypeError):
            self.service('true')
    def test_favorite_added_after_scan_blocks_real_executor(self):
        cleanup=CleanupService(self.service())
        scan=CleanupScanner(cleanup).scan('jellyfin', ['old'])
        report=CleanupExecutionService().plan(scan, mode='execute')
        self.favorite('series', OTHER)
        provider=JellyfinProvider('http://unused', 'test')
        with patch.object(JellyfinProvider, 'delete_item') as delete:
            result=DefaultCleanupExecutor(
                provider=provider, cleanup_service=cleanup,
                deletion_intent_repository=JsonCleanupDeletionIntentRepository(self.root / 'intents'),
                audit_writer=JsonlCleanupAuditWriter(self.root / 'audit.jsonl', durable=True),
            ).execute(report)
        delete.assert_not_called()
        self.assertEqual(result.modified, 0)
        self.assertEqual(JsonCleanupDeletionIntentRepository(self.root / 'intents').list(), ())

if __name__ == '__main__':
    unittest.main()
