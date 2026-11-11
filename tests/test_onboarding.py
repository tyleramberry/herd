"""First run, the way a non-technical pair meets: one invites, the other pastes, and they're connected.

Runs real Hermes Multiplayer stores against the real relay (relay/server.mjs), like test_room.py. Covers what the
first-run screen relies on: a dead or wrong relay fails at once in plain words, inviting twice never splits a team,
a whole pasted invite message joins, and the first-run name prompt has what it needs."""
import http.server
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_room import NODE, ROOT, _node_has_sqlite  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, _tools = _pkg.load()


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _NotARelay(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"<html>hello</html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@unittest.skipUnless(_node_has_sqlite(), "needs node 22.5+ to run the relay")
class FirstRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen(
            [NODE, "--no-warnings", str(ROOT / "relay" / "server.mjs"), "--port", "0", "--hold-ms", "400"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        cls.relay = re.search(r"http://\S+", cls.proc.stdout.readline()).group(0)
        cls.web = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _NotARelay)
        threading.Thread(target=cls.web.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.proc.stdout.close()
        cls.web.shutdown()
        cls.web.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        store.AUTO_SYNC = False
        store.TRANSPORT = None
        store._initialized.clear()
        self.A, self.B = Gateway(root, "tyler"), Gateway(root, "riley")

    def tearDown(self):
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        store.AUTO_SYNC = True
        self.tmp.cleanup()

    def test_invite_then_paste_connects_two_people(self):
        with self.A:
            invite = store.create_room(self.relay)["invite"]
            store.post_message("general", "hi riley")
        message = f"Join my team on Hermes Multiplayer: {invite}\n\nIn Hermes, open Hermes Multiplayer and paste this."
        with self.B:
            store.join_room(message)  # the whole message, as a non-technical teammate would paste it
        for gw in (self.A, self.B, self.A, self.B):
            with gw:
                store._room_kick.set()
                store.sync_all()
        with self.B:
            self.assertIn("hi riley", [m["content"] for m in store.list_messages("general")])
            self.assertTrue(store.status()["room"]["connected"])

    def test_inviting_twice_hands_out_the_same_room(self):
        with self.A:
            first = store.create_room(self.relay)["invite"]
            again = store.create_room("")
        self.assertEqual(again["invite"], first)
        self.assertTrue(again.get("existing"))

    def test_a_dead_relay_fails_at_once_in_plain_words(self):
        dead = f"http://127.0.0.1:{_closed_port()}"
        with self.A:
            started = time.monotonic()
            with self.assertRaises(store.MultiplayerError) as c:
                store.create_room(dead)
            self.assertLess(time.monotonic() - started, store.RELAY_HEALTH_TIMEOUT_S)
            self.assertIn("Couldn't reach the team room server", str(c.exception))
            self.assertFalse(store.status()["room"]["joined"], "a dead relay must not be saved as the room")

    def test_an_address_that_is_not_a_relay_says_so(self):
        other = f"http://127.0.0.1:{self.web.server_address[1]}"
        with self.A:
            with self.assertRaises(store.MultiplayerError) as c:
                store.create_room(other)
            self.assertIn("isn't a Hermes Multiplayer team room server", str(c.exception))
        with self.B:
            with self.assertRaises(store.MultiplayerError):
                store.join_room(f"{other}/r/0123456789abcdef0123#{'k' * 43}")
            self.assertFalse(store.status()["room"]["joined"])

    def test_text_with_no_invite_is_explained(self):
        with self.B:
            with self.assertRaises(store.MultiplayerError) as c:
                store.join_room("hey, here's the thing we talked about")
            self.assertIn("isn't an invite link", str(c.exception))

    def test_first_run_asks_for_a_name_once(self):
        root = Path(self.tmp.name)
        fresh = Gateway(root, "fresh")
        fresh.settings["display_name"] = ""
        with fresh:
            me = store.status()["self"]
            self.assertFalse(me["name_chosen"])
            self.assertTrue(me["suggested_name"])
            store.set_display_name("Riley")
            me = store.status()["self"]
            self.assertTrue(me["name_chosen"])
            self.assertEqual(me["display_name"], "Riley")
            self.assertNotIn("suggested_name", me)


class SuggestedNameTest(unittest.TestCase):
    def test_suggestion_is_a_friendly_word_not_a_role_account(self):
        name = store.suggested_name()
        self.assertNotIn(name.lower(), {"root", "user", "admin", "localhost"})
        if name:
            self.assertEqual(name[0], name[0].upper())

    def test_find_room_link_inside_a_message(self):
        link = "https://relay.example/r/0123456789abcdef0123#" + "k" * 43
        self.assertEqual(store.find_room_link(f"Join me: {link}\n\nthanks"), link)
        self.assertEqual(store.find_room_link(f"  {link}  "), link)
        self.assertEqual(store.find_room_link("https://riley.ts.net:8642#ABCDE-FGHJK"), "")

    def test_agent_setup_needs_no_restart(self):
        self.assertNotIn("restart the gateway", store.INJECTION_SETUP_PROMPT.lower())
        self.assertNotIn("restart the gateway", store.WAKE_REASONS["injection_not_allowed"].lower())


if __name__ == "__main__":
    unittest.main()
