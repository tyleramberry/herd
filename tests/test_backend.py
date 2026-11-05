"""Backend tests: FastAPI TestClient against the Herd router with a temp SQLite db."""
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import herd
from herd import tools
from herd.dashboard import plugin_api

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "herd.db"
    monkeypatch.setattr(plugin_api, "_db_path", lambda: db)
    monkeypatch.setattr(plugin_api, "_initialized", set())
    events = []
    monkeypatch.setattr(plugin_api, "_broadcast", lambda msg: events.append(msg))
    # Gateway identity is module state set from plugin settings; reset it per test.
    monkeypatch.setattr(plugin_api, "_GATEWAY_ID", None)
    app = FastAPI()
    app.include_router(plugin_api.router, prefix="/api/plugins/herd")
    c = TestClient(app)
    c.events = events
    return c


def _channel_id(client, name):
    return next(ch["id"] for ch in client.get("/api/plugins/herd/channels").json() if ch["name"] == name)


def test_general_channel_seeded(client):
    channels = client.get("/api/plugins/herd/channels").json()
    assert [ch["name"] for ch in channels] == ["general"]
    assert channels[0]["message_count"] == 0


def test_create_channel(client):
    r = client.post("/api/plugins/herd/channels", json={"name": "design", "topic": "pixels"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "design" and body["topic"] == "pixels" and body["id"]
    names = [ch["name"] for ch in client.get("/api/plugins/herd/channels").json()]
    assert names == ["design", "general"]


def test_duplicate_channel_name_rejected(client):
    assert client.post("/api/plugins/herd/channels", json={"name": "ops"}).status_code == 200
    r = client.post("/api/plugins/herd/channels", json={"name": "ops"})
    assert r.status_code == 409
    assert client.post("/api/plugins/herd/channels", json={"name": "  "}).status_code == 422
    assert [ch["name"] for ch in client.get("/api/plugins/herd/channels").json()].count("ops") == 1


def test_post_and_list_messages(client):
    cid = _channel_id(client, "general")
    r = client.post(
        f"/api/plugins/herd/channels/{cid}/messages",
        json={"content": "hello herd", "author_name": "tyler", "gateway_id": "gw-a"},
    )
    assert r.status_code == 200
    msg = r.json()
    assert msg["content"] == "hello herd" and msg["author_type"] == "human" and msg["gateway_id"] == "gw-a"
    assert client.events and client.events[-1]["id"] == msg["id"]

    listed = client.get(f"/api/plugins/herd/channels/{cid}/messages").json()
    assert [m["id"] for m in listed] == [msg["id"]]
    assert client.get("/api/plugins/herd/channels").json()[0]["message_count"] == 1


def test_message_insert_is_idempotent_by_id(client):
    cid = _channel_id(client, "general")
    payload = {"id": "11111111-1111-4111-8111-111111111111", "content": "once"}
    first = client.post(f"/api/plugins/herd/channels/{cid}/messages", json=payload).json()
    second = client.post(f"/api/plugins/herd/channels/{cid}/messages", json={**payload, "content": "dupe"}).json()
    assert first == second and second["content"] == "once"
    assert len(client.get(f"/api/plugins/herd/channels/{cid}/messages").json()) == 1


def test_post_message_errors(client):
    assert client.post("/api/plugins/herd/channels/nope/messages", json={"content": "x"}).status_code == 404
    cid = _channel_id(client, "general")
    assert client.post(f"/api/plugins/herd/channels/{cid}/messages", json={"content": " "}).status_code == 422


def test_after_filter(client):
    cid = _channel_id(client, "general")
    url = f"/api/plugins/herd/channels/{cid}/messages"
    for i, ts in enumerate(["2026-11-04T10:00:00+00:00", "2026-11-04T11:00:00+00:00", "2026-11-04T12:00:00+00:00"]):
        client.post(url, json={"content": f"m{i}", "created_at": ts})
    after = client.get(url, params={"after": "2026-11-04T10:30:00+00:00"}).json()
    assert [m["content"] for m in after] == ["m1", "m2"]
    assert client.get(url, params={"after": "2026-11-04T12:00:00+00:00"}).json() == []


def test_participants_register_and_list(client):
    r = client.post("/api/plugins/herd/participants", json={"display_name": "Tyler", "kind": "human", "gateway_id": "gw-a"})
    assert r.status_code == 200
    pid = r.json()["id"]
    # heartbeat / rename upserts the same row
    client.post("/api/plugins/herd/participants", json={"id": pid, "display_name": "Tyler A"})
    client.post("/api/plugins/herd/participants", json={"display_name": "Hermes", "kind": "agent"})
    people = client.get("/api/plugins/herd/participants").json()
    assert [p["display_name"] for p in people] == ["Hermes", "Tyler A"]
    assert client.post("/api/plugins/herd/participants", json={}).status_code == 422


def test_agent_tools_return_json(client):
    listed = json.loads(tools.herd_list_channels({}))
    assert listed["ok"] and listed["channels"][0]["name"] == "general"

    posted = json.loads(tools.herd_post({"channel": "#general", "content": "from agent"}, task_id="t1"))
    assert posted["ok"] and posted["message"]["author_type"] == "agent"
    assert posted["message"]["author_name"] == "Hermes"

    missing = json.loads(tools.herd_post({"channel": "nowhere", "content": "x"}))
    assert missing["ok"] is False and "not found" in missing["error"]
    assert json.loads(tools.herd_post({}))["ok"] is False


def test_gateway_id_setting_flows_through(client):
    cid = _channel_id(client, "general")
    url = f"/api/plugins/herd/channels/{cid}/messages"

    # Unset -> "local"
    assert client.post(url, json={"content": "a"}).json()["gateway_id"] == "local"

    plugin_api.set_gateway_id("gw-b")
    assert client.post(url, json={"content": "b"}).json()["gateway_id"] == "gw-b"
    p = client.post("/api/plugins/herd/participants", json={"display_name": "Bo"}).json()
    assert p["gateway_id"] == "gw-b"
    agent = json.loads(tools.herd_post({"channel": "general", "content": "c"}))
    assert agent["message"]["gateway_id"] == "gw-b"

    # Explicit value wins over the setting
    assert client.post(url, json={"content": "d", "gateway_id": "gw-x"}).json()["gateway_id"] == "gw-x"
    p = client.post("/api/plugins/herd/participants", json={"display_name": "Cy", "gateway_id": "gw-x"}).json()
    assert p["gateway_id"] == "gw-x"

    # Clearing falls back to "local"
    for cleared in (None, "", "   "):
        plugin_api.set_gateway_id(cleared)
        assert client.post(url, json={"content": "e"}).json()["gateway_id"] == "local"
        p = client.post("/api/plugins/herd/participants", json={"display_name": "Di"}).json()
        assert p["gateway_id"] == "local"


class _Ctx:
    def __init__(self, config=None, fail=False):
        self.tools = []
        self._config = config or {}
        self._fail = fail

    def register_tool(self, **kwargs):
        self.tools.append(kwargs["name"])

    def get_config(self, key):
        if self._fail:
            raise KeyError("plugins.entries.herd.settings")
        return self._config.get(key)


def test_register_picks_up_gateway_setting(monkeypatch):
    monkeypatch.setattr(plugin_api, "_GATEWAY_ID", None)
    ctx = _Ctx({"gateway_id": "gw-settings"})
    herd.register(ctx)
    assert ctx.tools == ["herd_post", "herd_list_channels"]
    assert plugin_api._gateway_id() == "gw-settings"
    assert plugin_api._gateway_id("explicit") == "explicit"


def test_register_survives_missing_settings(monkeypatch):
    monkeypatch.setattr(plugin_api, "_GATEWAY_ID", None)
    ctx = _Ctx(fail=True)
    herd.register(ctx)
    assert ctx.tools == ["herd_post", "herd_list_channels"]
    assert plugin_api._gateway_id() == "local"

    class _NoConfig:
        def __init__(self):
            self.tools = []

        def register_tool(self, **kwargs):
            self.tools.append(kwargs["name"])

    bare = _NoConfig()  # ctx without get_config at all
    herd.register(bare)
    assert bare.tools == ["herd_post", "herd_list_channels"]
    assert plugin_api._gateway_id() == "local"


def test_no_environment_reads_in_plugin_source():
    # Split so this test file never contains the forbidden substrings itself.
    forbidden = ["os." + "environ", "os." + "getenv", "get" + "env(", "HERMES_" + "GATEWAY_ID"]
    for rel in ("__init__.py", "tools.py", "dashboard/plugin_api.py"):
        text = (ROOT / rel).read_text()
        for needle in forbidden:
            assert needle not in text, f"{rel} contains {needle!r}"
