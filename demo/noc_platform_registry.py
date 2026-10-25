"""Compatibility import for existing repository-level NOC checks.

The canonical registry lives in app/portal so the existing portal image can
use it without copying the repository-level demo package into the container.
"""
from pathlib import Path
import sys

_APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from portal.platform_registry import (  # noqa: E402
    CATEGORIES,
    COMPONENTS,
    STATES,
    _parse_utc_z,
    build_portal_component_registry,
)

__all__ = [
    "CATEGORIES", "COMPONENTS", "STATES", "_parse_utc_z",
    "build_portal_component_registry",
]
