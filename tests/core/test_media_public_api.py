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
