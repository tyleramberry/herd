"""No built-in relay: creating a room requires an address the user supplies."""
from __future__ import annotations
import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from dashboard import multiplayer_store as store  # noqa: E402


class RelayRequiredTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE
        store.DB_PATH_OVERRIDE = str(pathlib.Path(self.tmp.name) / "hm.db")
        store.SETTINGS_OVERRIDE = {"display_name": "T", "mention_wake": True}

    def tearDown(self):
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self.saved
        self.tmp.cleanup()

    def test_no_default_constant(self):
        self.assertFalse(hasattr(store, "DEFAULT_RELAY_URL"))

    def test_create_room_without_address_is_refused(self):
        for blank in ("", None, "   "):
            with self.assertRaises(store.MultiplayerError) as cm:
                store.create_room(blank)
            self.assertEqual(cm.exception.status, 422)

    def test_room_status_offers_no_relay(self):
        self.assertEqual(store.room_status(), {"joined": False})


if __name__ == "__main__":
    unittest.main()
