"""Strict, server-owned, two-viewer Sports sharing canary configuration."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID

class SharedAdmissionConfigError(ValueError):
    """Invalid or unavailable server-owned canary configuration."""

API_CONFIG_PATH = '/mnt/storage/configs/atlas/runtime/sports/shared-admission.json'
CONTROLLER_CONFIG_PATH = '/mnt/storage/configs/sportyfin/state/shared-admission.json'

@dataclass(frozen=True)
class SharedAdmissionRoute:
    target_id: str
    resource_source_id: str
    jellyfin_item_id: str
    dispatcharr_channel_id: int
    dispatcharr_channel_uuid: str
    dispatcharr_stream_id: int
    dispatcharr_account_id: int
    capacity: int
    viewer_user_ids: tuple[str, ...]
    generation: str

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.mapping(), sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def mapping(self):
        return {name: list(value) if isinstance(value, tuple) else value for name, value in self.__dict__.items()}

@dataclass(frozen=True)
class SharedAdmissionConfig:
    routes: tuple[SharedAdmissionRoute, ...] = ()

    def bindings(self):
        return {(row.target_id, row.resource_source_id): row.fingerprint for row in self.routes}

    def for_target(self, target_id):
        return next((row for row in self.routes if row.target_id == target_id), None)

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate configuration key')
        result[key] = value
    return result

def load_shared_admission(default_path=API_CONFIG_PATH):
    path = Path(os.environ.get('ATLAS_SPORTS_SHARED_ADMISSION_FILE', default_path))
    try:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return SharedAdmissionConfig()
        with os.fdopen(descriptor, 'rb') as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 16384:
                raise ValueError('Invalid configuration file')
            # A canary whitelist must not be writable by other users.
            if metadata.st_mode & 0o022: raise ValueError('Unsafe configuration permissions')
            raw = handle.read(16385)
            if len(raw) > 16384: raise ValueError('Configuration exceeds budget')
        data = json.loads(raw, object_pairs_hook=_unique)
        if set(data) != {'version', 'enabled', 'mode', 'routes'}:
            raise ValueError('Invalid configuration fields')
        if type(data['version']) is not int or data['version'] != 1 or type(data['enabled']) is not bool or data['mode'] != 'canary':
            raise ValueError('Unsupported sharing mode')
        if not isinstance(data['routes'], list) or len(data['routes']) > 1:
            raise ValueError('Canary must contain at most one route')
        routes = []
        for row in data['routes']:
            if not isinstance(row, dict) or set(row) != set(SharedAdmissionRoute.__dataclass_fields__):
                raise ValueError('Invalid route fields')
            row = dict(row)
            for name in ('target_id', 'resource_source_id', 'generation'):
                if not isinstance(row[name], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', row[name]):
                    raise ValueError('Invalid route identity')
            if not isinstance(row['jellyfin_item_id'], str) or not re.fullmatch(r'[a-f0-9]{32}', row['jellyfin_item_id']):
                raise ValueError('Invalid Jellyfin binding')
            if not isinstance(row['dispatcharr_channel_uuid'], str) or str(UUID(row['dispatcharr_channel_uuid'])) != row['dispatcharr_channel_uuid']:
                raise ValueError('Invalid channel UUID')
            for name in ('dispatcharr_channel_id', 'dispatcharr_stream_id', 'dispatcharr_account_id', 'capacity'):
                if type(row[name]) is not int or row[name] <= 0: raise ValueError('Invalid native identifier')
            if row['capacity'] != 1: raise ValueError('Canary requires capacity one')
            viewers = row['viewer_user_ids']
            if not isinstance(viewers, list) or len(viewers) != 2 or len(set(viewers)) != 2:
                raise ValueError('Canary requires two distinct viewers')
            if any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) for value in viewers):
                raise ValueError('Invalid viewer identity')
            row['viewer_user_ids'] = tuple(viewers)
            routes.append(SharedAdmissionRoute(**row))
        if data['enabled'] and len(routes) != 1: raise ValueError('Enabled canary requires one route')
        return SharedAdmissionConfig(tuple(routes) if data['enabled'] else ())
    except Exception as error:
        raise SharedAdmissionConfigError('Shared admission configuration is unavailable.') from error
