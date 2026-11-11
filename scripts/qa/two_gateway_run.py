#!/usr/bin/env python3
"""Q-11 — reproducible two-gateway SPINE run (TC-2.1 / TC-2.2 / TC-2.3, three consecutive, S-16).

Why this exists: Q-9's SPINE log was a recording of someone else's two-Mac run with no B-side
primary evidence, no three-consecutive capture and no TC-2.3 evidence. This harness replays the
SPINE between two REAL gateway processes, reads every delivery on the RECEIVING side, and can be
re-run by anyone with one command.

Topology (one machine, two processes, four loopback ports, nothing shared):

    gateway A (q11-a)                         gateway B (q11-b)
      :P_peer  /herd/v1/sync   <---3s loop---  :Q_peer  /herd/v1/sync
      :P_api   /api/plugins/herd/*             :Q_api   /api/plugins/herd/*
      <tmp>/a/herd.db                          <tmp>/b/herd.db

Each side runs the plugin's own code: ``herd._wire_api_server`` (the peer route + the real 3 s
background sync loop, behind Hermes Multiplayer's OWN ``Bearer <HERD_SECRET>`` check — the gateway's Hermes Multiplayer
secret, never its API_SERVER_KEY, which is refused on /herd/v1/*) and ``dashboard/plugin_api.py`` (the FastAPI backend the desktop half calls).
B is spawned first with no peer (the README's one-sided link); A links to B.

One harness-only route, ``POST /harness/agent-post`` on each gateway's peer app (never in plugin
code): it runs the same own-key check and calls ``tools.herd_post`` — the exact handler Hermes
invokes for the ``herd_post`` agent tool — in-process. The backend composer route deliberately
hardcodes ``author_type="human"`` (an HTTP client must not be able to forge agent posts), so this
is how TC-2.3 / S-16 get a row authored by the agent path. Every cross-gateway hop is still real
HTTP + the real sync loop + real SQLite.

The driver talks to both gateways over HTTP only (stdlib ``urllib``).

Usage:
  python scripts/qa/two_gateway_run.py                    # full run (exit 0 all PASS, 1 any FAIL,
                                                          #           2 a gateway failed to start)
  python scripts/qa/two_gateway_run.py --keep             # keep temp homes + gateway logs
  python scripts/qa/two_gateway_run.py --old-peer-ref REF # override the pre-S-16 ref
  python scripts/qa/two_gateway_run.py --gateway          # internal: run ONE gateway process
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

ROOT = Path(__file__).resolve().parents[2]
PEER_PATH = "/herd/v1/sync"
API_PREFIX = "/api/plugins/herd"
AGENT_POST_PATH = "/harness/agent-post"
CHANNEL = "general"
NAME_A, NAME_B = "q11-a", "q11-b"
KEY_A = "q11-a-api-server-key"
KEY_B = "q11-b-api-server-key"
# Each gateway's own Hermes Multiplayer secret (HERD_SECRET): what a peer must present on /herd/v1/*. The
# API_SERVER_KEYs above only guard StubAdapter / the harness-only agent-post route.
SECRET_A = "q11-a-herd-secret"
SECRET_B = "q11-b-herd-secret"
ARRIVAL_TIMEOUT_S = 10.0
S16_TASK_IDS = ("t_16d10f75", "t_2f22ab63", "t_810b8329")
FALLBACK_OLD_REF = "a20f742^"

RESULTS: list[tuple[str, bool, str]] = []


def check(tc: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((tc, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {tc}  {detail}", flush=True)
    return bool(ok)


def info(text: str) -> None:
    print(f"  INFO  {text}", flush=True)


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
    """Run ONE gateway: the plugin's peer route + sync loop, its backend router, + the harness route."""
    sys.path.insert(0, str(ROOT / "tests"))
    import _pkg  # noqa: E402  (test loader: imports the repo root as the `herd` package)

    herd, store, tools = _pkg.load()

    home = Path(os.environ["HERD_GW_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    store.DB_PATH_OVERRIDE = home / "herd.db"
    store.SETTINGS_OVERRIDE = {
        "display_name": os.environ["HERD_GW_NAME"],
        "peer_name": os.environ.get("HERD_GW_PEER_NAME", ""),
        "peer_url": os.environ.get("HERD_GW_PEER_URL", ""),
        "__secrets__": {"HERD_PEER_KEY": os.environ.get("HERD_GW_PEER_KEY", ""),
                        "HERD_SECRET": os.environ.get("HERD_GW_SECRET", "")},
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

    adapter = StubAdapter()
    peer_app = web.Application()
    herd._wire_api_server(peer_app, adapter)

    async def harness_agent_post(request: "web.Request") -> "web.Response":
        # HARNESS-ONLY: the plugin's real agent tool handler, invoked in-process. The backend
        # composer route stays human-only on purpose; this route exists only in this script.
        denied = adapter._check_auth(request)
        if denied is not None:
            return denied
        try:
            body = await request.json()
        except (ValueError, json.JSONDecodeError):
            return web.json_response({"error": "Body must be JSON."}, status=400)
        args = {"channel": body.get("channel") or CHANNEL,
                "content": body.get("content") or "",
                "task_id": body.get("task_id")}
        out = await asyncio.to_thread(tools.herd_post, args)  # returns a JSON *string*
        return web.json_response({"tool_result": out})

    peer_app.router.add_post(AGENT_POST_PATH, harness_agent_post)

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
        await runner.cleanup()

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
        self.tmp = Path(tempfile.mkdtemp(prefix="herd-q11-"))
        self.procs: list[subprocess.Popen] = []
        self.logs: list = []

    def spawn(self, name: str, short: str, own_key: str, peer_name: str, peer_url: str,
              peer_key: str, own_secret: str) -> dict:
        home = self.tmp / short
        peer_port, api_port = free_port(), free_port()
        env = dict(os.environ,
                   HERD_GW_HOME=str(home), HERD_GW_NAME=name, HERD_GW_PEER_NAME=peer_name,
                   HERD_GW_PEER_URL=peer_url, HERD_GW_PEER_KEY=peer_key, HERD_GW_KEY=own_key,
                   HERD_GW_SECRET=own_secret,
                   HERD_GW_PEER_PORT=str(peer_port), HERD_GW_API_PORT=str(api_port),
                   # Isolate each gateway from the operator's real ~/.hermes.
                   HERMES_HOME=str(home / "hermes-home"),
                   PYTHONPATH="")
        log = open(self.tmp / f"{short}.log", "w")
        self.logs.append(log)
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--gateway"],
                                env=env, stdout=log, stderr=subprocess.STDOUT)
        self.procs.append(proc)
        return {"name": name, "short": short, "proc": proc, "log": log, "home": home,
                "peer": f"http://127.0.0.1:{peer_port}", "api": f"http://127.0.0.1:{api_port}",
                "key": own_key, "secret": own_secret, "peer_key": peer_key, "gateway_id": ""}

    def stop_procs(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
        for proc in self.procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        for log in self.logs:
            try:
                log.close()
            except Exception:  # noqa: BLE001
                pass

    def cleanup(self) -> None:
        self.stop_procs()
        if not self.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)
        else:
            print(f"kept: {self.tmp}", flush=True)


def ping(gw: dict) -> tuple[int, dict]:
    # Calling a gateway's OWN peer route needs its OWN Hermes Multiplayer secret (not its API_SERVER_KEY).
    status, body = http("GET", gw["peer"] + "/herd/v1/ping", key=gw["secret"])
    return status, (body or {})


def messages(gw: dict, channel_id: str = CHANNEL) -> list[dict]:
    status, body = api(gw, "GET", f"/channels/{urllib.parse.quote(channel_id)}/messages?limit=500")
    return body if status == 200 and isinstance(body, list) else []


def rows_with(gw: dict, mid: str) -> list[dict]:
    return [m for m in messages(gw) if m.get("id") == mid]


def wait_for(gw: dict, mid: str, t0: float, seconds: float = ARRIVAL_TIMEOUT_S):
    """Poll a gateway's own backend (no reload, no refocus) until ``mid`` is there."""
    while time.time() - t0 < seconds:
        rows = rows_with(gw, mid)
        if rows:
            return rows, time.time() - t0
        time.sleep(0.1)
    return [], None


def agent_post(gw: dict, content: str, task_id=None) -> tuple[int, dict]:
    body = {"channel": CHANNEL, "content": content}
    if task_id is not None:
        body["task_id"] = task_id
    status, resp = http("POST", gw["peer"] + AGENT_POST_PATH, body, key=gw["key"])
    try:
        return status, json.loads((resp or {}).get("tool_result") or "{}")
    except (TypeError, ValueError):
        return status, {"raw": resp}


def lat(x) -> str:
    return f"{x:.2f}s" if x is not None else f"not within {ARRIVAL_TIMEOUT_S:.0f}s"


EXCHANGES: list[dict] = []   # every #i exchange row, for §3 and the roll-ups
POSTED: list[str] = []       # every message id this run wrote


def human_exchange(row: str, i: int, src: dict, dst: dict, mid: str, content: str,
                   kick: dict | None, plugin_only: str) -> bool:
    t0 = time.time()
    status, posted = api(src, "POST", f"/channels/{CHANNEL}/messages", {"id": mid, "content": content})
    POSTED.append(mid)
    if kick is not None:
        api(kick, "POST", "/sync", {})
    rows, latency = wait_for(dst, mid, t0)
    r = rows[0] if rows else {}
    ok = (status == 200 and len(rows) == 1 and r.get("content") == content
          and r.get("gateway_id") == src["gateway_id"] and r.get("gateway_name") == src["name"])
    EXCHANGES.append({"row": f"{row}#{i}", "id": mid, "latency": latency, "read_on": dst["name"],
                      "ok": ok, "kick": "driver /sync on A" if kick else plugin_only})
    check(f"{row}#{i}", ok,
          f"id={mid} on {dst['name']}: rows={len(rows)} gateway_id={str(r.get('gateway_id'))[:12]} "
          f"gateway_name={r.get('gateway_name')!r} content_ok={r.get('content') == content} "
          f"latency={lat(latency)} sync={'driver' if kick else 'plugin-only'} (post HTTP {status})")
    return ok


def agent_exchange(row: str, i: int, a: dict, b: dict, content: str, task_id=None,
                   expect_task: str | None = None) -> tuple[bool, str]:
    t0 = time.time()
    status, tool = agent_post(a, content, task_id)
    msg = tool.get("message") or {}
    mid = str(msg.get("id") or "")
    if mid:
        POSTED.append(mid)
    if i > 1 or row.startswith("S-16"):
        api(a, "POST", "/sync", {})
    rows, latency = wait_for(b, mid, t0) if mid else ([], None)
    r = rows[0] if rows else {}
    ok = (status == 200 and tool.get("ok") is True and len(rows) == 1
          and r.get("author_type") == "agent" and r.get("author_name") == msg.get("author_name")
          and r.get("content") == content and r.get("gateway_id") == a["gateway_id"])
    task_detail = ""
    if expect_task is not None:
        ok = ok and r.get("task_id") == expect_task
        task_detail = f" task_id={r.get('task_id')!r} (posted {expect_task!r})"
    EXCHANGES.append({"row": f"{row}#{i}", "id": mid, "latency": latency, "read_on": b["name"],
                      "ok": ok, "kick": "driver /sync on A" if (i > 1 or row.startswith("S-16"))
                      else "none (A's post kicker / 3 s loop)"})
    check(f"{row}#{i}", ok,
          f"tool ok={tool.get('ok')} id={mid} on {b['name']}: rows={len(rows)} "
          f"author_type={r.get('author_type')!r} author_name={r.get('author_name')!r} "
          f"gateway_id={str(r.get('gateway_id'))[:12]} content_ok={r.get('content') == content}"
          f"{task_detail} latency={lat(latency)}")
    return ok, mid


def in_order(gw: dict, ids: list[str]) -> bool:
    order = [m["id"] for m in messages(gw)]
    try:
        pos = [order.index(x) for x in ids]
    except ValueError:
        return False
    return pos == sorted(pos)


# ---------------------------------------------------------------------------
# S-16 (d): a pre-change peer fed the payload A really pushes
# ---------------------------------------------------------------------------


def resolve_old_ref(override: str | None) -> str:
    if override:
        return override
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "--format=%H", "-S", "task_id", "--", "dashboard/herd_store.py"],
            stderr=subprocess.DEVNULL).decode().split()
        if out:
            return out[-1] + "^"   # oldest commit that changed the task_id count = the introducer
    except Exception:  # noqa: BLE001
        pass
    return FALLBACK_OLD_REF


def old_peer_check(a: dict, ref: str, task_ids: list[str]) -> None:
    row = "S-16.pre-change peer ingests the new payload"
    try:
        source = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{ref}:dashboard/herd_store.py"],
                                         stderr=subprocess.PIPE).decode()
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", ref],
                                      stderr=subprocess.DEVNULL).decode().strip()
    except Exception as exc:  # noqa: BLE001
        check(row, False, f"could not read {ref}:dashboard/herd_store.py ({exc.__class__.__name__})")
        return
    info(f"pre-change ref {ref} = {sha}; task_id occurrences in its herd_store.py: "
         f"{source.count('task_id')}")
    if "task_id" in source:
        check(row, False, f"ref {ref} is not pre-change — it already knows task_id")
        return

    # Body from A's REAL export: A's own peer route, A's own key, empty request body.
    status, export = http("POST", a["peer"] + PEER_PATH, {}, key=a["secret"])
    export = export or {}
    tied = [m for m in (export.get("messages") or []) if m.get("id") in task_ids]
    body = {"v": 2, "from": export.get("from"), "channels": export.get("channels"),
            "messages": tied, "reactions": [], "after_seq": 0, "after_rseq": 0}
    with_task = [m for m in tied if m.get("task_id")]
    info(f"A's real export: HTTP {status}, {len(export.get('messages') or [])} rows; "
         f"task-tied rows fed: {[(m['id'][:8], m.get('task_id')) for m in tied]}")
    if not with_task:
        check(row, False, "positive control failed: assembled payload has no row with a non-empty task_id "
                          "(the check would prove nothing)")
        return

    tmp = Path(tempfile.mkdtemp(prefix="herd-q11-prechange-"))
    try:
        path = tmp / "herd_store_prechange.py"
        path.write_text(source)
        spec = importlib.util.spec_from_file_location("herd_store_prechange", path)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        old.DB_PATH_OVERRIDE = tmp / "prechange.db"
        old.SETTINGS_OVERRIDE = {"display_name": "pre-s16", "__secrets__": {}}
        old.AUTO_SYNC = False
        # The desktop broadcast has no listener in the driver process (it only logs a
        # "dropped" traceback); ingest/export logic is untouched.
        old._notify = lambda *_a, **_k: None

        out = old.handle_peer_sync(json.loads(json.dumps(body)))
        problems: list[str] = []
        if not isinstance(out, dict):
            problems.append(f"returned {type(out).__name__}")
            out = {}
        if out.get("v") != 2:
            problems.append(f"v={out.get('v')}")
        stored = {m["id"]: m for m in old.list_messages(CHANNEL, limit=500)}
        for m in tied:
            got = [x for x in old.list_messages(CHANNEL, limit=500) if x["id"] == m["id"]]
            if len(got) != 1:
                problems.append(f"{m['id'][:8]} stored {len(got)}x")
                continue
            g = got[0]
            for k in ("id", "content", "author_type"):
                if g.get(k) != m.get(k):
                    problems.append(f"{m['id'][:8]}.{k} {g.get(k)!r} != {m.get(k)!r}")
        with old.connect() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
        if "task_id" in cols:
            problems.append("pre-change DB has a task_id column")
        out2 = old.handle_peer_sync(json.loads(json.dumps(body)))
        for m in tied:
            n = len([x for x in old.list_messages(CHANNEL, limit=500) if x["id"] == m["id"]])
            if n != 1:
                problems.append(f"re-feed: {m['id'][:8]} stored {n}x")
        check(row, not problems,
              f"ref={ref} ({sha}) v={out.get('v')} accepted={out.get('accepted')} "
              f"re-feed accepted={(out2 or {}).get('accepted')} stored={len([i for i in task_ids if i in stored])}"
              f"/{len(tied)} task_id-column={'task_id' in cols} "
              + ("problems=" + "; ".join(problems) if problems else "id/content/author_type verbatim, idempotent"))

        exported = old.export_batch(0).get("messages") or []
        leaked = [m["id"] for m in exported if "task_id" in m]
        check("S-16.pre-change export_batch has no task_id key", bool(exported) and not leaked,
              f"{len(exported)} rows exported by the pre-change module, {len(leaked)} carry task_id "
              f"(keys: {sorted(exported[0].keys()) if exported else []})")
    except Exception as exc:  # noqa: BLE001
        check(row, False, f"raised {exc.__class__.__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_peer_state(home: Path) -> list[dict]:
    """After the gateways stop: A's peer_state cursors (not exposed by GET /status)."""
    try:
        path = ROOT / "dashboard" / "herd_store.py"
        spec = importlib.util.spec_from_file_location("herd_store_peerstate_reader", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.DB_PATH_OVERRIDE = home / "herd.db"
        mod.SETTINGS_OVERRIDE = {"__secrets__": {}}
        mod.AUTO_SYNC = False
        with mod.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT url, push_seq, pull_seq, remote_name, last_ok, last_error FROM peer_state").fetchall()]
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"{exc.__class__.__name__}: {exc}"}]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gateway", action="store_true", help="internal: run ONE gateway process")
    parser.add_argument("--keep", action="store_true", help="keep temp homes + gateway logs")
    parser.add_argument("--old-peer-ref", default=None, help="pre-S-16 git ref for the old-peer check")
    args = parser.parse_args()
    if args.gateway:
        return gateway_main()

    run = Run(keep=args.keep)
    started = time.time()
    try:
        print("== Q-11 two-gateway SPINE run ==", flush=True)
        print(f"  root:    {ROOT}")
        print(f"  workdir: {run.tmp}")
        # B first (no peer configured: the README's one-sided link), then A linked to B.
        b = run.spawn(NAME_B, "b", KEY_B, "", "", "", own_secret=SECRET_B)
        a = run.spawn(NAME_A, "a", KEY_A, NAME_B, b["peer"], SECRET_B, own_secret=SECRET_A)
        if not (wait_up(a["api"] + API_PREFIX + "/status", "", 40)
                and wait_up(b["api"] + API_PREFIX + "/status", "", 40)
                and wait_up(a["peer"] + "/herd/v1/ping", a["secret"], 20)
                and wait_up(b["peer"] + "/herd/v1/ping", b["secret"], 20)):
            print("  gateway failed to start; log tails:")
            for gw in (a, b):
                gw["log"].flush()
                print(f"  --- {gw['name']} ({gw['log'].name}) ---")
                print(Path(gw["log"].name).read_text()[-2000:])
            return 2
        print(f"  A ({NAME_A}) api={a['api']}  peer={a['peer']}")
        print(f"  B ({NAME_B}) api={b['api']}  peer={b['peer']}")
        print()

        # --- ENV ---------------------------------------------------------------
        sa, _ = api(a, "GET", "/status")
        sb, _ = api(b, "GET", "/status")
        pa, ping_a = ping(a)
        pb, ping_b = ping(b)
        a["gateway_id"] = (ping_a.get("from") or {}).get("gateway_id", "")
        b["gateway_id"] = (ping_b.get("from") or {}).get("gateway_id", "")
        check("ENV.healthy", sa == 200 and sb == 200 and pa == 200 and pb == 200
              and bool(a["gateway_id"]) and bool(b["gateway_id"]),
              f"/status A={sa} B={sb}; /herd/v1/ping A={pa} B={pb}; "
              f"A.gateway_id={a['gateway_id']} B.gateway_id={b['gateway_id']} v={ping_a.get('v')}")
        check("ENV.settings", (ping_a.get("from") or {}).get("display_name") == NAME_A,
              f"A ping display_name={(ping_a.get('from') or {}).get('display_name')!r} (spawned as {NAME_A!r})")
        # S-20: the gateway's API_SERVER_KEY must NOT open Hermes Multiplayer's peer routes (only its Hermes Multiplayer secret does).
        ka, kbody_a = http("GET", a["peer"] + "/herd/v1/ping", key=a["key"])
        kb, kbody_b = http("GET", b["peer"] + "/herd/v1/ping", key=b["key"])
        codes = [((body or {}).get("error") or {}).get("code") if isinstance((body or {}).get("error"), dict)
                 else None for body in (kbody_a, kbody_b)]
        check("ENV.gateway-key-refused", ka == 401 and kb == 401
              and codes == ["gateway_auth_failed", "gateway_auth_failed"],
              f"/herd/v1/ping with API_SERVER_KEY: A={ka} B={kb}; error.code={codes}")

        # --- TC-2.1 A->B ---------------------------------------------------------
        print("\n-- TC-2.1  A -> B (human, A's composer route; read on B) --")
        ids = []
        oks = []
        for i in (1, 2, 3):
            mid = f"q11-a2b-{i}"
            ids.append(mid)
            # i==1: no driver /sync — delivery must ride the plugin's own kicker / 3 s loop.
            oks.append(human_exchange("TC-2.1.A->B", i, a, b, mid, f"Q-11 A->B exchange {i}",
                                      None if i == 1 else a, "none (A's post kicker / 3 s loop)"))
        check("TC-2.1.A->B (3 consecutive)", all(oks) and in_order(b, ids),
              f"landed={sum(oks)}/3 in-order-on-B={in_order(b, ids)}")

        # --- TC-2.2 B->A ---------------------------------------------------------
        # B has no peer configured, so B's own /sync is a no-op; delivery is A's pull (the
        # linked side pushes AND pulls). #1 rides A's 3 s loop alone; #2/#3 kick A's /sync.
        print("\n-- TC-2.2  B -> A (human, B's composer route; read on A) --")
        # Settle first: A's post-kicker from TC-2.1#3 sleeps 50 ms before syncing, and without
        # a gap it (not the loop) would pick up #1. After the gap nothing on A is pending, so
        # #1 can only arrive by A's 3 s background loop pass (A's last_attempt must advance).
        time.sleep(0.5)
        ids = []
        oks = []
        for i in (1, 2, 3):
            mid = f"q11-b2a-{i}"
            ids.append(mid)
            if i == 1:
                _, st0 = api(a, "GET", "/status")
                attempt0 = (((st0 or {}).get("peers") or [{}])[0]).get("last_attempt", "")
            oks.append(human_exchange("TC-2.2.B->A", i, b, a, mid, f"Q-11 B->A exchange {i}",
                                      None if i == 1 else a, "none (A's 3 s loop pulls; B has no peer)"))
            if i == 1:
                _, st1 = api(a, "GET", "/status")
                attempt1 = (((st1 or {}).get("peers") or [{}])[0]).get("last_attempt", "")
                info(f"TC-2.2#1 delivered by A's background loop: A last_attempt {attempt0} -> {attempt1} "
                     "(no driver /sync, no A-side post, B has no peer configured)")
        check("TC-2.2.B->A (3 consecutive)", all(oks) and in_order(a, ids),
              f"landed={sum(oks)}/3 in-order-on-A={in_order(a, ids)}")

        # --- TC-2.3 agent on A -> B ---------------------------------------------
        print("\n-- TC-2.3  agent on A (tools.herd_post in-process) -> read on B --")
        ids = []
        oks = []
        for i in (1, 2, 3):
            ok, mid = agent_exchange("TC-2.3.agent->B", i, a, b, f"Q-11 agent answer {i}")
            oks.append(ok)
            ids.append(mid)
        check("TC-2.3.agent->B (3 consecutive)", all(oks) and in_order(b, ids),
              f"landed={sum(oks)}/3 in-order-on-B={in_order(b, ids)}")

        # --- S-16 ---------------------------------------------------------------
        print("\n-- S-16  task_id payload regression --")
        s16_ids = []
        oks = []
        for i, tid in enumerate(S16_TASK_IDS, start=1):
            ok, mid = agent_exchange("S-16.task_id", i, a, b, f"Q-11 S-16 answer for {tid}",
                                     task_id=tid, expect_task=tid)
            oks.append(ok)
            s16_ids.append(mid)
        check("S-16.task_id round-trip (3 consecutive)", all(oks) and in_order(b, s16_ids),
              f"landed={sum(oks)}/3 in-order-on-B={in_order(b, s16_ids)}")

        # (b) absent stays absent
        t0 = time.time()
        content = "Q-11 S-16 answer with no task"
        st, tool = agent_post(a, content)
        mid = str((tool.get("message") or {}).get("id") or "")
        if mid:
            POSTED.append(mid)
        api(a, "POST", "/sync", {})
        rows_b, latency = wait_for(b, mid, t0) if mid else ([], None)
        rows_a = rows_with(a, mid) if mid else []
        tb = rows_b[0].get("task_id") if rows_b else "MISSING"
        ta = rows_a[0].get("task_id") if rows_a else "MISSING"
        check("S-16.task_id absent stays absent",
              tool.get("ok") is True and len(rows_b) == 1 and len(rows_a) == 1
              and tb in ("", None) and ta in ("", None) and rows_b[0].get("content") == content,
              f"id={mid} B.task_id={tb!r} A.task_id={ta!r} tool.task_id={(tool.get('message') or {}).get('task_id')!r} "
              f"latency={lat(latency)}")

        # (c) a bad task_id is refused and nothing is written
        before_a = len(messages(a))
        bad_content = "Q-11 S-16 bad task id: this must never be written"
        st, tool = agent_post(a, bad_content, task_id="not-a-task")
        api(a, "POST", "/sync", {})
        time.sleep(1.0)
        after_a = len(messages(a))
        seen = [g["name"] for g in (a, b) if any(m.get("content") == bad_content for m in messages(g))]
        check("S-16.bad task_id refused",
              tool.get("ok") is False and after_a == before_a and not seen,
              f"tool={json.dumps(tool)[:140]} A count {before_a}->{after_a} content seen on={seen}")

        # (d) a pre-change peer ingests the payload A really pushes
        ref = resolve_old_ref(args.old_peer_ref)
        old_peer_check(a, ref, s16_ids)

        # --- Q-11 roll-ups -------------------------------------------------------
        print("\n-- Q-11 roll-ups --")
        exch_ok = [e for e in EXCHANGES if e["ok"]]
        check("Q-11.three-consecutive", len(EXCHANGES) == 12 and len(exch_ok) == 12,
              f"{len(exch_ok)}/{len(EXCHANGES)} #1/#2/#3 exchange rows landed "
              "(TC-2.1, TC-2.2, TC-2.3, S-16.task_id)")
        api(a, "POST", "/sync", {})
        time.sleep(0.5)
        ma, mb = messages(a), messages(b)
        dup = []
        for mid in POSTED:
            na = sum(1 for m in ma if m["id"] == mid)
            nb = sum(1 for m in mb if m["id"] == mid)
            if na != 1 or nb != 1:
                dup.append(f"{mid}:A={na},B={nb}")
        check("Q-11.no-duplicates", bool(POSTED) and not dup,
              f"{len(POSTED)} ids posted; every one held exactly once on A and on B"
              if not dup else f"{dup}")

        # --- sync state ----------------------------------------------------------
        print("\n-- sync state (A = linked side, B = one-sided) --")
        _, st_a = api(a, "GET", "/status")
        _, st_b = api(b, "GET", "/status")
        peers = (st_a or {}).get("peers") or []
        incoming = (st_b or {}).get("incoming") or []
        for p in peers:
            info(f"A /status peer: name={p.get('name')} url={p.get('url')} remote_name={p.get('remote_name')} "
                 f"connected={p.get('connected')} last_ok={p.get('last_ok')} "
                 f"last_attempt={p.get('last_attempt')} last_error={p.get('last_error')!r}")
        for inc in incoming:
            info(f"B /status incoming: gateway_id={inc.get('gateway_id')} name={inc.get('name')} "
                 f"syncs={inc.get('syncs')} last_seen={inc.get('last_seen')} linked_back={inc.get('linked_back')}")
        info(f"B /status peers configured: {len((st_b or {}).get('peers') or [])} (one-sided link)")
        a_in = next((x for x in incoming if x.get("gateway_id") == a["gateway_id"]), None)
        check("SYNC.link-healthy",
              len(peers) == 1 and peers[0].get("connected") is True and not peers[0].get("last_error")
              and peers[0].get("remote_name") == NAME_B and a_in is not None and int(a_in.get("syncs") or 0) > 0,
              f"A->B connected={peers[0].get('connected') if peers else None} "
              f"last_error={peers[0].get('last_error') if peers else None!r}; "
              f"B saw A {a_in.get('syncs') if a_in else 0} syncs")
        info(f"A has {len(ma)} rows in #{CHANNEL}, B has {len(mb)} rows in #{CHANNEL}")

        # Stop the gateways, then read A's peer_state cursors from its SQLite file.
        run.stop_procs()
        for ps in read_peer_state(a["home"]):
            info(f"A peer_state (after stop): {json.dumps(ps)}")

        print("\n-- three-consecutive table --")
        for e in EXCHANGES:
            print(f"  {e['row']:<18} id={e['id']:<36} read_on={e['read_on']}  latency={lat(e['latency']):<8} "
                  f"sync={e['kick']}  {'PASS' if e['ok'] else 'FAIL'}")

        print("\n== summary ==")
        failed = [r for r in RESULTS if not r[1]]
        for tc, ok, _detail in RESULTS:
            print(f"  {'PASS' if ok else 'FAIL'}  {tc}")
        print(f"  {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed "
              f"({time.time() - started:.1f}s)")
        return 1 if failed else 0
    finally:
        run.cleanup()


if __name__ == "__main__":
    sys.exit(main())
