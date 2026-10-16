from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]


class MetadataIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT/'modules/sports/src'))
        global MetadataStore, SourceIdentity, MetadataIdentityRegistry, MetadataIdentityConflict
        from providers.metadata_store import MetadataStore
        from providers.metadata_identity import SourceIdentity, MetadataIdentityRegistry, MetadataIdentityConflict

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'metadata.sqlite'
        self.store = MetadataStore(self.path)
        self.registry = MetadataIdentityRegistry(self.store)
        self.owner = SourceIdentity('thesportsdb', '4391', '2475454')
        self.alias = SourceIdentity('espn', 'football/nfl', '401872996')
        self.evidence = 'a'*64

    def enroll(self, owner=None, aliases=None):
        return self.registry.enroll_verified(self.owner if owner is None else owner,
            [self.alias] if aliases is None else aliases, evidence_sha256=self.evidence)

    def test_existing_primary_identity_remains_the_owner(self):
        self.enroll()
        self.assertEqual(self.registry.resolve(self.owner), self.owner)
        self.assertEqual(self.registry.resolve(self.alias), self.owner)
        self.assertEqual(self.registry.resolve(self.alias).event_id, '2475454')

    def test_mapping_survives_registry_recreation(self):
        self.enroll()
        reopened = MetadataIdentityRegistry(MetadataStore(self.path))
        self.assertEqual(reopened.resolve(self.alias), self.owner)

    def test_idempotent_enrollment(self):
        self.enroll()
        self.enroll()
        with self.store.connection() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM metadata_aliases').fetchone()[0], 2)

    def test_unknown_identity_is_not_automatically_claimed(self):
        self.assertIsNone(self.registry.resolve(self.alias))
        with self.store.connection() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM metadata_aliases').fetchone()[0], 0)

    def test_conflict_rolls_back_new_owner_and_all_new_aliases(self):
        self.enroll()
        other = SourceIdentity('thesportsdb', '4391', '9999999')
        unbound = SourceIdentity('espn', 'football/nfl', '9999999')
        with self.assertRaises(MetadataIdentityConflict):
            self.enroll(other, [unbound, self.alias])
        self.assertIsNone(self.registry.resolve(other))
        self.assertIsNone(self.registry.resolve(unbound))
        self.assertEqual(self.registry.resolve(self.alias), self.owner)

    def test_existing_canonical_owners_cannot_be_merged(self):
        self.enroll(self.owner, [])
        self.enroll(self.alias, [])
        with self.assertRaises(MetadataIdentityConflict):
            self.enroll()
        self.assertEqual(self.registry.resolve(self.alias), self.alias)

    def test_alias_cannot_become_another_canonical_owner(self):
        self.enroll()
        other = SourceIdentity('espn','football/nfl','9999999')
        with self.assertRaises(MetadataIdentityConflict):
            self.enroll(self.alias, [other])
        self.assertIsNone(self.registry.resolve(other))

    def test_no_evidence_no_enrollment(self):
        for evidence in ('', 'suggested-match', 'A'*64, None):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.registry.enroll_verified(self.owner,[self.alias], evidence_sha256=evidence)
        self.assertIsNone(self.registry.resolve(self.owner))

    def test_provider_and_league_are_part_of_identity(self):
        other = SourceIdentity('espn','basketball/nba',self.alias.event_id)
        self.enroll()
        self.assertIsNone(self.registry.resolve(other))

    def test_unbounded_iterator_not_accepted_as_alias_batch(self):
        with self.assertRaises(TypeError):
            self.enroll(aliases=iter([self.alias]))
        self.assertIsNone(self.registry.resolve(self.owner))

    def test_alias_enrollment_budget(self):
        aliases = [SourceIdentity('espn','football/nfl',str(i+1)) for i in range(32)]
        with self.assertRaises(ValueError):
            self.enroll(aliases=aliases)
        self.assertIsNone(self.registry.resolve(self.owner))

    def test_invalid_source_identity(self):
        for provider, route, event_id in (
            ('other','football/nfl','1'), ('espn','mma/pfl','1'),
            ('thesportsdb','football/nfl','1'), ('espn','football/nfl','../x'),
        ):
            with self.subTest(provider=provider,route=route), self.assertRaises(ValueError):
                SourceIdentity(provider,route,event_id)

if __name__ == '__main__':
    unittest.main()
