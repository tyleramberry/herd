"""Package contract: manifest ↔ registration, tool handler shape, desktop catalog lint (rule 8)."""
import inspect
import json
import os
import re
import sys
import unittest
from pathlib import Path

try:  # PyYAML is a test-only dependency (the plugin's runtime is stdlib-only); skip cleanly without it
    import yaml
except Exception:  # noqa: BLE001
    yaml = None

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

hermes_multiplayer, store, tools = _pkg.load()
ROOT = _pkg.ROOT
SOURCE = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")


def _manifest():
    assert yaml is not None  # ManifestTest is skip-guarded on this; keeps type checkers honest
    return yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))


class FakeCtx:
    def __init__(self):
        self.tools, self.platform, self.commands, self.injected = {}, {}, {}, []

    def register_tool(self, name, toolset, schema, handler, **kw):
        self.tools[name] = (toolset, schema, handler)

    def register_platform_handler(self, platform, factory):
        self.platform[platform] = factory

    def register_command(self, name, handler, description="", args_hint="", **kw):
        self.commands[name] = handler

    def inject_message(self, content, role="user", *, session_key=None, origin=None):
        self.injected.append((session_key, content))
        return True


@unittest.skipUnless(yaml is not None, "PyYAML not installed (pip install -r requirements-dev.txt)")
class ManifestTest(unittest.TestCase):
    def test_provides_tools_matches_register(self):
        ctx = FakeCtx()
        hermes_multiplayer.register(ctx)
        self.assertEqual(sorted(ctx.tools), sorted(_manifest()["provides_tools"]))
        self.assertEqual(sorted(ctx.tools),
                         ["multiplayer_list_channels", "multiplayer_post", "multiplayer_read_channel", "multiplayer_set_status"])
        self.assertEqual(list(ctx.platform), ["api_server"])
        for name, (_ts, schema, handler) in ctx.tools.items():
            self.assertEqual(schema["name"], name)
            params = inspect.signature(handler).parameters
            self.assertTrue(any(p.kind is p.VAR_KEYWORD for p in params.values()), name)
        status_schema = ctx.tools["multiplayer_set_status"][1]
        self.assertEqual(status_schema["parameters"]["properties"]["status"]["enum"], list(store.STATUS_PHRASES))
        self.assertEqual(status_schema["parameters"]["required"], ["status"])

    def test_manifest_fields(self):
        m = _manifest()
        self.assertEqual(m["name"], "hermes-multiplayer")
        self.assertIsInstance(m["version"], str)
        self.assertRegex(m["requires_hermes"], r"^>=\d+\.\d+\.\d+$")
        self.assertEqual(m["config_schema"]["peer_key"]["type"], "secret")
        self.assertEqual(m["config_schema"]["peer_key"]["env"], store.SECRET_ENV)
        dash = json.loads((ROOT / "dashboard" / "manifest.json").read_text())
        self.assertEqual((dash["name"], dash["api"]), ("hermes-multiplayer", "plugin_api.py"))
        self.assertTrue(dash["tab"]["hidden"])

    def test_no_env_or_dotenv_reads(self):
        for path in list(ROOT.glob("*.py")) + list((ROOT / "dashboard").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("os.environ", text, path)
            self.assertNotIn(".env", text.replace("env: HERMES_MULTIPLAYER", ""), path)
            self.assertNotIn("HERMES_PEER_", text, path)
            self.assertNotIn("sys.modules[", text, path)


class DesktopLintTest(unittest.TestCase):
    ALLOWED = {"@hermes/plugin-sdk", "react", "react/jsx-runtime"}

    def test_only_allowed_imports(self):
        specs = re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", SOURCE)
        specs += re.findall(r"^\s*import\s+['\"]([^'\"]+)['\"]", SOURCE, flags=re.M)
        self.assertTrue(specs)
        self.assertLessEqual(set(specs), self.ALLOWED)

    def test_no_dynamic_code_or_globals(self):
        for bad in ("import(", "require(", "eval(", "new Function", ".prototype", "window.", "document.",
                    "data-slot", "localStorage", "hermesDesktop", "fetch("):
            self.assertNotIn(bad, SOURCE, bad)

    def test_no_jsx_syntax(self):
        self.assertNotIn("</", SOURCE)
        self.assertNotIn("/>", SOURCE)

    def test_no_hardcoded_colors(self):
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", SOURCE))
        self.assertIsNone(re.search(r"\b(rgb|rgba|hsl|hsla|oklch)\(", SOURCE))

    def test_every_sdk_identifier_used_is_imported(self):
        imported = set(re.search(r"import \{([^}]*)\} from '@hermes/plugin-sdk'", SOURCE).group(1)
                       .replace("\n", " ").replace(" ", "").split(","))
        imported.discard("")
        for name in imported:
            self.assertGreater(len(re.findall(r"\b" + name + r"\b", SOURCE)), 1, f"{name} imported but unused")
        for comp in set(re.findall(r"jsxs?\(([A-Z][A-Za-z]+),", SOURCE)):
            local = re.search(r"function " + comp + r"\b", SOURCE)
            self.assertTrue(comp in imported or local, f"{comp} used but not imported/defined")

    def test_contract(self):
        for needle in ("id: PLUGIN_ID", "const PLUGIN_ID = 'hermes-multiplayer'", "defaultEnabled: false", "ROUTES_AREA",
                       "SIDEBAR_NAV_AREA", "PANES_AREA", "ctx.onEvent('plugin.hermes-multiplayer.message.created'",
                       "ctx.setInterval", "pluginSettingsHref(PLUGIN_ID)"):
            self.assertIn(needle, SOURCE, needle)


if __name__ == "__main__":
    unittest.main()
