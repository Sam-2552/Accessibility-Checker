"""SQLite database layer for WebAPT web interface."""

import sqlite3
import hashlib
import secrets
import os
import re
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.environ.get("WEBAPT_DB", "webapt.db")


# ── Display helpers ───────────────────────────────────────────────────────────

def redact_credentials(text: str) -> str:
    """Redact passwords and credentials from task text for display."""
    if not text:
        return text
    # Pattern: word/word (username/password style) — but NOT http:// or https://
    text = re.sub(
        r'(?<![:/])(?<!\w)\b(\w[\w.@+-]*)/(\w+)\b(?=\s|$|,|\.)',
        lambda m: f"{m.group(1)}/{'*' * len(m.group(2))}",
        text,
    )
    # Pattern: password: value or pass: value
    text = re.sub(
        r'(password|pass|passwd|pwd|secret)\s*[=:]\s*\S+',
        r'\1: [REDACTED]',
        text,
        flags=re.IGNORECASE,
    )
    # Pattern: credentials: user/pass or credentials user pass
    text = re.sub(
        r'(credentials?|creds?)\s+(\S+)\s+(\S+)',
        r'\1 \2 [REDACTED]',
        text,
        flags=re.IGNORECASE,
    )
    return text


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_conn():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt        TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                is_admin    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                task_type   TEXT NOT NULL CHECK(task_type IN ('accessibility','analysis','full')),
                target_url  TEXT NOT NULL,
                extra_task  TEXT NOT NULL DEFAULT '',
                project_name TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'queued'
                            CHECK(status IN ('queued','running','done','failed','cancelled')),
                queue_pos   INTEGER,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                started_at  TEXT,
                finished_at TEXT,
                result_summary TEXT,
                output_dir  TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at  TEXT NOT NULL
            );
        """)
        # Seed a default admin if no users exist
        row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
        if row["c"] == 0:
            _create_user_inner(conn, "admin", "admin123", is_admin=1)
            print("[DB] Created default admin user: admin / admin123")


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()


def _create_user_inner(conn, username: str, password: str, is_admin: int = 0):
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, is_admin) VALUES (?,?,?,?)",
        (username, pw_hash, salt, is_admin),
    )


def create_user(username: str, password: str, is_admin: bool = False) -> bool:
    try:
        with db_conn() as conn:
            _create_user_inner(conn, username, password, int(is_admin))
        return True
    except sqlite3.IntegrityError:
        return False


def authenticate(username: str, password: str):
    """Returns user row or None."""
    with db_conn() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            return None
        expected = _hash_password(password, user["salt"])
        if secrets.compare_digest(expected, user["password_hash"]):
            return dict(user)
        return None


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with db_conn() as conn:
        conn.execute(
            """INSERT INTO sessions (token, user_id, expires_at)
               VALUES (?, ?, datetime('now', '+7 days'))""",
            (token, user_id),
        )
    return token


def get_session_user(token: str):
    if not token:
        return None
    with db_conn() as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token = ? AND s.expires_at > datetime('now')""",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def delete_session(token: str):
    with db_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ── Task/Queue helpers ────────────────────────────────────────────────────────

def enqueue_task(user_id: int, task_type: str, target_url: str,
                 extra_task: str, project_name: str) -> int:
    with db_conn() as conn:
        # Compute queue position (queued + running tasks count + 1)
        count = conn.execute(
            "SELECT COUNT(*) as c FROM tasks WHERE status IN ('queued','running')"
        ).fetchone()["c"]
        cursor = conn.execute(
            """INSERT INTO tasks
               (user_id, task_type, target_url, extra_task, project_name, status, queue_pos)
               VALUES (?,?,?,?,?,'queued',?)""",
            (user_id, task_type, target_url, extra_task, project_name, count + 1),
        )
        return cursor.lastrowid


def get_queue():
    """All queued and running tasks, ordered by queue position."""
    with db_conn() as conn:
        rows = conn.execute(
            """SELECT t.*, u.username FROM tasks t
               JOIN users u ON u.id = t.user_id
               WHERE t.status IN ('queued','running')
               ORDER BY t.queue_pos ASC, t.created_at ASC""",
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int):
    with db_conn() as conn:
        row = conn.execute(
            "SELECT t.*, u.username FROM tasks t JOIN users u ON u.id = t.user_id WHERE t.id = ?",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None


def get_next_queued_task():
    with db_conn() as conn:
        row = conn.execute(
            """SELECT * FROM tasks WHERE status = 'queued'
               ORDER BY queue_pos ASC, created_at ASC LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None


def set_task_running(task_id: int):
    with db_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='running', started_at=datetime('now') WHERE id=?",
            (task_id,),
        )


def set_task_done(task_id: int, summary: str, output_dir: str):
    with db_conn() as conn:
        conn.execute(
            """UPDATE tasks SET status='done', finished_at=datetime('now'),
               result_summary=?, output_dir=? WHERE id=?""",
            (summary, output_dir, task_id),
        )


def set_task_failed(task_id: int, error: str):
    with db_conn() as conn:
        conn.execute(
            """UPDATE tasks SET status='failed', finished_at=datetime('now'),
               result_summary=? WHERE id=?""",
            (error[:2000], task_id),
        )


def cancel_task(task_id: int, user_id: int) -> bool:
    with db_conn() as conn:
        result = conn.execute(
            """UPDATE tasks SET status='cancelled', finished_at=datetime('now')
               WHERE id=? AND user_id=? AND status='queued'""",
            (task_id, user_id),
        )
        return result.rowcount > 0


def get_user_tasks(user_id: int, limit: int = 20):
    with db_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks WHERE user_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_tasks(limit: int = 50):
    with db_conn() as conn:
        rows = conn.execute(
            """SELECT t.*, u.username FROM tasks t
               JOIN users u ON u.id = t.user_id
               ORDER BY t.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def recompute_queue_positions():
    """Recalculate queue_pos for all queued tasks after a cancellation."""
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM tasks WHERE status='queued' ORDER BY queue_pos ASC, created_at ASC"
        ).fetchall()
        for i, row in enumerate(rows, start=2):  # running task holds pos 1
            conn.execute("UPDATE tasks SET queue_pos=? WHERE id=?", (i, row["id"]))
