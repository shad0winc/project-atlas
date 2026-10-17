"""Publish and validate a complete private archive within the four-writer native fence."""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HEAD = 'da798030f5c23949f9a65b6ccd798a9df6ad80d1'
PINS = {'scripts/diagnostics/sports-native-consumption-drill.py': '18ee371e35885bc5a2f731c36f6d3096e922759cd4558d2f4544fe8539200e77', 'scripts/lib/sports-strict-consumption.py': '3a5a3c8c20f0dca9d8d700795fb5373c6cfd91d5f099fcb043ff16dc18392730', 'scripts/lib/sports-postgres-prepare.py': '34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc', 'scripts/lib/sports-dispatcharr-recovery-drill.py': '042791e83a2c15a58f9da660876430dfe54926fc701bcf1b70d744335692b27a', 'scripts/lib/sports-native-consumption.py': 'e0c20b0ea2ec412b59caf78f691acbf5da8c081b0526bfd8d3cb876bf906802b', 'scripts/lib/sports-recovery-lifecycle.py': 'e5fa5c7baff858d064457c83d9e3f2102bc371337471865b10596ad1cf36a84c', 'scripts/lib/sports-recovery-consumption.py': 'df7cc1d8897783db8073de033758f3012918a626f782df26263382b738600abd', 'scripts/lib/sports-recovery-publication.py': 'b0266e90b83ca297070aa98c563ae3fc98f674b46aa14f41357cc682b61d38c8', 'scripts/diagnostics/sports-recovery-consumption-drill.py': 'abe7252feceab92ac730e1494952e4a0681a42e8390524dd5e6bc704efeb5a5c', 'scripts/diagnostics/sports-cold-copy-drill.py': '1d714b2d4be23d3234045836b1c31e1d92826fbcc03fa08411d184e7f7191ecb', 'scripts/diagnostics/sports-teamarr-recovery-drill.py': '68b4920da2fe6a2bca558de15879d941a65e591d3979ac9ee59e3c5ccd925e9e', 'scripts/diagnostics/sports-dispatcharr-recovery-drill.py': 'a4844aa7f64856fcdbef32645c1d9197c99fb5f8618382eb9b94072fc25283d7', 'scripts/lib/sports-metadata-consumption.py': '1dee5d98983676dbf512582510002caf648738060bb6bc20a2d19f413d39c387', 'scripts/lib/metadata-recovery.py': 'c8d98f872e7a84aacfb71edb8ee97961d26b816e415930f23ebc33792df79457', 'scripts/lib/sports-metadata-policy.py': '3680284e07edd90b39364569f6244df7ac01de2c9f5a4d050aa5ce77bc7f9a38', 'modules/sports/src/providers/metadata_store.py': '7fd660add05beba1d908c50a9542d65d39b1815c5428ef88207a4a4d37710632', 'modules/sports/src/providers/metadata_identity.py': '0fc6340a33a0a0e4852d2ef7e2a82f2ef1daf8b2356d1de2d2ef00666e98dfb2', 'modules/sports/src/providers/metadata_refresh.py': '48d2cc2e1e1522f3360dd9f5648172dbddd8efe16c65255896a96113ca822136', 'modules/sports/src/providers/metadata_broker.py': 'e04d683e85b7cff3fb166350cc428ecf96232eb5307b1f410430d7641464f9bc', 'modules/sports/src/providers/espn_metadata.py': '725de8493a94f99aba88ecdb0899da4390fbba9dc173d6ee10880c7a5c9a3596', 'modules/sports/src/providers/espn_directory.py': '26e0a119a5b132ff31d028857809193715b8c0a15606ccb712b67c79f06bafae', 'scripts/lib/sports-maintenance-recovery.py': '680ca9edf981ca6e307eb7aa48a2bd6795e4d429f1d4066fbbc6b43425ad5cc6', 'scripts/commands/restore.sh': '198a06d90c1ccb03926e09447b05b34b0a500b41fb846a9c8f3928d1df1e1634', 'scripts/lib/execution-exclusion.sh': 'daa08a3775cc51eb84602cf57550e8668c8d1e8f5adfb562c29e727affb7ae0d', 'scripts/lib/sports-backup-fence.py': 'b9fc2de36353c17b8b62a4c283641c54cd4e15bab5423aba071e211320d6e8e7', 'scripts/lib/sports-backup-archive.py': '17c090d21228747a9861498d5a095e3c401627287e2de519966c43465e17e900', 'scripts/commands/backup.sh': '53c52fb9e25b30f6e22da6e9c629c93762f1efd77652275f41daf3b45d1b4fa7', 'scripts/lib/backup-recovery.sh': '45484d0882f46e55aa8233c919f787e044931238ca0af9f5155335c9bdcfcc98', 'scripts/lib/sports-backend-recovery.sh': 'fb46fd1d1721d23c2286ac7aac4054768d6e82b1755ab33a5ac6eaedebd4b013', 'scripts/lib/metadata-recovery.sh': 'a1ab38ddb98e0a2267cbfd3999e2b3b1713a26bc18336539b3d816785ba69f18', 'modules/sports/docker-compose.yml': 'a7d012f22a9044cfba18b6f1e0aec1cbd137dd7c131657cd855cf2f2f68c4f84'}


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def run():
    for relative, digest in PINS.items():
        path = ROOT/relative
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Maintenance rehearsal support source mismatch')
    component = load('interruption_native_rehearsal', 'scripts/diagnostics/sports-native-consumption-drill.py')
    strict = load('archive_preparation_support', 'scripts/lib/sports-backup-archive.py')
    metadata = load('interruption_metadata_support', 'scripts/lib/sports-metadata-consumption.py')
    maintenance = load('maintenance_recovery_support', 'scripts/lib/sports-maintenance-recovery.py')
    maintenance.failure_cases()
    backup_fence = load('backup_fence_support', 'scripts/lib/sports-backup-fence.py')
    component.run(expected_head=HEAD, prepare_baseline=strict.prepare_baseline, pg_baseline_marker='snapshot',
        metadata_hooks={name: getattr(metadata, name) for name in ('initialize', 'mutate', 'verify')},
        orchestrate_recovery=maintenance.recover, capture_boundary=backup_fence.capture)
    print('SYNTHETIC_BACKUP_ARCHIVE_DRILL=PASS', flush=True)
    print('STATE=isolated-complete-backup-archive-not-deployed', flush=True)


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_BACKUP_ARCHIVE_DRILL=FAIL; no production restore requested.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
