"""
SQLite persistence for Audit Bot — chat history, risk scans, findings.
Database: Data/audit_bot.db (auto-created on first use)
"""
import sqlite3
import json
import os
import threading

_local = threading.local()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    actions     TEXT,
    risks       TEXT,
    source      TEXT DEFAULT 'local',
    tokens_used INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    total_rows  INTEGER,
    findings    INTEGER,
    high_risk   INTEGER DEFAULT 0,
    medium_risk INTEGER DEFAULT 0,
    low_risk    INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id     INTEGER REFERENCES risk_scans(id),
    check_type  TEXT NOT NULL,
    level       TEXT NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT,
    evidence    TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_project ON chat_messages(project, created_at);
CREATE INDEX IF NOT EXISTS idx_scans_project ON risk_scans(project, created_at);
CREATE INDEX IF NOT EXISTS idx_findings_scan ON risk_findings(scan_id);
"""

_db_path = None


def init_db(data_dir):
    """Set the database path. Call once at app startup."""
    global _db_path
    _db_path = os.path.join(data_dir, 'audit_bot.db')


def get_db():
    """Get a thread-local SQLite connection (auto-creates schema on first call)."""
    if _db_path is None:
        raise RuntimeError("Database not initialized. Call init_db(data_dir) first.")

    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect(_db_path, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.executescript(_SCHEMA)
    return _local.conn


# ── Chat Messages ────────────────────────────────────────────────────────────

def save_message(project, role, content, actions=None, risks=None, source='local', tokens=0):
    """Insert a chat message and return its id."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO chat_messages (project, role, content, actions, risks, source, tokens_used) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project, role, content,
         json.dumps(actions) if actions else None,
         json.dumps(risks) if risks else None,
         source, tokens)
    )
    db.commit()
    return cur.lastrowid


def get_history(project, limit=50):
    """Fetch recent chat messages for a project (oldest first)."""
    db = get_db()
    rows = db.execute(
        "SELECT id, role, content, actions, risks, source, tokens_used, created_at "
        "FROM chat_messages WHERE project = ? ORDER BY created_at DESC LIMIT ?",
        (project, limit)
    ).fetchall()

    messages = []
    for r in reversed(rows):  # reverse to get oldest-first order
        msg = {
            'id': r['id'],
            'role': r['role'],
            'content': r['content'],
            'source': r['source'],
            'tokens_used': r['tokens_used'],
            'created_at': r['created_at']
        }
        if r['actions']:
            try:
                msg['actions'] = json.loads(r['actions'])
            except (json.JSONDecodeError, TypeError):
                msg['actions'] = []
        if r['risks']:
            try:
                msg['risks'] = json.loads(r['risks'])
            except (json.JSONDecodeError, TypeError):
                msg['risks'] = []
        messages.append(msg)
    return messages


def clear_history(project):
    """Delete all chat messages for a project."""
    db = get_db()
    db.execute("DELETE FROM chat_messages WHERE project = ?", (project,))
    db.commit()


def get_token_usage(project):
    """Get total tokens used for a project."""
    db = get_db()
    row = db.execute(
        "SELECT COALESCE(SUM(tokens_used), 0) as total FROM chat_messages WHERE project = ?",
        (project,)
    ).fetchone()
    return row['total'] if row else 0


# ── Risk Scans ───────────────────────────────────────────────────────────────

def save_scan(project, results):
    """Save a risk scan and its individual findings. Returns scan_id."""
    db = get_db()
    summary = results.get('summary', {})

    cur = db.execute(
        "INSERT INTO risk_scans (project, total_rows, findings, high_risk, medium_risk, low_risk) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (project, summary.get('total_rows', 0), summary.get('total_findings', 0),
         summary.get('high', 0), summary.get('medium', 0), summary.get('low', 0))
    )
    scan_id = cur.lastrowid

    for finding in results.get('findings', []):
        db.execute(
            "INSERT INTO risk_findings (scan_id, check_type, level, title, detail, evidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (scan_id, finding.get('check_type', ''),
             finding.get('level', 'low'),
             finding.get('title', ''),
             finding.get('detail', ''),
             json.dumps(finding.get('evidence', [])))
        )

    db.commit()
    return scan_id


def get_scans(project, limit=10):
    """List recent risk scans for a project."""
    db = get_db()
    rows = db.execute(
        "SELECT id, total_rows, findings, high_risk, medium_risk, low_risk, created_at "
        "FROM risk_scans WHERE project = ? ORDER BY created_at DESC LIMIT ?",
        (project, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def get_scan_findings(scan_id):
    """Get all findings for a specific scan."""
    db = get_db()
    rows = db.execute(
        "SELECT id, check_type, level, title, detail, evidence, created_at "
        "FROM risk_findings WHERE scan_id = ? ORDER BY "
        "CASE level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END",
        (scan_id,)
    ).fetchall()

    findings = []
    for r in rows:
        f = dict(r)
        if f.get('evidence'):
            try:
                f['evidence'] = json.loads(f['evidence'])
            except (json.JSONDecodeError, TypeError):
                f['evidence'] = []
        findings.append(f)
    return findings
