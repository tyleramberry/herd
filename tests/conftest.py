"""Make the repo root importable as the ``herd`` package for tests."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_package() -> None:
    if "herd" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        "herd", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["herd"] = module
    spec.loader.exec_module(module)


_load_package()
