"""Static lint of desktop/plugin.js against the catalog admission rules."""
import re
from pathlib import Path

SOURCE = (Path(__file__).resolve().parent.parent / "desktop" / "plugin.js").read_text()
ALLOWED = {"@hermes/plugin-sdk", "react", "react/jsx-runtime"}


def test_only_allowed_import_specifiers():
    specifiers = re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", SOURCE)
    specifiers += re.findall(r"^\s*import\s+['\"]([^'\"]+)['\"]", SOURCE, flags=re.M)
    assert specifiers, "expected at least one import"
    assert set(specifiers) <= ALLOWED, set(specifiers) - ALLOWED


def test_no_dynamic_import_or_require():
    assert not re.search(r"\bimport\s*\(", SOURCE)
    assert "require(" not in SOURCE


def test_no_jsx_syntax():
    assert "</" not in SOURCE
    assert "/>" not in SOURCE
    assert not re.search(r"return\s*\(?\s*<[A-Za-z]", SOURCE)


def test_no_eval_or_bare_globals():
    assert "eval(" not in SOURCE
    assert "new Function" not in SOURCE
    assert "window.setInterval" not in SOURCE
    assert "window.setTimeout" not in SOURCE
    assert "window.addEventListener" not in SOURCE
    assert ".prototype" not in SOURCE


def test_no_hardcoded_colors():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", SOURCE)
    assert not re.search(r"\b(rgb|rgba|hsl|hsla|oklch)\(", SOURCE)


def test_plugin_contract():
    assert "id: PLUGIN_ID" in SOURCE and "const PLUGIN_ID = 'herd'" in SOURCE
    assert "defaultEnabled: false" in SOURCE
    for needle in ("ROUTES_AREA", "SIDEBAR_NAV_AREA", "PANES_AREA", "'comment-discussion'",
                   "host.onEvent('plugin.herd.message.created'", "ctx.setInterval"):
        assert needle in SOURCE, needle
