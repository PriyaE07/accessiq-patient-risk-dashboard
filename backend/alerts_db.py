"""
Persists flagged high-risk predictions to SQLite, so they survive past a
single request/response — the "actually save this so someone follows up"
piece, as opposed to everything else in this app, which is computed fresh
on every call and never stored.

Only single-patient form submissions create alerts (a real staff member
entering one real patient, at a genuine decision point) — the worklist and
Overview pages sample demo data fresh on every refresh, so persisting those
would just fill the table with re-sampled duplicates, not real triage work.

Uses the plain `sqlite3` standard-library module directly rather than an
ORM — the schema is one table with a handful of columns, so an ORM would be
more machinery than the problem needs. Each function opens its own short-
lived connection rather than sharing one across requests, which sidesteps
having to think about connection/thread safety with FastAPI's request
concurrency.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "alerts.db"

VALID_STATUSES = {"new", "acknowledged", "resolved"}


def init_db():
    """Create the alerts table if it doesn't exist yet. Safe to call every
    startup — CREATE TABLE IF NOT EXISTS is a no-op once the table exists."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT NOT NULL,
                risk_score REAL NOT NULL,
                top_factors TEXT NOT NULL,
                patient_data TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "prediction_type": row["prediction_type"],
        "risk_score": row["risk_score"],
        # top_factors and patient_data are stored as JSON text (sqlite has
        # no native list/dict column type) -- decode them back on the way out.
        "top_factors": json.loads(row["top_factors"]),
        "patient_data": json.loads(row["patient_data"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_alert(prediction_type: str, risk_score: float, top_factors: list[dict], patient_data: dict) -> dict:
    """Save one flagged prediction as a new alert. Returns the saved row."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            INSERT INTO alerts (prediction_type, risk_score, top_factors, patient_data, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'new', ?, ?)
            """,
            (prediction_type, risk_score, json.dumps(top_factors), json.dumps(patient_data), now, now),
        )
        alert_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return _row_to_dict(row)


def list_alerts(status: str | None = None) -> list[dict]:
    """Most recent alerts first, optionally filtered to one status."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(row) for row in rows]


def update_alert_status(alert_id: int, new_status: str) -> dict | None:
    """Move an alert to a new status (e.g. 'new' -> 'acknowledged'). Returns
    the updated row, or None if no alert with that id exists."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{new_status}', must be one of {VALID_STATUSES}")

    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "UPDATE alerts SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, alert_id)
        )
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return _row_to_dict(row) if row else None
