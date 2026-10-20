"""Source-generation adapter for the held component journal.

Source publication/retention uses actual immutable generation operations. Five
runtime surfaces are delegated to an explicit adapter; no production Docker or
systemd implementation or CLI is enabled by this module.
"""
from __future__ import annotations

from atlas.deployment_component_rollout import SURFACES, digest, observation, require
from atlas.deployment_publication_journal import read_file


class GenerationRolloutAdapter:
    def __init__(self, generation, runtime_adapter, *, held_guard):
        self.generation, self.runtime = generation, runtime_adapter
        self.held_guard = held_guard
        require(all(callable(getattr(runtime_adapter, name, None)) for name in
                    ('observe', 'apply', 'rollback', 'verify', 'confirm', 'source_inactive')),
                'component_runtime_adapter_incomplete')
        # Pin a complete already-prepared generation; never prepare or fill it here.
        state = generation.inspect()
        self.catalog_sha256 = read_file(generation.marker)
        self.target_fingerprint = digest({'schema_version': 1, 'source': str(generation.target),
            'tree': state['tree'], 'archive_sha256': state['archive_sha256'],
            'marker_sha256': self.catalog_sha256})

    def _held(self):
        require(self.held_guard() is True, 'component_source_hold_unproven')

    def _source(self):
        require(read_file(self.generation.marker) == self.catalog_sha256, 'component_source_marker_changed')
        state = self.generation.inspect()
        if state['namespace'] in ('staged', 'retained'):
            return {'fingerprint': 'absent', 'identity': 'absent'}
        require(state['namespace'] == 'published', 'component_source_namespace_unknown')
        info = self.generation.target.lstat()
        identity = digest({'device': info.st_dev, 'inode': info.st_ino, 'mode': info.st_mode,
                           'uid': info.st_uid, 'gid': info.st_gid, 'marker_sha256': self.catalog_sha256,
                           'target_fingerprint': self.target_fingerprint})
        return {'fingerprint': self.target_fingerprint, 'identity': identity}

    @staticmethod
    def _name(name): require(name in SURFACES, 'component_source_unknown_surface')

    def observe(self, name):
        self._name(name);self._held()
        result = self._source() if name == 'source' else observation(self.runtime.observe(name))
        self._held()
        return result

    def apply(self, name):
        self._name(name);self._held()
        if name == 'source': self.generation.publish(held_guard=self.held_guard)
        else: self.runtime.apply(name)
        self._held()

    def rollback(self, name):
        self._name(name);self._held()
        if name == 'source':
            self.generation.retain(held_guard=self.held_guard, inactive_guard=self.runtime.source_inactive)
        else: self.runtime.rollback(name)
        self._held()

    def confirm(self, name, mode, expected):
        self._name(name);self._held();observation(expected)
        require(mode in ('apply', 'rollback') and self.observe(name) == expected,
                'component_confirmation_precondition_changed')
        if name == 'source':
            # Idempotent calls reflush both namespace and files after a visible
            # rename that may have survived an earlier fsync exception or SIGKILL.
            state = self.generation.inspect()
            if mode == 'apply':
                require(state['namespace'] == 'published', 'component_confirmation_source_not_published')
                self.generation.publish(held_guard=self.held_guard)
            else:
                require(state['namespace'] == 'retained', 'component_confirmation_source_not_retained')
                self.generation.retain(held_guard=self.held_guard, inactive_guard=self.runtime.source_inactive)
        else:
            require(observation(self.runtime.confirm(name, mode, expected)) == expected,
                    'component_runtime_confirmation_changed')
        self._held()
        result = self.observe(name)
        require(result == expected, 'component_confirmation_identity_changed')
        return result

    def verify(self, mode):
        require(mode in ('apply', 'rollback'), 'component_source_invalid_mode');self._held()
        state = self.generation.inspect()
        require(state['namespace'] == ('published' if mode == 'apply' else 'retained'),
                'component_source_final_namespace_differs')
        require(self.runtime.verify(mode) is True, 'component_runtime_final_verification_failed')
        if mode == 'rollback':
            require(self.runtime.source_inactive() is True, 'component_source_still_referenced')
        self._held()
        return True
