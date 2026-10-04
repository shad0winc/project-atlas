"""Identity, routing and policy isolation for explicit acquisition wiring."""

import unittest
from unittest.mock import Mock, patch

from atlas.media_requests import MediaRequest, MediaRequestProviderError
from atlas.media_requests.providers.acquisition_factory import (
    SeerrTVDBResolver, build_acquisition_provider,
)
from atlas.media_requests.providers.managed_profiles import ArrProfileBinding


def request(**changes):
    fields = dict(request_id="resolver", user_id="viewer", media_type="tv",
                  provider="jellyseerr", provider_media_id="123", title="Fixture",
                  season_number=1, created_at="2026-10-04T02:29:54Z")
    fields.update(changes)
    return MediaRequest(**fields)


def inputs():
    routes = dict(movie=0, tv=0, anime_movie=1, anime_tv=1)
    bindings = {(c, s): ArrProfileBinding(f"http://{c}.invalid/api/v3", "synthetic")
                for c, s in routes.items()}
    profiles = {(c, mode): index for c in routes
                for index, mode in enumerate(("english_preferred", "english_required", "original_subbed"), 7)}
    return dict(base_url="http://seerr.invalid", api_key="synthetic",
                category_servers=routes, bindings=bindings, profile_ids=profiles,
                read_tv_metadata=Mock(return_value=dict(id=123, externalIds=dict(tvdbId=456))))


class ResolverTests(unittest.TestCase):
    def test_unseen_titles_resolve_by_identity_for_both_exact_bindings(self):
        for category, server, tmdb, tvdb in (("tv", 0, 123, 456), ("anime_tv", 1, 789, 987)):
            with self.subTest(category=category):
                read = Mock(return_value=dict(id=tmdb, externalIds=dict(tvdbId=tvdb)))
                resolver = SeerrTVDBResolver({"tv": 0, "anime_tv": 1}, read)
                self.assertEqual(tvdb, resolver(request(media_type=category, provider_media_id=str(tmdb)), server))
                read.assert_called_once_with(f"/api/v1/tv/{tmdb}")

    def test_binding_failures_block_before_metadata_read(self):
        read = Mock()
        resolver = SeerrTVDBResolver({"tv": 0}, read)
        cases = ((request(), 1), (request(), True), (request(), -1),
                 (request(media_type="anime_tv"), 1),
                 (request(media_type="movie", season_number=None), 0),
                 (request(provider="other"), 0))
        for row, server in cases:
            with self.subTest(category=row.media_type.value, server=server), self.assertRaises(MediaRequestProviderError):
                resolver(row, server)
        read.assert_not_called()

    def test_noncanonical_tmdb_never_reads(self):
        read = Mock()
        resolver = SeerrTVDBResolver({"tv": 0}, read)
        for tmdb in ("00123", "0", "1.0", "123abc"):
            with self.subTest(tmdb=tmdb), self.assertRaises(MediaRequestProviderError):
                resolver(request(provider_media_id=tmdb), 0)
        read.assert_not_called()

    def test_missing_malformed_and_conflicting_identity_fail_closed(self):
        cases = (None, [], {}, dict(id=124, externalIds=dict(tvdbId=456)),
                 dict(id=True, externalIds=dict(tvdbId=456)), dict(id="123", externalIds=dict(tvdbId=456)),
                 dict(id=123), dict(id=123, externalIds=[]),
                 dict(id=123, externalIds=dict(tvdbId=None)),
                 dict(id=123, externalIds=dict(tvdbId=True)),
                 dict(id=123, externalIds=dict(tvdbId="456")),
                 dict(id=123, externalIds=dict(tvdbId=0)),
                 dict(id=123, externalIds=dict(tvdbId=456), mediaInfo=dict(tmdbId=124)),
                 dict(id=123, externalIds=dict(tvdbId=456), mediaInfo=dict(tvdbId=457)),
                 dict(id=123, externalIds=dict(tvdbId=456), mediaInfo=[]))
        for reply in cases:
            with self.subTest(reply=reply), self.assertRaisesRegex(MediaRequestProviderError, "TVDB identity could not be verified"):
                SeerrTVDBResolver({"tv": 0}, Mock(return_value=reply))(request(), 0)

    def test_optional_managed_identity_corroborates(self):
        reply = dict(id=123, externalIds=dict(tvdbId=456), mediaInfo=dict(tmdbId=123, tvdbId=456))
        self.assertEqual(456, SeerrTVDBResolver({"tv": 0}, Mock(return_value=reply))(request(), 0))

    def test_private_transport_failure_is_sanitized(self):
        resolver = SeerrTVDBResolver({"tv": 0}, Mock(side_effect=RuntimeError("secret private URL")))
        with self.assertRaises(MediaRequestProviderError) as caught:
            resolver(request(), 0)
        self.assertNotIn("secret", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_routes_are_copied_not_live_mutable(self):
        routes = {"tv": 0}
        resolver = SeerrTVDBResolver(routes, Mock(return_value=dict(id=123, externalIds=dict(tvdbId=456))))
        routes["tv"] = 1
        self.assertEqual(456, resolver(request(), 0))
        with self.assertRaises(TypeError):
            resolver.category_servers["tv"] = 2


class FactoryTests(unittest.TestCase):
    def test_build_is_read_only_and_copies_all_maps(self):
        config = inputs()
        provider = build_acquisition_provider(**config)
        config["read_tv_metadata"].assert_not_called()
        config["category_servers"]["tv"] = 9
        config["bindings"].clear()
        config["profile_ids"].clear()
        self.assertEqual(0, provider.tv_server_id)
        self.assertEqual(12, len(provider.audio_profile_ids))
        self.assertEqual(4, len(provider.managed_profile_reader.bindings))

    def test_incomplete_or_extra_routes_bindings_and_policy_maps_block(self):
        for section in ("category_servers", "bindings", "profile_ids"):
            for mutation in ("missing", "extra"):
                config = inputs()
                if mutation == "missing":
                    config[section].pop(next(iter(config[section])))
                else:
                    config[section]["unexpected"] = 1
                with self.subTest(section=section, mutation=mutation), self.assertRaises(MediaRequestProviderError):
                    build_acquisition_provider(**config)
                config["read_tv_metadata"].assert_not_called()

    def test_same_policy_id_in_one_category_blocks(self):
        config = inputs()
        config["profile_ids"][("tv", "english_required")] = 7
        with self.assertRaises(MediaRequestProviderError):
            build_acquisition_provider(**config)

    def test_boolean_and_zero_profile_ids_block(self):
        for value in (True, 0, -1, "7"):
            config = inputs()
            config["profile_ids"][("tv", "english_required")] = value
            with self.subTest(value=value), self.assertRaises(MediaRequestProviderError):
                build_acquisition_provider(**config)

    def test_generalized_resolver_drives_bound_native_inventory(self):
        config = inputs()
        provider = build_acquisition_provider(**config)
        row = request(audio_preference="english_required")
        with patch.object(type(provider.managed_profile_reader), "_read_json", return_value=[dict(id=42, tvdbId=456, qualityProfileId=8)]) as read:
            provider.validate_submission(row)
        read.assert_called_once_with(config["bindings"][("tv", 0)], "series")
        config["read_tv_metadata"].assert_called_once_with("/api/v1/tv/123")

    def test_existing_incompatible_profile_still_blocks(self):
        provider = build_acquisition_provider(**inputs())
        with patch.object(type(provider.managed_profile_reader), "_read_json", return_value=[dict(id=42, tvdbId=456, qualityProfileId=7)]):
            with self.assertRaises(MediaRequestProviderError):
                provider.validate_submission(request(audio_preference="english_required"))

    def test_legacy_flow_does_not_consult_resolver_or_profile_reader(self):
        config = inputs()
        provider = build_acquisition_provider(**config)
        with patch.object(type(provider.managed_profile_reader), "_read_json") as read:
            provider.validate_submission(request())
        read.assert_not_called()
        config["read_tv_metadata"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
