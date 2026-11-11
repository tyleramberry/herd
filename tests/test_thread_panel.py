"""Spec §2: threads open in a right-hand panel inside the route, and the pane stays inside the plugin SDK.

The render contract runs the shipped desktop/plugin.js in node (tests/s17_thread_panel_render_probe.mjs). The
source checks pin what a render probe cannot see: no document/window access, no listeners outside our own
handlers, and the panel reading the same thread state as the rest of the pane.
"""
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, _tools = _pkg.load()
ROOT = _pkg.ROOT
SOURCE = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    end = SOURCE.index("\nfunction ", start + 1)
    return SOURCE[start:end]


class ThreadPanelProbeTest(unittest.TestCase):
    @unittest.skipIf(shutil.which("node") is None, "node is not installed")
    def test_thread_panel_render_probe(self):
        probe = ROOT / "tests" / "s17_thread_panel_render_probe.mjs"
        done = subprocess.run(["node", str(probe), str(ROOT / "desktop" / "plugin.js")],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PROBE OK", done.stdout)


class ThreadPanelSourceTest(unittest.TestCase):
    def test_route_renders_the_panel_and_the_compact_pane_does_not(self):
        multiplayer_view = _function_body("MultiplayerView")
        self.assertIn("!compact && threadId && selected", multiplayer_view)
        self.assertIn("jsx(ThreadPanel, { channel: selected, rootId: threadId, selfId, $thread }", multiplayer_view)
        self.assertIn("if (openThreadId && compact) {", SOURCE)  # the compact pane keeps its in-column thread

    def test_panel_width_is_a_share_of_the_row(self):
        # A fixed-basis right sidebar set with inline styles (arbitrary Tailwind widths are not in the
        # host's CSS scan), capped at 45% of the row so the messages keep most of the space.
        body = _function_body("ThreadPanel")
        self.assertIn("flex: '0 0 380px'", body)
        self.assertIn("width: 380", body)
        self.assertIn("maxWidth: '45%'", body)

    def test_close_and_escape_live_on_the_panel(self):
        body = _function_body("ThreadPanel")
        self.assertIn("'aria-label': 'Close thread'", body)
        self.assertIn("e.key === 'Escape' && !e.defaultPrevented", body)
        self.assertIn("$thread.set(null)", body)

    def test_panel_reads_the_same_thread_state_and_query(self):
        body = _function_body("ThreadBody")
        self.assertIn("queryKey: KEYS.thread(rootId)", body)
        self.assertIn("'/messages/' + encodeURIComponent(rootId) + '/thread'", body)
        self.assertIn("jsx(ThreadBody, { rootId })", _function_body("ThreadPanel"))
        self.assertIn("threadParentId: rootId", _function_body("ThreadPanel"))

    def test_panel_adds_no_event_or_timer_and_no_dom_reach(self):
        panel = _function_body("ThreadPanel") + _function_body("ThreadBody")
        for bad in ("addEventListener", "document", "window", "setInterval", "setTimeout", "ctx.onEvent",
                    "useEffect", "useRef", "createPortal"):
            self.assertNotIn(bad, panel, bad)

    def test_the_pane_imports_only_the_sdk_and_jsx_runtime(self):
        specs = set(re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", SOURCE))
        self.assertLessEqual(specs, {"@hermes/plugin-sdk", "react/jsx-runtime"})
        self.assertNotIn("react'", SOURCE)  # no hooks import: the panel owns no React state of its own


if __name__ == "__main__":
    unittest.main()
