"""Command-line interface for Atlas invitations."""
from __future__ import annotations
import argparse, json, os, sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote
from atlas.identity import IdentityPaths
from atlas.invitations import InvitationError, InvitationStore, default_store

def _parser():
    p=argparse.ArgumentParser(prog='atlas invite'); p.add_argument('--identity-directory'); p.add_argument('--base-url')
    sub=p.add_subparsers(dest='action', required=True)
    c=sub.add_parser('create'); c.add_argument('--email'); c.add_argument('--role',choices=('admin','user'),default='user'); c.add_argument('--created-by'); c.add_argument('--days',type=int); c.add_argument('--json',action='store_true')
    l=sub.add_parser('list'); l.add_argument('--status',choices=('pending','completed','revoked','expired')); l.add_argument('--json',action='store_true')
    s=sub.add_parser('show'); s.add_argument('invite_id')
    r=sub.add_parser('revoke'); r.add_argument('invite_id'); r.add_argument('--revoked-by')
    v=sub.add_parser('verify'); v.add_argument('--token')
    sub.add_parser('cleanup'); return p

def _store(a): return InvitationStore(IdentityPaths(Path(a.identity_directory).expanduser().resolve())) if a.identity_directory else default_store()
def _days(a):
    raw=a.days if a.days is not None else os.getenv('ATLAS_INVITE_EXPIRATION_DAYS','7')
    try: value=int(raw)
    except (TypeError,ValueError) as exc: raise InvitationError('ATLAS_INVITE_EXPIRATION_DAYS must be an integer') from exc
    if value<=0: raise InvitationError('invitation expiration days must be greater than zero')
    return value
def _url(token,base): return f"{(base or os.getenv('ATLAS_BASE_URL','http://atlas.local')).rstrip('/')}/register?token={quote(token,safe='')}"
def _json(v): print(json.dumps(v,indent=2,sort_keys=True))
def main(argv:Sequence[str]|None=None)->int:
    a=_parser().parse_args(argv); store=_store(a)
    try:
        if a.action=='create':
            issue=store.create(email=a.email,role=a.role,created_by=a.created_by,expires_in=timedelta(days=_days(a))); result=dict(issue.invitation); result.update(token=issue.token,registration_url=_url(issue.token,a.base_url))
            if a.json: _json(result)
            else:
                print('Invitation created'); print(f"ID: {result['invite_id']}"); print(f"Email: {result['email'] or '-'}"); print(f"Role: {result['role']}"); print(f"Expires: {result['expires_at']}"); print(f"Registration URL: {result['registration_url']}"); print('The token is shown only once.')
            return 0
        if a.action=='list':
            records=store.list(status=a.status)
            if a.json: _json(records)
            else:
                print('ID\tEMAIL\tROLE\tSTATUS\tEXPIRES')
                for r in records: print(f"{r['invite_id']}\t{r['email'] or '-'}\t{r['role']}\t{r['status']}\t{r['expires_at']}")
            return 0
        if a.action=='show': _json(store.get(a.invite_id)); return 0
        if a.action=='revoke': _json(store.revoke(a.invite_id,revoked_by=a.revoked_by)); return 0
        if a.action=='verify':
            if a.token:
                r=store.verify_token(a.token); print(f"PASS\tinvitation token valid: {r['invite_id']}"); return 0
            errors=store.verify()
            if errors:
                for e in errors: print(f'FAIL\t{e}')
                return 1
            print('PASS\tinvitation storage valid'); return 0
        if a.action=='cleanup':
            expired=store.cleanup_expired(); print(f'Archived expired invitations: {len(expired)}')
            for invite_id in expired: print(invite_id)
            return 0
    except InvitationError as exc: print(str(exc),file=sys.stderr); return 1
    return 1
if __name__=='__main__': raise SystemExit(main())
