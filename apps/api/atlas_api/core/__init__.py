"""Shared application configuration for the Atlas API."""

from .settings import AtlasAPISettings, SettingsError

__all__ = [
    "AtlasAPISettings",
    "SettingsError",
]
