"""Compatibility alias for Service Lifecycle orchestration.

The canonical implementation lives in
:mod:`atlas.service_lifecycle.services.lifecycle`.

This legacy module path resolves to the canonical module object so imports,
private test hooks, monkeypatch targets, and module-level state remain fully
compatible during the incremental package migration.
"""

from __future__ import annotations

import sys

from .services import lifecycle as _canonical_module


sys.modules[__name__] = _canonical_module
