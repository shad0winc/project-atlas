"""Compatibility alias for the Service Doctor implementation.

The canonical implementation lives in
:mod:`atlas.service_lifecycle.services.doctor`.
"""

from __future__ import annotations

import sys

from .services import doctor as _canonical_module


sys.modules[__name__] = _canonical_module
