"""Rollback committed native fixture writes, then restart the preserved baseline."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
HEAD = '8382217abff006192e41b7bed784f033fab06f65'
DEPLOYMENT = 'update-20261015T211211Z-632971'
PINS = {'scripts/lib/sports-native-consumption.py': 'e0c20b0ea2ec412b59caf78f691acbf5da8c081b0526bfd8d3cb876bf906802b', 'scripts/lib/sports-recovery-lifecycle.py': 'e5fa5c7baff858d064457c83d9e3f2102bc371337471865b10596ad1cf36a84c', 'scripts/lib/sports-recovery-consumption.py': 'df7cc1d8897783db8073de033758f3012918a626f782df26263382b738600abd', 'scripts/lib/sports-recovery-publication.py': 'b0266e90b83ca297070aa98c563ae3fc98f674b46aa14f41357cc682b61d38c8', 'scripts/diagnostics/sports-recovery-consumption-drill.py': 'abe7252feceab92ac730e1494952e4a0681a42e8390524dd5e6bc704efeb5a5c', 'scripts/diagnostics/sports-cold-copy-drill.py': '1d714b2d4be23d3234045836b1c31e1d92826fbcc03fa08411d184e7f7191ecb', 'scripts/diagnostics/sports-teamarr-recovery-drill.py': '68b4920da2fe6a2bca558de15879d941a65e591d3979ac9ee59e3c5ccd925e9e', 'scripts/diagnostics/sports-dispatcharr-recovery-drill.py': 'a4844aa7f64856fcdbef32645c1d9197c99fb5f8618382eb9b94072fc25283d7'}


def require(value):
    if not value: raise RuntimeError('Synthetic native consumption drill held')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def pg_code(change=False, consumed=False, baseline='after-dump'):
    require(baseline in {'after-dump', 'snapshot'})
    marker = 'native-consumer-committed' if consumed else baseline
    code = r'''
import subprocess
base=['/usr/lib/postgresql/17/bin/psql','-XAt','-h','/var/run/postgresql',
    '-U','dispatch','-d','atlas_cold_drill','-v','ON_ERROR_STOP=1']
def sql(query):
    result=subprocess.run(base+['-c',query],capture_output=True,timeout=10)
    assert result.returncode==0
    return result.stdout.decode().strip()
''' + (r'''
assert sql("SELECT marker FROM atlas_cold_copy_probe WHERE id=1")=='after-dump'
sql("BEGIN; UPDATE atlas_cold_copy_probe SET marker='native-consumer-committed' WHERE id=1; CREATE TABLE atlas_after_native_cutover(id integer); INSERT INTO atlas_after_native_cutover VALUES(1); COMMIT")
''' if change else '') + "\nassert sql(\"SELECT marker FROM atlas_cold_copy_probe WHERE id=1\")=="+repr(marker)+"\nassert sql(\"SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename='atlas_after_native_cutover'\")=="+repr('1' if consumed else '0')+"\nprint('native-pg-marker-valid')\n"

    return code.replace("=='after-dump'", "=="+repr(baseline))


def team_code(change=False, consumed=False):
    marker = 'native-consumer-committed' if consumed else 'after-dump'
    return "import sqlite3\nc=sqlite3.connect('/app/data/teamarr.db',timeout=2)\ntry:\n" + (
        " c.execute(\"UPDATE atlas_teamarr_probe SET marker='native-consumer-committed'\");c.commit()\n" if change else '') + \
        " assert c.execute('SELECT marker FROM atlas_teamarr_probe ORDER BY id').fetchall()==[("+repr(marker)+",)]\nfinally:c.close()\nprint('native-team-marker-valid')\n"


def run(*, expected_head=None, prepare_baseline=None, pg_baseline_marker='after-dump', metadata_hooks=None, recover_journal=None, orchestrate_recovery=None, capture_boundary=None):
    require(capture_boundary is None or (callable(capture_boundary) and orchestrate_recovery is not None))
    require(orchestrate_recovery is None or (callable(orchestrate_recovery) and metadata_hooks is not None and recover_journal is None))
    require(recover_journal is None or (callable(recover_journal) and metadata_hooks is not None))
    require(metadata_hooks is None or (prepare_baseline is not None and isinstance(metadata_hooks, dict)
        and set(metadata_hooks) == {'initialize', 'mutate', 'verify'}
        and all(callable(value) for value in metadata_hooks.values())))
    require((expected_head is None and prepare_baseline is None and pg_baseline_marker == 'after-dump')
        or (isinstance(expected_head, str) and len(expected_head) == 40
            and all(c in '0123456789abcdef' for c in expected_head)
            and callable(prepare_baseline) and pg_baseline_marker == 'snapshot'))
    checkpoint_head = HEAD if expected_head is None else expected_head
    for name, digest in PINS.items():
        path = ROOT/name
        require(path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == digest)
    require(os.geteuid() == 0 and os.getegid() == 0)
    native = load('native_drill_support', 'scripts/lib/sports-native-consumption.py')
    fixture = load('native_drill_journal', 'scripts/diagnostics/sports-recovery-consumption-drill.py')
    cold = load('native_drill_cold', 'scripts/diagnostics/sports-cold-copy-drill.py')
    team = load('native_drill_team', 'scripts/diagnostics/sports-teamarr-recovery-drill.py')
    dispatch = load('native_drill_dispatch', 'scripts/diagnostics/sports-dispatcharr-recovery-drill.py')
    fence = native.fence; consumer = native.consumer; pub = native.pub
    cold.LABEL = fence.LABEL; team_base = team.utilities(ROOT); team_base.LABEL = fence.LABEL
    bases = {'dispatcharr': cold, 'teamarr': team_base}
    def git(path, *args): return cold.invoke('git', '-C', str(path), *args).stdout.decode().strip()
    require(git(ROOT, 'rev-parse', 'HEAD') == checkpoint_head
        and git('/opt/project-atlas', 'rev-parse', 'HEAD') == checkpoint_head
        and git('/opt/project-atlas', 'branch', '--show-current') == 'main'
        and not git('/opt/project-atlas', 'status', '--porcelain=v1'))
    pointer = Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink()); before_pointer = pointer.read_bytes()
    require(before_pointer.decode().strip() == DEPLOYMENT)
    def observe():
        rows = []
        for name in ('atlas-dispatcharr', 'atlas-teamarr', 'atlas-sports-writer'):
            item = cold.inspect(name); require(item['State']['Running'])
            rows.append((name, item['Image'], item['State']['Pid'], item['State']['StartedAt'],
                sorted(item['Mounts'], key=lambda row: json.dumps(row, sort_keys=True))))
        return rows
    before = observe(); resources = []; phase = 'prepare'
    with tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp') as first, \
         tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp') as current, \
         tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp') as final:
        # Native workspace accepts UUID-only names, not arbitrary local paths.
        work = Path('/tmp')/('project-atlas-native-consumption.'+uuid.uuid4().hex)
        require(not work.exists()); work.mkdir(mode=0o700)
        first, current, final = Path(first), Path(current), Path(final)
        def journal(root): fixture.fixture(root); consumer.arm(root)
        def volumes():
            identifier = uuid.uuid4().hex
            for role, base in bases.items():
                app, data = fence.names(identifier, role); resources.append((base, app, data, identifier))
                base.docker('volume', 'create', '--driver', 'local', '--label', fence.LABEL+'='+identifier, data)
            return identifier
        def apps(identifier, seed=False):
            for role, base in bases.items():
                app, data = fence.names(identifier, role)
                if role == 'dispatcharr':
                    args = cold.app_arguments(app, data, identifier); args.insert(-1, '--user=0:0')
                else: args = team.app_arguments(base, app, data, identifier)
                base.invoke(*args); base.docker('start', app)
                if role == 'dispatcharr':
                    dispatch.wait_ready(base, app, data, identifier)
                    if seed: require(base.docker('exec', '--user', '1000:1000', app, 'python3', '-B', '-c', cold.SNAPSHOT, timeout=60) == 'snapshot-captured')
                else:
                    team.wait_ready(base, app, identifier, data)
                    if seed: require(base.docker('exec', app, 'python3', '-B', '-c', team.SEED, timeout=30) == 'snapshot-captured')
        def markers(identifier, consumed=False, change=False, baseline=pg_baseline_marker):
            app, _ = fence.names(identifier, 'dispatcharr')
            require(cold.docker('exec', '--user', '1000:1000', app, 'python3', '-B', '-c', pg_code(change, consumed, baseline), timeout=30) == 'native-pg-marker-valid')
            app, _ = fence.names(identifier, 'teamarr')
            require(team_base.docker('exec', app, 'python3', '-B', '-c', team_code(change, consumed), timeout=30) == 'native-team-marker-valid')
        try:
            phase = 'baseline-native-start'; old_id = volumes(); apps(old_id, seed=capture_boundary is None)
            if capture_boundary is None: markers(old_id, baseline='after-dump')
            captured_baseline = []
            def capture_baseline():
                nonlocal phase
                require(not captured_baseline)
                captured_baseline.append(False)
                if capture_boundary is not None:
                    # Native dump/SQLite seed capture must occur after the four-writer stop proof.
                    app, _ = fence.names(old_id, 'dispatcharr')
                    require(cold.docker('exec', '--user', '1000:1000', app, 'python3', '-B', '-c', cold.SNAPSHOT, timeout=60) == 'snapshot-captured')
                    app, _ = fence.names(old_id, 'teamarr')
                    require(team_base.docker('exec', app, 'python3', '-B', '-c', team.SEED, timeout=30) == 'snapshot-captured')
                    markers(old_id, baseline='after-dump')
                journal(first); fence.arm(first, old_id); fence.detach(first)
                phase = 'baseline-native-capture'; native.capture(first, work/'baseline', 'after-dump')
                print('NATIVE_STOPPED_BASELINE_CAPTURE=PASS', flush=True)
                if prepare_baseline is not None:
                    phase = 'strict-dump-preparation'
                    prepare_baseline(native, first, work/'baseline', cold, dispatch)
                    print('STRICT_DUMP_BASELINE_PREPARATION=PASS', flush=True)
                captured_baseline[0] = True
            if capture_boundary is None: capture_baseline()
            else: capture_boundary(native, work/'baseline', capture_baseline)
            require(captured_baseline == [True])
            fixture.fixture(current); native.install_baseline(current, work/'baseline')
            if metadata_hooks is not None: metadata_hooks['initialize'](native, current)
            consumer.arm(current)
            original = pub.read_json(current/'transaction/PLAN.json')['surfaces']
            phase = 'consumer-native-start'; changed_id = volumes(); native.materialize(work/'baseline', changed_id); apps(changed_id)
            fence.arm(current, changed_id)
            markers(changed_id, consumed=True, change=True)
            if metadata_hooks is not None: metadata_hooks['mutate'](native, current)
            print('NATIVE_DATABASE_COMMITS=PASS', flush=True)
            phase = 'detach-and-capture-writes'; fence.detach(current)
            native.capture(current, work/'captured', 'native-consumer-committed')
            old_jwt = pub.digest(work/'baseline/dispatcharr-jwt')
            require(pub.digest(work/'captured/dispatcharr-jwt') == old_jwt)
            phase = 'import-and-recover'; native.import_writes(current, work/'captured')
            completed_restored = []
            def complete_restored():
                nonlocal phase
                require(not completed_restored)
                completed_restored.append(False)
                fixture.verify(current, original)
                if metadata_hooks is not None: metadata_hooks['verify'](native, current)
                require(pub.digest(current/'current/dispatcharr-jwt') == old_jwt)
                print('NATIVE_WRITES_QUARANTINED_AND_BASELINE_RESTORED=PASS', flush=True)
                phase = 'restored-native-start'; restored_id = volumes(); native.materialize(current/'current', restored_id)
                apps(restored_id); markers(restored_id)
                # Prove persistence across a further normal app restart. The final
                # lifecycle ledger is armed after this new start epoch is observed.
                for role, base in bases.items():
                    app, data = fence.names(restored_id, role)
                    if role == 'dispatcharr': dispatch.stop(base, app, data, restored_id)
                    else: team.stop(base, app, restored_id, data)
                for role, base in bases.items():
                    app, data = fence.names(restored_id, role); base.docker('start', app)
                    if role == 'dispatcharr': dispatch.wait_ready(base, app, data, restored_id)
                    else: team.wait_ready(base, app, restored_id, data)
                markers(restored_id)
                if metadata_hooks is not None: metadata_hooks['verify'](native, current)
                journal(final); fence.arm(final, restored_id); fence.detach(final)
                print('NATIVE_RESTORED_APPLICATION_AND_PERSISTENCE_RESTART=PASS', flush=True)
                completed_restored[0] = True
            if orchestrate_recovery is not None:
                orchestrate_recovery(native, current, complete_restored)
            else:
                # WAL snapshot import is complete before any recovery operation.
                if recover_journal is None: native.recover(current); native.recover(current)
                else: recover_journal(native, current)
                complete_restored()
            require(completed_restored == [True])
            copied_wal = pub.read_json(work/'captured/CAPTURE.json')['copied_wal']
        except Exception:
            print('NATIVE_CONSUMPTION_DRILL=FAIL phase='+phase, file=sys.stderr); raise
        finally:
            import shutil
            failures = 0
            for base, app, data, identifier in reversed(resources):
                try: base.cleanup([app], data, identifier)
                except Exception: failures += 1
            try: shutil.rmtree(work)
            finally:
                require(pointer.read_bytes() == before_pointer and observe() == before
                    and git('/opt/project-atlas', 'rev-parse', 'HEAD') == checkpoint_head
                    and not git('/opt/project-atlas', 'status', '--porcelain=v1'))
            require(failures == 0)
    print(json.dumps({'version': 1, 'scope': ('synthetic-four-writer-native-backup-fence' if capture_boundary is not None else 'synthetic-maintenance-native-recovery' if orchestrate_recovery is not None else 'synthetic-combined-consumption-interruptions' if recover_journal is not None else 'synthetic-atlas-metadata-consumption' if metadata_hooks is not None else 'synthetic-strict-dump-consumption' if prepare_baseline is not None else 'synthetic-native-cold-checkpoint-consumption'),
        'native_database_commits': True, 'detached_capture_import': True, 'teamarr_copied_wal': copied_wal,
        'modified_native_state_quarantined': True, 'baseline_native_restart': True,
        'restored_persistence_restart': True, 'jwt_preserved': True,
        'four_writer_capture_fence': capture_boundary is not None, 'maintenance_abort_orchestration': orchestrate_recovery is not None, 'combined_recovery_interruptions': recover_journal is not None, 'atlas_metadata_and_policy': metadata_hooks is not None, 'direct_native_writes_to_journal': False, 'strict_dump_prepare_in_this_drill': prepare_baseline is not None,
        'production_state_access': False, 'live_restore_enabled': False}, sort_keys=True))
    print('SYNTHETIC_BACKUP_FENCE_DRILL=PASS' if capture_boundary is not None else 'SYNTHETIC_MAINTENANCE_RECOVERY_DRILL=PASS' if orchestrate_recovery is not None else 'SYNTHETIC_CONSUMPTION_INTERRUPTION_DRILL=PASS' if recover_journal is not None else 'SYNTHETIC_METADATA_CONSUMPTION_DRILL=PASS' if metadata_hooks is not None else 'SYNTHETIC_STRICT_CONSUMPTION_DRILL=PASS' if prepare_baseline is not None else 'SYNTHETIC_NATIVE_CONSUMPTION_DRILL=PASS')
    print('STATE=isolated-four-writer-native-backup-fence-not-deployed' if capture_boundary is not None else 'STATE=isolated-maintenance-native-recovery-not-deployed' if orchestrate_recovery is not None else 'STATE=isolated-combined-consumption-interruptions-not-deployed' if recover_journal is not None else 'STATE=isolated-Atlas-metadata-consumption-not-deployed' if metadata_hooks is not None else 'STATE=isolated-strict-dump-consumption-not-deployed' if prepare_baseline is not None else 'STATE=isolated-native-cold-checkpoint-recovery-not-deployed')


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_NATIVE_CONSUMPTION_DRILL=FAIL; no production restore requested.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
