"""Held component-rollout journal engine; production action adapter is pending.

No CLI, publication, current-pointer write, owner release or maintenance disable.
An adapter supplies bounded observations/actions; only private fixture adapters are
implemented in this stage. Journal receipts are not acceptance receipts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

from atlas.deployment_publication_journal import create_once, encoded, identifier, read_file, safe_directory, sync_directory
from atlas.maintenance_control import MaintenanceControlError
from atlas.maintenance_transaction import TransactionMaintenanceAuthority

SURFACES = ('source', 'authority-unit', 'authority-service', 'api', 'portal', 'caddy')


def require(value, code):
    if not value:
        raise MaintenanceControlError(code)


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def fingerprint(value):
    return isinstance(value, str) and (value == 'absent' or re.fullmatch('[0-9a-f]{64}', value) is not None)


def observation(value):
    require(isinstance(value, dict) and set(value) == {'fingerprint', 'identity'}
            and fingerprint(value['fingerprint']) and fingerprint(value['identity'])
            and (value['fingerprint'] == 'absent') == (value['identity'] == 'absent'), 'rollout_invalid_observation')
    return value


class ComponentRollout(TransactionMaintenanceAuthority):
    """Journal engine under the original owner's proven inherited flock."""
    def __init__(self, runtime_root, owner, inherited_fd, *, adapter, **kwargs):
        super().__init__(runtime_root, owner, inherited_fd, **kwargs)
        self.adapter = adapter

    def _hold(self):
        state = self.status()
        require(state['enabled'] and not state['transition_pending'] and not state['state_uncertain']
                and self._present(self.flag) and not self._present(self.pending)
                and not self._present(self.publication_pending), 'rollout_hold_not_proven')

    def _owner_snapshot(self):
        directory = self.recovery_lock.lstat()
        require(set(path.name for path in self.recovery_lock.iterdir()) == {'owner'}, 'rollout_owner_inventory_changed')
        owner = self._owner()
        file = (self.recovery_lock / 'owner').lstat()
        fields = lambda st: {'device': st.st_dev, 'inode': st.st_ino, 'uid': st.st_uid,
                             'gid': st.st_gid, 'mode': stat.S_IMODE(st.st_mode), 'links': st.st_nlink}
        after = self.recovery_lock.lstat()
        require((directory.st_dev, directory.st_ino, directory.st_mtime_ns, directory.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns),
                'rollout_owner_inventory_changed')
        return {'directory': fields(directory), 'file': fields(file), 'sha256': hashlib.sha256(owner[2]).hexdigest()}

    def _paths(self, rollout):
        identifier(rollout)
        return self.root / 'deployments/rollout-journals' / rollout

    def _plan(self, plan, rollout):
        require(isinstance(plan, dict) and set(plan) == {'schema_version', 'rollout_id', 'original_owner',
                'expected_current', 'generation', 'artifacts', 'protected', 'surfaces'}, 'rollout_invalid_plan')
        require(plan['schema_version'] == 1 and plan['rollout_id'] == rollout
                and plan['original_owner'] == self.identifier, 'rollout_plan_identity_differs')
        identifier(plan['expected_current'])
        require(len({rollout, self.identifier, plan['expected_current']}) == 3, 'rollout_identities_overlap')
        generation = Path(plan['generation'])
        require(generation.is_absolute() and generation.name == 'source'
                and generation.parent.parent == self.root / 'deployments/repairs'
                and identifier(generation.parent.name), 'rollout_invalid_generation')
        require(isinstance(plan['surfaces'], list) and [entry.get('name') for entry in plan['surfaces']] == list(SURFACES),
                'rollout_surface_order_differs')
        for entry in plan['surfaces']:
            require(set(entry) == {'name', 'before', 'after'} and observation(entry['before'])
                    and fingerprint(entry['after']) and entry['after'] != 'absent'
                    and entry['after'] != entry['before']['fingerprint'], 'rollout_surface_plan_differs')
        require(set(plan['artifacts']) == {'source-archive', 'target-recipe', 'rollback-recipe', 'authority-unit'},
                'rollout_artifacts_incomplete')
        for item in plan['artifacts'].values():
            require(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'rollout_invalid_artifact')
            self._pin(item['path'], item['sha256'])
        required = {str(self.root / 'deployments/records' / record / file)
                    for record in (plan['expected_current'], self.identifier) for file in ('metadata', 'status')}
        require(isinstance(plan['protected'], dict) and required <= set(plan['protected'])
                and len(plan['protected']) <= 4096, 'rollout_protected_evidence_incomplete')
        for name, sha in plan['protected'].items():
            self._pin(name, sha)

    @staticmethod
    def _pin(name, sha):
        require(isinstance(name, str) and Path(name).is_absolute() and '..' not in Path(name).parts
                and isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha)
                and read_file(Path(name)) == sha, 'rollout_pinned_evidence_changed')

    def _context(self, rollout):
        self._hold()
        folder = self._paths(rollout)
        safe_directory(folder)
        plan = json.loads(read_file(folder / 'plan.json', limit=4 * 1024 * 1024))
        self._plan(plan, rollout)
        context = json.loads(read_file(folder / 'context.json', limit=65536))
        require(context == {'schema_version': 1, 'plan_sha256': digest(plan), 'owner': self._owner_snapshot(),
                            'current_sha256': read_file(self.root / 'deployments/current'),
                            'scope': 'component-rollout-held-not-publication-not-acceptance'}, 'rollout_context_changed')
        require(read_file(self.root / 'deployments/current', limit=256) == (plan['expected_current'] + '\n').encode()
                and read_file(folder / 'original-lock-owner', limit=4096) == self._owner()[2], 'rollout_original_boundary_changed')
        return folder, plan, context

    def prepare(self, rollout, plan):
        rollout = identifier(rollout)
        with self._exclusive():
            self._hold()
            self._plan(plan, rollout)
            require(read_file(self.root / 'deployments/current', limit=256) == (plan['expected_current'] + '\n').encode(),
                    'rollout_current_differs')
            context = {'schema_version': 1, 'plan_sha256': digest(plan), 'owner': self._owner_snapshot(),
                       'current_sha256': read_file(self.root / 'deployments/current'),
                       'scope': 'component-rollout-held-not-publication-not-acceptance'}
            folder = self._paths(rollout)
            if folder.exists() or folder.is_symlink():
                old_folder, old_plan, old_context = self._context(rollout)
                require(old_plan == plan and old_context == context, 'rollout_plan_conflict')
                self._events(old_folder, plan)
                self._flush_journal(old_folder)
                return folder
            parent = folder.parent
            if not parent.exists():
                safe_directory(parent.parent)
                parent.mkdir(mode=0o700)
                sync_directory(parent.parent)
            safe_directory(parent)
            for entry in plan['surfaces']:
                require(observation(self.adapter.observe(entry['name'])) == entry['before'], 'rollout_initial_runtime_changed')
            folder.mkdir(mode=0o700)
            sync_directory(parent)
            create_once(folder / 'plan.json', encoded(plan))
            create_once(folder / 'context.json', encoded(context))
            create_once(folder / 'original-lock-owner', self._owner()[2])
            self.checkpoint('rollout_plan_durable')
            self._context(rollout)
            return folder

    def _events(self, folder, plan):
        names = set(path.name for path in folder.iterdir())
        base = {'plan.json', 'context.json', 'original-lock-owner'}
        require(base <= names and all(re.fullmatch(r'event-[0-9]{6}\.json', name) for name in names - base),
                'rollout_journal_inventory_changed')
        paths = sorted(folder / name for name in names - base)
        state = {'mode': 'apply', 'completed': {}, 'restored': {}, 'pending': None, 'verified': False,
                 'sequence': 0, 'previous': digest(plan)}
        for index, path in enumerate(paths, 1):
            require(path.name == f'event-{index:06d}.json', 'rollout_journal_sequence_changed')
            event = json.loads(read_file(path, limit=65536))
            require(set(event) == {'sequence', 'previous', 'kind', 'mode', 'surface', 'observed'}
                    and event['sequence'] == index and event['previous'] == state['previous'], 'rollout_journal_chain_changed')
            kind, mode, surface = event['kind'], event['mode'], event['surface']
            if kind == 'rollback-begin':
                require(mode == 'rollback' and state['mode'] == 'apply' and state['pending'] is None
                        and surface is None and event['observed'] is None, 'rollout_invalid_rollback_boundary')
                state['mode'], state['verified'] = 'rollback', False
            elif kind == 'intent':
                require(mode == state['mode'] and state['pending'] is None and not state['verified'], 'rollout_invalid_intent')
                remaining = [name for name in SURFACES if name not in state['completed']] if mode == 'apply' else [
                    name for name in reversed(SURFACES) if name in state['completed'] and name not in state['restored']]
                require(remaining and surface == remaining[0], 'rollout_intent_order_changed')
                entry = next(item for item in plan['surfaces'] if item['name'] == surface)
                expected = entry['before'] if mode == 'apply' else state['completed'][surface]
                require(observation(event['observed']) == expected, 'rollout_intent_runtime_changed')
                state['pending'] = event
            elif kind in ('complete', 'cancel'):
                pending = state['pending']
                require(pending is not None and mode == state['mode'] and surface == pending['surface'], 'rollout_completion_without_intent')
                observed = observation(event['observed'])
                entry = next(item for item in plan['surfaces'] if item['name'] == surface)
                if kind == 'cancel':
                    require(mode == 'apply' and observed == entry['before'], 'rollout_invalid_cancel')
                else:
                    expected = entry['after'] if mode == 'apply' else entry['before']['fingerprint']
                    require(observed['fingerprint'] == expected, 'rollout_result_fingerprint_differs')
                    state['completed' if mode == 'apply' else 'restored'][surface] = observed
                state['pending'] = None
            elif kind == 'verified-held':
                remaining = [name for name in SURFACES if name not in state['completed']] if state['mode'] == 'apply' else [
                    name for name in state['completed'] if name not in state['restored']]
                require(mode == state['mode'] and not remaining and state['pending'] is None
                        and surface is None and event['observed'] is None and not state['verified'], 'rollout_invalid_verification')
                state['verified'] = True
            else:
                raise MaintenanceControlError('rollout_unknown_event')
            state['sequence'], state['previous'] = index, hashlib.sha256(read_file(path, limit=65536)).hexdigest()
        return state

    def _flush_journal(self, folder):
        # An earlier fsync exception may have left complete visible bytes. Explicit
        # resume must flush them again before trusting an old intent/completion.
        for path in sorted(folder.iterdir()):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid()
                        and not info.st_mode & 0o022, 'rollout_journal_file_unavailable')
                os.fsync(fd)
            finally:
                os.close(fd)
        sync_directory(folder)
        sync_directory(folder.parent)

    def _append(self, folder, state, kind, *, surface=None, observed=None, mode=None):
        number = state['sequence'] + 1
        require(number <= 999999, 'rollout_journal_limit')
        event = {'sequence': number, 'previous': state['previous'], 'kind': kind,
                 'mode': mode or state['mode'], 'surface': surface, 'observed': observed}
        create_once(folder / f'event-{number:06d}.json', encoded(event))
        self.checkpoint(f'{event["mode"]}:{surface or "boundary"}:{kind}:durable')

    def _confirm(self, surface, mode, observed):
        # Adapters with multi-step durable writes must reflush a visible target
        # before a completion is adopted after interruption. Identity must stay exact.
        confirm = getattr(self.adapter, 'confirm', None)
        if confirm is not None:
            require(observation(confirm(surface, mode, observed)) == observed,
                    'rollout_confirmation_identity_changed')
        require(observation(self.adapter.observe(surface)) == observed,
                'rollout_confirmation_runtime_changed')

    def _stable(self, state, plan, *, pending_surface=None):
        for entry in plan['surfaces']:
            name = entry['name']
            if name == pending_surface:
                continue
            expected = state['restored'].get(name, state['completed'].get(name, entry['before']))
            require(observation(self.adapter.observe(name)) == expected, 'rollout_runtime_drift')

    def inspect_rollout(self, rollout):
        with self._exclusive():
            folder, plan, _ = self._context(rollout)
            state = self._events(folder, plan)
            pending = state['pending']
            self._stable(state, plan, pending_surface=pending['surface'] if pending else None)
            outcome = 'none'
            if pending:
                entry = next(item for item in plan['surfaces'] if item['name'] == pending['surface'])
                observed = observation(self.adapter.observe(pending['surface']))
                after = entry['after'] if state['mode'] == 'apply' else entry['before']['fingerprint']
                outcome = 'not-applied' if observed == pending['observed'] else 'applied' if observed['fingerprint'] == after else 'unknown'
            self._context(rollout)
            return {'mode': state['mode'], 'verified_held': state['verified'], 'pending_outcome': outcome,
                    'journal_events': state['sequence'], 'completed_surfaces': list(state['completed']),
                    'restored_surfaces': list(state['restored']), 'owner_release_permitted': False,
                    'publication_permitted': False, 'public_reopen_permitted': False}

    def run(self, rollout, *, rollback=False):
        """Explicit resume only; unknown observations refuse without an action."""
        with self._exclusive():
            folder, plan, _ = self._context(rollout)
            state = self._events(folder, plan)
            self._flush_journal(folder)
            self._context(rollout)
            if state['mode'] == 'rollback':
                require(rollback, 'rollout_forward_after_rollback_refused')
            if rollback and state['mode'] == 'apply':
                pending = state['pending']
                self._stable(state, plan, pending_surface=pending['surface'] if pending else None)
                if pending:
                    observed = observation(self.adapter.observe(pending['surface']))
                    entry = next(item for item in plan['surfaces'] if item['name'] == pending['surface'])
                    if observed == entry['before']:
                        self._append(folder, state, 'cancel', surface=pending['surface'], observed=observed)
                    else:
                        require(observed['fingerprint'] == entry['after'], 'rollout_uncertain_action_requires_review')
                        self._confirm(pending['surface'], 'apply', observed)
                        self._context(rollout)
                        self._stable(state, plan, pending_surface=pending['surface'])
                        self._append(folder, state, 'complete', surface=pending['surface'], observed=observed)
                    state = self._events(folder, plan)
                self._append(folder, state, 'rollback-begin', mode='rollback')
                state = self._events(folder, plan)
            while True:
                self._context(rollout)
                pending = state['pending']
                self._stable(state, plan, pending_surface=pending['surface'] if pending else None)
                if state['verified']:
                    require(self.adapter.verify(state['mode']) is True, 'rollout_final_verification_failed')
                    self._context(rollout)
                    self._stable(state, plan)
                    return self.inspect_rollout(rollout)
                remaining = [name for name in SURFACES if name not in state['completed']] if state['mode'] == 'apply' else [
                    name for name in reversed(SURFACES) if name in state['completed'] and name not in state['restored']]
                if not remaining:
                    require(self.adapter.verify(state['mode']) is True, 'rollout_final_verification_failed')
                    self._context(rollout)
                    self._stable(state, plan)
                    self._append(folder, state, 'verified-held')
                    state = self._events(folder, plan)
                    continue
                name = remaining[0]
                entry = next(item for item in plan['surfaces'] if item['name'] == name)
                observed = observation(self.adapter.observe(name))
                if pending is None:
                    expected = entry['before'] if state['mode'] == 'apply' else state['completed'][name]
                    require(observed == expected, 'rollout_action_precondition_changed')
                    self._append(folder, state, 'intent', surface=name, observed=observed)
                    state = self._events(folder, plan)
                    pending = state['pending']
                after = entry['after'] if state['mode'] == 'apply' else entry['before']['fingerprint']
                if observed == pending['observed']:
                    self._context(rollout)
                    self._stable(state, plan, pending_surface=name)
                    self.checkpoint(f'{state["mode"]}:{name}:before-action')
                    if state['mode'] == 'apply': self.adapter.apply(name)
                    else: self.adapter.rollback(name)
                    self.checkpoint(f'{state["mode"]}:{name}:after-action')
                    observed = observation(self.adapter.observe(name))
                require(observed['fingerprint'] == after, 'rollout_uncertain_action_requires_review')
                self._confirm(name, state['mode'], observed)
                self._context(rollout)
                self._stable(state, plan, pending_surface=name)
                self._append(folder, state, 'complete', surface=name, observed=observed)
                state = self._events(folder, plan)
