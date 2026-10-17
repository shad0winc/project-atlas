"""Atlas-schema metadata and disabled policy in strict native rollback rehearsal."""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HEAD = '66275e4ae9306e584b11cafad6aa982d1b083ddb'
PINS = {'scripts/diagnostics/sports-native-consumption-drill.py': 'ad22722a98616c5ade855a610d6c91c269e8aad6f590d77b99575f462a55f58f', 'scripts/lib/sports-strict-consumption.py': '3a5a3c8c20f0dca9d8d700795fb5373c6cfd91d5f099fcb043ff16dc18392730', 'scripts/lib/sports-postgres-prepare.py': '34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc', 'scripts/lib/sports-dispatcharr-recovery-drill.py': '042791e83a2c15a58f9da660876430dfe54926fc701bcf1b70d744335692b27a', 'scripts/lib/sports-native-consumption.py': 'e0c20b0ea2ec412b59caf78f691acbf5da8c081b0526bfd8d3cb876bf906802b', 'scripts/lib/sports-recovery-lifecycle.py': 'e5fa5c7baff858d064457c83d9e3f2102bc371337471865b10596ad1cf36a84c', 'scripts/lib/sports-recovery-consumption.py': 'df7cc1d8897783db8073de033758f3012918a626f782df26263382b738600abd', 'scripts/lib/sports-recovery-publication.py': 'b0266e90b83ca297070aa98c563ae3fc98f674b46aa14f41357cc682b61d38c8', 'scripts/diagnostics/sports-recovery-consumption-drill.py': 'abe7252feceab92ac730e1494952e4a0681a42e8390524dd5e6bc704efeb5a5c', 'scripts/diagnostics/sports-cold-copy-drill.py': '1d714b2d4be23d3234045836b1c31e1d92826fbcc03fa08411d184e7f7191ecb', 'scripts/diagnostics/sports-teamarr-recovery-drill.py': '68b4920da2fe6a2bca558de15879d941a65e591d3979ac9ee59e3c5ccd925e9e', 'scripts/diagnostics/sports-dispatcharr-recovery-drill.py': 'a4844aa7f64856fcdbef32645c1d9197c99fb5f8618382eb9b94072fc25283d7', 'scripts/lib/sports-metadata-consumption.py': '1dee5d98983676dbf512582510002caf648738060bb6bc20a2d19f413d39c387', 'scripts/lib/metadata-recovery.py': 'c8d98f872e7a84aacfb71edb8ee97961d26b816e415930f23ebc33792df79457', 'scripts/lib/sports-metadata-policy.py': '3680284e07edd90b39364569f6244df7ac01de2c9f5a4d050aa5ce77bc7f9a38', 'modules/sports/src/providers/metadata_store.py': '7fd660add05beba1d908c50a9542d65d39b1815c5428ef88207a4a4d37710632', 'modules/sports/src/providers/metadata_identity.py': '0fc6340a33a0a0e4852d2ef7e2a82f2ef1daf8b2356d1de2d2ef00666e98dfb2', 'modules/sports/src/providers/metadata_refresh.py': '48d2cc2e1e1522f3360dd9f5648172dbddd8efe16c65255896a96113ca822136', 'modules/sports/src/providers/metadata_broker.py': 'e04d683e85b7cff3fb166350cc428ecf96232eb5307b1f410430d7641464f9bc', 'modules/sports/src/providers/espn_metadata.py': '725de8493a94f99aba88ecdb0899da4390fbba9dc173d6ee10880c7a5c9a3596', 'modules/sports/src/providers/espn_directory.py': '26e0a119a5b132ff31d028857809193715b8c0a15606ccb712b67c79f06bafae'}


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def run():
    for relative, digest in PINS.items():
        path = ROOT/relative
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Atlas metadata consumption source mismatch')
    component = load('metadata_native_rehearsal', 'scripts/diagnostics/sports-native-consumption-drill.py')
    strict = load('metadata_strict_preparation', 'scripts/lib/sports-strict-consumption.py')
    metadata = load('metadata_rehearsal_support', 'scripts/lib/sports-metadata-consumption.py')
    component.run(expected_head=HEAD, prepare_baseline=strict.prepare_baseline, pg_baseline_marker='snapshot',
        metadata_hooks={name: getattr(metadata, name) for name in ('initialize', 'mutate', 'verify')})


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_METADATA_CONSUMPTION_DRILL=FAIL; no production restore requested.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
