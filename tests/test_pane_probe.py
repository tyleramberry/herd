"""Desktop behaviour (Track 0 reactions and wake banner, Track 1 search), run through the shipped
desktop/plugin.js under node (see tests/pane_probe.mjs). Skipped where node isn't installed."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "node not installed")
class PaneProbe(unittest.TestCase):
    def test_pane_probe_passes(self):
        proc = subprocess.run(
            ["node", str(ROOT / "tests" / "pane_probe.mjs")],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("all checks passed", proc.stdout)


if __name__ == "__main__":
    unittest.main()
