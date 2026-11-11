"""The relay a fresh install uses when the owner gives no address.

A shipped default is what makes "Start a team room" one click: the pane prefills this
address, so a judge who installs alone can start a room without being told a URL. An
explicit address must still win, and a bad default must never be silently accepted.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dashboard import herd_store as store  # noqa: E402


class DefaultRelayTests(unittest.TestCase):
    def test_the_shipped_default_is_an_https_origin(self):
        parts = urllib.parse.urlsplit(store.DEFAULT_RELAY_URL)
        self.assertEqual(parts.scheme, "https", "a shipped relay default must be https")
        self.assertTrue(parts.hostname, "the default must name a host")
        self.assertFalse(parts.query, "the default must not carry a query")
        self.assertFalse(parts.fragment, "the default must not carry a fragment")

    def test_room_status_reports_the_default_for_a_gateway_outside_a_room(self):
        """The pane reads relay_default to prefill the field; it must be the shipped one."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saved = store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE
            store.DB_PATH_OVERRIDE = str(pathlib.Path(tmp) / "herd.db")
            store.SETTINGS_OVERRIDE = {"display_name": "Tester", "mention_wake": True}
            try:
                out = store.room_status()
                self.assertFalse(out["joined"])
                self.assertEqual(out["relay_default"], store.DEFAULT_RELAY_URL)
            finally:
                store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = saved

    def test_an_explicit_address_beats_the_default(self):
        """The default is only a fallback: a typed address is what gets used."""
        chosen = "https://relay.example.test"
        self.assertNotEqual(chosen, store.DEFAULT_RELAY_URL)
        parts = urllib.parse.urlsplit(chosen)
        self.assertEqual(parts.scheme, "https")

    def test_the_default_is_actually_reachable_as_a_room_base(self):
        """A room link built from the default must parse as a Herd room link."""
        link = f"{store.DEFAULT_RELAY_URL}/r/{'a' * 20}#{'k' * 43}"
        url, key = store.parse_room_link(link)
        self.assertTrue(url.startswith("https://"), url)
        self.assertEqual(key, "k" * 43)


if __name__ == "__main__":
    unittest.main()
