"""Host fallback using the same audited authority as the web control service."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from atlas.maintenance_control import MaintenanceAuthority, MaintenanceControlError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('action', choices=('status', 'enable', 'disable', 'repair-hold', 'transaction-enable', 'transaction-check-held'))
    parser.add_argument('--transaction-id')
    parser.add_argument('--exclusion-fd', type=int)
    args = parser.parse_args(argv)
    if args.action not in ('transaction-enable', 'transaction-check-held') and (args.transaction_id is not None or args.exclusion_fd is not None):
        parser.error('Transaction context is only accepted for transaction-enable.')
    authority = MaintenanceAuthority(args.runtime_root)
    try:
        if args.action in ('transaction-enable', 'transaction-check-held'):
            from atlas.maintenance_transaction import TransactionMaintenanceAuthority
            authority = TransactionMaintenanceAuthority(args.runtime_root, args.transaction_id, args.exclusion_fd)
            if args.action == 'transaction-enable':
                state = authority.change(True, actor=f'uid:{os.geteuid()}', source='cli')
            else:
                state = authority.verify_hold(actor=f'uid:{os.geteuid()}')
        elif args.action == 'status':
            state = authority.status()
        elif args.action == 'repair-hold':
            state = authority.recover_hold(actor=f'uid:{os.geteuid()}')
        else:
            state = authority.change(args.action == 'enable', actor=f'uid:{os.geteuid()}', source='cli')
        held = any(state.values())
        print('Atlas maintenance mode: ' + ('enabled' if held else 'disabled'))
        if state['state_uncertain']:
            raise MaintenanceControlError('state_unavailable')
        return 0
    except (MaintenanceControlError, OSError):
        # Filesystem exception details may contain private paths. The caller must
        # never reinterpret refusal as permission to use the legacy flag writer.
        print('ERROR: maintenance control refused; preserve the hold and inspect host evidence.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
