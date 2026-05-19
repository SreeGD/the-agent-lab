"""Shared test fixtures and helpers.

The labs/ files have lesson-number prefixes (e.g. `16_vibe_coding.py`), which
aren't valid Python identifiers. We use importlib to import them by path.
"""

import importlib.util
import sys
from pathlib import Path

LABS_DIR = Path(__file__).resolve().parent.parent


def load_lab(filename: str):
    """Load a labs/ module by filename. Handles digit-prefixed names."""
    path = LABS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    # Replace digits and special chars in the safe module name
    safe_name = "lab_" + filename.replace(".py", "").replace("-", "_")
    spec = importlib.util.spec_from_file_location(safe_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[safe_name] = module
    spec.loader.exec_module(module)
    return module
