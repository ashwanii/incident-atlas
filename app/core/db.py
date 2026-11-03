import sqlite3
from contextlib import contextmanager
from app.core import config

@contextmanager
def connection(write=False):
    db = sqlite3.connect(config.DB_PATH, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        if write:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def initialize():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY, source_key TEXT UNIQUE NOT NULL,
          title TEXT NOT NULL, kind TEXT NOT NULL, services TEXT NOT NULL,
          content TEXT NOT NULL, digest TEXT NOT NULL, version INTEGER NOT NULL,
          status TEXT NOT NULL, confidence REAL NOT NULL, reasons TEXT NOT NULL,
          origin TEXT NOT NULL, updated_at TEXT NOT NULL, owner TEXT NOT NULL,
          reviewed_on TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS aliases (source_key TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id));
        CREATE TABLE IF NOT EXISTS versions (
          document_id TEXT NOT NULL, version INTEGER NOT NULL, snapshot TEXT NOT NULL,
          PRIMARY KEY(document_id, version));
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY, document_id TEXT, action TEXT, at TEXT);
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, document_id TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS telemetry (
          id INTEGER PRIMARY KEY, route TEXT, status INTEGER, latency_ms REAL, at TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
          document_id UNINDEXED, title, services, content, tokenize='porter unicode61');
        CREATE INDEX IF NOT EXISTS doc_status ON documents(status, deleted, kind);
        """)
