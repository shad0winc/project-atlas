"""Default-off, reviewed acquisition routing. Construction performs no network IO."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from ..provider import MediaRequestProviderError
from .acquisition_factory import build_acquisition_provider
from .managed_profiles import ArrProfileBinding, CATEGORIES, _NoRedirect
from ..models import MediaAudioPreference

ERROR = "Reviewed acquisition configuration could not be verified"
MAX_CONFIG_BYTES = 65_536


def acquisition_routing_enabled() -> bool:
    value = os.getenv("ATLAS_ACQUISITION_ROUTING_ENABLED", "0").strip()
    if value not in {"0", "1"}:
        raise MediaRequestProviderError("Acquisition routing opt-in must be 0 or 1")
    return value == "1"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Nonfinite JSON value")


def _endpoint(value, *, arr=False):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Invalid endpoint")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment
            or re.search(r"[\s\\]", value)
            or re.fullmatch(r"(?:/[A-Za-z0-9._-]+)*/?", parsed.path) is None
            or any(part in {".", ".."} for part in parsed.path.split("/"))):
        raise ValueError("Invalid endpoint")
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid endpoint port")
    if arr and not parsed.path.rstrip("/").endswith("/api/v3"):
        raise ValueError("Invalid Arr endpoint")
    identity = (parsed.scheme, parsed.hostname.lower(), port or (443 if parsed.scheme == "https" else 80), parsed.path.rstrip("/"))
    return value.rstrip("/"), identity


def _credential(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 4096
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError("Invalid credential")
    return value


def _read_config(environment):
    raw_path = environment.get("ATLAS_ACQUISITION_ROUTING_CONFIG", "")
    expected_hash = environment.get("ATLAS_ACQUISITION_ROUTING_SHA256", "")
    if not isinstance(raw_path, str) or not raw_path or raw_path != raw_path.strip():
        raise ValueError("Missing configuration path")
    path = Path(raw_path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe configuration path")
    if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        raise ValueError("Missing reviewed configuration digest")
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError("Symlink configuration parent")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_uid not in {0, os.geteuid()}
                or stat.S_IMODE(before.st_mode) not in {0o600, 0o640}
                or before.st_size > MAX_CONFIG_BYTES):
            raise ValueError("Unsafe configuration file")
        raw = handle.read(MAX_CONFIG_BYTES + 1)
        after = os.fstat(handle.fileno())
        current = path.lstat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode", "st_uid", "st_nlink")
    if (len(raw) > MAX_CONFIG_BYTES
            or any(getattr(before, key) != getattr(after, key) for key in fields)
            or any(getattr(after, key) != getattr(current, key) for key in fields)
            or hashlib.sha256(raw).hexdigest() != expected_hash):
        raise ValueError("Configuration changed or digest mismatch")
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=_invalid_constant)


def _metadata_reader(base_url, api_key):
    # URL/key live only in this backend closure; never in a logged config object.
    def read(path):
        if not isinstance(path, str) or re.fullmatch(r"/api/v1/tv/[1-9][0-9]*", path) is None:
            raise MediaRequestProviderError("TV metadata endpoint is invalid")
        try:
            request = Request(base_url + path, headers={"X-Api-Key": api_key, "Accept": "application/json"}, method="GET")
            with build_opener(_NoRedirect()).open(request, timeout=10) as response:
                if response.status != 200:
                    raise ValueError("Unexpected metadata status")
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Metadata exceeds budget")
            return json.loads(raw, object_pairs_hook=_unique, parse_constant=_invalid_constant)
        except Exception:
            raise MediaRequestProviderError("TV metadata could not be verified") from None
    return read


def configured_acquisition_provider(*, base_url, api_key, category_servers):
    """Build from exact reviewed bytes; never allocate/verify native profiles here.

    Caller must enforce the opt-in and schema/recovery activation contract.
    Native profile contents and route identities must be reviewed separately.
    """
    try:
        if (not isinstance(category_servers, dict) or set(category_servers) != CATEGORIES
                or any(type(value) is not int or value < 0 for value in category_servers.values())):
            raise ValueError("Invalid configured server map")
        environment = dict(os.environ)
        config = _read_config(environment)
        if (not isinstance(config, dict) or set(config) != {"schema_version", "categories"}
                or type(config["schema_version"]) is not int or config["schema_version"] != 1
                or not isinstance(config["categories"], dict)
                or set(config["categories"]) != CATEGORIES):
            raise ValueError("Invalid configuration schema")
        base_url, _ = _endpoint(base_url)
        api_key = _credential(api_key)
        routes, bindings, profiles, endpoints = {}, {}, {}, set()
        modes = {mode.value for mode in MediaAudioPreference}
        for category, row in config["categories"].items():
            if not isinstance(row, dict) or set(row) != {"server_id", "arr_url", "api_key_env", "profiles"}:
                raise ValueError("Invalid category configuration")
            configured_server = row["server_id"]
            if type(configured_server) is not int or configured_server < 0 or category_servers.get(category) != configured_server:
                raise ValueError("Environment/config routing mismatch")
            endpoint, identity = _endpoint(row["arr_url"], arr=True)
            if identity in endpoints:
                raise ValueError("Instance endpoints must be distinct")
            endpoints.add(identity)
            key_env = row["api_key_env"]
            if not isinstance(key_env, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", key_env) is None:
                raise ValueError("Invalid credential reference")
            key = _credential(environment.get(key_env))
            policies = row["profiles"]
            if not isinstance(policies, dict) or set(policies) != modes:
                raise ValueError("Incomplete audio policies")
            routes[category] = configured_server
            bindings[(category, configured_server)] = ArrProfileBinding(endpoint, key)
            profiles.update({(category, mode): value for mode, value in policies.items()})
        if routes["movie"] == routes["anime_movie"] or routes["tv"] == routes["anime_tv"]:
            raise ValueError("Regular/anime server bindings must be distinct")
        return build_acquisition_provider(base_url=base_url, api_key=api_key,
            category_servers=routes, bindings=bindings, profile_ids=profiles,
            read_tv_metadata=_metadata_reader(base_url, api_key))
    except Exception:
        raise MediaRequestProviderError(ERROR) from None
