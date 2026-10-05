"""Exercise real payload assembly, preserved state and lost-response recovery."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlas.media_requests.providers.native_policy_plan import INSTANCES, MODES
from atlas.media_requests.providers.native_policy_installation import (
    NativePolicyInstallationError, NativePolicyReconciliationRequired,
    NativePolicyInstaller, NativePolicyJournal, compile_native_installation, profile_payload,
)


def fixture():
    qualities = [
        {"id": 1, "name": "WEBDL-720p", "resolution": 720},
        {"id": 2, "name": "WEBDL-1080p", "resolution": 1080},
        {"id": 3, "name": "WEBDL-2160p", "resolution": 2160},
        {"id": 4, "name": "DVD", "resolution": 480},
        {"id": 5, "name": "Raw-HD", "resolution": 1080},
        {"id": 0, "name": "Unknown", "resolution": 0},
    ]
    formats = [{"id": key, "name": name, "includeCustomFormatWhenRenaming": False,
                "specifications": [{"name": name, "implementation": "ReleaseTitleSpecification",
                 "required": True, "negate": False, "fields": [{"name": "value", "value": "Fixture"}]}]}
               for key, name in enumerate(("Tier", "Unsafe", "Unused"), 1)]
    profile = {"id": 7, "name": "Guide profile", "upgradeAllowed": True,
               "cutoff": 2, "minFormatScore": 0, "cutoffFormatScore": 100,
               "minUpgradeFormatScore": 1,
               "items": [{"quality": quality, "allowed": quality["resolution"] == 1080, "items": []}
                         for quality in qualities],
               "formatItems": [{"format": row["id"], "name": row["name"], "score": score}
                               for row, score in zip(formats, (100, -10000, 0))]}
    specifications = [
        {"implementation": "ReleaseTitleSpecification", "fields": [{"name": "value", "type": "textbox"}]},
        {"implementation": "LanguageSpecification", "fields": [
            {"name": "value", "type": "select", "selectOptions": [{"value": value} for value in (-2, -1, 0, 1)]},
            {"name": "exceptLanguage", "type": "checkbox", "value": False}]},
        {"implementation": "ResolutionSpecification", "fields": [
            {"name": "value", "type": "select", "selectOptions": [{"value": value} for value in (720, 1080, 2160)]}]},
    ]
    snapshot = {"schema_version": 1, "instances": {}}
    schema = {"schema_version": 1, "instances": {}}
    for name in INSTANCES:
        baseline = deepcopy(profile)
        if name.startswith("radarr"):
            baseline["language"] = {"id": -2, "name": "Original"}
        snapshot["instances"][name] = {"profiles": [baseline], "custom_formats": deepcopy(formats),
                                      "active_profile_id": 7, "proper_repack_policy": "preferAndUpgrade"}
        template = deepcopy(baseline)
        template.pop("id")
        for score in template["formatItems"]:
            score["score"] = 0
        schema["instances"][name] = {"version": "Fixture.1", "image_id": "sha256:fixture",
            "schemas": {"qualityprofile/schema": template, "customformat/schema": deepcopy(specifications)}}
    return snapshot, schema


class FakeNative:
    def __init__(self, baseline, schema):
        self.baseline = deepcopy(baseline)
        self.profiles = deepcopy(baseline["profiles"])
        self.formats = deepcopy(baseline["custom_formats"])
        self.schemas = deepcopy(schema["schemas"])
        self.version = schema["version"]
        self.management = {"downloadPropersAndRepacks": "preferAndUpgrade", "unrelated": "private-marker"}
        self.titles = [{"id": 44, "qualityProfileId": 7, "monitored": True,
                        "title": "private-marker", "seasons": [{"seasonNumber": 1, "monitored": True}]}]
        self.posts = []
        self.fault = None
        self.fault_kind = None
        self.read_fault = False

    def read(self, endpoint):
        if self.read_fault:
            raise RuntimeError("private URL and credentials")
        if endpoint == "system/status":
            return {"version": self.version}
        if endpoint in self.schemas:
            return deepcopy(self.schemas[endpoint])
        return deepcopy({"qualityprofile": self.profiles, "customformat": self.formats,
                         "config/mediamanagement": self.management,
                         "movie": self.titles, "series": self.titles}[endpoint])

    def create(self, endpoint, payload):
        assert endpoint in {"customformat", "qualityprofile"}
        self.posts.append((endpoint, deepcopy(payload)))
        fault = self.fault if self.fault_kind in (None, endpoint) else None
        if fault is not None:
            self.fault = None
        if fault == "before_commit":
            raise TimeoutError("private-marker")
        rows = self.formats if endpoint == "customformat" else self.profiles
        result = deepcopy(payload)
        result["id"] = max(row["id"] for row in rows) + 1
        if fault == "bad_payload":
            result["name"] += " changed"
        rows.append(result)
        if endpoint == "customformat":
            for profile in self.profiles:
                profile["formatItems"].append({"format": result["id"], "name": result["name"], "score": 0})
        if fault == "alter_existing_score":
            self.profiles[0]["formatItems"][0]["score"] += 1
        if fault == "alter_monitoring":
            self.titles[0]["seasons"][0]["monitored"] = False
        if fault == "after_commit":
            raise TimeoutError("private-marker")
        if fault == "wrong_id":
            return {"id": result["id"] + 100}
        return deepcopy(result)


class NativeInstallationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot, self.schema = fixture()
        self.compiled = compile_native_installation(self.snapshot, self.schema)
        self.clients = {name: FakeNative(self.snapshot["instances"][name], self.schema["instances"][name]) for name in INSTANCES}
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "journal"
        self.root.mkdir(mode=0o700)
        self.installer = NativePolicyInstaller(self.clients, NativePolicyJournal(self.root), lambda: True)
        self.addCleanup(self.directory.cleanup)

    def total_posts(self):
        return sum(len(client.posts) for client in self.clients.values())

    def test_complete_install_allocates_native_ids_and_preserves_guides_titles_and_management(self):
        result = self.installer.install(self.compiled)
        assert result["stage"] == "NATIVE_POLICIES_INSTALLED_NOT_ACTIVATED"
        assert result["activation_allowed"] is False
        assert result["proper_repack_policy_changed"] is False
        assert "sports_sharing_capacity" in result["release_gates_preserved"]
        for name, client in self.clients.items():
            assert client.titles[0]["qualityProfileId"] == 7
            assert client.titles[0]["monitored"]
            assert client.management["downloadPropersAndRepacks"] == "preferAndUpgrade"
            assert len(result["profile_ids"][name]) == 3
            assert 7 not in result["profile_ids"][name].values()
            assert client.formats[:3] == self.snapshot["instances"][name]["custom_formats"]
            assert [row["score"] for row in client.profiles[0]["formatItems"][:3]] == [100, -10000, 0]
            assert all(row["score"] == 0 for row in client.profiles[0]["formatItems"][3:])
            for profile in client.profiles[1:]:
                assert [row["score"] for row in profile["formatItems"][:3]] == [0, 0, 0]
        assert (self.root / "journal.json").stat().st_mode & 0o777 == 0o600
        assert (self.root / "writer.lock").stat().st_mode & 0o777 == 0o600

    def test_verified_resume_is_readback_only_and_keeps_native_ids(self):
        first = self.installer.install(self.compiled)
        posts = self.total_posts()
        second = self.installer.install(self.compiled)
        assert second == first and self.total_posts() == posts

    def test_lost_response_after_commit_reconciles_without_duplicate_creation(self):
        self.clients["radarr"].fault = "after_commit"
        with self.assertRaises(NativePolicyReconciliationRequired):
            self.installer.install(self.compiled)
        assert self.total_posts() == 1
        result = self.installer.install(self.compiled)
        assert result["activation_allowed"] is False
        assert self.total_posts() == sum(len(row["custom_formats"]) + 3 for row in self.compiled["instances"].values())

    def test_lost_response_without_visible_commit_never_replays(self):
        self.clients["radarr"].fault = "before_commit"
        with self.assertRaises(NativePolicyReconciliationRequired):
            self.installer.install(self.compiled)
        for _ in range(2):
            with self.assertRaises(NativePolicyReconciliationRequired):
                self.installer.install(self.compiled)
        assert self.total_posts() == 1

    def test_delayed_creation_becomes_visible_then_resume_accepts_exact_receipt(self):
        client = self.clients["radarr"]
        client.fault = "before_commit"
        with self.assertRaises(NativePolicyReconciliationRequired):
            self.installer.install(self.compiled)
        kind, payload = client.posts[0]
        # Emulate the original server request committing later, not a client retry.
        committed = deepcopy(payload)
        committed["id"] = 4
        client.formats.append(committed)
        client.profiles[0]["formatItems"].append({"format": 4, "name": committed["name"], "score": 0})
        self.installer.install(self.compiled)
        assert len([post for post in client.posts if post == (kind, payload)]) == 1

    def test_lost_profile_response_is_reconciled_without_recreating_formats_or_profile(self):
        client = self.clients["radarr"]
        client.fault, client.fault_kind = "after_commit", "qualityprofile"
        with self.assertRaises(NativePolicyReconciliationRequired):
            self.installer.install(self.compiled)
        profile_posts = [post for post in client.posts if post[0] == "qualityprofile"]
        assert len(profile_posts) == 1
        self.installer.install(self.compiled)
        assert len([post for post in client.posts if post == profile_posts[0]]) == 1

    def test_conflicting_name_candidates_require_reconciliation_and_no_post_replay(self):
        client = self.clients["radarr"]
        client.fault = "after_commit"
        with self.assertRaises(NativePolicyReconciliationRequired):
            self.installer.install(self.compiled)
        conflicting = deepcopy(client.formats[-1])
        conflicting["id"] += 1
        client.formats.append(conflicting)
        with self.assertRaises(NativePolicyInstallationError):
            self.installer.install(self.compiled)
        assert self.total_posts() == 1

    def test_verified_owned_definition_drift_blocks_resume(self):
        self.installer.install(self.compiled)
        posts = self.total_posts()
        self.clients["radarr"].formats[-1]["specifications"][0]["fields"][0]["value"] = 720
        with self.assertRaises(NativePolicyInstallationError):
            self.installer.install(self.compiled)
        assert self.total_posts() == posts

    def test_duplicate_appended_score_rows_are_rejected(self):
        self.installer.install(self.compiled)
        posts = self.total_posts()
        client = self.clients["radarr"]
        client.profiles[0]["formatItems"].append(deepcopy(client.profiles[0]["formatItems"][-1]))
        with self.assertRaises(NativePolicyInstallationError):
            self.installer.install(self.compiled)
        assert self.total_posts() == posts

    def test_conflicting_response_id_stops_and_cannot_be_adopted_on_resume(self):
        self.clients["radarr"].fault = "wrong_id"
        for _ in range(2):
            with self.assertRaises(NativePolicyInstallationError):
                self.installer.install(self.compiled)
        assert self.total_posts() == 1

    def test_changed_existing_score_or_monitoring_stops_further_posts(self):
        for fault in ("alter_existing_score", "alter_monitoring"):
            with self.subTest(fault=fault):
                self.setUp()
                self.clients["radarr"].fault = fault
                with self.assertRaises(NativePolicyInstallationError):
                    self.installer.install(self.compiled)
                assert self.total_posts() == 1

    def test_case_insensitive_owned_name_collision_stops_before_post(self):
        client = self.clients["radarr"]
        original = client.read
        calls = 0
        def conflicting_read(endpoint):
            nonlocal calls
            if endpoint == "customformat":
                calls += 1
                if calls == 3:
                    candidate = deepcopy(self.compiled["instances"]["radarr"]["custom_formats"][0]["payload"])
                    candidate["id"] = 4
                    candidate["name"] = candidate["name"].upper()
                    client.formats.append(candidate)
            return original(endpoint)
        client.read = conflicting_read
        with self.assertRaises(NativePolicyInstallationError):
            self.installer.install(self.compiled)
        assert self.total_posts() == 0

    def test_native_version_schema_and_baseline_drift_fail_before_any_post(self):
        for case in ("version", "schema", "baseline", "proper"):
            with self.subTest(case=case):
                self.setUp()
                client = self.clients["radarr"]
                if case == "version":
                    client.version = "Changed"
                elif case == "schema":
                    client.schemas["customformat/schema"][0]["fields"][0]["type"] = "private-marker"
                elif case == "baseline":
                    client.formats[0]["specifications"][0]["fields"][0]["value"] = "Changed"
                else:
                    client.management["downloadPropersAndRepacks"] = "doNotPrefer"
                with self.assertRaises(NativePolicyInstallationError):
                    self.installer.install(self.compiled)
                assert self.total_posts() == 0

    def test_guard_failure_and_intent_persistence_failure_prevent_post(self):
        self.installer.guard = lambda: False
        with self.assertRaises(NativePolicyInstallationError):
            self.installer.install(self.compiled)
        assert self.total_posts() == 0
        self.installer.guard = lambda: True
        original = self.installer.journal.save
        def fail_intent():
            if self.installer.journal.state["operations"]:
                raise OSError("private-marker")
            original()
        with patch.object(self.installer.journal, "save", fail_intent):
            with self.assertRaises(OSError):
                self.installer.install(self.compiled)
        assert self.total_posts() == 0

    def test_receipt_persistence_failure_recovers_from_durable_intent(self):
        original = self.installer.journal.save
        def fail_receipt():
            if any("response_id" in row for row in self.installer.journal.state["operations"].values()):
                raise OSError("private-marker")
            original()
        with patch.object(self.installer.journal, "save", fail_receipt):
            with self.assertRaises(NativePolicyReconciliationRequired):
                self.installer.install(self.compiled)
        assert self.total_posts() == 1
        self.installer.install(self.compiled)
        assert self.total_posts() == sum(len(row["custom_formats"]) + 3 for row in self.compiled["instances"].values())

    def test_private_errors_hide_transport_data(self):
        self.clients["radarr"].read_fault = True
        with self.assertRaises(NativePolicyInstallationError) as error:
            self.installer.install(self.compiled)
        assert "private" not in str(error.exception) and "credentials" not in str(error.exception)

    def test_journal_rejects_another_plan_symlinks_and_unprotected_modes(self):
        self.installer.install(self.compiled)
        changed = deepcopy(self.compiled)
        changed["instances"]["radarr"]["profiles"]["english_required"]["payload"]["minFormatScore"] = 1
        with self.assertRaises(NativePolicyInstallationError):
            self.installer.install(changed)
        link = self.root.parent / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(NativePolicyInstallationError):
            with NativePolicyJournal(link).locked():
                pass
        (self.root / "journal.json").chmod(0o644)
        with self.assertRaises(NativePolicyInstallationError):
            self.installer.install(self.compiled)

    def test_single_writer_lock(self):
        with NativePolicyJournal(self.root).locked():
            with self.assertRaises(NativePolicyInstallationError):
                with NativePolicyJournal(self.root).locked():
                    pass

    def test_compiler_preserves_input_and_emits_complete_fields_and_disabled_qualities(self):
        original = deepcopy((self.snapshot, self.schema))
        assert self.compiled == compile_native_installation(self.snapshot, self.schema)
        assert (self.snapshot, self.schema) == original
        row = self.compiled["instances"]["radarr"]
        language = next(spec for item in row["custom_formats"] for spec in item["payload"]["specifications"]
                        if spec["implementation"] == "LanguageSpecification")
        assert next(field for field in language["fields"] if field["name"] == "exceptLanguage")["value"] is False
        ids = {entry["key"]: index for index, entry in enumerate(row["custom_formats"], 100)}
        payload = profile_payload(row, "english_required", ids)
        assert "id" not in payload and payload["language"] == {"id": -1, "name": "Any"}
        assert all(not item["allowed"] for item in payload["items"][:-1])
        assert {item["quality"]["resolution"] for item in payload["items"][-1]["items"]} == {720, 1080, 2160}
        assert payload["cutoff"] == payload["items"][-1]["id"]

    def test_compiler_rejects_unknown_implementation_fields_and_invalid_options(self):
        for case in ("implementation", "field", "option", "required_default", "catalog"):
            with self.subTest(case=case):
                schema = deepcopy(self.schema)
                specs = schema["instances"]["radarr"]["schemas"]["customformat/schema"]
                if case == "implementation":
                    specs[0]["implementation"] = "UnknownSpecification"
                elif case == "field":
                    specs[0]["fields"][0]["type"] = "unknown"
                elif case == "option":
                    specs[1]["fields"][0]["selectOptions"] = [{"value": 0}]
                elif case == "required_default":
                    del specs[1]["fields"][1]["value"]
                else:
                    schema["instances"]["radarr"]["schemas"]["qualityprofile/schema"]["formatItems"].pop()
                with self.assertRaises(NativePolicyInstallationError):
                    compile_native_installation(self.snapshot, schema)

    def test_profile_payload_rejects_guessed_overlapping_or_duplicate_native_ids(self):
        row = self.compiled["instances"]["radarr"]
        for bad in (1, True, 0):
            ids = {entry["key"]: bad for entry in row["custom_formats"]}
            with self.assertRaises(NativePolicyInstallationError):
                profile_payload(row, MODES[0], ids)
