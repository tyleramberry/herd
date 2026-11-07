"""Read-only Kanban task titles for Herd's task badge (S-16 / F4).

What it reads: exactly one value — ``SELECT title FROM tasks WHERE id = ?`` — from the local Hermes
Kanban database (``<hermes root>/kanban.db`` or ``<root>/kanban/boards/<slug>/kanban.db``), so the
Herd pane can label an agent's answer with the title of the task the agent explicitly linked.

Read-only: the file is opened with the SQLite ``mode=ro`` URI and a short busy timeout; it is never
written, migrated or created, and no private core module is imported.

Soft-degrade: any failure (missing file, missing table, locked, corrupt) yields ``None`` and the
caller shows the task id alone. Nothing here raises out of the read path and no title is invented.

Disclosed under rule 13 in the README ("Reads outside plugin data").

Standalone on purpose: no relative imports, because the dashboard host may load it by path.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

TASK_ID_RE = re.compile(r"^t_[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_TITLE = 200
READ_TIMEOUT_S = 0.25
# Tests point this at a temp kanban.db; production resolves the Hermes root below.
DB_PATH_OVERRIDE: Optional[Path] = None


def normalize_task_id(value: Any) -> Optional[str]:
    """The task id if it is exactly a Kanban id, else None. No case-folding, repair or truncation."""
    text = str(value or "").strip()
    return text if TASK_ID_RE.match(text) else None


def hermes_root() -> Optional[Path]:
    """The Hermes root (e.g. ``~/.hermes``), profile-aware via core; None if core can't say."""
    try:
        from hermes_constants import get_default_hermes_root

        return Path(get_default_hermes_root())
    except Exception:  # noqa: BLE001
        return None


def board_slug() -> str:
    """The current board slug (``<root>/kanban/current``), or ``default`` when unset or malformed."""
    try:
        root = hermes_root()
        if root is None:
            return "default"
        slug = (root / "kanban" / "current").read_text(encoding="utf-8").strip()
        return slug if SLUG_RE.match(slug) else "default"
    except Exception:  # noqa: BLE001
        return "default"


def kanban_db_path() -> Optional[Path]:
    """Where the Kanban DB is, or None. Never creates anything."""
    if DB_PATH_OVERRIDE is not None:
        return Path(DB_PATH_OVERRIDE)
    root = hermes_root()
    if root is None:
        return None
    slug = board_slug()
    legacy = root / "kanban.db"
    candidate = legacy if slug == "default" else root / "kanban" / "boards" / slug / "kanban.db"
    try:
        if candidate.is_file():
            return candidate
        # Older layouts, or a stale ``current`` slug pointing at a board that is gone.
        if legacy.is_file():
            return legacy
    except OSError:
        return None
    return None


def task_title(task_id: Any) -> Optional[str]:
    """The task's title, read-only, or None for anything short of a clean hit."""
    tid = normalize_task_id(task_id)
    if not tid:
        return None
    try:
        path = kanban_db_path()
        if path is None or not path.is_file():
            return None
    except Exception:  # noqa: BLE001
        return None
    conn = None
    try:
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=READ_TIMEOUT_S)
        conn.execute("PRAGMA busy_timeout=250")
        row = conn.execute("SELECT title FROM tasks WHERE id = ?", (tid,)).fetchone()
        if row is None:
            return None
        title = row[0]
        if not isinstance(title, str) or not title.strip():
            return None
        return title.strip()[:MAX_TITLE]
    except Exception:  # noqa: BLE001
        return None
    finally:
        if conn is not None:
            conn.close()


def task_link(task_id: Any) -> dict:
    """What the badge endpoint returns for one id. Never raises."""
    try:
        tid = normalize_task_id(task_id)
        return {"task_id": tid or "", "valid": bool(tid),
                "title": task_title(tid) if tid else None, "board": board_slug()}
    except Exception:  # noqa: BLE001
        return {"task_id": "", "valid": False, "title": None, "board": ""}
