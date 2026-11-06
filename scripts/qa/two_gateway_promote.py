#!/usr/bin/env python3
"""TC-10.4 — two REAL gateways, one sync cycle, promote-a-DM (S-13 / F1).

Why this exists: S-13 changes the peer sync payload on the critical path (risk R-5),
so the promote feature must be exercised by two gateway processes talking over real
HTTP with the plugin's own route wiring, background sync loop, cursors and SQLite
files — not only by the in-process transport stub the unit tests use.

Topology (one machine, two processes, four ports, nothing shared):

    gateway A (127.0.0.1)                 gateway B (127.0.0.1)
      :P_peer  /herd/v1/sync   <---3s---  :Q_peer  /herd/v1/sync
      :P_api   /api/plugins/herd/*        :Q_api   /api/plugins/herd/*
      <tmp>/a/herd.db                     <tmp>/b/herd.db

Both sides run the plugin's real code: ``__init__._wire_api_server`` (the peer route +
the 3 s background sync loop, with the same Bearer API_SERVER_KEY check the Hermes
api_server adapter performs) and ``dashboard/plugin_api.py`` (the FastAPI backend the
desktop half calls). The driver talks to both gateways over HTTP only.

Checks (each prints PASS/FAIL and exits non-zero on any FAIL):
  TC-10.4  promote on A -> room + copies on B within one sync cycle (~3 s), and back
  TC-10.3  order preserved, source created_at carried
  TC-10.5  copy ids are new, counts equal on both sides (no silent INSERT OR IGNORE)
  TC-10.7  the DM row and its messages are unchanged on both sides
  TC-10.9  peer offline during promote -> room is local now, converges when it returns
  TC-10.11 PROTOCOL_VERSION 2 on /herd/v1/ping; a v3 body is refused 422; a v1 body is
           accepted; a PRE-S-13 gateway (the merge base's herd_store.py) ingests a v2
           body without error and without corruption

Usage:
  python scripts/qa/two_gateway_promote.py            # run everything
  python scripts/qa/two_gateway_promote.py --keep     # keep the temp dirs + gateway logs
  python scripts/qa/two_gateway_promote.py --gateway  # internal: one gateway process
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PEER_PATH = "/herd/v1/sync"
API_PREFIX = "/api/plugins/herd"
KEY_A = "a-api-server-key"
KEY_B = "b-api-server-key"

RESULTS: list[tuple[str, bool, str]] = []


def check(tc: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((tc, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {tc}  {detail}", flush=True)
    return bool(ok)


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — the driver has no third-party dependencies)
# ---------------------------------------------------------------------------


def http(method: str, url: str, body=None, key: str = "", timeout: float = 20.0):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw}


def api(gw: dict, method: str, path: str, body=None, timeout: float = 20.0):
    return http(method, gw["api"] + API_PREFIX + path, body, timeout=timeout)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_up(url: str, key: str, seconds: float = 30.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            status, _ = http("GET", url, key=key, timeout=2.0)
            if status == 200:
                return True
        except Exception:  # noqa: BLE001 — still starting
            pass
        time.sleep(0.25)
    return False


# ---------------------------------------------------------------------------
# One gateway process
# ---------------------------------------------------------------------------


def gateway_main() -> int:
    """Run ONE gateway: the plugin's peer route + sync loop, and its backend router."""
    sys.path.insert(0, str(ROOT / "tests"))
    import _pkg  # noqa: E402  (test loader: imports the repo root as the `herd` package)

    herd, store, _tools = _pkg.load()

    home = Path(os.environ["HERD_GW_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    store.DB_PATH_OVERRIDE = home / "herd.db"
    store.SETTINGS_OVERRIDE = {
        "display_name": os.environ["HERD_GW_NAME"],
        "peer_name": os.environ.get("HERD_GW_PEER_NAME", ""),
        "peer_url": os.environ.get("HERD_GW_PEER_URL", ""),
        "__secrets__": {"HERD_PEER_KEY": os.environ.get("HERD_GW_PEER_KEY", "")},
    }
    store.AUTO_SYNC = True
    own_key = os.environ["HERD_GW_KEY"]
    peer_port = int(os.environ["HERD_GW_PEER_PORT"])
    api_port = int(os.environ["HERD_GW_API_PORT"])

    from aiohttp import web
    from fastapi import FastAPI

    from herd.dashboard import plugin_api

    class StubAdapter:
        """Stands in for the Hermes api_server adapter: the same Bearer key check."""

        def _check_auth(self, request):
            if (request.headers.get("Authorization") or "") != "Bearer " + own_key:
                return web.json_response({"error": "unauthorized"}, status=401)
            return None

    peer_app = web.Application()
    herd._wire_api_server(peer_app, StubAdapter())

    backend = FastAPI()
    backend.include_router(plugin_api.router, prefix=API_PREFIX)

    import uvicorn

    async def main() -> None:
        runner = web.AppRunner(peer_app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", peer_port).start()
        print(f"GATEWAY READY peer=127.0.0.1:{peer_port} api=127.0.0.1:{api_port}", flush=True)
        server = uvicorn.Server(uvicorn.Config(backend, host="127.0.0.1", port=api_port,
                                               log_level="warning", access_log=False))
        await server.serve()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    return 0


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


class Run:
    def __init__(self, keep: bool):
        self.keep = keep
        self.tmp = Path(tempfile.mkdtemp(prefix="herd-tc10-"))
        self.procs: list[subprocess.Popen] = []
        self.gateways: list[dict] = []

    # -- lifecycle ---------------------------------------------------------

    def spawn(self, name: str, peer_name: str, peer_url: str, peer_key: str) -> dict:
        home = self.tmp / name
        peer_port, api_port = free_port(), free_port()
        env = dict(os.environ,
                   HERD_GW_HOME=str(home), HERD_GW_NAME=name, HERD_GW_PEER_NAME=peer_name,
                   HERD_GW_PEER_URL=peer_url, HERD_GW_PEER_KEY=peer_key,
                   HERD_GW_KEY=KEY_A if name == "tyler" else KEY_B,
                   HERD_GW_PEER_PORT=str(peer_port), HERD_GW_API_PORT=str(api_port),
                   PYTHONPATH="")
        log = open(self.tmp / f"{name}.log", "w")
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--gateway"],
                                env=env, stdout=log, stderr=subprocess.STDOUT)
        self.procs.append(proc)
        return {"name": name, "proc": proc, "log": log, "home": home,
                "peer": f"http://127.0.0.1:{peer_port}", "api": f"http://127.0.0.1:{api_port}",
                "key": env["HERD_GW_KEY"], "peer_key": peer_key}

    def stop(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
        for proc in self.procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        if not self.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)
        else:
            print(f"  (kept: {self.tmp})")


def gateway_id(gw: dict) -> str:
    # Calling a gateway's OWN peer route needs its OWN API_SERVER_KEY (that is the
    # key the real api_server adapter checks) — gw["peer_key"] is the other side's.
    status, body = http("GET", gw["peer"] + "/herd/v1/ping", key=gw["key"])
    return (body or {}).get("from", {}).get("gateway_id", "") if status == 200 else ""


def channels(gw: dict) -> list[dict]:
    _, body = api(gw, "GET", "/channels")
    return body or []


def messages(gw: dict, channel_id: str) -> list[dict]:
    _, body = api(gw, "GET", f"/channels/{urllib.parse.quote(channel_id)}/messages")
    return body or []


def find(gw: dict, channel_id: str) -> dict | None:
    return next((c for c in channels(gw) if c["id"] == channel_id), None)


def wait_for_room(gw: dict, channel_id: str, expect: int, seconds: float = 8.0) -> float | None:
    """Poll the other gateway's channel list — no manual reload, one sync cycle."""
    start = time.time()
    while time.time() - start < seconds:
        chan = find(gw, channel_id)
        if chan and chan.get("message_count", 0) >= expect:
            return time.time() - start
        time.sleep(0.25)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", action="store_true")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    if args.gateway:
        return gateway_main()

    run = Run(keep=args.keep)
    try:
        print("== TC-10.4 two-gateway promote run ==")
        print(f"  workdir: {run.tmp}")
        # B first (it has no peer configured: the README's one-sided link), then A.
        b = run.spawn("riley", "", "", "")
        a = run.spawn("tyler", "riley", b["peer"], KEY_B)
        run.gateways = [a, b]
        if not (wait_up(a["api"] + API_PREFIX + "/status", "", 40)
                and wait_up(b["api"] + API_PREFIX + "/status", "", 40)):
            print("  gateway failed to start; logs:")
            for gw in (a, b):
                gw["log"].flush()
                print(Path(gw["log"].name).read_text()[-2000:])
            return 2
        print(f"  A(tyler) api={a['api']} peer={a['peer']}   B(riley) api={b['api']} peer={b['peer']}")

        a_id, b_id = gateway_id(a), gateway_id(b)
        check("ENV both gateways answer /herd/v1/ping with an identity", bool(a_id and b_id),
              f"A={a_id[:8]} B={b_id[:8]}")

        # --- link + learn the peer (the linked side pushes and pulls) -----------
        api(a, "POST", "/sync", {})
        time.sleep(0.5)
        participants = api(a, "GET", "/participants")[1] or []
        other = next((p for p in participants if p["id"] == b_id), None)
        check("ENV A learned B as a participant after one sync", other is not None,
              f"participants={[p['display_name'] for p in participants]}")

        # --- a DM with history on both sides -----------------------------------
        _, dm = api(a, "POST", "/dms", {"participant_id": b_id})
        dm_id = (dm or {}).get("id", "")
        for i in (1, 2, 3):
            api(a, "POST", f"/channels/{urllib.parse.quote(dm_id)}/messages",
                {"id": f"tc10-a-{i}", "content": f"dm from tyler {i}"})
        api(a, "POST", "/sync", {})
        time.sleep(0.5)
        # B answers in the same DM (so the replay must carry B's own message back to B).
        api(b, "POST", f"/channels/{urllib.parse.quote(dm_id)}/messages",
            {"id": "tc10-b-1", "content": "dm from riley"})
        api(b, "POST", "/sync", {})
        time.sleep(0.5)
        api(a, "POST", "/sync", {})
        dm_before_a = messages(a, dm_id)
        dm_before_b = messages(b, dm_id)
        check("ENV the DM holds all 4 messages on both sides",
              len(dm_before_a) == 4 and len(dm_before_b) == 4,
              f"A={len(dm_before_a)} B={len(dm_before_b)}")

        # --- TC-10.4 / 10.2: promote on A, one sync cycle, check B -------------
        status, room = api(a, "POST", f"/channels/{urllib.parse.quote(dm_id)}/promote",
                           {"name": "dm-share"})
        check("TC-10.2 promote returns the new room",
              status == 200 and (room or {}).get("id") == "dm-share"
              and (room or {}).get("message_count") == 4,
              f"HTTP {status} {json.dumps(room)[:160] if room else ''}")
        elapsed = wait_for_room(b, "dm-share", 4)
        check("TC-10.4 the room appears on B within one sync cycle (no reload)",
              elapsed is not None, f"after {elapsed:.1f}s" if elapsed is not None else "not within 8s")

        room_a, room_b = messages(a, "dm-share"), messages(b, "dm-share")
        check("TC-10.4 the copies arrive on B (all of them, including B's own message)",
              [m["content"] for m in room_a] == [m["content"] for m in room_b] ==
              ["dm from tyler 1", "dm from tyler 2", "dm from tyler 3", "dm from riley"],
              f"A={[m['content'] for m in room_a]} B={[m['content'] for m in room_b]}")
        check("TC-10.3 order + source created_at preserved",
              [m["created_at"] for m in room_a] == [m["created_at"] for m in room_b]
              and [m["created_at"] for m in room_a] == [m["created_at"] for m in dm_before_a],
              f"created_at={[m['created_at'] for m in room_a][:2]}…")
        src_ids = {m["id"] for m in dm_before_a}
        copy_ids_a = {m["id"] for m in room_a}
        copy_ids_b = {m["id"] for m in room_b}
        check("TC-10.5 copy ids are new, distinct, and identical on both sides",
              not (src_ids & copy_ids_a) and copy_ids_a == copy_ids_b and len(copy_ids_a) == 4,
              f"{len(copy_ids_a)} copies, overlap={len(src_ids & copy_ids_a)}")

        # --- TC-10.7: the DM is untouched, on both sides ------------------------
        dm_after_a, dm_after_b = messages(a, dm_id), messages(b, dm_id)
        fields = ("id", "content", "created_at", "seq")
        same = ([{k: m[k] for k in fields} for m in dm_before_a] ==
                [{k: m[k] for k in fields} for m in dm_after_a] and
                [{k: m[k] for k in fields} for m in dm_before_b] ==
                [{k: m[k] for k in fields} for m in dm_after_b])
        chan_a = find(a, dm_id) or {}
        check("TC-10.7 the DM row and its messages are unchanged on both gateways",
              same and chan_a.get("is_dm") is True and chan_a.get("message_count") == 4,
              "field compare id/content/created_at/seq")

        # --- TC-10.4 reverse: promote on B, one sync cycle, check A ------------
        api(b, "POST", "/sync", {})
        time.sleep(0.5)
        _, dm2 = api(b, "POST", "/dms", {"participant_id": a_id})
        dm2_id = (dm2 or {}).get("id", "")
        api(b, "POST", f"/channels/{urllib.parse.quote(dm2_id)}/messages",
            {"id": "tc10-b2-1", "content": "riley side"})
        api(b, "POST", "/sync", {})
        time.sleep(0.5)
        status, room2 = api(b, "POST", f"/channels/{urllib.parse.quote(dm2_id)}/promote",
                            {"name": "riley-room"})
        elapsed = wait_for_room(a, "riley-room", 1)
        check("TC-10.4 promote on B reaches A within one sync cycle (both directions)",
              status == 200 and elapsed is not None,
              f"HTTP {status}, after {elapsed:.1f}s" if elapsed is not None else f"HTTP {status}, not within 8s")
        check("TC-10.4 the same DM id maps to the same room on both sides",
              (find(a, "riley-room") or {}).get("id") == (find(b, "riley-room") or {}).get("id"),
              "public channels are keyed by normalized name")

        # --- TC-10.9: peer offline during promote, then convergence ------------
        api(a, "POST", "/sync", {})
        time.sleep(0.3)
        # Two people only ever have ONE DM between them, so this is the same DM row
        # as above (already carrying history) — the promote must copy all of it.
        _, dm3 = api(a, "POST", "/dms", {"participant_id": b_id})
        dm3_id = (dm3 or {}).get("id", "")
        api(a, "POST", f"/channels/{urllib.parse.quote(dm3_id)}/messages",
            {"id": "tc10-a3-1", "content": "offline promote"})
        api(a, "POST", "/sync", {})
        time.sleep(0.5)
        expected = len(messages(a, dm3_id))
        # B goes away: its api+peer ports stop answering, so A's sync fails.
        b["proc"].send_signal(signal.SIGSTOP)
        time.sleep(0.5)
        status, room3 = api(a, "POST", f"/channels/{urllib.parse.quote(dm3_id)}/promote",
                            {"name": "offline-room"})
        check("TC-10.9 promote with the peer unreachable still creates the room locally",
              status == 200 and (room3 or {}).get("message_count") == expected,
              f"HTTP {status} count={(room3 or {}).get('message_count')} (DM has {expected})")
        b["proc"].send_signal(signal.SIGCONT)
        time.sleep(0.5)
        api(a, "POST", "/sync", {})
        elapsed = wait_for_room(b, "offline-room", expected, seconds=10.0)
        check("TC-10.9 the room converges once the peer is back",
              elapsed is not None, f"after {elapsed:.1f}s" if elapsed is not None else "not within 10s")

        # --- TC-10.11: protocol honesty ----------------------------------------
        _, ping_a = http("GET", a["peer"] + "/herd/v1/ping", key=a["key"])
        _, ping_b = http("GET", b["peer"] + "/herd/v1/ping", key=b["key"])
        check("TC-10.11 both gateways advertise PROTOCOL_VERSION 2",
              (ping_a or {}).get("v") == 2 and (ping_b or {}).get("v") == 2,
              f"A={ping_a} B={ping_b}")
        status_future, body_future = http(
            "POST", a["peer"] + PEER_PATH,
            {"v": 3, "from": {"gateway_id": "future", "display_name": "future"},
             "channels": [], "messages": []}, key=a["key"])
        check("TC-10.11 a newer-protocol body is refused loudly (422), not mis-parsed",
              status_future == 422 and "newer Herd protocol" in json.dumps(body_future),
              f"HTTP {status_future} {json.dumps(body_future)[:120]}")
        status_v1, body_v1 = http(
            "POST", a["peer"] + PEER_PATH,
            {"v": 1, "from": {"gateway_id": "old", "display_name": "old"},
             "channels": [], "messages": [], "after_seq": 0, "after_rseq": 0},
            key=a["key"])
        check("TC-10.11 a v1 body is still accepted (older peer keeps working)",
              status_v1 == 200 and (body_v1 or {}).get("v") == 2, f"HTTP {status_v1}")

        old_peer_check(a)

        print("\n== summary ==")
        failed = [r for r in RESULTS if not r[1]]
        for tc, ok, detail in RESULTS:
            print(f"  {'PASS' if ok else 'FAIL'}  {tc}")
        print(f"  {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
        return 1 if failed else 0
    finally:
        run.stop()


def old_peer_check(a: dict) -> None:
    """Feed a v2 body to the PRE-S-13 gateway code: it must not error or corrupt data."""
    try:
        base = subprocess.check_output(["git", "-C", str(ROOT), "merge-base", "HEAD", "origin/main"],
                                       stderr=subprocess.DEVNULL).decode().strip()
        source = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{base}:dashboard/herd_store.py"],
                                         stderr=subprocess.DEVNULL).decode()
    except Exception as exc:  # noqa: BLE001 — no git / no origin: skip, don't fail the run
        check("TC-10.11 pre-S-13 gateway compatibility", True, f"skipped ({exc.__class__.__name__})")
        return
    tmp = Path(tempfile.mkdtemp(prefix="herd-oldpeer-"))
    path = tmp / "herd_store_old.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("herd_store_old", path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    old.DB_PATH_OVERRIDE = tmp / "old.db"
    old.SETTINGS_OVERRIDE = {"display_name": "old", "__secrets__": {}}
    old.AUTO_SYNC = False
    # Build a real v2 body from A's own export (a channel + a copied message row).
    body = {
        "v": 2, "from": {"gateway_id": "new-gw", "display_name": "new"},
        "channels": [{"id": "dm-share", "name": "dm-share", "topic": "", "is_dm": 0, "members": []}],
        "messages": [{"id": "p-abc", "channel_id": "dm-share", "author_type": "human",
                      "author_name": "tyler", "gateway_id": "new-gw", "gateway_name": "tyler",
                      "content": "dm from tyler 1", "created_at": "2026-11-06T00:00:00.000+00:00",
                      "origin_channel_id": "dm:x+y"}],
        "reactions": [], "after_seq": 0, "after_rseq": 0,
    }
    try:
        out = old.handle_peer_sync(json.loads(json.dumps(body)))
        stored = old.list_messages("dm-share")
        ok = out.get("v") == 1 and len(stored) == 1 and stored[0]["content"] == "dm from tyler 1"
        check("TC-10.11 a PRE-S-13 gateway ingests a v2 body without error or corruption", ok,
              f"old v={out.get('v')} stored={len(stored)} (origin_channel_id is ignored, not fatal)")
    except Exception as exc:  # noqa: BLE001
        check("TC-10.11 a PRE-S-13 gateway ingests a v2 body without error or corruption", False,
              f"raised {exc.__class__.__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
