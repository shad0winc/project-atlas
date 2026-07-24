"""Tests for the public Atlas media API."""

from atlas import media


def test_media_mutation_symbols_are_publicly_importable() -> None:
    assert media.ProviderOperation is not None
    assert media.ProviderMutationResult is not None
    assert media.ProviderMutationError is not None
    assert media.RecordingMediaProvider is not None


def test_media_capability_symbols_are_publicly_importable() -> None:
    assert media.ProviderCapability is not None
    assert media.ProviderCapabilities is not None
    assert media.ProviderCapabilityError is not None


def test_media_all_exports_mutation_symbols() -> None:
    expected = {
        "ProviderOperation",
        "ProviderMutationResult",
        "ProviderMutationError",
        "RecordingMediaProvider",
    }

    assert expected <= set(media.__all__)


def test_media_all_exports_capability_symbols() -> None:
    expected = {
        "ProviderCapability",
        "ProviderCapabilities",
        "ProviderCapabilityError",
    }

    assert expected <= set(media.__all__)


def test_media_mutation_dispatcher_symbols_are_publicly_importable() -> None:
    assert media.MediaMutationDispatcher is not None
    assert media.MediaMutationDispatchError is not None


def test_media_all_exports_mutation_dispatcher_symbols() -> None:
    assert "MediaMutationDispatcher" in media.__all__
    assert "MediaMutationDispatchError" in media.__all__


def test_media_mutation_mode_is_publicly_importable() -> None:
    assert media.MediaMutationMode is not None


def test_media_all_exports_mutation_mode() -> None:
    assert "MediaMutationMode" in media.__all__
