"""公共数据库层 — 初始化、保存、查询"""
import sqlite3, json
from datetime import datetime, timezone


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_link TEXT UNIQUE NOT NULL,
            title TEXT,
            company TEXT,
            location TEXT,
            salary TEXT,
            description TEXT,
            posted TEXT,
            posted_hours INTEGER,
            badges TEXT,
            keyword TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            applied INTEGER DEFAULT 0,
            applied_at TEXT,
            progress TEXT,
            can_auto_apply INTEGER DEFAULT 1,
            last_apply_status TEXT,
            user_disabled INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crawl_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawled_at TEXT NOT NULL,
            keyword TEXT,
            salary TEXT,
            total_fetched INTEGER,
            new_jobs INTEGER,
            updated_jobs INTEGER
        )
    """)
    # 兼容旧表
    for col, typ in [
        ("applied", "INTEGER DEFAULT 0"), ("applied_at", "TEXT"),
        ("progress", "TEXT"), ("posted_hours", "INTEGER"),
        ("can_auto_apply", "INTEGER DEFAULT 1"),
        ("last_apply_status", "TEXT"),
    ]:
        try: conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError: pass
    conn.commit()
    return conn


def stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    today = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND date(first_seen)=date('now')").fetchone()[0]
    ext = conn.execute("SELECT COUNT(*) FROM jobs WHERE can_auto_apply=0").fetchone()[0]
    applied = conn.execute("SELECT COUNT(*) FROM jobs WHERE applied=1").fetchone()[0]
    unknown = conn.execute("SELECT COUNT(*) FROM jobs WHERE last_apply_status='unknown_questions'").fetchone()[0]
    return total, today, ext, applied, unknown
