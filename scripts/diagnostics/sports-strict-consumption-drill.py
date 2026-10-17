"""Strict dump restore, native consumer commits, quarantine and restored restarts."""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HEAD = '1c2fc60d7f12f10a34834b0b1088ddf70c2d9242'
PINS = {'scripts/diagnostics/sports-native-consumption-drill.py': 'f903fd2161c7ac40314b8f5f159fda6326fb5f680603a99619e6bbc5824a9f82', 'scripts/lib/sports-strict-consumption.py': '3a5a3c8c20f0dca9d8d700795fb5373c6cfd91d5f099fcb043ff16dc18392730', 'scripts/lib/sports-postgres-prepare.py': '34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc', 'scripts/lib/sports-dispatcharr-recovery-drill.py': '042791e83a2c15a58f9da660876430dfe54926fc701bcf1b70d744335692b27a', 'scripts/lib/sports-native-consumption.py': 'e0c20b0ea2ec412b59caf78f691acbf5da8c081b0526bfd8d3cb876bf906802b', 'scripts/lib/sports-recovery-lifecycle.py': 'e5fa5c7baff858d064457c83d9e3f2102bc371337471865b10596ad1cf36a84c', 'scripts/lib/sports-recovery-consumption.py': 'df7cc1d8897783db8073de033758f3012918a626f782df26263382b738600abd', 'scripts/lib/sports-recovery-publication.py': 'b0266e90b83ca297070aa98c563ae3fc98f674b46aa14f41357cc682b61d38c8', 'scripts/diagnostics/sports-recovery-consumption-drill.py': 'abe7252feceab92ac730e1494952e4a0681a42e8390524dd5e6bc704efeb5a5c', 'scripts/diagnostics/sports-cold-copy-drill.py': '1d714b2d4be23d3234045836b1c31e1d92826fbcc03fa08411d184e7f7191ecb', 'scripts/diagnostics/sports-teamarr-recovery-drill.py': '68b4920da2fe6a2bca558de15879d941a65e591d3979ac9ee59e3c5ccd925e9e', 'scripts/diagnostics/sports-dispatcharr-recovery-drill.py': 'a4844aa7f64856fcdbef32645c1d9197c99fb5f8618382eb9b94072fc25283d7'}


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def run():
    for relative, digest in PINS.items():
        path = ROOT/relative
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Strict consumption support source mismatch')
    component = load('strict_native_rehearsal', 'scripts/diagnostics/sports-native-consumption-drill.py')
    preparation = load('strict_native_preparation', 'scripts/lib/sports-strict-consumption.py')
    component.run(expected_head=HEAD, prepare_baseline=preparation.prepare_baseline, pg_baseline_marker='snapshot')


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_STRICT_CONSUMPTION_DRILL=FAIL; no production restore requested.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
