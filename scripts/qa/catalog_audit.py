#!/usr/bin/env python3
"""Sentry Q-3: static catalog-rules audit for the Herd plugin.

Checks the plugin tree against the Hermes plugin-catalog admission rules
(plugin-catalog/README.md in NousResearch/hermes-agent) that can be checked
statically, BEFORE `hermes plugins validate` runs. It complements validate; it
does not replace it. Stdlib only, so it runs on a clean machine.

    python scripts/qa/catalog_audit.py [PLUGIN_ROOT] [--entry path/to/herd.yaml]
                                       [--expect-tools a,b,c]

Exit code 0 = no FAIL findings (WARN findings still need a human read),
1 = at least one FAIL.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --- tiny YAML subset reader (plugin.yaml / catalog entry are flat) ---------

def _scalar(v: str):
    v = v.strip()
    if " #" in v:
        v = v.split(" #", 1)[0].strip()
    if v in ("", "~", "null"):
        return None
    if v in ("[]",):
        return []
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return _Quoted(v[1:-1])
    return v


class _Quoted(str):
    """A YAML scalar that was quoted in the source (rule: quote `version`)."""


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        # PyYAML loses quoting; recover it for `version`.
        m = re.search(r"^version:\s*(['\"])", text, re.M)
        if m and isinstance(data.get("version"), str):
            data["version"] = _Quoted(data["version"])
        return data
    except ImportError:
        pass
    root: dict = {}
    stack: list[tuple[int, object]] = [(-1, root)]
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            if isinstance(parent, list):
                parent.append(_scalar(line[2:]))
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        if val.strip() in ("", ">-", ">", "|", "|-"):
            # child block: list or mapping, decided by the next line
            child: object = {}
            if isinstance(parent, dict):
                parent[key] = child
            stack.append((indent, child))
            continue
        if isinstance(parent, dict):
            parent[key] = _scalar(val)
    # convert dicts that only received list items
    return _fix_lists(root, path)


def _fix_lists(node, path: Path):
    # second pass: re-read list blocks (simple parser above stores them as {})
    text = path.read_text(encoding="utf-8").splitlines()
    def collect(key_line_idx: int, indent: int):
        items = []
        for raw in text[key_line_idx + 1:]:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            ind = len(raw) - len(raw.lstrip())
            if ind <= indent:
                break
            if raw.strip().startswith("- "):
                items.append(_scalar(raw.strip()[2:]))
            else:
                return None
        return items
    for i, raw in enumerate(text):
        s = raw.strip()
        if not s or s.startswith("#") or ":" not in s or s.startswith("- "):
            continue
        key, _, val = s.partition(":")
        if val.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        items = collect(i, indent)
        if items:
            _set_first_empty(node, key.strip(), items)
    return node


def _set_first_empty(node, key, items):
    if isinstance(node, dict):
        if key in node and node[key] == {}:
            node[key] = items
            return True
        for v in node.values():
            if _set_first_empty(v, key, items):
                return True
    return False


# --- findings ---------------------------------------------------------------

@dataclass
class Finding:
    level: str  # FAIL | WARN | INFO
    rule: str
    where: str
    msg: str


F: list[Finding] = []


def add(level, rule, where, msg):
    F.append(Finding(level, rule, str(where), msg))


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}
SELF = Path(__file__).resolve()


def iter_files(root: Path):
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.is_file() and p.resolve() != SELF:
            yield p


def rel(root: Path, p: Path) -> str:
    return str(p.relative_to(root))


# --- rule 17: no unscannable executable payloads -----------------------------

MAGIC = {
    b"\x7fELF": "ELF binary",
    b"\xcf\xfa\xed\xfe": "Mach-O binary",
    b"\xce\xfa\xed\xfe": "Mach-O binary",
    b"\xca\xfe\xba\xbe": "Mach-O universal / Java class",
    b"\x00asm": "WebAssembly",
}


def tracked_files(root: Path):
    """Files a reviewer sees at the pin: git-tracked ones (incl. __pycache__), else everything."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True)
        names = [n for n in out.stdout.decode().split("\0") if n]
        if names:
            return [root / n for n in names if (root / n).is_file()]
    except (OSError, subprocess.CalledProcessError):
        pass
    return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts]


def check_binaries(root: Path):
    for p in tracked_files(root):
        if p.suffix in (".pyc", ".pyo"):
            add("FAIL", "17", rel(root, p), "committed Python bytecode")
            continue
        try:
            head = p.open("rb").read(4)
        except OSError:
            continue
        for magic, kind in MAGIC.items():
            if head.startswith(magic):
                add("FAIL", "17", rel(root, p), kind)
        if head[:2] == b"MZ":
            add("FAIL", "17", rel(root, p), "PE/MZ executable")


# --- secrets (rule 11 + Q-1 TC-0.7) ------------------------------------------

SECRET_RES = [
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "API key (sk-...)"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"""(?i)(api_server_key|secret|token|password)\s*[:=]\s*['"][A-Za-z0-9_\-]{12,}['"]"""),
     "hardcoded credential-looking literal"),
]
TEXT_EXT = {".py", ".js", ".mjs", ".ts", ".json", ".yaml", ".yml", ".md", ".toml", ".cfg", ".ini", ".txt", ".env", ".sh"}


def check_secrets(root: Path):
    for p in iter_files(root):
        if p.name == ".env" or p.name.endswith(".env"):
            add("FAIL", "11", rel(root, p), ".env file committed")
        if p.suffix not in TEXT_EXT:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for rx, kind in SECRET_RES:
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                add("FAIL", "11", f"{rel(root, p)}:{line}", f"possible secret: {kind}")


# --- Python checks (rules 6, 9, 11, 12, 13; Q-1 TC-0.8–0.10) -----------------

CORE_PKGS = ("hermes_cli", "agent", "gateway", "run_agent", "tools", "pm", "hermes_bootstrap", "plugins")
# Core modules the plugin developer guide / Desktop SDK docs tell plugins to import.
DOCUMENTED_CORE = {"agent.secret_scope", "hermes_cli.config", "hermes_cli.plugins",
                   "hermes_cli.plugin_events", "plugins.plugin_storage"}
SECRETISH = re.compile(r"(?i)key|token|secret|passw|auth|cred")


def _env_finding(where, name):
    if name is None or SECRETISH.search(name):
        add("FAIL", "11", where, f"reads os.environ{'[' + repr(name) + ']' if name else ''} directly — "
            "secrets must come from agent.secret_scope.get_secret(NAME)")
    else:
        add("WARN", "11", where, f"reads env var {name!r} directly — fine if not a secret; "
            "note get_secret honours the active profile, os.environ does not")


class PyVisitor(ast.NodeVisitor):
    def __init__(self, root, path):
        self.root, self.path = root, path
        self.where = rel(root, path)
        self.core_aliases: set[str] = set()
        self.tools: list[tuple[str, int, ast.AST | None]] = []
        self.hooks: list[tuple[str, int]] = []
        self.middleware: list[tuple[str, int]] = []
        self.funcs: dict[str, ast.FunctionDef] = {}

    def at(self, node):
        return f"{self.where}:{getattr(node, 'lineno', '?')}"

    def visit_Import(self, node):
        for a in node.names:
            top = a.name.split(".")[0]
            if top in CORE_PKGS:
                self.core_aliases.add((a.asname or a.name).split(".")[0])
            if top in ("subprocess",):
                add("WARN", "13", self.at(node), "imports subprocess — shell-out must be disclosed (rule 13) and respect approvals (rule 12)")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        mod = node.module or ""
        top = mod.split(".")[0]
        if top in CORE_PKGS:
            for a in node.names:
                self.core_aliases.add(a.asname or a.name)
            if mod not in DOCUMENTED_CORE:
                add("WARN", "9", self.at(node), f"imports core module '{mod}' — validate warns on undocumented core imports; confirm it is a public surface")
        if top == "subprocess":
            add("WARN", "13", self.at(node), "imports from subprocess — disclose shell commands")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.funcs[node.name] = node
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def _target_root(self, t):
        while isinstance(t, (ast.Attribute, ast.Subscript)):
            t = t.value
        return t.id if isinstance(t, ast.Name) else None

    def visit_Assign(self, node):
        for t in node.targets:
            self._check_store(t, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._check_store(node.target, node)
        self.generic_visit(node)

    def _check_store(self, t, node):
        if isinstance(t, (ast.Attribute, ast.Subscript)):
            r = self._target_root(t)
            if r in self.core_aliases:
                add("FAIL", "9", self.at(node), f"assigns into core object '{r}' (runtime override)")
            if r == "sys" and isinstance(t, ast.Subscript):
                add("FAIL", "9", self.at(node), "writes sys.modules")
            if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute) and t.value.attr == "modules":
                add("FAIL", "9", self.at(node), "writes sys.modules")

    def visit_Call(self, node):
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        if name in ("eval", "exec") and isinstance(fn, ast.Name):
            add("FAIL", "7", self.at(node), f"{name}() — security scan will flag as dangerous")
        if name == "setattr" and node.args:
            r = self._target_root(node.args[0])
            if r in self.core_aliases:
                add("FAIL", "9", self.at(node), f"setattr on core object '{r}'")
        if name == "getenv" or (isinstance(fn, ast.Attribute) and name == "get" and
                                 isinstance(fn.value, ast.Attribute) and fn.value.attr == "environ"):
            arg = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
            _env_finding(self.at(node), arg)
        if name in ("system", "popen", "run", "Popen", "check_output", "check_call") and isinstance(fn, ast.Attribute) and \
                isinstance(fn.value, ast.Name) and fn.value.id in ("os", "subprocess"):
            add("WARN", "12/13", self.at(node), f"{fn.value.id}.{name}() — shell command: disclose and route through approvals")
        if name == "open" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            s = node.args[0].value
            if s.endswith(".env") or "auth.json" in s:
                add("FAIL", "11", self.at(node), f"opens credential file '{s}'")
        if name in ("register_tool", "register_hook", "register_middleware"):
            tool_name = None
            handler = None
            for kw in node.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    tool_name = kw.value.value
                if kw.arg == "handler":
                    handler = kw.value
            if tool_name is None and node.args and isinstance(node.args[0], ast.Constant):
                tool_name = node.args[0].value
            if tool_name is None:
                add("WARN", "6", self.at(node), f"{name}() with a non-literal name — capability match must be checked by hand")
            elif name == "register_tool":
                self.tools.append((tool_name, node.lineno, handler))
            elif name == "register_hook":
                self.hooks.append((tool_name, node.lineno))
            else:
                self.middleware.append((tool_name, node.lineno))
            for kw in node.keywords:
                if kw.arg == "override" and isinstance(kw.value, ast.Constant) and kw.value.value:
                    add("WARN", "9", self.at(node), "register_tool(override=True) replaces a core tool — needs explicit grant and reviewer sign-off")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        v = node.value
        if isinstance(v, ast.Attribute) and v.attr == "environ" and isinstance(node.ctx, ast.Load):
            arg = node.slice.value if isinstance(node.slice, ast.Constant) else None
            _env_finding(self.at(node), arg)
        self.generic_visit(node)


def check_python(root: Path):
    tools, hooks, mws = {}, {}, {}
    for p in iter_files(root):
        if p.suffix != ".py" or "tests" in p.relative_to(root).parts or "scripts" in p.relative_to(root).parts:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except SyntaxError as e:
            add("FAIL", "load", rel(root, p), f"syntax error: {e}")
            continue
        v = PyVisitor(root, p)
        v.visit(tree)
        for name, line, handler in v.tools:
            tools[name] = f"{v.where}:{line}"
            if isinstance(handler, ast.Name) and handler.id in v.funcs:
                fd = v.funcs[handler.id]
                if fd.args.kwarg is None:
                    add("FAIL", "TC-0.9", f"{v.where}:{fd.lineno}", f"tool handler '{fd.name}' does not accept **kwargs")
                for node in ast.walk(fd):
                    if isinstance(node, ast.Return) and isinstance(node.value, (ast.Dict, ast.List)):
                        add("FAIL", "TC-0.9", f"{v.where}:{node.lineno}", f"tool handler '{fd.name}' returns a dict/list literal; must return a JSON string")
        for name, line in v.hooks:
            hooks[name] = f"{v.where}:{line}"
        for name, line in v.middleware:
            mws[name] = f"{v.where}:{line}"
    return tools, hooks, mws


# --- desktop/plugin.js (rule 8; Q-1 TC-0.4–0.7) -------------------------------

ALLOWED_IMPORTS = {"@hermes/plugin-sdk", "react", "react/jsx-runtime"}
JS_RULES = [
    (re.compile(r"\beval\s*\("), "FAIL", "8", "eval()"),
    (re.compile(r"\bnew\s+Function\s*\("), "FAIL", "8", "new Function()"),
    (re.compile(r"""data-(slot|tour|sidebar|testid)"""), "FAIL", "8", "touches app markup (data-slot/tour/sidebar/testid)"),
    (re.compile(r"\bMutationObserver\b"), "FAIL", "8", "MutationObserver (core UI rewriting)"),
    (re.compile(r"\.prototype\s*\.\s*\w+\s*="), "FAIL", "8", "prototype patching"),
    (re.compile(r"Object\.defineProperty\s*\([^)]*prototype"), "FAIL", "8", "prototype patching via defineProperty"),
    (re.compile(r"""createElement\(\s*['"]script['"]"""), "FAIL", "8", "script-tag injection"),
    (re.compile(r"window\.hermesDesktop"), "WARN", "8", "raw window.hermesDesktop bridge call"),
    (re.compile(r"\bclosest\(\s*['\"]\[data-"), "WARN", "8", "selects app markup via closest()"),
    (re.compile(r"\b(window\.)?(setInterval|setTimeout|addEventListener)\s*\("), "WARN", "TC-1.7",
     "bare timer/listener — use ctx.setTimeout / ctx.setInterval / ctx.addEventListener"),
    (re.compile(r"#[0-9a-fA-F]{3,8}\b(?![\w-])"), "WARN", "TC-0.6", "hardcoded hex color — use theme vars"),
    (re.compile(r"\brgba?\s*\("), "WARN", "TC-0.6", "hardcoded rgb() color — use theme vars"),
    (re.compile(r"\bfetch\s*\(\s*['\"`]https?://"), "FAIL", "3/13", "fetch to absolute URL — self-update or undisclosed network call?"),
    (re.compile(r"\blocalStorage\b|\bsessionStorage\b"), "WARN", "8", "direct Web Storage — prefer ctx.storage"),
]
IMPORT_RE = re.compile(r"""(?:^|\s)import\s+(?:[^'"]*?from\s+)?['"]([^'"]+)['"]""", re.M)
DYN_IMPORT_RE = re.compile(r"""\bimport\s*\(\s*([^)]*)\)""")


def check_js(root: Path):
    js_files = [p for p in iter_files(root) if p.suffix in (".js", ".mjs") and "tests" not in p.relative_to(root).parts]
    for p in js_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        where = rel(root, p)
        for m in IMPORT_RE.finditer(text):
            spec = m.group(1)
            if spec not in ALLOWED_IMPORTS and not spec.startswith("./"):
                add("FAIL", "8", f"{where}:{text.count(chr(10), 0, m.start()) + 1}", f"import of '{spec}' (only @hermes/plugin-sdk, react, react/jsx-runtime)")
        for m in DYN_IMPORT_RE.finditer(text):
            arg = m.group(1).strip().strip("'\"`")
            if arg not in ALLOWED_IMPORTS:
                add("FAIL", "8", f"{where}:{text.count(chr(10), 0, m.start()) + 1}", f"dynamic import({m.group(1).strip()})")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for rx, level, rule, msg in JS_RULES:
                if rx.search(line):
                    if "TC-1.7" == rule and re.search(r"ctx\.(setInterval|setTimeout|addEventListener)", line):
                        continue
                    add(level, rule, f"{where}:{i}", msg)
        if re.search(r"<[A-Z][A-Za-z]*[\s/>]", text) and "jsx" not in p.name:
            add("WARN", "TC-0.4", where, "looks like JSX — plugin.js loads uncompiled; run `node --check`")


# --- manifest + capability match (rules 6, 10, 14) ----------------------------

SEMVER_FLOOR = re.compile(r"^>=\s*\d+\.\d+(\.\d+)?$")
CATALOG_CAP_KEYS = {"provides_tools", "provides_hooks", "provides_middleware", "requires_env"}
CATALOG_CATEGORIES = {"desktop", "memory", "platform", "web", "tools", "voice", "automation", "models", "general"}


def as_list(v):
    if v is None or v == {}:
        return []
    return list(v) if isinstance(v, list) else [v]


def check_manifest(root: Path, tools, hooks, mws, expect_tools):
    man_path = root / "plugin.yaml"
    if not man_path.exists():
        add("FAIL", "load", "plugin.yaml", "missing — no loadable plugin at this commit")
        return None
    man = load_yaml(man_path)
    if man.get("name") != "herd":
        add("WARN", "names", "plugin.yaml", f"name is {man.get('name')!r}, expected 'herd'")
    rh = man.get("requires_hermes")
    if not rh:
        add("FAIL", "14", "plugin.yaml", "requires_hermes missing — declare the SemVer floor here AND in the catalog entry")
    elif not SEMVER_FLOOR.match(str(rh)):
        add("FAIL", "14", "plugin.yaml", f"requires_hermes {rh!r} is not a SemVer floor like '>=0.22.7'")
    if not man.get("version"):
        add("WARN", "14", "plugin.yaml", "no version")
    declared = set(as_list(man.get("provides_tools")))
    registered = set(tools)
    for t in sorted(registered - declared):
        add("FAIL", "6", tools[t], f"tool '{t}' registered but not in plugin.yaml provides_tools")
    for t in sorted(declared - registered):
        add("FAIL", "6", "plugin.yaml", f"tool '{t}' declared but never registered")
    for h in sorted(set(hooks) - set(as_list(man.get("provides_hooks")))):
        add("FAIL", "6", hooks[h], f"hook '{h}' registered but not declared")
    if expect_tools is not None and registered != expect_tools:
        add("FAIL", "TC-0.8", "plugin.yaml", f"registered tools {sorted(registered)} != locked scope {sorted(expect_tools)}")
    deps = as_list(man.get("python_dependencies"))
    for d in deps:
        if isinstance(d, str) and ">=" in d and "<" not in d:
            add("WARN", "10", "plugin.yaml", f"dependency '{d}' has a bare floor — add an upper bound")
    if not (root / "README.md").exists():
        add("FAIL", "13", "README.md", "missing — rule-13 disclosures must live in the README")
    else:
        readme = (root / "README.md").read_text(encoding="utf-8").lower()
        if "network" not in readme or "credential" not in readme:
            add("WARN", "13", "README.md", "no disclosure section found (expect network calls / stored credentials / background processes)")
    return man


def check_entry(entry_path: Path, man: dict | None):
    e = load_yaml(entry_path)
    where = str(entry_path)
    if e.get("name") != "herd":
        add("FAIL", "schema", where, "name must be 'herd'")
    sha = str(e.get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        add("FAIL", "2", where, f"sha {sha!r} is not a full 40-hex commit")
    if not str(e.get("repo", "")).startswith("https://"):
        add("FAIL", "schema", where, "repo must be https://")
    if e.get("version") is not None and not isinstance(e.get("version"), _Quoted):
        add("FAIL", "schema", where, "version must be quoted")
    if e.get("category") and e.get("category") not in CATALOG_CATEGORIES:
        add("FAIL", "schema", where, f"category {e.get('category')!r} not in {sorted(CATALOG_CATEGORIES)}")
    if e.get("tier") not in (None, "community"):
        add("WARN", "schema", where, "contributors may only set tier: community")
    caps = e.get("capabilities") or {}
    if isinstance(caps, dict):
        for k in caps:
            if k not in CATALOG_CAP_KEYS:
                add("FAIL", "6", where, f"capabilities key '{k}' is not in the entry schema {sorted(CATALOG_CAP_KEYS)}")
    if man:
        if str(e.get("version")) != str(man.get("version")):
            add("FAIL", "14", where, f"entry version {e.get('version')!r} != plugin.yaml {man.get('version')!r}")
        if str(e.get("requires_hermes")) != str(man.get("requires_hermes")):
            add("FAIL", "14", where, f"entry requires_hermes {e.get('requires_hermes')!r} != plugin.yaml {man.get('requires_hermes')!r}")
        if isinstance(caps, dict):
            for k in ("provides_tools", "provides_hooks", "provides_middleware", "requires_env"):
                if set(as_list(caps.get(k))) != set(as_list(man.get(k))):
                    add("FAIL", "6", where, f"capabilities.{k} {as_list(caps.get(k))} != plugin.yaml {as_list(man.get(k))}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--entry", help="catalog entry yaml (herd.yaml) to cross-check")
    ap.add_argument("--expect-tools", default="herd_list_channels,herd_post,herd_read_channel",
                    help="comma list of tools the locked scope expects ('' to skip)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    F.clear()
    check_binaries(root)
    check_secrets(root)
    tools, hooks, mws = check_python(root)
    check_js(root)
    expect = set(t for t in a.expect_tools.split(",") if t) if a.expect_tools else None
    man = check_manifest(root, tools, hooks, mws, expect)
    if a.entry:
        check_entry(Path(a.entry), man)
    order = {"FAIL": 0, "WARN": 1, "INFO": 2}
    for f in sorted(F, key=lambda f: (order[f.level], f.rule, f.where)):
        print(f"{f.level:4}  rule {f.rule:7} {f.where}: {f.msg}")
    fails = sum(f.level == "FAIL" for f in F)
    warns = sum(f.level == "WARN" for f in F)
    print(f"\ncatalog_audit: {fails} FAIL, {warns} WARN  (tools registered: {sorted(tools) or 'none'})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
