"""Explicit, immutable source-to-canonical mappings; no automatic name matching."""
from dataclasses import dataclass
import re
from providers.espn_metadata import ROUTES


class MetadataIdentityConflict(ValueError):
    pass


@dataclass(frozen=True)
class SourceIdentity:
    provider: str
    route: str
    event_id: str

    def __post_init__(self):
        if self.provider not in {'espn', 'thesportsdb'}:
            raise ValueError('Unsupported source provider')
        if not isinstance(self.event_id, str) or not re.fullmatch(r'[0-9]{1,32}', self.event_id):
            raise ValueError('Invalid source event identity')
        if self.provider == 'espn':
            if not isinstance(self.route, str) or self.route not in ROUTES:
                raise ValueError('Unsupported source league')
        elif not isinstance(self.route, str) or not re.fullmatch(r'[0-9]{1,32}', self.route):
            raise ValueError('Invalid primary league identity')

    def values(self):
        return (self.provider, self.route, self.event_id)


class MetadataIdentityRegistry:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def _existing(connection, source):
        row = connection.execute('''SELECT owner_provider,owner_route,owner_event_id
            FROM metadata_aliases WHERE provider=? AND route=? AND event_id=?''',
            source.values()).fetchone()
        return SourceIdentity(*row) if row else None

    def resolve(self, source):
        if not isinstance(source, SourceIdentity):
            raise TypeError('SourceIdentity required')
        with self.store.locked(), self.store.connection() as connection:
            return self._existing(connection, source)

    def enroll_verified(self, owner, aliases, *, evidence_sha256):
        """Writer-only enrollment from independently reviewed evidence.

        The evidence digest is provenance, not a machine-verifiable proof. A caller
        must verify that records are the same real event before invoking this method.
        No API, policy loader or production caller is installed in this candidate.
        Never call this with heuristic suggestions or schedule adjacency alone.
        """
        if not isinstance(aliases, (list, tuple)):
            raise TypeError("Explicit alias list required")
        if not isinstance(owner, SourceIdentity) or any(not isinstance(s, SourceIdentity) for s in aliases):
            raise TypeError('SourceIdentity required')
        if not isinstance(evidence_sha256, str) or not re.fullmatch('[a-f0-9]{64}', evidence_sha256):
            raise ValueError('Verified evidence digest required')
        sources = tuple(dict.fromkeys((owner, *aliases)))
        if len(sources) > 32:
            raise ValueError('Alias enrollment exceeds budget')
        with self.store.locked(), self.store.connection() as connection:
            for source in sources:
                current = self._existing(connection, source)
                if current is not None and current != owner:
                    raise MetadataIdentityConflict('Source already belongs to a different canonical owner')
            for source in sources:
                connection.execute('''INSERT OR IGNORE INTO metadata_aliases
                    VALUES (?,?,?,?,?,?,?)''', (*source.values(), *owner.values(), evidence_sha256))
        return owner
