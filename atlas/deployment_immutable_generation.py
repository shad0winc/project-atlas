"""Durable, immutable repair source staging and guarded namespace transitions.

Preparation creates only a new repair's inactive staging tree. Publish/retain are
internal primitives for the pending component adapter, not deployment commands.
No service, container, current pointer, maintenance state or recovery lock change.
"""
from __future__ import annotations

import hashlib
import ctypes
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

from atlas.deployment_publication_journal import create_once, encoded, identifier, read_file, safe_directory, sync_directory
from atlas.maintenance_control import MaintenanceControlError


def require(value, code):
    if not value:
        raise MaintenanceControlError(code)


def tree_oid(files):
    root = {}
    for name, row in files.items():
        node = root
        for part in name.split('/')[:-1]:
            require(part not in node or isinstance(node[part], dict), 'generation_source_path_collision')
            node = node.setdefault(part, {})
        last = name.split('/')[-1]
        require(last not in node, 'generation_source_path_collision')
        node[last] = (row['oid'], row['executable'])
    def encode(node):
        raw = bytearray()
        for name in sorted(node, key=lambda key: key.encode() + (b'/' if isinstance(node[key], dict) else b'')):
            row = node[name]
            mode, oid = ('40000', encode(row)) if isinstance(row, dict) else ('100755' if row[1] else '100644', row[0])
            raw.extend(mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(oid))
        return hashlib.sha1(b'tree ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    return encode(root)


def rename_no_replace(source, destination):
    # Linux renameat2 keeps the absence precondition atomic, including an empty
    # foreign directory appearing between the caller's check and namespace write.
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, 'renameat2', None)
    if rename is None:
        raise OSError('atomic no-replace rename is unavailable')
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        raise OSError(ctypes.get_errno(), 'atomic source namespace transition refused')


class ImmutableGeneration:
    def __init__(self, runtime_root, repair_id, archive, archive_sha256, commit, tree, *, checkpoint=None):
        self.root = Path(runtime_root)
        self.repair_id = identifier(repair_id)
        self.archive = Path(archive)
        for value, length in ((archive_sha256, 64), (commit, 40), (tree, 40)):
            require(isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value), 'generation_invalid_identity')
        self.archive_sha256, self.commit, self.tree = archive_sha256, commit, tree
        self.parent = self.root / 'deployments/repairs' / repair_id
        self.staging, self.target, self.retained = (self.parent / name for name in ('source-staging', 'source', 'source-retained'))
        self.marker = self.parent / 'source-generation.json'
        self.checkpoint = checkpoint or (lambda phase: None)

    @staticmethod
    def _identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid, info.st_nlink)

    def _catalog(self):
        safe_directory(self.archive.parent)
        fd = os.open(self.archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        files, directories, seen = {}, set(), set()
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.geteuid()
                    and not before.st_mode & 0o022, 'generation_archive_unavailable')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == self.archive_sha256, 'generation_archive_checksum_differs')
                stream.seek(0)
                with tarfile.open(fileobj=stream, mode='r:*') as archive:
                    require(archive.pax_headers.get('comment') == self.commit, 'generation_archive_commit_differs')
                    for member in archive:
                        name = member.name.rstrip('/')
                        path = PurePosixPath(name)
                        require(name and not path.is_absolute() and str(path) == name and '..' not in path.parts
                                and '\\' not in name and '\0' not in name and name not in seen,
                                'generation_unsafe_archive_member')
                        seen.add(name)
                        require(member.isdir() or member.isfile(), 'generation_archive_link_or_special_file')
                        if member.isdir():
                            directories.add(name)
                            continue
                        blob = hashlib.sha1(b'blob ' + str(member.size).encode() + b'\0')
                        content = hashlib.sha256()
                        with archive.extractfile(member) as src:
                            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                                blob.update(chunk);content.update(chunk)
                        files[name] = {'oid': blob.hexdigest(), 'sha256': content.hexdigest(), 'bytes': member.size,
                                       'executable': bool(member.mode & 0o111)}
                require(files and tree_oid(files) == self.tree, 'generation_archive_tree_differs')
                parents = {str(parent) for name in files for parent in PurePosixPath(name).parents if str(parent) != '.'}
                require(directories <= parents and not set(files) & parents, 'generation_archive_directory_coverage_differs')
            require(self._identity(os.fstat(fd)) == self._identity(before)
                    and self._identity(self.archive.lstat()) == self._identity(before), 'generation_archive_changed')
        finally:
            os.close(fd)
        return files

    def _expected(self, files):
        return {'schema_version': 1, 'repair_id': self.repair_id, 'archive_sha256': self.archive_sha256,
                'archive_commit': self.commit, 'source_tree': self.tree, 'files': files,
                'scope': 'immutable-source-bytes-not-deployment-not-acceptance'}

    def _namespace(self):
        for path in (self.root, self.root / 'deployments', self.parent.parent):
            safe_directory(path)
        if self.parent.exists() or self.parent.is_symlink():
            safe_directory(self.parent)
        else:
            self.parent.mkdir(mode=0o700)
            os.chown(self.parent, os.geteuid(), os.getegid())
            os.chmod(self.parent, 0o700)
            sync_directory(self.parent.parent)
        require(set(path.name for path in self.parent.iterdir()) <= {'source-staging', 'source', 'source-retained', 'source-generation.json'},
                'generation_repair_inventory_differs')
        require(self.parent.stat().st_uid == os.geteuid() and stat.S_IMODE(self.parent.stat().st_mode) == 0o700,
                'generation_repair_directory_metadata_differs')

    def _verify(self, path, files):
        safe_directory(path)
        observed = set()
        directories = {path}
        for file in path.rglob('*'):
            info = file.lstat()
            require(not file.is_symlink() and info.st_uid == os.geteuid() and info.st_gid == os.getegid(),
                    'generation_source_owner_or_link_differs')
            if stat.S_ISDIR(info.st_mode):
                require(stat.S_IMODE(info.st_mode) == 0o555, 'generation_directory_not_immutable')
                directories.add(file)
                continue
            name = file.relative_to(path).as_posix()
            require(name in files and stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                    'generation_source_inventory_differs')
            expected = files[name]
            require(stat.S_IMODE(info.st_mode) == (0o555 if expected['executable'] else 0o444)
                    and info.st_size == expected['bytes'] and read_file(file) == expected['sha256'],
                    'generation_source_bytes_or_mode_differs')
            observed.add(name)
        root_info = path.lstat()
        require(stat.S_IMODE(root_info.st_mode) == 0o555 and root_info.st_uid == os.geteuid()
                and root_info.st_gid == os.getegid() and observed == set(files), 'generation_source_coverage_differs')
        expected_directories = {path} | {path / str(parent) for name in files for parent in PurePosixPath(name).parents if str(parent) != '.'}
        require(directories == expected_directories, 'generation_directory_coverage_differs')

    def _flush(self, path):
        directories = [path]
        for file in path.rglob('*'):
            if file.is_dir(): directories.append(file);continue
            fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try: os.fsync(fd)
            finally: os.close(fd)
        for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
            sync_directory(directory)
        marker_fd = os.open(self.marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try: os.fsync(marker_fd)
        finally: os.close(marker_fd)
        sync_directory(self.parent)

    def _marker(self, files):
        require(read_file(self.marker, limit=4 * 1024 * 1024) == encoded(self._expected(files)), 'generation_marker_differs')

    def prepare(self):
        files = self._catalog()
        self._namespace()
        require(not self.target.exists() and not self.target.is_symlink()
                and not self.retained.exists() and not self.retained.is_symlink(), 'generation_namespace_already_transitioned')
        if self.staging.exists() or self.staging.is_symlink():
            # Never fill missing bytes or replace an interrupted/foreign preparation.
            self._verify(self.staging, files)
            self._marker(files)
            self._flush(self.staging)
            return self.staging
        require(not self.marker.exists() and not self.marker.is_symlink(), 'generation_orphan_marker')
        self.staging.mkdir(mode=0o700)
        sync_directory(self.parent)
        self.checkpoint('staging-created')
        archive_fd = os.open(self.archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(archive_fd, 'rb') as stream, tarfile.open(fileobj=stream, mode='r:*') as archive:
            for member in archive:
                if not member.isfile(): continue
                name = member.name
                require(name in files, 'generation_archive_changed')
                target = self.staging / name
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                content = hashlib.sha256()
                try:
                    with os.fdopen(fd, 'wb', closefd=False) as dst, archive.extractfile(member) as src:
                        for chunk in iter(lambda: src.read(1024 * 1024), b''):
                            content.update(chunk);dst.write(chunk)
                        require(content.hexdigest() == files[name]['sha256'], 'generation_archive_changed')
                        os.fchmod(fd, 0o555 if files[name]['executable'] else 0o444)
                        dst.flush();os.fsync(fd)
                finally:
                    os.close(fd)
                self.checkpoint('file-durable')
        require(read_file(self.archive) == self.archive_sha256, 'generation_archive_changed')
        directories = [path for path in self.staging.rglob('*') if path.is_dir()] + [self.staging]
        for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
            directory.chmod(0o555)
            sync_directory(directory)
        self._verify(self.staging, files)
        self.checkpoint('staging-tree-durable')
        create_once(self.marker, encoded(self._expected(files)))
        self.checkpoint('staging-marker-durable')
        self._flush(self.staging)
        self.checkpoint('staging-durable')
        return self.staging

    def inspect(self):
        files = self._catalog()
        safe_directory(self.parent)
        self._marker(files)
        present = [name for name, path in (('staged', self.staging), ('published', self.target), ('retained', self.retained))
                   if path.exists() or path.is_symlink()]
        require(len(present) == 1, 'generation_namespace_ambiguous')
        path = {'staged': self.staging, 'published': self.target, 'retained': self.retained}[present[0]]
        self._verify(path, files)
        return {'namespace': present[0], 'tree': self.tree, 'archive_sha256': self.archive_sha256,
                'file_count': len(files), 'source_path': str(path), 'deployment_or_acceptance_proven': False}

    def publish(self, *, held_guard):
        require(held_guard() is True, 'generation_held_context_unproven')
        state = self.inspect()
        require(state['namespace'] in ('staged', 'published'), 'generation_retained_requires_new_plan')
        if state['namespace'] == 'staged':
            require(not self.target.exists() and not self.target.is_symlink(), 'generation_target_appeared')
            self.checkpoint('before-source-rename')
            rename_no_replace(self.staging, self.target)
            self.checkpoint('source-renamed')
        sync_directory(self.parent)
        self._flush(self.target)
        require(held_guard() is True, 'generation_held_context_changed')
        self.checkpoint('source-namespace-durable')
        return self.inspect()

    def retain(self, *, held_guard, inactive_guard):
        require(held_guard() is True and inactive_guard() is True, 'generation_inactive_context_unproven')
        state = self.inspect()
        require(state['namespace'] in ('published', 'retained'), 'generation_not_published')
        if state['namespace'] == 'published':
            require(not self.retained.exists() and not self.retained.is_symlink(), 'generation_retained_target_appeared')
            self.checkpoint('before-retain-rename')
            rename_no_replace(self.target, self.retained)
            self.checkpoint('source-retained-renamed')
        sync_directory(self.parent)
        self._flush(self.retained)
        require(held_guard() is True and inactive_guard() is True, 'generation_inactive_context_changed')
        self.checkpoint('retained-namespace-durable')
        return self.inspect()
