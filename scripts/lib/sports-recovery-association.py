"""Bind a validated Sports bundle to a stopped prepared PostgreSQL copy.

This is a content association, not an attestation of backup-time consistency,
consumer identity, production ownership or permission to publish live state.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

import importlib.util


class AssociationError(ValueError):
    pass


def require(condition):
    if not condition:
        raise AssociationError('Invalid Sports recovery association')


def helper(name):
    spec = importlib.util.spec_from_file_location(
        name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observe(bundle_root, postgres_root, *, database, admin_role):
    bundle = helper('sports-recovery-bundle')
    postgres = helper('sports-postgres-prepare')
    database = postgres.identifier(database)
    admin_role = postgres.identifier(admin_role)
    # Both existing validators require private paths owned by the calling UID.
    # No ownership conversion, cold-copy acquisition or native restore runs here.
    manifest = bundle.validate_bundle(bundle_root)
    require(manifest['native_backend'] == 'captured')
    receipt = postgres.validate_prepared(postgres_root)
    require(receipt['application_database'] == database
            and receipt['admin_role'] == admin_role)
    records = {row['surface']: row for row in manifest['files']}
    require(records['dispatcharr-database']['sha256'] == receipt['source_dump_sha256'])
    raw_bundle = bundle.bytes_checked(bundle_root / 'BUNDLE.json', 16384)
    raw_postgres = bundle.bytes_checked(postgres_root / 'PREPARED.json', 16384)
    # Bind exactly the documents that the validators interpreted, even if a
    # private caller changes a document between validation and hashing it.
    require(json.loads(raw_bundle, object_pairs_hook=bundle.unique) == manifest
            and json.loads(raw_postgres, object_pairs_hook=bundle.unique) == receipt)
    return {
        'bundle_document_sha256': hashlib.sha256(raw_bundle).hexdigest(),
        'postgres_document_sha256': hashlib.sha256(raw_postgres).hexdigest(),
        'source_dump_sha256': receipt['source_dump_sha256'],
        'prepared_cluster_sha256': receipt['prepared_cluster_sha256'],
    }


def associate(bundle_root, postgres_root, *, database, admin_role):
    bundle_root = Path(bundle_root)
    postgres_root = Path(postgres_root)
    observation = observe(bundle_root, postgres_root, database=database, admin_role=admin_role)
    receipt = {
        'version': 1,
        'state': 'associated-not-live-ready',
        'ready_for_live_apply': False,
        'bundle_root': str(bundle_root),
        'postgres_root': str(postgres_root),
        'application_database': database,
        'admin_role': admin_role,
        **observation,
    }
    bundle = helper('sports-recovery-bundle')
    workspace = Path(tempfile.mkdtemp(prefix='project-atlas-sports-association.', dir='/tmp'))
    try:
        bundle.write_private(workspace / '.association.json',
                             (json.dumps(receipt, sort_keys=True) + '\n').encode())
        require(observe(bundle_root, postgres_root, database=database, admin_role=admin_role)
                == observation)
        (workspace / '.association.json').rename(workspace / 'ASSOCIATION.json')
        bundle.sync_directory(workspace)
        validate_association(workspace)
        return workspace
    except BaseException:
        # Remove only the new association workspace, never either input tree.
        shutil.rmtree(workspace)
        raise


def validate_association(workspace):
    bundle = helper('sports-recovery-bundle')
    workspace = bundle.safe_path(workspace)
    require(workspace.parent == Path('/tmp') and re.fullmatch(
        r'project-atlas-sports-association\.[A-Za-z0-9_-]+', workspace.name) is not None)
    bundle.directory(workspace)
    require({path.name for path in workspace.iterdir()} == {'ASSOCIATION.json'})
    receipt = json.loads(bundle.bytes_checked(workspace / 'ASSOCIATION.json', 16384),
                         object_pairs_hook=bundle.unique)
    require(isinstance(receipt, dict) and set(receipt) == {
        'version', 'state', 'ready_for_live_apply', 'bundle_root', 'postgres_root',
        'application_database', 'admin_role', 'bundle_document_sha256',
        'postgres_document_sha256', 'source_dump_sha256', 'prepared_cluster_sha256'})
    require(type(receipt['version']) is int and receipt['version'] == 1
            and receipt['state'] == 'associated-not-live-ready'
            and receipt['ready_for_live_apply'] is False)
    for key in ('bundle_root', 'postgres_root'):
        require(isinstance(receipt[key], str))
    observation = observe(Path(receipt['bundle_root']), Path(receipt['postgres_root']),
                          database=receipt['application_database'], admin_role=receipt['admin_role'])
    require(all(receipt[key] == value for key, value in observation.items()))
    return receipt
