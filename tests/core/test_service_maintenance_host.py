"""Host scan and privilege-boundary regressions."""
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from atlas.service_lifecycle import (
    ImageReference, ManagedService, MaintenanceReport, ServiceHealth, ServiceHealthStatus,
    ServiceImage, ServiceLifecycleService, ServiceRuntime, ServiceUpdate, ServiceUpdateService, UpdateStatus,
)
from atlas.service_lifecycle.providers.runtime_snapshot import RuntimeSnapshotProvider

path = Path(__file__).resolve().parents[2] / "tools/operations/atlas_service_maintenance.py"
spec = importlib.util.spec_from_file_location("service_maintenance_host", path)
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
IMAGE = "sha256:" + "b" * 64
OTHER = "sha256:" + "c" * 64
REFERENCE = "lscr.io/linuxserver/bazarr:latest"


class HostTests(unittest.TestCase):
    def entry(self):
        service = ManagedService(identifier="bazarr", name="Bazarr", provider="docker-compose",
                                 container_name="bazarr", compose_project="project-atlas")
        runtime = ServiceRuntime(state="running", health="unknown",
                                 image=ServiceImage(reference=REFERENCE, image_id="sha256:" + "a" * 64))
        health = ServiceHealth(ServiceHealthStatus.DEGRADED)
        update = ServiceUpdate(service_identifier="bazarr", service_name="Bazarr",
                               current_image=ImageReference.parse(REFERENCE), status=UpdateStatus.UNKNOWN,
                               evaluated_at="2026-09-28T00:00:00Z")
        return {"service": service.to_dict(), "runtime": runtime.to_dict(),
                "health": health.to_dict(), "update": update.to_dict()}

    def fixture_docker(self, *args):
        if args[:2] == ("image", "inspect"):
            return json.dumps([{
                "Id": IMAGE, "Os": "linux", "Architecture": "amd64", "Descriptor": {"digest": IMAGE},
                "Created": "2026-11-04T01:21:37Z",
                "Config": {"Labels": {"org.opencontainers.image.version": "v1.6.2-ls371"}},
            }]).encode()
        return json.dumps([{
            "Id": "d" * 64, "Image": IMAGE, "Config": {"Image": IMAGE, "Labels": {
                "io.project-atlas.configured-image": REFERENCE, "com.docker.compose.project": "project-atlas",
            }},
            "RestartCount": 0,
            "State": {"Running": True, "Status": "running", "StartedAt": "2026-11-10T23:30:00Z",
                      "FinishedAt": None, "ExitCode": 0},
        }]).encode()

    def validate(self, entry):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(json.dumps({"schema_version": 1, "generated_at": host.now(),
                                       "provider": "docker-compose", "services": [entry],
                                       "history": MaintenanceReport().to_dict()}))
            provider = RuntimeSnapshotProvider(path)
            provider.inspect_runtime("bazarr")
            provider.inspect_health("bazarr")
            provider.inspect_update("bazarr")
            return ServiceUpdateService(ServiceLifecycleService(provider)).inspect_updates()

    def test_current_running_digest_replaces_stale_snapshot(self):
        with patch.object(host, "docker", side_effect=self.fixture_docker), \
             patch.object(host, "registry", return_value=(IMAGE, [])):
            entry = host.scan_entry(self.entry())
        self.assertEqual(IMAGE, entry["runtime"]["image"]["image_id"])
        self.assertEqual("current", entry["update"]["status"])
        self.assertEqual("unknown", entry["health"]["status"])
        self.assertEqual(IMAGE, entry["update"]["details"]["local_descriptor_digest"])
        self.validate(entry)

    def test_platform_manifest_also_counts_as_current(self):
        with patch.object(host, "docker", side_effect=self.fixture_docker), \
             patch.object(host, "registry", return_value=(OTHER, [IMAGE])):
            entry = host.scan_entry(self.entry())
        self.assertEqual("current", entry["update"]["status"])

    def test_older_registry_build_is_not_advertised_as_update(self):
        with patch.object(host, "docker", side_effect=self.fixture_docker), \
             patch.object(host, "registry", return_value=(OTHER, [])), \
             patch.object(host, "remote_version", return_value="v1.6.2-ls366"):
            entry = host.scan_entry(self.entry())
        self.assertEqual("unknown", entry["update"]["status"])
        self.assertIsNone(entry["update"]["available_image"])
        self.validate(entry)

    def test_registry_failure_removes_stale_available_target(self):
        with patch.object(host, "docker", side_effect=self.fixture_docker), \
             patch.object(host, "registry", side_effect=RuntimeError("registry_failed")):
            entry = host.scan_entry(self.entry())
        self.assertEqual("unknown", entry["update"]["status"])
        self.assertFalse(entry["update"]["details"]["registry_comparison"])

    def test_missing_container_is_reported_without_reusing_image_identity(self):
        with patch.object(host, "container", side_effect=RuntimeError("docker_observation_failed")):
            entry = host.scan_entry(self.entry())
        self.assertEqual("unavailable", entry["health"]["status"])
        self.assertIsNone(entry["runtime"]["image"]["image_id"])
        self.validate(entry)

    def test_reading_old_report_preserves_observation_date(self):
        report = self.validate(self.entry())
        self.assertEqual("2026-09-28T00:00:00Z", report.evaluated_at)

    def test_failed_api_validation_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, private = root / "runtime", root / "private"
            runtime.mkdir()
            private.mkdir()
            path = runtime / "latest.json"
            original = {"schema_version": 1, "services": [self.entry()]}
            path.write_text(json.dumps(original))
            before = path.read_bytes()
            lock = root / "scheduler.lock"
            lock.touch()
            def command(*args):
                if args[0] == "exec":
                    raise RuntimeError("api_validation_failed")
                return b"1.50"
            with patch.object(host, "SNAPSHOT", path), patch.object(host, "ROOT", private), \
                 patch.object(host, "DEPLOYMENT_LOCK", lock), \
                 patch.object(host, "scan_entry", side_effect=lambda entry: entry), \
                 patch.object(host, "maintenance_history", return_value={}), \
                 patch.object(host.os, "fchown"), patch.object(host, "docker", side_effect=command):
                with self.assertRaisesRegex(RuntimeError, "api_validation_failed"):
                    host.publish_scan(lambda value: None)
            self.assertEqual(before, path.read_bytes())
            self.assertEqual([], list(runtime.glob(".scan-*")))

    def test_socket_refuses_other_linux_uids_before_dispatch(self):
        handler = host.Handler.__new__(host.Handler)
        handler.request = Mock()
        handler.request.getsockopt.return_value = struct.pack("3i", 123, 1000, 1000)
        handler.rfile = io.BytesIO(b'{"operation":"scan","actor":"admin"}\n')
        handler.wfile = io.BytesIO()
        handler.server = SimpleNamespace(jobs=Mock())
        handler.handle()
        self.assertEqual("peer_not_permitted", json.loads(handler.wfile.getvalue())["error"])
        handler.server.jobs.submit.assert_not_called()

    def test_busy_and_unknown_operations_cannot_start_another_job(self):
        jobs = host.Jobs.__new__(host.Jobs)
        with self.assertRaisesRegex(RuntimeError, "invalid_operation"):
            jobs.submit("arbitrary-command", "admin")
        with tempfile.TemporaryDirectory() as directory:
            jobs.path = Path(directory) / "job.json"
            jobs.path.write_text('{"status":"running"}')
            with patch.object(host.threading, "Thread") as thread:
                with self.assertRaisesRegex(RuntimeError, "operation_busy"):
                    jobs.submit("scan", "admin")
                thread.assert_not_called()


class BazarrContextTests(unittest.TestCase):
    def setUp(self):
        from hashlib import sha256
        self.sha = sha256
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tx = self.root / 'bazarr-ls371-1c267431e51a'
        self.tx.mkdir()
        self.marker = self.root / 'maintenance/enabled'
        self.marker.parent.mkdir()
        self.marker.write_bytes(b'maintenance\n')
        self.pointer = self.root / 'deployments/current'
        record = self.root / 'deployments/records' / host.BAZARR_PUBLICATION
        record.mkdir(parents=True)
        (record / 'MANIFEST.sha256').write_bytes(b'baseline\n')
        self.pointer.write_text(host.BAZARR_PUBLICATION + '\n')
        self.runner = self.root / 'runner/atlas_bazarr_update.py'
        self.runner.parent.mkdir()
        self.runner.write_bytes(b'# reviewed runner fixture\n')
        info = self.marker.stat()
        self.inputs = {
            'baseline_manifest_sha256': sha256(b'baseline\n').hexdigest(),
            'maintenance_inode': [info.st_dev, info.st_ino],
            'maintenance_sha256': sha256(self.marker.read_bytes()).hexdigest(),
            'source_pins': {self.runner.name: sha256(self.runner.read_bytes()).hexdigest()},
            'original': {'Id': 'old-bazarr'},
            'protected': {'api': {'name': '/atlas-api', 'image': 'api-image',
                                  'started_at': 'start', 'running': True,
                                  'restart_count': 0, 'paused': False}},
        }
        (self.tx / 'inputs.json').write_text(json.dumps(self.inputs))
        self.api = {'Id': 'api', 'Name': '/atlas-api', 'Image': 'api-image',
                    'Config': {'Labels': {}}, 'State': {'StartedAt': 'start', 'Running': True},
                    'RestartCount': 0}
        self.command = Mock(side_effect=self.docker)
        for name, value in (('BAZARR', self.tx), ('MARKER', self.marker), ('RUNNER', self.runner),
                            ('docker', self.command)):
            patcher = patch.object(host, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def docker(self, *args):
        if args[0] == 'ps':
            return b'api\n'
        return json.dumps([self.api]).encode()

    def test_unchanged_reviewed_context_is_recognized(self):
        self.assertTrue(host.bazarr_context_matches())

    def test_new_atlas_publication_requires_new_context_review(self):
        self.pointer.write_text('baseline-services-maintenance-99595facca1d\n')
        self.assertFalse(host.bazarr_context_matches())
        self.command.assert_not_called()

    def test_changed_protected_runtime_requires_new_context_review(self):
        self.api['Image'] = 'replacement-api-image'
        self.assertFalse(host.bazarr_context_matches())

    def test_changed_runner_source_requires_review(self):
        self.runner.write_bytes(b'# changed\n')
        self.assertFalse(host.bazarr_context_matches())

    def test_changed_maintenance_marker_requires_review(self):
        self.marker.write_bytes(b'changed\n')
        self.assertFalse(host.bazarr_context_matches())

    def test_missing_context_fails_closed(self):
        (self.tx / 'inputs.json').unlink()
        self.assertFalse(host.bazarr_context_matches())

    def test_retained_assets_do_not_offer_rollback_after_publication_changes(self):
        self.pointer.write_text('baseline-services-maintenance-99595facca1d\n')
        (self.tx / 'completed.json').write_text(json.dumps({
            'retained_original_id': 'old-bazarr', 'container_id': 'active-bazarr',
            'version_label': 'v1.6.2-ls371',
        }))
        (self.tx / 'fresh-backup.json').write_text('{}')
        self.command.side_effect = None
        self.command.return_value = b'[{"State":{"Running":false}}]'
        with patch.object(host, 'container', return_value={'Id': 'active-bazarr'}):
            state = host.bazarr_status()
        self.assertEqual('updated', state['status'])
        self.assertFalse(state['can_rollback'])
        self.assertFalse(state['can_apply'])
        self.assertEqual('deployment_context_changed', state['blocked_reason'])

    def test_blocked_rollback_cannot_start_a_job(self):
        jobs = host.Jobs.__new__(host.Jobs)
        jobs.path = self.root / 'job.json'
        with patch.object(host, 'bazarr_status', return_value={
            'maintenance_enabled': True, 'can_rollback': False,
        }), patch.object(host.threading, 'Thread') as thread:
            with self.assertRaisesRegex(RuntimeError, 'reviewed_operation_unavailable'):
                jobs.submit('bazarr.rollback', 'admin')
        thread.assert_not_called()
        self.assertFalse(jobs.path.exists())


if __name__ == "__main__":
    unittest.main()
