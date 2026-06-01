import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "audit_log.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_url TEXT UNIQUE,
    repo TEXT,
    issue_number TEXT,
    title TEXT,
    classification_json TEXT,
    located_files_json TEXT,
    debug_plan_json TEXT,
    draft_response TEXT,
    critic_review_json TEXT,
    resolved_classification_json TEXT,
    resolved_debug_plan_json TEXT,
    resolver_notes TEXT,
    accuracy TEXT,
    created_at TEXT,
    updated_at TEXT
)
"""


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _get_connection()
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def save_triage_record(
    issue_url: str,
    repo: str,
    issue_number: str,
    title: str,
    classification: Dict[str, Any],
    located_files: Dict[str, Any],
    debug_plan: Dict[str, Any],
    draft_response: str,
    critic_review: Optional[Dict[str, Any]] = None,
    resolved_classification: Optional[Dict[str, Any]] = None,
    resolved_debug_plan: Optional[Dict[str, Any]] = None,
    resolver_notes: Optional[str] = None,
    accuracy: Optional[str] = None,
) -> None:
    conn = _get_connection()
    now = datetime.utcnow().isoformat() + "Z"
    try:
        conn.execute(
            """
            INSERT INTO audit_log (
                issue_url, repo, issue_number, title,
                classification_json, located_files_json, debug_plan_json,
                draft_response, critic_review_json, resolved_classification_json,
                resolved_debug_plan_json, resolver_notes, accuracy,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(issue_url) DO UPDATE SET
                repo=excluded.repo,
                issue_number=excluded.issue_number,
                title=excluded.title,
                classification_json=excluded.classification_json,
                located_files_json=excluded.located_files_json,
                debug_plan_json=excluded.debug_plan_json,
                draft_response=excluded.draft_response,
                critic_review_json=excluded.critic_review_json,
                resolved_classification_json=excluded.resolved_classification_json,
                resolved_debug_plan_json=excluded.resolved_debug_plan_json,
                resolver_notes=excluded.resolver_notes,
                accuracy=COALESCE(excluded.accuracy, audit_log.accuracy),
                updated_at=excluded.updated_at
            """,
            (
                issue_url,
                repo,
                issue_number,
                title,
                json.dumps(classification or {}),
                json.dumps(located_files or {}),
                json.dumps(debug_plan or {}),
                draft_response or "",
                json.dumps(critic_review or {}),
                json.dumps(resolved_classification or {}),
                json.dumps(resolved_debug_plan or {}),
                resolver_notes or "",
                accuracy or None,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_triage_record(issue_url: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.execute("SELECT * FROM audit_log WHERE issue_url = ?", (issue_url,))
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_triage_records() -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM audit_log ORDER BY updated_at DESC"
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_accuracy(issue_url: str, accuracy: str) -> None:
    conn = _get_connection()
    now = datetime.utcnow().isoformat() + "Z"
    try:
        conn.execute(
            "UPDATE audit_log SET accuracy = ?, updated_at = ? WHERE issue_url = ?",
            (accuracy, now, issue_url),
        )
        conn.commit()
    finally:
        conn.close()
