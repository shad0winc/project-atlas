"""Local Unix-socket transport for the narrow maintenance authority.

The application must authenticate global_admin and CSRF before calling this
interface. The socket additionally checks Linux peer UID. It accepts no paths,
credentials, deployment IDs, lock release, or recovery/repair commands.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import socketserver
import stat
import struct

from atlas.maintenance_control import MaintenanceAuthority, MaintenanceControlError

MAX_MESSAGE = 2048
STATE_KEYS = {'enabled', 'transition_pending', 'recovery_held', 'state_uncertain'}


class MaintenanceServer(socketserver.UnixStreamServer):
    allow_reuse_address = False

    def __init__(self, socket_path: Path, authority: MaintenanceAuthority, *, allowed_uid: int, socket_gid: int):
        self.path = Path(socket_path)
        self.authority = authority
        if type(allowed_uid) is not int or allowed_uid < 0 or type(socket_gid) is not int or socket_gid < 0:
            raise MaintenanceControlError('invalid_server_configuration')
        self.allowed_uids = {0, allowed_uid}
        parent = self.path.parent
        if (not self.path.is_absolute() or parent.resolve(strict=True) != parent
            or parent.lstat().st_uid != os.geteuid() or parent.lstat().st_mode & 0o022
            or self.path.exists() or self.path.is_symlink()):
            raise MaintenanceControlError('socket_unavailable')
        super().__init__(str(self.path), MaintenanceHandler, bind_and_activate=False)
        try:
            self.server_bind()
            self.socket_inode = self.path.lstat().st_ino
            os.chown(self.path, os.geteuid(), socket_gid)
            os.chmod(self.path, 0o660)
            self.server_activate()
        except BaseException:
            self.server_close()
            raise

    def server_close(self):
        super().server_close()
        try:
            info = self.path.lstat()
            if stat.S_ISSOCK(info.st_mode) and info.st_ino == getattr(self, 'socket_inode', None):
                self.path.unlink()
        except FileNotFoundError:
            pass

    def handle_error(self, request, client_address):
        # Never write raw client messages, paths, exceptions or credentials.
        return

    def dispatch(self, request: object, *, peer_uid: int) -> dict:
        if peer_uid not in self.allowed_uids:
            raise MaintenanceControlError('peer_not_permitted')
        if not isinstance(request, dict):
            raise MaintenanceControlError('invalid_request')
        operation = request.get('operation')
        if operation == 'status' and set(request) == {'operation'}:
            return self.authority.status()
        if operation not in ('enable', 'disable') or set(request) != {'operation', 'actor'}:
            raise MaintenanceControlError('invalid_request')
        return self.authority.change(operation == 'enable', actor=request['actor'], source='web')


class MaintenanceHandler(socketserver.StreamRequestHandler):
    timeout = 3

    def handle(self):
        try:
            _, uid, _ = struct.unpack('3i', self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid not in self.server.allowed_uids:
                raise MaintenanceControlError('peer_not_permitted')
            raw = self.rfile.readline(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE or not raw.endswith(b'\n'):
                raise MaintenanceControlError('invalid_request')
            try:
                request = json.loads(raw)
            except (ValueError, UnicodeError):
                raise MaintenanceControlError('invalid_request') from None
            response = {'ok': True, 'state': self.server.dispatch(request, peer_uid=uid)}
        except MaintenanceControlError as exc:
            response = {'ok': False, 'error': str(exc)}
        except Exception:
            response = {'ok': False, 'error': 'control_unavailable'}
        try:
            self.wfile.write((json.dumps(response, sort_keys=True) + '\n').encode())
        except OSError:
            pass


class MaintenanceClient:
    def __init__(self, socket_path: Path):
        self.socket_path = Path(socket_path)

    def request(self, operation: str, *, actor: str | None = None) -> dict[str, bool]:
        if operation not in ('status', 'enable', 'disable'):
            raise MaintenanceControlError('invalid_request')
        request = {'operation': operation}
        if operation != 'status':
            MaintenanceAuthority._identity(actor, 'web')
            request['actor'] = actor
        raw = (json.dumps(request) + '\n').encode()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
                stream.settimeout(4)
                stream.connect(str(self.socket_path))
                stream.sendall(raw)
                with stream.makefile('rb') as response:
                    raw_response = response.readline(MAX_MESSAGE + 1)
            if len(raw_response) > MAX_MESSAGE or not raw_response.endswith(b'\n'):
                raise MaintenanceControlError('control_unavailable')
            result = json.loads(raw_response)
            if not isinstance(result, dict):
                raise MaintenanceControlError('control_unavailable')
            if result.get('ok') is not True:
                error = result.get('error')
                if error not in ('invalid_request', 'peer_not_permitted', 'operation_busy',
                    'recovery_held', 'state_unavailable', 'exclusion_unavailable',
                    'audit_unavailable', 'transition_incomplete', 'transition_requires_host_repair'):
                    error = 'control_unavailable'
                raise MaintenanceControlError(error)
            state = result.get('state')
            if not isinstance(state, dict) or set(state) != STATE_KEYS or any(type(v) is not bool for v in state.values()):
                raise MaintenanceControlError('control_unavailable')
            return state
        except (OSError, ValueError, UnicodeError):
            raise MaintenanceControlError('control_unavailable') from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', required=True, type=Path)
    parser.add_argument('--socket', required=True, type=Path)
    parser.add_argument('--allowed-uid', required=True, type=int)
    parser.add_argument('--socket-gid', required=True, type=int)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('The host maintenance authority requires root.')
    os.umask(0o077)
    authority = MaintenanceAuthority(args.runtime_root)
    with MaintenanceServer(args.socket, authority, allowed_uid=args.allowed_uid, socket_gid=args.socket_gid) as server:
        server.serve_forever()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
