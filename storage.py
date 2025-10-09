# storage.py
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT UNIQUE,
  title TEXT,
  snippet TEXT,
  retrieved_at TEXT,
  search_query TEXT,
  rank INTEGER
);
CREATE TABLE IF NOT EXISTS passages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER,
  passage TEXT,
  score REAL,
  saved_at TEXT,
  note TEXT,
  FOREIGN KEY(source_id) REFERENCES sources(id)
);
"""

def get_conn(db_path="searchagent.db"):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return conn

def init_db(conn):
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    conn.commit()

def save_source(conn, url, title, snippet, query, rank):
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("""
      INSERT OR IGNORE INTO sources (url, title, snippet, retrieved_at, search_query, rank)
      VALUES (?, ?, ?, ?, ?, ?)
    """, (url, title, snippet, now, query, rank))
    conn.commit()
    cur.execute("SELECT id FROM sources WHERE url = ?", (url,))
    row = cur.fetchone()
    return row[0] if row else None

def save_passage(conn, source_id, passage, score, note=""):
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("""
      INSERT INTO passages (source_id, passage, score, saved_at, note)
      VALUES (?, ?, ?, ?, ?)
    """, (source_id, passage, score, now, note))
    conn.commit()
    return cur.lastrowid
