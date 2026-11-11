"""Preload the root package under the identity pytest uses for __init__.py.

pytest's Package collector imports the repository root ``__init__.py`` under the
synthetic top-level module name ``__init__`` while collecting ``tests/``. When the
checkout directory is not a valid Python identifier (e.g. ``hermes-multiplayer``), that import
fails on the relative imports and every test errors out. Preloading the same file
under that identity — with the repo root as its search path — makes the suite
independent of the checkout directory name. Test infrastructure only: pytest is
never imported by the installed plugin.
"""
import importlib.util
import os
import sys
from pathlib import Path

os.environ["HERMES_MULTIPLAYER_NO_ACK_DELAY"] = "1"
ROOT = Path(__file__).resolve().parent.parent

if "__init__" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "__init__", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["__init__"] = module
    spec.loader.exec_module(module)
