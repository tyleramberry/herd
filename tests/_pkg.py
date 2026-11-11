"""Load the repo root as the ``hermes_multiplayer`` package (the way Hermes imports a plugin directory)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load():
    if "hermes_multiplayer" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "hermes_multiplayer", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["hermes_multiplayer"] = module
        spec.loader.exec_module(module)
    import hermes_multiplayer.dashboard.multiplayer_store as store  # noqa: E402
    import hermes_multiplayer.tools as tools  # noqa: E402
    return sys.modules["hermes_multiplayer"], store, tools
