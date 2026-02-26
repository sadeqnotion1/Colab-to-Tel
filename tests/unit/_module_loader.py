from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(relative_path: str, module_name: str) -> ModuleType:
    """Load a module from a repo-relative file path without importing package __init__."""
    module_path = REPO_ROOT / relative_path
    spec = spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec: {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
