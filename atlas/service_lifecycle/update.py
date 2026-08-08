"""Compatibility alias for the Update Discovery service.

The canonical implementation lives in
:mod:`atlas.service_lifecycle.services.updates`.
"""

from __future__ import annotations

import sys

from .services import updates as _canonical_module


sys.modules[__name__] = _canonical_module
