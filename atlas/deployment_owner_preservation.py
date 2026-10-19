"""Seal original ownership preservation evidence; never release or move a lock.

This host-only preparation binds a fresh private receipt and complete current
owner identity. It is not a publication, CI/public acceptance, or release permit.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat

from atlas.deployment_private_acceptance import PrivateHeldAcceptance
from atlas.deployment_publication_journal import encoded, read_file
from atlas.maintenance_control import MaintenanceControlError


class OwnerPreservationPlan(PrivateHeldAcceptance):
    def _inventory(self, intent):
        before = self.recovery_lock.lstat()
        if set(path.name for path in self.recovery_lock.iterdir()) != {'owner'}:
            raise MaintenanceControlError('original_owner_inventory_changed')
        owner = self._owner()
        fields = self._owner_fields(owner)
        if fields != intent['original_owner']:
            raise MaintenanceControlError('publication_original_owner_changed')
        file_info = (self.recovery_lock/'owner').lstat()
        after = self.recovery_lock.lstat()
        directory = lambda value: (value.st_dev,value.st_ino,value.st_uid,value.st_gid,
                                  stat.S_IMODE(value.st_mode),value.st_mtime_ns,value.st_ctime_ns)
        if directory(before) != directory(after):
            raise MaintenanceControlError('original_owner_inventory_changed')
        return {'directory':{'device':before.st_dev,'inode':before.st_ino,'uid':before.st_uid,
                    'gid':before.st_gid,'mode':stat.S_IMODE(before.st_mode)},
                'files':{'owner':{'device':file_info.st_dev,'inode':file_info.st_ino,
                    'uid':file_info.st_uid,'gid':file_info.st_gid,'mode':stat.S_IMODE(file_info.st_mode),
                    'links':file_info.st_nlink,'sha256':hashlib.sha256(owner[2]).hexdigest()}}}

    def _boundary(self, publication, manifest):
        _, folder = self._paths(publication)
        expected={'schema_version':1,'publication_id':publication,
            'record_manifest_sha256':hashlib.sha256(manifest).hexdigest(),
            'scope':'held-boundary-observed-not-acceptance','original_owner_retained':True,
            'ordinary_reopening_permitted':False}
        if read_file(folder/'held-boundary.json',limit=4096) != encoded(expected):
            raise MaintenanceControlError('owner_plan_held_boundary_unproven')

    def prepare(self, publication, attempt, private_sha256):
        with self._exclusive():
            # Validation supplies a current, exact, fresh private receipt; it
            # explicitly denies CI/public proof and release permission.
            receipt=self.validate(publication,attempt,private_sha256)
            source=Path(receipt['context']['source']['root'])
            tracked=self._command('git','-C',str(source),'show','HEAD:atlas/deployment_owner_preservation.py')
            collector_sha=hashlib.sha256(tracked).hexdigest()
            if collector_sha != read_file(Path(__file__)):
                raise MaintenanceControlError('owner_plan_source_differs')
            intent=self._context(publication);_, manifest=self._expected(intent)
            self._boundary(publication,manifest)
            inventory=self._inventory(intent)
            _,folder=self._paths(publication)
            plan={'schema_version':1,'scope':'owner-preservation-preparation-only',
                'publication_id':publication,'original_owner':intent['original_owner'],
                'owner_plan_collector_sha256':collector_sha,
                'original_lock_inventory':inventory,
                'intent_sha256':read_file(folder/'intent.json'),
                'held_boundary_sha256':read_file(folder/'held-boundary.json'),
                'private_attempt':attempt,'private_receipt_sha256':private_sha256,
                'private_context_sha256':hashlib.sha256(encoded(receipt['context'])).hexdigest(),
                'current_sha256':read_file(self.root/'deployments/current'),
                'archive_relative':'deployments/publication-journals/'+publication+'/original-update.lock',
                'archive_method_required':'same-filesystem-whole-directory-rename-with-parent-fsync',
                'original_owner_retained':True,'owner_release_permitted':False,
                'ci_acceptance_proven':False,'public_acceptance_proven':False,
                'ordinary_reopening_permitted':False}
            target=folder/'owner-preservation.json'
            self._note(target,plan)
            self.checkpoint('owner_preservation_plan_durable')
            # A callback/filesystem failure must never turn this preparation into
            # an ownership mutation. Recheck all admission evidence before return.
            self.validate(publication,attempt,private_sha256)
            if self._inventory(self._context(publication)) != inventory:
                raise MaintenanceControlError('original_owner_inventory_changed')
            self._boundary(publication,manifest)
            return target

    def inspect_plan(self, publication, attempt, private_sha256):
        # Revalidation must remain fresh; inspection never refreshes old evidence.
        with self._exclusive():
            _,folder=self._paths(publication)
            old=read_file(folder/'owner-preservation.json',limit=65536)
            result=self.prepare(publication,attempt,private_sha256)
            if read_file(result,limit=65536)!=old:
                raise MaintenanceControlError('owner_preservation_plan_conflict')
            return json.loads(old)
