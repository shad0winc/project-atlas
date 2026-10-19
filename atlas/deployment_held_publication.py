"""Native held record publication and restart classification. Never releases owner.

Source/runtime/Doctor/Verify gates belong to the native shell coordinator. These
structural journal observations are not private or public acceptance receipts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from atlas.deployment_publication_journal import (
    PublicationIntentJournal, create_once, encoded, read_file, safe_directory, sync_directory,
)
from atlas.maintenance_control import MaintenanceControlError


class HeldPublication(PublicationIntentJournal):
    def _context(self, publication):
        return self._inspect(publication, allow_published_current=True)

    def _expected(self, intent):
        candidate = self.root / intent['candidate_relative']
        metadata = read_file(candidate / 'metadata', limit=1024 * 1024).decode('ascii')
        values = {}
        for line in metadata.splitlines():
            if '=' not in line:continue
            key, value = line.split('=', 1)
            if key in values:raise MaintenanceControlError('duplicate_publication_metadata')
            values[key] = value
        if (values.get('deployment_id') != intent['publication_id'] or values.get('type') != 'baseline'
                or values.get('previous_baseline') != intent['old_current']):
            raise MaintenanceControlError('publication_record_identity_mismatch')
        pins = dict(intent['candidate_files']);pins['status'] = hashlib.sha256(b'verified\n').hexdigest()
        manifest = ''.join(pins[name] + '  ' + name + '\n' for name in sorted(pins)).encode()
        return pins, manifest

    def _record(self, path, pins, manifest):
        safe_directory(path)
        if set(item.name for item in path.iterdir()) != set(pins) | {'MANIFEST.sha256'}:
            raise MaintenanceControlError('publication_record_inventory_changed')
        if read_file(path / 'MANIFEST.sha256', limit=1024 * 1024) != manifest or any(
                read_file(path / name) != digest for name, digest in pins.items()):
            raise MaintenanceControlError('publication_record_changed')

    def _record_observation(self, publication, manifest):
        return {'schema_version':1,'publication_id':publication,
            'manifest_sha256':hashlib.sha256(manifest).hexdigest(),
            'scope':'record-bytes-observed-not-acceptance'}

    def _check_record_observation(self, publication, manifest):
        _, folder = self._paths(publication)
        if read_file(folder / 'record-observed.json', limit=4096) != encoded(self._record_observation(publication, manifest)):
            raise MaintenanceControlError('publication_record_observation_missing')

    def _note(self, path, value):
        raw = encoded(value)
        if path.exists() or path.is_symlink():
            if read_file(path, limit=4 * 1024 * 1024) != raw:
                raise MaintenanceControlError('publication_observation_conflict')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
            sync_directory(path.parent)
        else:create_once(path, raw)

    def record(self, publication):
        """Materialize the exact prepared candidate with verified status, once."""
        with self._exclusive():
            intent = self._context(publication);pins, manifest = self._expected(intent)
            records = self.root / 'deployments/records';safe_directory(records)
            target = records / publication;_, folder = self._paths(publication)
            staging = folder / 'record-staging'
            if target.exists() or target.is_symlink():
                self._record(target, pins, manifest)
                sync_directory(records)
            else:
                if read_file(self.root / 'deployments/current', limit=256) != (intent['old_current'] + '\n').encode():
                    raise MaintenanceControlError('published_pointer_without_record')
                if staging.exists() or staging.is_symlink():
                    # Only a complete exact staging directory can be adopted.
                    # Partial artifacts are retained for explicit host review.
                    self._record(staging, pins, manifest)
                else:
                    staging.mkdir(mode=0o700);sync_directory(folder)
                    candidate = self.root / intent['candidate_relative']
                    for name in sorted(pins):
                        if name == 'status':create_once(staging / name, b'verified\n');continue
                        source = os.open(candidate / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                        destination = None
                        try:
                            destination = os.open(staging / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                            with os.fdopen(source, 'rb', closefd=False) as src, os.fdopen(destination, 'wb', closefd=False) as dst:
                                import shutil
                                shutil.copyfileobj(src, dst, 1024 * 1024);dst.flush();os.fsync(destination)
                        finally:
                            os.close(source)
                            if destination is not None:os.close(destination)
                    create_once(staging / 'MANIFEST.sha256', manifest)
                    self._record(staging, pins, manifest);sync_directory(staging)
                self.checkpoint('record_staged_durable')
                # Target is absent under the shared native exclusion. No existing
                # record is replaced; recheck immediately before directory rename.
                if target.exists() or target.is_symlink():raise MaintenanceControlError('publication_target_appeared')
                os.rename(staging, target);self.checkpoint('record_renamed')
                sync_directory(records);sync_directory(folder)
            self.checkpoint('record_namespace_durable')
            self._context(publication);self._record(target, pins, manifest)
            self._note(folder / 'record-observed.json', self._record_observation(publication, manifest))
            return target

    def state(self, publication):
        with self._exclusive():
            intent = self._context(publication);pins, manifest = self._expected(intent)
            target = self.root / 'deployments/records' / publication
            current = read_file(self.root / 'deployments/current', limit=256)
            if target.exists() or target.is_symlink():self._record(target, pins, manifest)
            if current == (publication + '\n').encode():
                self._record(target, pins, manifest)
                self._generation(intent)
                self._check_record_observation(publication, manifest)
                return 'current-published'
            return 'before-current'

    def _generation(self, intent):
        generation = self.root / 'source/generations' / intent['publication_id']
        safe_directory(generation)
        if (read_file(generation / '.atlas-deployment-id', limit=256) != (intent['publication_id'] + '\n').encode()
                or read_file(generation / '.atlas-source-sha256', limit=256)
                != (intent['candidate_files']['core-source.tar.gz'] + '\n').encode()):
            raise MaintenanceControlError('publication_generation_marker_mismatch')
        # Full archive/blob/config provenance stays mandatory in native runtime
        # verification and scheduler-source publication; these markers add no waiver.

    def held_boundary(self, publication):
        with self._exclusive():
            intent = self._context(publication);pins, manifest = self._expected(intent)
            self._record(self.root / 'deployments/records' / publication, pins, manifest)
            self._generation(intent)
            self._check_record_observation(publication, manifest)
            if read_file(self.root / 'deployments/current', limit=256) != (publication + '\n').encode():
                raise MaintenanceControlError('publication_pointer_not_observed')
            _, folder = self._paths(publication)
            self._note(folder / 'held-boundary.json', {'schema_version':1,'publication_id':publication,
                'record_manifest_sha256':hashlib.sha256(manifest).hexdigest(),
                'scope':'held-boundary-observed-not-acceptance','original_owner_retained':True,
                'ordinary_reopening_permitted':False})
            self.checkpoint('held_boundary_durable')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--owner', required=True);parser.add_argument('--publication', required=True)
    parser.add_argument('--fd', type=int, required=True)
    parser.add_argument('action', choices=('state','candidate','record','held-boundary'))
    args = parser.parse_args();journal = HeldPublication(args.runtime_root, args.owner, args.fd)
    try:
        if args.action == 'state':print(journal.state(args.publication))
        elif args.action == 'candidate':
            intent = journal._context(args.publication);print(journal.root / intent['candidate_relative'])
        elif args.action == 'record':journal.record(args.publication)
        else:journal.held_boundary(args.publication)
    except (OSError, ValueError, KeyError, MaintenanceControlError):
        print('ERROR: held publication refused; preserve marker, original owner and journal.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':raise SystemExit(main())
