"""The background sync loop must carry the profile secret scope (QA S2 finding).

Under the multiplex gateway, get_secret fails closed for any task without a profile
scope. The 3-second loop task is created at app startup (no scope), so before this
fix every pass resolved the peer key as empty and wrote a false error. These tests
fake the scope modules to pin: scope bound before sync_all, reset afterwards (even
on failure), and graceful degradation when the scope machinery is absent.
"""
import os
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

herd, _store, _tools = _pkg.load()

_SCOPE_MODULES = ("agent", "agent.secret_scope", "hermes_constants")


class _FakeStore:
    def __init__(self, events, raise_on_sync=False):
        self.events = events
        self.raise_on_sync = raise_on_sync

    def sync_all(self):
        self.events.append(("sync",))
        if self.raise_on_sync:
            raise RuntimeError("peer unreachable")


class SyncScopeTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self._saved = {name: sys.modules.get(name) for name in _SCOPE_MODULES}

    def tearDown(self):
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def _drop_scope_modules(self):
        for name in _SCOPE_MODULES:
            sys.modules.pop(name, None)

    def _install_fakes(self, *, fail_set=False):
        events = self.events
        agent = types.ModuleType("agent")
        scope = types.ModuleType("agent.secret_scope")

        def build_profile_secret_scope(home):
            events.append(("build", str(home)))
            return {"HERD_PEER_KEY": "k-1"}

        def set_secret_scope(mapping, *, profile_home=None):
            if fail_set:
                raise RuntimeError("scope machine broke")
            events.append(("set", mapping.get("HERD_PEER_KEY"), profile_home))
            return "TOKEN"

        def reset_secret_scope(token):
            events.append(("reset", token))

        scope.build_profile_secret_scope = build_profile_secret_scope
        scope.set_secret_scope = set_secret_scope
        scope.reset_secret_scope = reset_secret_scope
        agent.secret_scope = scope
        consts = types.ModuleType("hermes_constants")
        consts.get_hermes_home = lambda: Path("/tmp/fake-profile-home")
        sys.modules["agent"] = agent
        sys.modules["agent.secret_scope"] = scope
        sys.modules["hermes_constants"] = consts

    def test_scope_is_bound_before_sync_and_reset_after(self):
        self._install_fakes()
        herd._sync_pass(_FakeStore(self.events))
        self.assertEqual(
            self.events,
            [
                ("build", "/tmp/fake-profile-home"),
                ("set", "k-1", "/tmp/fake-profile-home"),
                ("sync",),
                ("reset", "TOKEN"),
            ],
        )

    def test_scope_is_reset_even_when_sync_raises(self):
        self._install_fakes()
        with self.assertRaises(RuntimeError):
            herd._sync_pass(_FakeStore(self.events, raise_on_sync=True))
        self.assertEqual([event[0] for event in self.events], ["build", "set", "sync", "reset"])

    def test_degrades_gracefully_without_scope_modules(self):
        self._drop_scope_modules()
        herd._sync_pass(_FakeStore(self.events))  # must not raise
        self.assertEqual(self.events, [("sync",)])

    def test_degrades_gracefully_when_scope_setup_fails(self):
        self._install_fakes(fail_set=True)
        store = _FakeStore(self.events)
        herd._sync_pass(store)  # scope failed, the pass still runs
        self.assertEqual([event[0] for event in self.events], ["build", "sync"])

    def test_helper_never_writes_peer_state_itself(self):
        # The store owns peer_state error/ok bookkeeping; the scope wrapper must not
        # touch the db, or it could re-introduce the every-cycle error it exists to stop.
        source = (Path(herd.__file__).read_text())
        start = source.index("def _sync_pass(")
        body = source[start:source.index("\ndef ", start + 1)]
        self.assertNotIn("herd_store", body.replace("store.sync_all", ""))


if __name__ == "__main__":
    unittest.main()
