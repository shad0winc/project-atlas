"""Compatibility alias for the Maintenance History service.

The canonical implementation lives in
:mod:`atlas.service_lifecycle.services.maintenance`.
"""

from __future__ import annotations

import sys

from .services import maintenance as _canonical_module


sys.modules[__name__] = _canonical_module
