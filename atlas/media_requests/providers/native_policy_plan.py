"""Build an offline, symbolic native policy plan. No service or file mutations."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

INSTANCES = ("radarr", "radarr-anime", "sonarr", "sonarr-anime")
MODES = ("english_preferred", "english_required", "original_subbed")
NEUTRAL_NAMES = frozenset({"Language: Not Original", "Dubs Only", "Anime Dual Audio"})
AUDIO_HINT = (
    r"\b(?:english|eng)[ ._-]*(?:audio|dub(?:bed)?)\b|"
    r"\b(?:\d{3,4}p|WEB[ ._-]?(?:DL|Rip)|Blu[ ._-]?Ray|BDRip|[xh][ ._-]?26[45]|HEVC|AV1)\b"
    r".*?\b(?:english|eng)\b(?![\s._\-\[\]()]*(?:sub(?:s|titles?|bed)?|cc|sdh|signs?|songs?)\b)"
)
HD_NAMES = frozenset({
    "HDTV-720p", "WEBDL-720p", "WEBRip-720p", "Bluray-720p",
    "HDTV-1080p", "WEBDL-1080p", "WEBRip-1080p", "Bluray-1080p",
    "Remux-1080p", "Bluray-1080p Remux", "HDTV-2160p", "WEBDL-2160p",
    "WEBRip-2160p", "Bluray-2160p", "Remux-2160p", "Bluray-2160p Remux",
})
SD_NAMES = frozenset({"SDTV", "DVD", "WEBDL-480p", "WEBRip-480p", "Bluray-480p", "Bluray-576p"})


class NativePolicyPlanError(ValueError):
    """The supplied snapshot cannot establish a complete isolated candidate."""


def _require(condition: bool) -> None:
    if not condition:
        raise NativePolicyPlanError("Native policy snapshot or candidate is invalid")


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _identity(value: object, *, zero: bool = False) -> int:
    _require(type(value) is int and value >= (0 if zero else 1))
    return value


def _unique(rows: object, field: str) -> dict[int, dict]:
    _require(isinstance(rows, list) and len(rows) <= 2000)
    result = {}
    for row in rows:
        _require(isinstance(row, dict))
        key = _identity(row.get(field))
        _require(key not in result and isinstance(row.get("name"), str))
        result[key] = row
    return result


def _qualities(profiles: dict[int, dict], allow_sd: bool) -> list[dict]:
    qualities = {}

    def visit(items: object, depth: int = 0) -> None:
        _require(isinstance(items, list) and len(items) <= 100 and depth <= 4)
        for item in items:
            _require(isinstance(item, dict))
            if item.get("items"):
                visit(item["items"], depth + 1)
            else:
                quality = item.get("quality")
                _require(isinstance(quality, dict))
                key = _identity(quality.get("id"), zero=True)
                _require(key not in qualities or qualities[key] == quality)
                qualities[key] = quality

    for profile in profiles.values():
        visit(profile.get("items"))
    names = HD_NAMES | (SD_NAMES if allow_sd else frozenset())
    selected = [deepcopy(row) for row in qualities.values() if row.get("name") in names]
    _require({720, 1080, 2160}.issubset({row.get("resolution") for row in selected}))
    _require(len({row["name"] for row in selected}) == len(selected))
    return sorted(selected, key=lambda row: (row.get("resolution", 0), row["id"]))


def _spec(implementation: str, value: object, *, negate: bool = False) -> dict:
    return {"name": implementation, "implementation": implementation,
            "required": True, "negate": negate, "fields": [{"name": "value", "value": value}]}


def _definition(key: str, label: str, specifications: list[dict]) -> dict:
    return {"key": key, "payload": {"name": "[Atlas v1] " + label,
            "includeCustomFormatWhenRenaming": False, "specifications": specifications}}


def _instance(name: str, row: dict, allow_anime_sd: bool) -> dict:
    _require(isinstance(row, dict))
    profiles = _unique(row.get("profiles"), "id")
    formats = _unique(row.get("custom_formats"), "id")
    _require(row.get("active_profile_id") == 7 and 7 in profiles)
    _require(row.get("proper_repack_policy") in {"preferAndUpgrade", "doNotUpgrade", "doNotPrefer"})
    _require(not any(item["name"].startswith("[Atlas v1]") for item in (*profiles.values(), *formats.values())))
    active = profiles[7]
    scores = active.get("formatItems")
    _require(isinstance(scores, list) and len(scores) <= 2000)
    baseline = {}
    for score in scores:
        _require(isinstance(score, dict) and type(score.get("score")) is int)
        key = _identity(score.get("format"))
        _require(key in formats and key not in baseline and score.get("name") == formats[key]["name"])
        baseline[key] = 0 if formats[key]["name"] in NEUTRAL_NAMES else score["score"]
    _require(set(baseline) == set(formats))
    positive = sum(max(score, 0) for score in baseline.values())
    soft = sum(-score for score in baseline.values() if -10000 < score < 0)
    step = positive + soft + 1
    bonus = 4 * step
    maximum = bonus + 3 * step + positive
    rejection = -maximum - 1
    _require(maximum < 2_147_483_647)
    definitions = []
    owned_scores = {}
    for key, score in baseline.items():
        if score == 0:
            continue
        original = formats[key]
        _require(isinstance(original.get("specifications"), list) and bool(original["specifications"]))
        symbolic = "base:" + str(key)
        definitions.append({"key": symbolic, "source_format_id": key,
            "source_format_sha256": _hash(original), "payload": {
                "name": "[Atlas v1] Base " + str(key) + " " + original["name"],
                "includeCustomFormatWhenRenaming": False,
                "specifications": deepcopy(original["specifications"])}})
        owned_scores[symbolic] = rejection if score <= -10000 else score
    english = _spec("LanguageSpecification", 1)
    definitions.extend([
        _definition("english_candidate", "English audio candidate", [english, _spec("ReleaseTitleSpecification", AUDIO_HINT)]),
        _definition("unsupported_language", "Neither English nor original", [
            _spec("LanguageSpecification", 1, negate=True), _spec("LanguageSpecification", -2, negate=True)]),
        _definition("not_english", "Not English", [_spec("LanguageSpecification", 1, negate=True)]),
        _definition("missing_english_hint", "Missing English audio hint", [_spec("ReleaseTitleSpecification", AUDIO_HINT, negate=True)]),
        _definition("not_original", "Not original", [_spec("LanguageSpecification", -2, negate=True)]),
    ])
    for resolution in (720, 1080, 2160):
        definitions.append(_definition("resolution:" + str(resolution), str(resolution) + "p", [
            _spec("ResolutionSpecification", resolution)]))
    _require(len({entry["payload"]["name"] for entry in definitions}) == len(definitions))
    qualities = _qualities(profiles, allow_anime_sd and "anime" in name)
    plans = {}
    for mode in MODES:
        values = {entry["key"]: 0 for entry in definitions}
        values.update(owned_scores)
        values["unsupported_language"] = rejection
        values["english_candidate"] = bonus if mode != "original_subbed" else 0
        for multiplier, resolution in enumerate((720, 1080, 2160), 1):
            values["resolution:" + str(resolution)] = multiplier * step
        if mode == "english_required":
            values["not_english"] = rejection
            values["missing_english_hint"] = rejection
        if mode == "original_subbed":
            values["not_original"] = rejection
        plans[mode] = {"name": "[Atlas v1] " + name + " " + mode,
            "upgrade_allowed": True, "minimum_format_score": 0, "minimum_upgrade_score": 1,
            "cutoff_format_score": maximum if mode != "original_subbed" else 3 * step + positive,
            "quality_equality_group": {"name": "Atlas supported qualities", "qualities": deepcopy(qualities)},
            "custom_format_scores": values,
            "radarr_language": {"id": -1, "name": "Any"} if name.startswith("radarr") else None,
            "full_english_subtitles_required_at_readiness": mode == "original_subbed"}
    return {"preserved_profile_ids": sorted(profiles), "preserved_format_ids": sorted(formats),
        "native_baseline_sha256": _hash(row), "required_instance_proper_repack_policy": "doNotPrefer",
        "observed_instance_proper_repack_policy": row["proper_repack_policy"],
        "score_bounds": {"base_positive_sum": positive, "base_soft_penalty_sum": soft,
            "resolution_step": step, "english_bonus": bonus, "hard_rejection_score": rejection,
            "maximum_positive_score": maximum}, "new_custom_formats": definitions,
        "new_profiles": plans, "sd_fallback_included": allow_anime_sd and "anime" in name}


def build_native_policy_plan(snapshot: dict, *, allow_anime_sd: bool = False) -> dict:
    """Return a candidate with symbolic IDs; never infer newly allocated native IDs."""
    try:
        _require(isinstance(snapshot, dict) and type(snapshot.get("schema_version")) is int and snapshot.get("schema_version") == 1)
        _require(type(allow_anime_sd) is bool)
        instances = snapshot.get("instances")
        _require(isinstance(instances, dict) and set(instances) == set(INSTANCES))
        result = {"schema_version": 1, "kind": "offline_native_policy_candidate",
            "source_snapshot_semantic_sha256": _hash(snapshot),
            "source_provenance": {field: snapshot.get(field) for field in
                ("canonical_head", "canonical_tree", "deployment_pointer")},
            "instances": {name: _instance(name, instances[name], allow_anime_sd) for name in INSTANCES},
            "activation_allowed": False, "native_ids_allocated": False,
            "release_gates_preserved": ["recyclarr_ownership_and_no_pruning", "native_candidate_acceptance",
                "instance_wide_proper_repack_impact", "spoken_audio_and_full_english_subtitles",
                "schema_migration_and_acquisition_activation", "delayed_uncertain_restart_receipt_outbox",
                "exact_episodes_future_follows_readiness", "retention", "sports_sharing_capacity", "release_reset"],
            "ownership_contract": {
                "existing_guide_profiles_and_definitions": "preserve",
                "atlas_profiles_and_definitions": "Atlas only; guide sync must not target or prune them",
                "existing_profile_new_format_rows": "new zero-score rows may be added by native services",
                "existing_titles_monitoring_and_search": "preserve; no reassignment or commands",
                "pruning_proof_verified": False, "cached_guide_identity_verified": False},
            "evidence": "Configuration candidate and arithmetic bounds only; no native or imported-media proof"}
        return result
    except NativePolicyPlanError:
        raise
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError):
        raise NativePolicyPlanError("Native policy snapshot or candidate is invalid") from None
