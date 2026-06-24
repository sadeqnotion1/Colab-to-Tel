"""Single source of truth for the dashboard/progress bar style.

M2 - Progress-System Unification.

Every renderer (progress_manager, task_dashboard, enhanced_status, ...) should
import BAR_STYLE from here instead of each calling os.environ.get(...) on its
own. This guarantees one consistent style across download / archive / upload.

Behavior is identical to the previous per-module definitions: the value is read
from the BAR_STYLE environment variable at import time, defaulting to 'gradient'.
"""

import os

_DEFAULT_BAR_STYLE = "gradient"


def get_bar_style() -> str:
    """Resolve the configured progress bar style (env-driven, safe default)."""
    return os.environ.get("BAR_STYLE", _DEFAULT_BAR_STYLE)


# Module-level constant kept for the existing `from .bar_style import BAR_STYLE`
# call sites. Resolved once at import, matching prior module-level behavior.
BAR_STYLE = get_bar_style()
