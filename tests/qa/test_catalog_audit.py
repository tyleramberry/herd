"""Self-tests for scripts/qa/catalog_audit.py (Sentry Q-3).

Each test builds a tiny plugin tree in tmp_path and checks the audit's verdict.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("catalog_audit", ROOT / "scripts/qa/catalog_audit.py")
audit = importlib.util.module_from_spec(_spec)
sys.modules["catalog_audit"] = audit
_spec.loader.exec_module(audit)

GOOD_YAML = """\
name: hermes-multiplayer
version: "0.1.0"
requires_hermes: ">=0.22.7"
provides_tools:
  - multiplayer_list_channels
  - multiplayer_post
  - multiplayer_read_channel
  - multiplayer_set_status
provides_hooks: []
"""

GOOD_INIT = '''\
import json
from agent.secret_scope import get_secret


def _list(args=None, **kwargs):
    return json.dumps({"channels": []})


def _post(args=None, **kwargs):
    return json.dumps({"ok": True})


def _read(args=None, **kwargs):
    return json.dumps({"messages": []})


def _status(args=None, **kwargs):
    return json.dumps({"ok": True})


def register(ctx):
    ctx.register_tool(name="multiplayer_list_channels", toolset="hermes-multiplayer", schema={}, handler=_list)
    ctx.register_tool(name="multiplayer_post", toolset="hermes-multiplayer", schema={}, handler=_post)
    ctx.register_tool(name="multiplayer_read_channel", toolset="hermes-multiplayer", schema={}, handler=_read)
    ctx.register_tool(name="multiplayer_set_status", toolset="hermes-multiplayer", schema={}, handler=_status)
'''

GOOD_JS = """\
import { definePlugin } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

export default definePlugin((ctx) => {
  ctx.setInterval(() => ctx.rest('/messages'), 5000)
  return jsx('div', { style: { color: 'var(--ui-text-secondary)' } })
})
"""

README = "# Hermes Multiplayer\n\n## Disclosures\nNetwork calls: peer gateways only. Stored credentials: none.\n"

ENTRY = """\
name: hermes-multiplayer
repo: https://github.com/tyleramberry/hermes-multiplayer
sha: {sha}
description: Multiplayer Hermes.
maintainer: tyleramberry
tier: community
category: {category}
version: {version}
requires_hermes: ">=0.22.7"
capabilities:
  {tools_key}:
    - multiplayer_list_channels
    - multiplayer_post
    - multiplayer_read_channel
    - multiplayer_set_status
  provides_hooks: []
  provides_middleware: []
  requires_env: []
"""


def make_tree(tmp_path, *, init=GOOD_INIT, js=GOOD_JS, yaml=GOOD_YAML, readme=README):
    (tmp_path / "plugin.yaml").write_text(yaml)
    (tmp_path / "__init__.py").write_text(init)
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop/plugin.js").write_text(js)
    (tmp_path / "README.md").write_text(readme)
    return tmp_path


def run(tmp_path, *extra):
    rc = audit.main([str(tmp_path), *extra])
    return rc, list(audit.F)


def fails(findings):
    return [f for f in findings if f.level == "FAIL"]


@pytest.fixture(params=["pyyaml", "fallback"])
def yaml_mode(request, monkeypatch):
    if request.param == "fallback":
        monkeypatch.setitem(sys.modules, "yaml", None)
    return request.param


def test_good_tree_passes(tmp_path, yaml_mode):
    rc, f = run(make_tree(tmp_path))
    assert rc == 0, fails(f)


def test_undeclared_tool_fails(tmp_path, yaml_mode):
    init = GOOD_INIT + '    ctx.register_tool(name="multiplayer_secret_extra", toolset="hermes-multiplayer", schema={}, handler=_read)\n'
    rc, f = run(make_tree(tmp_path, init=init))
    assert rc == 1
    assert any(x.rule == "6" and "multiplayer_secret_extra" in x.msg for x in f)


def test_core_override_and_env_read_fail(tmp_path):
    init = GOOD_INIT + "import os\nimport run_agent\nrun_agent.AIAgent.chat = None\nKEY = os.environ['API_SERVER_KEY']\n"
    rc, f = run(make_tree(tmp_path, init=init))
    rules = {x.rule for x in fails(f)}
    assert {"9", "11"} <= rules


def test_handler_without_kwargs_fails(tmp_path):
    init = GOOD_INIT.replace("def _post(args=None, **kwargs):", "def _post(args=None):")
    rc, f = run(make_tree(tmp_path, init=init))
    assert any(x.rule == "TC-0.9" for x in fails(f))


def test_desktop_surface_violations_fail(tmp_path):
    js = GOOD_JS + "import x from 'lodash'\neval('1')\ndocument.querySelector('[data-slot=sidebar]')\n"
    rc, f = run(make_tree(tmp_path, js=js))
    msgs = " ".join(x.msg for x in fails(f))
    assert "lodash" in msgs and "eval" in msgs and "markup" in msgs


def test_bare_timer_and_hex_color_warn(tmp_path):
    js = GOOD_JS + "window.setInterval(() => {}, 10)\nconst c = '#ff0000'\n"
    rc, f = run(make_tree(tmp_path, js=js))
    assert rc == 0
    rules = {x.rule for x in f if x.level == "WARN"}
    assert {"TC-1.7", "TC-0.6"} <= rules


def test_binary_and_pyc_fail(tmp_path):
    t = make_tree(tmp_path)
    (t / "helper.so").write_bytes(b"\x7fELF" + b"\0" * 16)
    (t / "x.pyc").write_bytes(b"\0" * 8)
    rc, f = run(t)
    assert len([x for x in fails(f) if x.rule == "17"]) == 2


def test_secret_literal_fails(tmp_path):
    fake = "abcd1234" + "efgh5678ijkl"  # built at runtime so this file doesn't trip the scan itself
    init = GOOD_INIT + 'API_SERVER_KEY = "' + fake + '"\n'
    rc, f = run(make_tree(tmp_path, init=init))
    assert any(x.rule == "11" for x in fails(f))


def test_bad_requires_hermes_fails(tmp_path, yaml_mode):
    rc, f = run(make_tree(tmp_path, yaml=GOOD_YAML.replace('">=0.22.7"', '"2026.9.24"')))
    assert any(x.rule == "14" for x in fails(f))


def test_entry_cross_check(tmp_path, yaml_mode):
    t = make_tree(tmp_path / "p") if (tmp_path / "p").mkdir() is None else None
    good = tmp_path / "good.yaml"
    good.write_text(ENTRY.format(sha="a" * 40, category="desktop", version='"0.1.0"', tools_key="provides_tools"))
    rc, f = run(t, "--entry", str(good))
    assert rc == 0, fails(f)
    # The H-2 v1 draft's shape: wrong capability keys, unquoted version, short sha.
    bad = tmp_path / "bad.yaml"
    bad.write_text(ENTRY.format(sha="543c1fe", category="desktop", version="0.1.0", tools_key="tools"))
    rc, f = run(t, "--entry", str(bad))
    msgs = " ".join(x.msg for x in fails(f))
    assert rc == 1
    assert "40-hex" in msgs and "quoted" in msgs and "'tools'" in msgs


def test_non_secret_env_read_only_warns(tmp_path):
    init = GOOD_INIT + "import os\nGW = os.environ.get('HERMES_GATEWAY_ID')\n"
    rc, f = run(make_tree(tmp_path, init=init))
    assert rc == 0
    assert any(x.rule == "11" and x.level == "WARN" for x in f)


def test_pyc_inside_pycache_fails(tmp_path):
    t = make_tree(tmp_path)
    (t / "__pycache__").mkdir()
    (t / "__pycache__/tools.cpython-313.pyc").write_bytes(b"\0" * 8)
    rc, f = run(t)
    assert any(x.rule == "17" and "__pycache__" in x.where for x in fails(f))
