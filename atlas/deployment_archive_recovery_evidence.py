"""Fresh recovery evidence for an already journaled owner archive.

Host-only component with no CLI. It never archives, completes a marker, reopens,
or rewrites an original receipt/plan/intent. A source-verified host driver must
run the native runtime/doctor/verify gates and supply CI/external/full inspection
admission. The original immutable admission must already declare this recovery
method; this module cannot retrofit authorization into a sealed archive intent.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import sys
import time

from atlas.deployment_publication_journal import create_once, encoded, read_file, safe_directory, sync_directory
from atlas.maintenance_control import MaintenanceControlError


def require(value, reason):
    if not value:raise MaintenanceControlError(reason)


def digest(raw):return hashlib.sha256(raw).hexdigest()


class ArchiveRecoveryEvidence:
    """Use a verified PrivateArchiveEvidence policy and its owner probe/flock.

    Only the three journaled archive phases are eligible. The original native
    private receipts stay expired; a new, distinctly scoped receipt records fresh
    gates against the exact preserved private context. This is evidence only.
    """
    maximum_age = 300

    def __init__(self, policy):
        self.policy = policy
        self.collector = policy.collector

    def _implementation(self):
        policy_path=Path(sys.modules[type(self.policy).__module__].__file__)
        return {'recovery_sha256':read_file(Path(__file__)), 'policy_sha256':read_file(policy_path)}

    def declaration(self, publication, preservation_pin):
        """Descriptor to seal before archival; never an authorization by itself."""
        return {'schema_version':1,'scope':'fresh-held-archive-recovery-evidence','publication_id':publication,'preservation_plan_sha256':preservation_pin,'implementation':self._implementation(),'maximum_age_seconds':300,'selection':'explicit-pinned-attempt'}

    def _context(self, publication, preservation_pin, intent_pin, source):
        require(isinstance(intent_pin,str) and re.fullmatch('[0-9a-f]{64}',intent_pin), 'archive_recovery_intent_pin_invalid')
        phase=self.policy._owner_phase(publication,preservation_pin)
        require(phase['phase'] in ('intent-durable-owner-live','moved-needs-parent-sync','archived'), 'archive_recovery_requires_journaled_archive')
        folder,plan,_=self.policy._plan(publication,preservation_pin)
        intent_raw=read_file(folder/'owner-archive-intent.json',limit=131072)
        require(digest(intent_raw)==intent_pin, 'archive_recovery_intent_changed')
        intent=json.loads(intent_raw)
        require(intent.get('admission',{}).get('recovery_evidence')==self.declaration(publication,preservation_pin),'archive_recovery_not_predeclared')
        context=self.policy._context(publication,source,folder,plan)
        return phase,context,folder

    def _fresh(self, before):
        started=before.get('started_at');monotonic=before.get('monotonic_started')
        require(type(self.maximum_age) in (int,float) and math.isfinite(self.maximum_age) and 0<self.maximum_age<=300,'archive_recovery_freshness_policy_invalid')
        require(all(type(v) in (int,float) and math.isfinite(v) for v in (started,monotonic)), 'archive_recovery_time_invalid')
        require(0<=time.time()-started<=self.maximum_age and 0<=time.monotonic()-monotonic<=self.maximum_age and before.get('boot_sha256')==self.collector._boot(), 'archive_recovery_expired_or_rebooted')

    def _before(self, publication, attempt, preservation_pin, intent_pin):
        path=self.collector._attempt(publication,attempt)
        raw=read_file(path/'before.json',limit=4*1024*1024);before=json.loads(raw)
        require(before.get('schema_version')==1 and before.get('scope')=='held-archive-recovery-attempt' and before.get('publication_id')==publication and before.get('attempt')==attempt and before.get('preservation_plan_sha256')==preservation_pin and before.get('archive_intent_sha256')==intent_pin and before.get('implementation')==self._implementation(), 'archive_recovery_attempt_invalid')
        self._fresh(before)
        phase,context,folder=self._context(publication,preservation_pin,intent_pin,Path(before['source_root']))
        require(phase==before['owner_phase'] and context==before['context'], 'archive_recovery_context_changed')
        return path,raw,before,phase,context,folder

    def _gates(self, path, *, completed):
        stages=('runtime','doctor','verify')
        expected={'before.json'}|{stage+suffix for stage in stages for suffix in ('.log','.exit')}
        if completed:expected.add('receipt.json')
        require({p.name for p in path.iterdir()}==expected,'archive_recovery_attempt_inventory_changed')
        rows={}
        for stage in stages:
            raw=read_file(path/(stage+'.log'),limit=16*1024*1024)
            require(read_file(path/(stage+'.exit'),limit=32)==b'0\n','archive_recovery_gate_failed')
            text=raw.decode(errors='replace')
            if stage=='doctor':
                states=re.findall(r'^\s+(OK|WARN|FAIL|UNKNOWN)\s+.+?:',text,re.MULTILINE)
                require(states and all(v=='OK' for v in states) and 'Overall Status: HEALTHY' in text,'archive_recovery_doctor_not_healthy')
            elif stage=='verify':
                require('Overall Status: PASS' in text and not re.search(r'^\s*FAIL(?:\s|$)',text,re.MULTILINE),'archive_recovery_verify_not_passed')
            rows[stage]={'exit_code':0,'log_sha256':digest(raw)}
        return rows

    def start(self, publication, preservation_pin, intent_pin, source, provider_path):
        with self.policy._exclusion():
            phase,context,folder=self._context(publication,preservation_pin,intent_pin,source)
            providers=self.collector._providers(source,provider_path)
            parent=folder/'private-attempts';safe_directory(parent)
            attempt=secrets.token_hex(16);path=parent/attempt;path.mkdir(mode=0o700);sync_directory(parent)
            before={'schema_version':1,'scope':'held-archive-recovery-attempt','publication_id':publication,'attempt':attempt,'source_root':str(source),'provider_path':str(provider_path),'preservation_plan_sha256':preservation_pin,'archive_intent_sha256':intent_pin,'context':context,'owner_phase':phase,'implementation':self._implementation(),'providers_before':providers,'started_at':time.time(),'monotonic_started':time.monotonic(),'boot_sha256':self.collector._boot()}
            create_once(path/'before.json',encoded(before))
            return path

    def finish(self, publication, attempt, preservation_pin, intent_pin):
        with self.policy._exclusion():
            path,raw,before,phase,context,_=self._before(publication,attempt,preservation_pin,intent_pin)
            rows=self._gates(path,completed=False)
            providers=self.collector._providers(Path(before['source_root']),Path(before['provider_path']))
            self._before(publication,attempt,preservation_pin,intent_pin)
            require(self._gates(path,completed=False)==rows,'archive_recovery_logs_changed')
            value={'schema_version':1,'scope':'fresh-held-archive-recovery-evidence','accepted_recovery':True,'publication_id':publication,'attempt':attempt,'preservation_plan_sha256':preservation_pin,'archive_intent_sha256':intent_pin,'before_sha256':digest(raw),'context':context,'owner_phase':phase,'implementation':before['implementation'],'stages':rows,'providers_before':before['providers_before'],'providers_after':providers,'started_at':before['started_at'],'finished_at':time.time(),'elapsed_seconds':time.monotonic()-before['monotonic_started'],'owner_identity_preserved':True,'original_receipts_rewritten':False,'archive_permission_granted':False,'owner_release_permitted':False,'public_reopen_permitted':False,'ci_acceptance_proven':False,'external_admission_proven':False}
            # Logs and exit records must be durable before publishing acceptance.
            import os
            for stage in rows:
                for suffix in ('.log','.exit'):
                    fd=os.open(path/(stage+suffix),os.O_RDONLY|os.O_NOFOLLOW)
                    try:os.fsync(fd)
                    finally:os.close(fd)
            self._fresh(before)
            self._before(publication,attempt,preservation_pin,intent_pin)
            require(self._gates(path,completed=False)==rows,'archive_recovery_logs_changed')
            create_once(path/'receipt.json',encoded(value))
            return path/'receipt.json'

    def validate(self, publication, attempt, preservation_pin, intent_pin, receipt_pin):
        with self.policy._exclusion():
            path,raw,before,phase,context,_=self._before(publication,attempt,preservation_pin,intent_pin)
            receipt_raw=read_file(path/'receipt.json',limit=4*1024*1024)
            require(digest(receipt_raw)==receipt_pin,'archive_recovery_receipt_changed')
            value=json.loads(receipt_raw)
            require(value.get('schema_version')==1 and value.get('scope')=='fresh-held-archive-recovery-evidence' and value.get('accepted_recovery') is True and value.get('publication_id')==publication and value.get('attempt')==attempt and value.get('preservation_plan_sha256')==preservation_pin and value.get('archive_intent_sha256')==intent_pin and value.get('before_sha256')==digest(raw) and value.get('context')==context and value.get('owner_phase')==phase and value.get('implementation')==before['implementation'] and value.get('started_at')==before['started_at'], 'archive_recovery_receipt_invalid')
            for key in ('original_receipts_rewritten','archive_permission_granted','owner_release_permitted','public_reopen_permitted','ci_acceptance_proven','external_admission_proven'):
                require(value.get(key) is False,'archive_recovery_permission_invalid')
            require(value.get('owner_identity_preserved') is True,'archive_recovery_owner_proof_invalid')
            finished=value.get('finished_at');elapsed=value.get('elapsed_seconds')
            require(all(type(v) in (int,float) and math.isfinite(v) for v in (finished,elapsed)) and before['started_at']<=finished<=time.time() and 0<=elapsed<=self.maximum_age and elapsed<=time.monotonic()-before['monotonic_started'],'archive_recovery_receipt_time_invalid')
            require(self._gates(path,completed=True)==value.get('stages'),'archive_recovery_logs_changed')
            self.collector._providers(Path(before['source_root']),Path(before['provider_path']))
            self._before(publication,attempt,preservation_pin,intent_pin)
            require(read_file(path/'receipt.json',limit=4*1024*1024)==receipt_raw and self._gates(path,completed=True)==value['stages'],'archive_recovery_receipt_changed')
            # A prior finish may have left valid visible bytes after an fsync
            # failure. Explicit validation must establish durability itself.
            import os
            for item in path.iterdir():
                fd=os.open(item,os.O_RDONLY|os.O_NOFOLLOW)
                try:os.fsync(fd)
                finally:os.close(fd)
            sync_directory(path);sync_directory(path.parent)
            self._before(publication,attempt,preservation_pin,intent_pin)
            require(read_file(path/'receipt.json',limit=4*1024*1024)==receipt_raw and self._gates(path,completed=True)==value['stages'],'archive_recovery_receipt_changed')
            self._fresh(before)
            return value
