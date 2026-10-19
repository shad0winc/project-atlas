import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'modules/sports/src'))
sys.path.insert(0,str(ROOT/'tests/core'))
from providers.metadata_store import MetadataStore
from providers.metadata_identity import MetadataIdentityRegistry,SourceIdentity
import test_backup_storage_safety as backup_fixtures

spec=importlib.util.spec_from_file_location('atlas_metadata_recovery',ROOT/'scripts/lib/metadata-recovery.py')
recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)


class MetadataRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'source';self.source.mkdir(mode=0o700)
        self.snapshot=self.root/'snapshot';self.snapshot.mkdir(mode=0o700)
        self.destination=self.snapshot/'metadata-recovery'
        self.store=MetadataStore(self.source/'metadata.sqlite')
        self.owner=SourceIdentity('thesportsdb','4391','2475454')
        self.alias=SourceIdentity('espn','football/nfl','401872996')
        MetadataIdentityRegistry(self.store).enroll_verified(self.owner,[self.alias],evidence_sha256='a'*64)

    def captured(self):
        self.assertTrue(recovery.capture(self.source,self.destination))
        return self.destination

    def archive(self,*,duplicate=False,extra=None,format_version='3'):
        path=self.root/'metadata.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            archive.add(self.destination,arcname='metadata-recovery')
            if duplicate:
                archive.add(self.destination/'database.sqlite',arcname='metadata-recovery/database.sqlite')
            if extra is not None:
                info,raw=extra
                archive.addfile(info,io.BytesIO(raw) if raw is not None else None)
            raw=(format_version+'\n').encode()
            info=tarfile.TarInfo('RECOVERY_FORMAT');info.size=len(raw);info.mode=0o600
            archive.addfile(info,io.BytesIO(raw))
        return path

    def shell(self,body,env=None):
        return subprocess.run(['bash','-c','set -euo pipefail\nsource "$REGISTRY"\n'+body],
            env={**os.environ,'REGISTRY':str(ROOT/'scripts/lib/backup-recovery.sh'),**(env or {})},
            capture_output=True,text=True,timeout=30)

    def test_capture_is_private_and_preserves_real_identity_registry(self):
        source_digest=recovery.digest(self.source/'metadata.sqlite')
        self.captured();recovery.validate_staged(self.destination)
        self.assertEqual(recovery.digest(self.source/'metadata.sqlite'),source_digest)
        self.assertEqual({p.name for p in self.destination.iterdir()},{'MANIFEST.json','database.sqlite'})
        self.assertEqual(self.destination.stat().st_mode&0o777,0o700)
        self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in self.destination.iterdir()))
        reopened=self.root/'reopened';reopened.mkdir(mode=0o700)
        shutil.copyfile(self.destination/'database.sqlite',reopened/'metadata.sqlite')
        (reopened/'metadata.sqlite').chmod(0o600)
        registry=MetadataIdentityRegistry(MetadataStore(reopened/'metadata.sqlite'))
        self.assertEqual(registry.resolve(self.alias),self.owner)
        self.assertEqual(registry.resolve(self.owner),self.owner)

    def test_absent_installation_does_not_create_state_or_artifacts(self):
        absent=self.root/'absent'
        self.assertFalse(recovery.capture(absent,self.destination))
        self.assertFalse(absent.exists());self.assertFalse(self.destination.exists())

    def test_present_empty_directory_fails_instead_of_becoming_absent(self):
        empty=self.root/'empty';empty.mkdir(mode=0o700)
        with self.assertRaises((recovery.RecoveryError,OSError)):
            recovery.capture(empty,self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_lock_fails_without_recreating_it(self):
        (self.source/'metadata.sqlite.lock').unlink()
        with self.assertRaises((recovery.RecoveryError,OSError)):
            recovery.capture(self.source,self.destination)
        self.assertFalse((self.source/'metadata.sqlite.lock').exists())

    def test_capture_refuses_symlink_directory_and_database(self):
        link=self.root/'link';link.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(recovery.RecoveryError):recovery.capture(link,self.destination)
        database=self.source/'metadata.sqlite';database.rename(self.source/'original.sqlite')
        database.symlink_to(self.source/'original.sqlite')
        with self.assertRaises(recovery.RecoveryError):recovery.capture(self.source,self.destination)

    def test_capture_refuses_unsafe_permissions(self):
        (self.source/'metadata.sqlite').chmod(0o640)
        with self.assertRaises(recovery.RecoveryError):recovery.capture(self.source,self.destination)
        self.assertFalse(self.destination.exists())

    def test_unknown_schema_is_rejected_and_partial_snapshot_removed(self):
        with self.store.connection() as connection:connection.execute('UPDATE metadata_schema SET version=2')
        with self.assertRaises(recovery.RecoveryError):recovery.capture(self.source,self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.snapshot.iterdir()),[])

    def test_broken_canonical_owner_is_not_a_valid_recovery_snapshot(self):
        with self.store.connection() as connection:
            connection.execute('DELETE FROM metadata_aliases WHERE provider=?',('thesportsdb',))
        with self.assertRaises(recovery.RecoveryError):recovery.capture(self.source,self.destination)
        self.assertFalse(self.destination.exists())

    def test_failed_validation_cannot_publish_partial_snapshot(self):
        with patch.object(recovery,'validate_database',side_effect=recovery.RecoveryError('invalid')):
            with self.assertRaises(recovery.RecoveryError):recovery.capture(self.source,self.destination)
        self.assertEqual(list(self.snapshot.iterdir()),[])

    def test_source_lock_acquisition_is_bounded(self):
        with self.store.locked():
            with self.assertRaises(recovery.RecoveryError):
                with recovery.source_lock(self.source/'metadata.sqlite.lock',os.geteuid(),timeout=.02):
                    self.fail('Acquired a held writer lock')

    def test_mutating_source_after_capture_does_not_change_snapshot(self):
        self.captured();digest=recovery.digest(self.destination/'database.sqlite')
        with self.store.locked(),self.store.connection() as connection:
            connection.execute('INSERT INTO metadata_attempts VALUES (123)')
        self.assertEqual(recovery.digest(self.destination/'database.sqlite'),digest)
        recovery.validate_staged(self.destination)

    def test_hot_wal_content_is_included_in_sqlite_backup(self):
        connection=sqlite3.connect(self.source/'metadata.sqlite')
        try:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('INSERT INTO metadata_attempts VALUES (456)');connection.commit()
            self.captured()
            read=sqlite3.connect(self.destination/'database.sqlite')
            try:self.assertEqual(read.execute('SELECT stamp FROM metadata_attempts').fetchall(),[(456.0,)])
            finally:read.close()
        finally:connection.close()

    def test_archive_validation_and_checksum_tampering(self):
        self.captured();recovery.validate_archive(self.archive())
        with (self.destination/'database.sqlite').open('ab') as handle:handle.write(b'tampered')
        with self.assertRaises(recovery.RecoveryError):recovery.validate_staged(self.destination)

    def test_duplicate_archive_member_rejected(self):
        self.captured()
        with self.assertRaises(recovery.RecoveryError):recovery.validate_archive(self.archive(duplicate=True))

    def test_archive_symlink_and_extra_artifacts_rejected(self):
        self.captured()
        info=tarfile.TarInfo('metadata-recovery/extra');info.type=tarfile.SYMTYPE;info.linkname='/tmp/unrelated'
        with self.assertRaises(recovery.RecoveryError):recovery.validate_archive(self.archive(extra=(info,None)))

    def test_format_three_safe_members_and_legacy_rejection(self):
        self.captured()
        archive=self.archive()
        result=self.shell('atlas_backup_recovery_validate_safe_members "$ARCHIVE"',{'ARCHIVE':str(archive)})
        self.assertEqual(result.returncode,0,result.stderr)
        archive=self.archive(format_version='2')
        result=self.shell('atlas_backup_recovery_validate_safe_members "$ARCHIVE"',{'ARCHIVE':str(archive)})
        self.assertNotEqual(result.returncode,0)

    def test_complete_backup_uses_format_three_only_when_metadata_exists(self):
        project,backups=backup_fixtures._make_project(self.root)
        env=backup_fixtures._recovery_environment(project)
        metadata=Path(env['ATLAS_RUNTIME_CONFIG_DIR'])/'private/sports-metadata'
        metadata.parent.mkdir(mode=0o700,parents=True)
        shutil.copytree(self.source,metadata)
        result=backup_fixtures._run_backup(project,backups)
        self.assertEqual(result.returncode,0,result.stderr)
        archives=list(backups.glob('atlas-*.tar.gz'));self.assertEqual(len(archives),1)
        with tarfile.open(archives[0]) as archive:
            self.assertEqual(archive.extractfile('RECOVERY_FORMAT').read(),b'3\n')
            self.assertIn(b'Recovery format: 3',archive.extractfile('BACKUP_INFO.txt').read())
            self.assertNotIn('metadata-recovery/metadata.sqlite.lock',archive.getnames())
        recovery.validate_archive(archives[0])
        result=self.shell('atlas_backup_recovery_validate_archive "$ARCHIVE"',
                          {**env,'ARCHIVE':str(archives[0])})
        self.assertEqual(result.returncode,0,result.stderr)
        staged=self.shell('atlas_backup_recovery_stage_archive "$ARCHIVE" /tmp',
                          {**env,'ATLAS_PROJECT_DIR':str(project),'ARCHIVE':str(archives[0])})
        self.assertEqual(staged.returncode,0,staged.stderr)
        stage=Path(staged.stdout.strip())
        self.assertTrue(stage.name.startswith('project-atlas-restore.'))
        try:
            recovery.validate_staged(stage/'metadata-recovery')
            self.assertEqual((stage/'RECOVERY_FORMAT').read_text(),'3\n')
        finally:
            shutil.rmtree(stage)

    def test_absent_metadata_keeps_existing_format_two_backup(self):
        project,backups=backup_fixtures._make_project(self.root)
        result=backup_fixtures._run_backup(project,backups)
        self.assertEqual(result.returncode,0,result.stderr)
        with tarfile.open(next(backups.glob('atlas-*.tar.gz'))) as archive:
            self.assertEqual(archive.extractfile('RECOVERY_FORMAT').read(),b'2\n')
            self.assertFalse(any(name.startswith('metadata-recovery') for name in archive.getnames()))

    def test_incomplete_metadata_prevents_backup_publication(self):
        project,backups=backup_fixtures._make_project(self.root)
        env=backup_fixtures._recovery_environment(project)
        metadata=Path(env['ATLAS_RUNTIME_CONFIG_DIR'])/'private/sports-metadata'
        metadata.mkdir(mode=0o700,parents=True)
        result=backup_fixtures._run_backup(project,backups)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(list(backups.glob('atlas-*.tar.gz')),[])
        self.assertEqual(list(backups.glob('*.partial')),[])

    def test_format_three_filesystem_restore_plan_is_rejected(self):
        stage=self.root/'stage';stage.mkdir();(stage/'RECOVERY_FORMAT').write_text('3\n')
        result=self.shell('atlas_backup_recovery_validate_staged_restore() { :; }; atlas_backup_recovery_restore_plan "$STAGE"',{'STAGE':str(stage)})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('format 3',result.stderr)

    def test_format_three_live_preflight_stops_before_deployment_actions(self):
        marker=self.root/'unexpected'
        with tempfile.TemporaryDirectory(prefix='project-atlas-restore.', dir='/tmp') as directory:
            stage=Path(directory);(stage/'RECOVERY_FORMAT').write_text('3\n')
            script='source "$RESTORE"; atlas_deployment_validate_source() { touch "$MARKER"; return 1; }; atlas_restore_require_production_preflight "$STAGE"'
            result=self.shell(script,{'RESTORE':str(ROOT/'scripts/commands/restore.sh'),
                                     'MARKER':str(marker),'STAGE':str(stage)})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('format 3',result.stderr)
        self.assertFalse(marker.exists())

if __name__=='__main__':unittest.main()
