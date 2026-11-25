#!/usr/bin/env python3
"""Optional personal SQLite task board. Commands: init-db, add, set-status, get, list; optional --db."""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
from storage import personal_root, private_path
DEFAULT_DB = None

VALID_STATUSES = {
    "archived", "blocked", "done", "ready", "review", "running", "scheduled", "todo", "triage"
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at INTEGER NOT NULL
)
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = private_path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def cmd_init_db(db_path: Path) -> int:
    conn = connect(db_path)
    with conn:
        conn.execute(SCHEMA)
    conn.close()
    print(json.dumps({"ok": True, "db": str(db_path)}))
    return 0


def cmd_add(db_path: Path, task_id: str, title: str, status: str) -> int:
    if status not in VALID_STATUSES:
        print(json.dumps({"ok": False, "error": f"invalid status: {status}"}))
        return 1
    conn = connect(db_path)
    try:
        with conn:
            conn.execute(SCHEMA)
            conn.execute(
                "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
                (task_id, title, status, int(time.time())),
            )
    except sqlite3.IntegrityError:
        print(json.dumps({"ok": False, "error": f"task exists: {task_id}"}))
        return 1
    finally:
        conn.close()
    print(json.dumps({"ok": True, "id": task_id, "status": status}))
    return 0


def cmd_set_status(db_path: Path, task_id: str, status: str) -> int:
    if status not in VALID_STATUSES:
        print(json.dumps({"ok": False, "error": f"invalid status: {status}"}))
        return 1
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        if cur.rowcount == 0:
            print(json.dumps({"ok": False, "error": f"task not found: {task_id}"}))
            return 1
    finally:
        conn.close()
    print(json.dumps({"ok": True, "id": task_id, "status": status}))
    return 0


def cmd_get(db_path: Path, task_id: str) -> int:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        print(json.dumps({"ok": False, "error": f"task not found: {task_id}"}))
        return 1
    print(json.dumps({"ok": True, "id": row[0], "title": row[1], "status": row[2], "created_at": row[3]}))
    return 0


def cmd_list(db_path: Path) -> int:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, title, status, created_at FROM tasks ORDER BY created_at"
        ).fetchall()
    finally:
        conn.close()
    print(json.dumps({"ok": True, "tasks": [
        {"id": r[0], "title": r[1], "status": r[2], "created_at": r[3]} for r in rows
    ]}))
    return 0


def main() -> int:
    args = sys.argv[1:]
    db_path = DEFAULT_DB
    if "--db" in args:
        idx = args.index("--db")
        if idx + 1 >= len(args):
            print("--db requires a path", file=sys.stderr)
            return 1
        db_path = Path(args[idx + 1]).expanduser().resolve()
        del args[idx:idx + 2]

    if db_path is None:
        db_path = personal_root() / "kanban.db"

    if not args:
        print(__doc__, file=sys.stderr)
        return 1

    cmd, rest = args[0], args[1:]
    if cmd == "init-db":
        return cmd_init_db(db_path)
    if cmd == "add" and len(rest) >= 2:
        return cmd_add(db_path, rest[0], rest[1], rest[2] if len(rest) > 2 else "todo")
    if cmd == "set-status" and len(rest) == 2:
        return cmd_set_status(db_path, rest[0], rest[1])
    if cmd == "get" and len(rest) == 1:
        return cmd_get(db_path, rest[0])
    if cmd == "list":
        return cmd_list(db_path)
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
