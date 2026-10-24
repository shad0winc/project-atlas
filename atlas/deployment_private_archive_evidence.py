"""Read-only private receipt validation across native owner-archive phases.

This is one host-driver component, not an archival driver or admission permit.
The caller must verify this module's promoted source, the historical collector's
source/environment, remote CI, external admission and full runtime inspection.
The required owner_probe must call the source-verified native OwnerArchive
inspector with the same runtime, original owner, publication, plan pin and flock.
No owner-live collector, capture, journal write, marker completion or reopen is
performed here. Old attempts and the preservation plan are never rewritten.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

from atlas.deployment_publication_journal import encoded, identifier, read_file
from atlas.maintenance_control import MaintenanceControlError


def _require(value, reason):
    if not value:
        raise MaintenanceControlError(reason)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


class PrivateArchiveEvidence:
    """Validate existing fresh private evidence under inherited exclusion.

    ``collector`` is the exact source-verified PrivateHeldAcceptance instance.
    It may run in an isolated historical-source process, loading this separately
    pinned module by file path. No newer Atlas core dependencies are required.
    ``owner_probe(publication, preservation_sha256)`` must invoke the separately
    verified native owner inspector; a boolean or an incomplete proof refuses.
    The resulting evidence does not verify CI, external admission or full native
    rollout inspection and never grants archive/release/reopen permission.
    """

    maximum_age = 300
    phases = frozenset((
        'owner-live', 'intent-durable-owner-live',
        'moved-needs-parent-sync', 'archived',
    ))

    def __init__(self, collector, *, owner_probe):
        _require(callable(owner_probe), 'private_archive_owner_probe_required')
        self.collector = collector
        self.owner_probe = owner_probe

    @contextmanager
    def _exclusion(self):
        collector = self.collector
        _require(type(collector.inherited_fd) is int and collector.inherited_fd >= 3,
                 'private_archive_exclusion_unavailable')
        borrowed = probe = None
        try:
            collector._directories()
            borrowed = os.dup(collector.inherited_fd)
            info = os.fstat(borrowed)
            path = collector.lock.lstat()
            _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                     and info.st_uid == os.geteuid() and not info.st_mode & 0o022
                     and stat.S_ISREG(path.st_mode)
                     and collector.lock.resolve(strict=True) == collector.lock
                     and (info.st_dev, info.st_ino) == (path.st_dev, path.st_ino),
                     'private_archive_exclusion_unavailable')
            probe = os.open(collector.lock, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            checked = os.fstat(probe)
            _require((checked.st_dev, checked.st_ino) == (info.st_dev, info.st_ino),
                     'private_archive_exclusion_unavailable')
            try:
                fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise MaintenanceControlError('private_archive_exclusive_parent_not_proven')
            try:
                fcntl.flock(borrowed, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MaintenanceControlError('private_archive_exclusive_parent_not_proven') from None
            yield
        except OSError:
            raise MaintenanceControlError('private_archive_io_uncertain') from None
        finally:
            # Closing duplicates must never unlock the parent's open description.
            for fd in (probe, borrowed):
                if fd is not None:
                    os.close(fd)

    def _owner_phase(self, publication, preservation_sha256):
        proof = self.owner_probe(publication, preservation_sha256)
        _require(isinstance(proof, dict) and set(proof) == {
            'phase', 'maintenance_enabled', 'publication_marker_preserved',
            'ordinary_reopening_permitted'}, 'private_archive_owner_proof_invalid')
        _require(proof['phase'] in self.phases
                 and proof['maintenance_enabled'] is True
                 and proof['publication_marker_preserved'] is True
                 and proof['ordinary_reopening_permitted'] is False,
                 'private_archive_owner_proof_invalid')
        return dict(proof)

    def _plan(self, publication, pin):
        _require(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin),
                 'private_archive_preservation_pin_invalid')
        _, folder = self.collector._paths(publication)
        raw = read_file(folder / 'owner-preservation.json', limit=65536)
        _require(_digest(raw) == pin, 'private_archive_preservation_changed')
        plan = json.loads(raw)
        _require(plan.get('schema_version') == 1
                 and plan.get('scope') == 'owner-preservation-preparation-only'
                 and plan.get('publication_id') == publication
                 and plan.get('original_owner', {}).get('deployment_id') == self.collector.identifier
                 and plan.get('owner_release_permitted') is False
                 and plan.get('ordinary_reopening_permitted') is False,
                 'private_archive_preservation_invalid')
        return folder, plan, raw

    def _context(self, publication, source, folder, plan):
        collector = self.collector
        # Native owner_probe verifies owner location/inventory, maintenance,
        # marker, current, plan and archive-journal inventory in every phase.
        # Rebuild private context with native protected-evidence/record/source/
        # generation/runtime primitives; never call owner-live _snapshot/state.
        raw = read_file(folder / 'intent.json', limit=4 * 1024 * 1024)
        _require(_digest(raw) == plan['intent_sha256'], 'private_archive_intent_changed')
        intent = json.loads(raw)
        _require(intent.get('schema_version') == 1
                 and intent.get('publication_id') == publication
                 and intent.get('original_owner') == plan['original_owner'],
                 'private_archive_intent_invalid')
        _require(collector._candidate(intent['candidate_relative'],
                                     intent['candidate_manifest_sha256']) == intent['candidate_files'],
                 'private_archive_candidate_changed')
        _require(all(read_file(Path(name)) == pin
                     for name, pin in intent['protected_evidence'].items()),
                 'private_archive_protected_evidence_changed')
        pins, manifest = collector._expected(intent)
        record = collector.root / 'deployments/records' / publication
        collector._record(record, pins, manifest)
        collector._check_record_observation(publication, manifest)
        current = read_file(collector.root / 'deployments/current', limit=256)
        _require(current == (publication + '\n').encode()
                 and _digest(current) == plan['current_sha256'],
                 'private_archive_current_changed')
        context = {
            'source': collector._source(source), 'publication_id': publication,
            'original_owner': intent['original_owner'],
            'intent_sha256': _digest(raw),
            'record_manifest_sha256': _digest(manifest),
            'generation_sha256': collector._generation_inventory(intent, source),
            'runtime': collector._runtime(record), 'current_sha256': _digest(current),
        }
        _require(_digest(encoded(context)) == plan['private_context_sha256'],
                 'private_archive_preserved_context_changed')
        return context

    def _fresh(self, before, receipt):
        started = before.get('started_at')
        monotonic_started = before.get('monotonic_started')
        finished = receipt.get('finished_at')
        duration = receipt.get('elapsed_seconds')
        _require(all(_number(value) for value in (started, monotonic_started, finished, duration)),
                 'private_archive_receipt_time_invalid')
        wall = time.time()
        elapsed = time.monotonic() - monotonic_started
        maximum = min(self.maximum_age, self.collector.maximum_age)
        _require(_number(maximum) and 0 < maximum <= 300
                 and 0 <= wall - started <= maximum
                 and 0 <= elapsed <= maximum
                 and started <= finished <= wall
                 and 0 <= duration <= maximum and duration <= elapsed
                 and receipt.get('started_at') == started
                 and before.get('boot_sha256') == self.collector._boot(),
                 'private_archive_receipt_expired_or_rebooted')

    def _logs(self, path, receipt):
        stages = receipt.get('stages')
        _require(isinstance(stages, dict) and set(stages) == {'runtime', 'doctor', 'verify'},
                 'private_archive_stages_invalid')
        expected = {'before.json', 'receipt.json'} | {
            stage + suffix for stage in stages for suffix in ('.log', '.exit')}
        _require({item.name for item in path.iterdir()} == expected,
                 'private_archive_attempt_inventory_changed')
        pins = {}
        for stage, row in stages.items():
            _require(isinstance(row, dict) and type(row.get('exit_code')) is int
                     and row['exit_code'] == 0, 'private_archive_gate_failed')
            raw = read_file(path / (stage + '.log'), limit=16 * 1024 * 1024)
            exit_raw = read_file(path / (stage + '.exit'), limit=32)
            _require(exit_raw == b'0\n' and _digest(raw) == row.get('log_sha256'),
                     'private_archive_logs_changed')
            text = raw.decode(errors='replace')
            if stage == 'doctor':
                states = re.findall(r'^\s+(OK|WARN|FAIL|UNKNOWN)\s+.+?:', text, re.MULTILINE)
                _require(states and all(value == 'OK' for value in states)
                         and 'Overall Status: HEALTHY' in text,
                         'private_archive_doctor_not_healthy')
            elif stage == 'verify':
                _require('Overall Status: PASS' in text
                         and not re.search(r'^\s*FAIL(?:\s|$)', text, re.MULTILINE),
                         'private_archive_verify_not_passed')
            pins[stage + '.log'] = _digest(raw)
            pins[stage + '.exit'] = _digest(exit_raw)
        return pins

    def validate(self, publication, attempt, private_sha256, preservation_sha256):
        publication = identifier(publication)
        _require(isinstance(private_sha256, str) and re.fullmatch('[0-9a-f]{64}', private_sha256),
                 'private_archive_receipt_pin_invalid')
        with self._exclusion():
            phase = self._owner_phase(publication, preservation_sha256)
            folder, plan, plan_raw = self._plan(publication, preservation_sha256)
            path = self.collector._attempt(publication, attempt)
            raw = read_file(path / 'receipt.json', limit=4 * 1024 * 1024)
            _require(_digest(raw) == private_sha256, 'private_archive_receipt_changed')
            receipt = json.loads(raw)
            before_raw = read_file(path / 'before.json', limit=4 * 1024 * 1024)
            before = json.loads(before_raw)
            _require(receipt.get('schema_version') == before.get('schema_version') == 1
                     and receipt.get('scope') == 'fresh-private-held-acceptance'
                     and receipt.get('accepted_private') is True
                     and receipt.get('publication_id') == before.get('publication_id') == publication
                     and receipt.get('attempt') == attempt
                     and receipt.get('original_owner_retained') is True
                     and receipt.get('owner_release_permitted') is False
                     and receipt.get('public_acceptance_proven') is False
                     and receipt.get('ci_acceptance_proven') is False
                     and receipt.get('before_sha256') == _digest(before_raw),
                     'private_archive_receipt_invalid')
            self._fresh(before, receipt)
            source = Path(before['source_root'])
            context = self._context(publication, source, folder, plan)
            _require(context == before['context'] == receipt['context'],
                     'private_archive_context_changed')
            logs = self._logs(path, receipt)
            providers = self.collector._providers(source, Path(before['provider_path']))
            _require(self._context(publication, source, folder, plan) == context,
                     'private_archive_context_changed')
            _require(read_file(folder / 'owner-preservation.json', limit=65536) == plan_raw
                     and read_file(path / 'receipt.json', limit=4 * 1024 * 1024) == raw
                     and read_file(path / 'before.json', limit=4 * 1024 * 1024) == before_raw
                     and all(read_file(path / name) == pin for name, pin in logs.items()),
                     'private_archive_evidence_changed')
            _require(self._owner_phase(publication, preservation_sha256) == phase,
                     'private_archive_owner_phase_changed')
            self._fresh(before, receipt)
            return {
                'schema_version': 1, 'scope': 'fresh-private-archive-evidence-validation-only',
                'publication_id': publication, 'attempt': attempt,
                'private_receipt_sha256': private_sha256,
                'preservation_plan_sha256': preservation_sha256,
                'private_context_sha256': _digest(encoded(context)),
                'owner_phase': phase['phase'], 'accepted_private': True,
                'current_providers_verified': providers,
                'receipt_rewritten': False, 'owner_archive_performed': False,
                'archive_permission_granted': False, 'owner_release_permitted': False,
                'public_reopen_permitted': False, 'ci_acceptance_proven': False,
                'external_admission_proven': False, 'full_rollout_inspection_proven': False,
            }
