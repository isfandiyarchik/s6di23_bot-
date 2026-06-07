import psycopg2
from psycopg2 import pool as psycopg2_pool
from contextlib import contextmanager
from threading import Lock
from datetime import datetime, timedelta
import os
import json
import logging
import math

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL") or ""

UZ_OFFSET = timedelta(hours=5)
def now_uz(): return datetime.utcnow() + UZ_OFFSET

# ── DB POOL ───────────────────────────────────────────────────
_db_pool = None
_db_pool_lock = Lock()

def get_pool():
    global _db_pool
    if _db_pool is None:
        with _db_pool_lock:
            if _db_pool is None:
                if not DATABASE_URL:
                    raise RuntimeError("DATABASE_URL орнатылмаған!")
                _db_pool = psycopg2_pool.ThreadedConnectionPool(
                    minconn=2, maxconn=15, dsn=DATABASE_URL, connect_timeout=10)
    return _db_pool

def get_db():
    p = get_pool()
    conn = p.getconn()
    try:
        conn.cursor().execute("SELECT 1")
    except Exception:
        try:
            p.putconn(conn, close=True)
        except Exception:
            pass
        conn = p.getconn()
    return conn, conn.cursor()

def release_db(conn):
    try:
        get_pool().putconn(conn)
    except Exception as e:
        logger.warning(f"release_db: {e}")

@contextmanager
def db_cursor():
    conn, cursor = get_db()
    try:
        yield conn, cursor
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        release_db(conn)

# ── INIT DB ───────────────────────────────────────────────────
def init_db():
    tables = [
        """CREATE TABLE IF NOT EXISTS students (
            id BIGINT PRIMARY KEY, username TEXT, last_active TIMESTAMP,
            full_name TEXT, birth_date TEXT, phone TEXT, hemis TEXT, started INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS user_news (
            id SERIAL PRIMARY KEY, content TEXT, author_id BIGINT,
            author_username TEXT, date TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS materials (
            id SERIAL PRIMARY KEY, file_id TEXT, file_type TEXT,
            uploader_id BIGINT, uploader_username TEXT, date TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS gallery (
            id SERIAL PRIMARY KEY, file_id TEXT, file_type TEXT,
            uploader_id BIGINT, uploader_username TEXT, date TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS schedule (
            id SERIAL PRIMARY KEY, day TEXT, subject TEXT, time TEXT)""",
        """CREATE TABLE IF NOT EXISTS suggestions (
            id SERIAL PRIMARY KEY, content TEXT, user_id BIGINT, date TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY, date TEXT, para INTEGER, subject TEXT,
            student_id BIGINT, student_name TEXT, status TEXT, marked_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY, type TEXT, name TEXT, phone TEXT)""",
        """CREATE TABLE IF NOT EXISTS contracts (
            id SERIAL PRIMARY KEY, student_id BIGINT UNIQUE, total_amount REAL, note TEXT)""",
        """CREATE TABLE IF NOT EXISTS contract_payments (
            id SERIAL PRIMARY KEY, student_id BIGINT, amount REAL, date TEXT, note TEXT)""",
        """CREATE TABLE IF NOT EXISTS test_variants (
            id SERIAL PRIMARY KEY, subject TEXT, file_id TEXT, file_type TEXT,
            file_name TEXT, uploader_id BIGINT, date TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS user_states (
            user_id BIGINT PRIMARY KEY, state TEXT, updated_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS attendance_sessions (
            admin_id BIGINT PRIMARY KEY, session_data TEXT, updated_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS blocked_users (
            user_id BIGINT PRIMARY KEY, reason TEXT, blocked_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS ai_history (
            user_id BIGINT PRIMARY KEY, history TEXT, updated_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS sent_reminders (
            key TEXT PRIMARY KEY, sent_at TIMESTAMP DEFAULT NOW())""",
    ]
    migrations = [
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS full_name TEXT",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS birth_date TEXT",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS phone TEXT",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS hemis TEXT",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS started INTEGER DEFAULT 0",
    ]
    with db_cursor() as (conn, cursor):
        for sql in tables:
            cursor.execute(sql)
        for sql in migrations:
            try:
                cursor.execute(sql)
            except Exception:
                conn.rollback()
        conn.commit()

# ── STATE ─────────────────────────────────────────────────────
_state_cache: dict = {}
_state_cache_lock = Lock()

def set_user_state(uid, state):
    with _state_cache_lock:
        _state_cache[uid] = state
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute(
                "INSERT INTO user_states(user_id,state,updated_at) VALUES(%s,%s,%s) "
                "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at",
                (uid, state, now_uz()))
            conn.commit()
    except Exception as e:
        logger.warning(f"set_user_state DB: {e}")

def get_user_state(uid):
    with _state_cache_lock:
        if uid in _state_cache:
            return _state_cache[uid]
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT state FROM user_states WHERE user_id=%s", (uid,))
            row = cursor.fetchone()
        val = row[0] if row else None
        with _state_cache_lock:
            _state_cache[uid] = val
        return val
    except Exception as e:
        logger.warning(f"get_user_state DB: {e}")
        return None

def clear_user_state(uid):
    with _state_cache_lock:
        _state_cache[uid] = None
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM user_states WHERE user_id=%s", (uid,))
            conn.commit()
    except Exception as e:
        logger.warning(f"clear_user_state DB: {e}")

# ── ATTENDANCE SESSION ────────────────────────────────────────
def save_attendance_session(admin_id, session):
    with db_cursor() as (conn, cursor):
        cursor.execute(
            "INSERT INTO attendance_sessions(admin_id,session_data,updated_at) VALUES(%s,%s,%s) "
            "ON CONFLICT(admin_id) DO UPDATE SET session_data=excluded.session_data,updated_at=excluded.updated_at",
            (admin_id, json.dumps(session, ensure_ascii=False), now_uz()))
        conn.commit()

def load_attendance_session(admin_id):
    with db_cursor() as (_, cursor):
        cursor.execute("SELECT session_data FROM attendance_sessions WHERE admin_id=%s", (admin_id,))
        row = cursor.fetchone()
    if not row: return None
    s = json.loads(row[0])
    if "results" in s:
        s["results"] = {int(k): v for k, v in s["results"].items()}
    return s

def delete_attendance_session(admin_id):
    with db_cursor() as (conn, cursor):
        cursor.execute("DELETE FROM attendance_sessions WHERE admin_id=%s", (admin_id,))
        conn.commit()

def cleanup_old_sessions():
    with db_cursor() as (conn, cursor):
        cursor.execute("DELETE FROM attendance_sessions WHERE updated_at < %s",
                       (now_uz() - timedelta(hours=2),))
        conn.commit()

# ── REMINDER HELPERS ──────────────────────────────────────────
def reminder_already_sent(key: str) -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT key FROM sent_reminders WHERE key=%s", (key,))
            return cursor.fetchone() is not None
    except Exception:
        return False

def mark_reminder_sent(key: str):
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute(
                "INSERT INTO sent_reminders(key, sent_at) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING",
                (key, now_uz()))
            conn.commit()
    except Exception as e:
        logger.warning(f"mark_reminder_sent({key}): {e}")
