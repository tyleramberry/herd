"""Load the repo root as the ``herd`` package (the way Hermes imports a plugin directory)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load():
    if "herd" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "herd", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["herd"] = module
        spec.loader.exec_module(module)
    import herd.dashboard.herd_store as store  # noqa: E402
    import herd.tools as tools  # noqa: E402
    return sys.modules["herd"], store, tools
