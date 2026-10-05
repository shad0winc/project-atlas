"""Compile and create isolated native policies with durable, non-replayed intents.

No import-time I/O or activation. Production callers supply bound clients and an
ownership/source/state guard; only customformat and qualityprofile creation is
supported. A pending creation is reconciled by reads and is never posted again.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Callable, Protocol

from .native_policy_plan import INSTANCES, MODES, build_native_policy_plan


class NativePolicyInstallationError(ValueError):
    """Installation evidence is incomplete or changed; details stay private."""


class NativePolicyReconciliationRequired(NativePolicyInstallationError):
    """An intent exists without a verified receipt; no blind replay is allowed."""


def _require(condition: bool, message: str = "Native installation evidence is invalid") -> None:
    if not condition:
        raise NativePolicyInstallationError(message)


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _id(value: object) -> int:
    _require(type(value) is int and value > 0)
    return value


def _rows(value: object) -> dict[int, dict]:
    _require(isinstance(value, list) and len(value) <= 4000)
    result = {}
    for row in value:
        _require(isinstance(row, dict))
        key = _id(row.get("id"))
        _require(key not in result and isinstance(row.get("name"), str))
        result[key] = row
    return result


def _named(value: object, key: str) -> dict[str, dict]:
    _require(isinstance(value, list) and len(value) <= 2000)
    result = {}
    for row in value:
        _require(isinstance(row, dict) and isinstance(row.get(key), str))
        _require(row[key] not in result)
        result[row[key]] = row
    return result


SCHEMA_FIELDS = frozenset({
    "id", "name", "implementation", "implementationName", "negate", "required", "fields",
    "label", "type", "value", "selectOptions", "selectOptionsProvider", "order", "isAdvanced",
    "quality", "items", "allowed", "resolution", "source", "modifier", "language",
    "upgradeAllowed", "cutoff", "minFormatScore", "cutoffFormatScore", "minUpgradeFormatScore",
    "formatItems", "format", "score", "includeCustomFormatWhenRenaming",
})


def schema_projection(value: object, depth: int = 0) -> object:
    """Same payload-relevant projection as the credential-free version capture."""
    _require(depth <= 12)
    if isinstance(value, dict):
        _require(len(value) <= 100)
        return {key: schema_projection(item, depth + 1)
                for key, item in value.items() if key in SCHEMA_FIELDS}
    if isinstance(value, list):
        _require(len(value) <= 2000)
        return [schema_projection(item, depth + 1) for item in value]
    if isinstance(value, str):
        _require(len(value) <= 16000 and "://" not in value)
        return value
    _require(value is None or type(value) in (int, bool, float))
    if type(value) is float:
        _require(math.isfinite(value))
    return value


def _specification(spec: dict, schemas: dict[str, dict]) -> dict:
    _require(isinstance(spec, dict))
    implementation = spec.get("implementation")
    _require(implementation in schemas)
    schema = schemas[implementation]
    fields = _named(schema.get("fields"), "name")
    supplied = _named(spec.get("fields"), "name")
    _require(set(supplied) <= set(fields))
    result = {key: deepcopy(spec[key]) for key in ("name", "implementation", "negate", "required")}
    _require(isinstance(result["name"], str))
    _require(type(result["negate"]) is bool and type(result["required"]) is bool)
    result["fields"] = []
    for name, field in fields.items():
        _require(name in supplied or "value" in field, "Native field has no reviewed value")
        value = supplied[name]["value"] if name in supplied else field["value"]
        kind = field.get("type")
        if kind == "checkbox":
            _require(type(value) is bool)
        elif kind == "textbox":
            _require(isinstance(value, str) and len(value) <= 16000)
        elif kind == "number":
            _require(type(value) in (int, float) and math.isfinite(value))
        elif kind == "select":
            _require(type(value) is int)
            options = field.get("selectOptions")
            _require(isinstance(options, list) and any(
                type(option.get("value")) is int and option["value"] == value for option in options))
        else:
            raise NativePolicyInstallationError("Native field type needs review")
        result["fields"].append({"name": name, "value": deepcopy(value)})
    return result


def _quality_leaves(items: list, depth: int = 0) -> tuple[dict[int, dict], set[int]]:
    _require(isinstance(items, list) and len(items) <= 100 and depth <= 4)
    leaves, groups = {}, set()
    for item in items:
        _require(isinstance(item, dict))
        if item.get("items"):
            groups.add(_id(item.get("id")))
            nested, nested_groups = _quality_leaves(item["items"], depth + 1)
            _require(not set(leaves).intersection(nested))
            leaves.update(nested)
            groups.update(nested_groups)
        else:
            quality = item.get("quality")
            _require(isinstance(quality, dict) and type(quality.get("id")) is int and quality["id"] >= 0)
            _require(quality["id"] not in leaves)
            leaves[quality["id"]] = deepcopy(quality)
    return leaves, groups


def compile_native_installation(snapshot: dict, schema_snapshot: dict) -> dict:
    """Compile creates against captured schemas; profile IDs remain unallocated."""
    try:
        plan = build_native_policy_plan(snapshot)
        _require(schema_snapshot.get("schema_version") == 1 and type(schema_snapshot["schema_version"]) is int)
        captured = schema_snapshot["instances"]
        _require(set(captured) == set(INSTANCES))
        instances = {}
        for name in INSTANCES:
            source, schemas = captured[name], captured[name]["schemas"]
            _require(isinstance(source.get("version"), str) and isinstance(source.get("image_id"), str))
            specification_schemas = _named(schemas["customformat/schema"], "implementation")
            profile_schema = schemas["qualityprofile/schema"]
            _require(isinstance(profile_schema, dict))
            required = {"items", "formatItems", "upgradeAllowed", "minFormatScore", "cutoff", "cutoffFormatScore", "minUpgradeFormatScore"}
            _require(required <= set(profile_schema))
            if name.startswith("radarr"):
                _require("language" in profile_schema)
            baseline = snapshot["instances"][name]
            baseline_formats = _rows(baseline["custom_formats"])
            schema_scores = {row["format"]: row["name"] for row in profile_schema["formatItems"]}
            _require(len(schema_scores) == len(profile_schema["formatItems"]))
            _require(schema_scores == {key: row["name"] for key, row in baseline_formats.items()})
            leaves, groups = _quality_leaves(profile_schema["items"])
            policy = plan["instances"][name]
            definitions = []
            for entry in policy["new_custom_formats"]:
                payload = deepcopy(entry["payload"])
                payload["specifications"] = [_specification(spec, specification_schemas) for spec in payload["specifications"]]
                definitions.append({"key": entry["key"], "payload": payload})
            profiles = {}
            # This is a client-defined quality equality-group ID, never a profile ID.
            group_id = max(groups | set(leaves) | {999}) + 1
            for mode in MODES:
                candidate = policy["new_profiles"][mode]
                selected = {row["id"]: row for row in candidate["quality_equality_group"]["qualities"]}
                _require(set(selected) <= set(leaves))
                _require(all(leaves[key] == value for key, value in selected.items()))
                disabled = [{"quality": deepcopy(value), "items": [], "allowed": False}
                            for key, value in leaves.items() if key not in selected]
                equality = {"id": group_id, "name": "Atlas supported qualities", "allowed": True,
                            "items": [{"quality": deepcopy(leaves[key]), "items": [], "allowed": True}
                                      for key in selected]}
                payload = {"name": candidate["name"], "upgradeAllowed": candidate["upgrade_allowed"],
                           "cutoff": group_id, "items": disabled + [equality],
                           "minFormatScore": candidate["minimum_format_score"],
                           "cutoffFormatScore": candidate["cutoff_format_score"],
                           "minUpgradeFormatScore": candidate["minimum_upgrade_score"]}
                if name.startswith("radarr"):
                    payload["language"] = deepcopy(candidate["radarr_language"])
                profiles[mode] = {"payload": payload, "owned_scores": deepcopy(candidate["custom_format_scores"])}
            instances[name] = {"version": source["version"], "image_id": source["image_id"],
                "schema_projection_sha256": {endpoint: _hash(value) for endpoint, value in schemas.items()},
                "preserved_profile_ids": policy["preserved_profile_ids"],
                "preserved_format_ids": policy["preserved_format_ids"],
                "baseline_profiles": deepcopy(baseline["profiles"]), "baseline_formats": deepcopy(baseline["custom_formats"]),
                "observed_proper_policy": policy["observed_instance_proper_repack_policy"],
                "custom_formats": definitions, "profiles": profiles}
        result = {"schema_version": 1, "kind": "native_policy_installation",
                  "source_snapshot_sha256": _hash(snapshot), "schema_snapshot_sha256": _hash(schema_snapshot),
                  "instances": instances, "activation_allowed": False,
                  "release_gates_preserved": plan["release_gates_preserved"]}
        return result
    except NativePolicyInstallationError:
        raise
    except Exception:
        raise NativePolicyInstallationError("Native payload compilation failed") from None


def profile_payload(instance: dict, mode: str, format_ids: dict[str, int]) -> dict:
    _require(mode in MODES)
    definitions = {entry["key"]: entry["payload"]["name"] for entry in instance["custom_formats"]}
    _require(set(format_ids) == set(definitions))
    ids = [_id(value) for value in format_ids.values()]
    _require(len(set(ids)) == len(ids) and not set(ids).intersection(instance["preserved_format_ids"]))
    result = deepcopy(instance["profiles"][mode]["payload"])
    result["formatItems"] = [{"format": row["id"], "name": row["name"], "score": 0}
                             for row in instance["baseline_formats"]]
    scores = instance["profiles"][mode]["owned_scores"]
    for key in definitions:
        result["formatItems"].append({"format": format_ids[key], "name": definitions[key], "score": scores[key]})
    return result


def _format_semantics(row: dict) -> dict:
    return {"name": row["name"], "includeCustomFormatWhenRenaming": row.get("includeCustomFormatWhenRenaming", False),
            "specifications": sorted([
                {"name": spec["name"], "implementation": spec["implementation"], "required": spec["required"],
                 "negate": spec["negate"], "fields": sorted(
                     [{"name": field["name"], "value": field.get("value")} for field in spec["fields"]],
                     key=lambda field: field["name"])} for spec in row["specifications"]],
                key=lambda spec: _encoded(spec))}


def _score_rows(rows: object) -> dict[int, dict]:
    _require(isinstance(rows, list) and len(rows) <= 4000)
    result = {}
    for row in rows:
        _require(isinstance(row, dict) and type(row.get("score")) is int)
        key = _id(row.get("format"))
        _require(key not in result)
        result[key] = row
    return result


def _profile_semantics(row: dict) -> dict:
    result = deepcopy(row)
    result.pop("id", None)
    result["formatItems"] = sorted(result["formatItems"], key=lambda item: item["format"])
    return result


class NativePolicyClient(Protocol):
    def read(self, endpoint: str) -> object: ...
    def create(self, endpoint: str, payload: dict) -> object: ...


class NativePolicyJournal:
    """Private fsynced journal; one writer and no removal/reset helper."""
    def __init__(self, root: Path):
        self.root = Path(root)
        _require(self.root.is_absolute())
        self.state: dict = {}

    def _path_guard(self) -> None:
        _require(not any(path.is_symlink() for path in (self.root, *self.root.parents)), "Journal path needs review")
        metadata = self.root.stat()
        _require(self.root.is_dir() and metadata.st_uid == os.geteuid() and stat.S_IMODE(metadata.st_mode) == 0o700,
                 "Journal directory must be private and owned")

    def _read(self, path: Path) -> dict:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            _require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid() and stat.S_IMODE(metadata.st_mode) == 0o600)
            raw = handle.read(20_000_001)
        _require(len(raw) <= 20_000_000)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                _require(key not in result)
                result[key] = value
            return result
        result = json.loads(raw, object_pairs_hook=unique)
        _require(isinstance(result, dict))
        return result

    @contextmanager
    def locked(self):
        self._path_guard()
        descriptor = os.open(self.root / "writer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            metadata = os.fstat(descriptor)
            _require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid() and stat.S_IMODE(metadata.st_mode) == 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise NativePolicyInstallationError("Native installation writer is already active") from None
            self._path_guard()
            path = self.root / "journal.json"
            self.state = self._read(path) if os.path.lexists(path) else {}
            yield self
        finally:
            os.close(descriptor)

    def save(self) -> None:
        self._path_guard()
        target = self.root / "journal.json"
        _require(not target.is_symlink())
        raw = _encoded(self.state)
        _require(len(raw) <= 20_000_000)
        descriptor, temporary = tempfile.mkstemp(prefix=".journal-", dir=self.root)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)


def _title_assignments(rows: object) -> dict[int, dict]:
    _require(isinstance(rows, list) and len(rows) <= 20000)
    result = {}
    for row in rows:
        _require(isinstance(row, dict))
        key = _id(row.get("id"))
        _require(key not in result and type(row.get("monitored")) is bool)
        result[key] = {"profile_id": _id(row.get("qualityProfileId")), "monitored": row["monitored"]}
        if "seasons" in row:
            seasons = row["seasons"]
            _require(isinstance(seasons, list))
            result[key]["seasons"] = sorted(
                [{"seasonNumber": season["seasonNumber"], "monitored": season["monitored"]} for season in seasons],
                key=lambda season: season["seasonNumber"])
    return result


class NativePolicyInstaller:
    def __init__(self, clients: dict[str, NativePolicyClient], journal: NativePolicyJournal,
                 guard: Callable[[], bool]):
        _require(set(clients) == set(INSTANCES) and callable(guard))
        self.clients, self.journal, self.guard = clients, journal, guard

    def _guard(self) -> None:
        _require(self.guard() is True, "Native installation guard is not satisfied")

    def _read(self, name: str, endpoint: str) -> object:
        try:
            return self.clients[name].read(endpoint)
        except Exception:
            raise NativePolicyInstallationError("Native read could not be verified") from None

    def _capture(self, name: str) -> dict:
        return {"profiles": self._read(name, "qualityprofile"), "formats": self._read(name, "customformat"),
                "management": self._read(name, "config/mediamanagement"),
                "titles": self._read(name, "movie" if name.startswith("radarr") else "series")}

    def _preserve(self, name: str, baseline: dict, receipts: dict) -> None:
        current = self._capture(name)
        old_formats, formats = _rows(baseline["formats"]), _rows(current["formats"])
        _require(all(key in formats and _hash(formats[key]) == _hash(row) for key, row in old_formats.items()),
                 "An existing native format changed")
        known_formats = {entry["id"] for entry in receipts.values() if entry["kind"] == "customformat" and entry["instance"] == name and entry["status"] == "verified"}
        pending_names = {entry["payload"]["name"] for entry in self.journal.state["operations"].values()
                         if entry["kind"] == "customformat" and entry["instance"] == name}
        additions = set(formats) - set(old_formats)
        _require(all(key in known_formats or formats[key]["name"] in pending_names for key in additions), "Unexpected native format appeared")
        old_profiles, profiles = _rows(baseline["profiles"]), _rows(current["profiles"])
        for key, old in old_profiles.items():
            _require(key in profiles, "Existing profile disappeared")
            before, after = deepcopy(old), deepcopy(profiles[key])
            before_scores = _score_rows(before.pop("formatItems"))
            after_scores = _score_rows(after.pop("formatItems"))
            _require(before == after and all(after_scores.get(identity) == value for identity, value in before_scores.items()),
                     "An existing native profile changed")
            _require(all(identity in additions and type(row.get("score")) is int and row["score"] == 0
                         for identity, row in after_scores.items() if identity not in before_scores),
                     "New native rows changed an existing score")
        known_profiles = {entry["id"] for entry in receipts.values() if entry["kind"] == "qualityprofile" and entry["instance"] == name and entry["status"] == "verified"}
        pending_profiles = {entry["payload"]["name"] for entry in self.journal.state["operations"].values()
                            if entry["kind"] == "qualityprofile" and entry["instance"] == name}
        _require(all(key in known_profiles or profiles[key]["name"] in pending_profiles for key in set(profiles) - set(old_profiles)),
                 "Unexpected native profile appeared")
        for entry in receipts.values():
            if entry["instance"] != name or entry["status"] != "verified":
                continue
            catalog = formats if entry["kind"] == "customformat" else profiles
            semantics = _format_semantics if entry["kind"] == "customformat" else _profile_semantics
            _require(entry["id"] in catalog and semantics(catalog[entry["id"]]) == semantics(entry["payload"]),
                     "Previously verified native policy changed")
        _require(_hash(current["management"]) == _hash(baseline["management"]), "Native management settings changed")
        _require(_title_assignments(current["titles"]) == _title_assignments(baseline["titles"]), "Managed title assignments or monitoring changed")

    def _create(self, name: str, kind: str, key: str, payload: dict) -> int:
        _require(kind in {"customformat", "qualityprofile"})
        _require(isinstance(payload.get("name"), str) and payload["name"].startswith("[Atlas v1] "), "Native creation target is outside Atlas ownership")
        self._guard()
        operation_key = name + ":" + kind + ":" + key
        operations = self.journal.state["operations"]
        row = operations.get(operation_key)
        if row is None:
            inventory = _rows(self._read(name, kind))
            _require(not any(item["name"].casefold() == payload["name"].casefold() for item in inventory.values()), "Owned native name already exists")
            row = {"instance": name, "kind": kind, "payload": deepcopy(payload),
                   "payload_sha256": _hash(payload), "before_ids": sorted(inventory), "status": "intent"}
            operations[operation_key] = row
            self.journal.save()  # Must succeed before issuing external work.
            self._guard()
            try:
                response = self.clients[name].create(kind, deepcopy(payload))
                _require(isinstance(response, dict))
                row["response_id"] = _id(response.get("id"))
                self.journal.save()
            except Exception:
                raise NativePolicyReconciliationRequired("Native creation outcome requires read-only reconciliation") from None
        _require(row["payload_sha256"] == _hash(payload) and row["payload"] == payload,
                 "Pending native operation payload changed")
        inventory = _rows(self._read(name, kind))
        candidates = [item for item in inventory.values() if item["name"].casefold() == payload["name"].casefold()]
        if not candidates:
            raise NativePolicyReconciliationRequired("Native intent has no visible receipt; creation will not be replayed")
        _require(len(candidates) == 1, "Native receipt is ambiguous")
        native = candidates[0]
        identity = _id(native.get("id"))
        _require(identity not in row["before_ids"] and ("response_id" not in row or row["response_id"] == identity), "Native receipt identity conflicts")
        semantics = _format_semantics if kind == "customformat" else _profile_semantics
        _require(semantics(native) == semantics(payload), "Native receipt differs from the intended payload")
        if row["status"] == "verified":
            _require(row["id"] == identity, "Verified native identity changed")
        row.update(status="verified", id=identity)
        self.journal.save()
        return identity

    def install(self, compiled: dict) -> dict:
        """Create unused policies only. Never change proper/repack or route requests."""
        _require(compiled.get("kind") == "native_policy_installation" and compiled.get("activation_allowed") is False)
        _require(set(compiled.get("instances", {})) == set(INSTANCES))
        self._guard()
        with self.journal.locked():
            state = self.journal.state
            compiled_hash = _hash(compiled)
            if not state:
                backups = {}
                for name in INSTANCES:
                    policy = compiled["instances"][name]
                    _require(self._read(name, "system/status")["version"] == policy["version"], "Native version changed")
                    for endpoint, fingerprint in policy["schema_projection_sha256"].items():
                        _require(_hash(schema_projection(self._read(name, endpoint))) == fingerprint, "Native schema changed")
                    backup = self._capture(name)
                    _require(set(_rows(backup["profiles"])) == set(policy["preserved_profile_ids"]))
                    _require(set(_rows(backup["formats"])) == set(policy["preserved_format_ids"]))
                    # Compare the captured public semantics, then preserve complete raw responses privately.
                    for row in policy["baseline_formats"]:
                        _require(_format_semantics(_rows(backup["formats"])[row["id"]]) == _format_semantics(row), "Baseline native format changed")
                    for row in policy["baseline_profiles"]:
                        native = _rows(backup["profiles"])[row["id"]]
                        _require(all(native.get(key) == value for key, value in row.items()), "Baseline native profile changed")
                    _require(backup["management"].get("downloadPropersAndRepacks") == policy["observed_proper_policy"], "Proper/repack policy changed")
                    _title_assignments(backup["titles"])
                    backups[name] = backup
                state.update(schema_version=1, compiled_sha256=compiled_hash, backups=backups, operations={}, status="prepared")
                self.journal.save()
            _require(state.get("schema_version") == 1 and state.get("compiled_sha256") == compiled_hash, "Journal belongs to a different native plan")
            profiles_by_instance = {}
            for name in INSTANCES:
                policy = compiled["instances"][name]
                self._guard()
                _require(self._read(name, "system/status")["version"] == policy["version"], "Native version changed")
                self._preserve(name, state["backups"][name], state["operations"])
                ids = {}
                for entry in policy["custom_formats"]:
                    ids[entry["key"]] = self._create(name, "customformat", entry["key"], entry["payload"])
                    self._preserve(name, state["backups"][name], state["operations"])
                profiles_by_instance[name] = {}
                for mode in MODES:
                    identity = self._create(name, "qualityprofile", mode, profile_payload(policy, mode, ids))
                    profiles_by_instance[name][mode] = identity
                    self._preserve(name, state["backups"][name], state["operations"])
            self._guard()
            for name in INSTANCES:
                self._preserve(name, state["backups"][name], state["operations"])
            state["status"] = "installed_not_activated"
            self.journal.save()
            return {"stage": "NATIVE_POLICIES_INSTALLED_NOT_ACTIVATED", "profile_ids": profiles_by_instance,
                    "activation_allowed": False, "proper_repack_policy_changed": False,
                    "release_gates_preserved": deepcopy(compiled["release_gates_preserved"])}
