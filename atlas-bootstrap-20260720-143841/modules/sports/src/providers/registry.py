#!/usr/bin/env python3

from __future__ import annotations

from providers.base import SportsProvider
from providers.thesportsdb import TheSportsDBProvider


def available_providers() -> list[SportsProvider]:
    return [
        TheSportsDBProvider(),
    ]


def enabled_providers() -> list[SportsProvider]:
    return [
        provider
        for provider in available_providers()
        if provider.enabled()
    ]
