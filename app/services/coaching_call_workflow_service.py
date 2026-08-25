from __future__ import annotations
from datetime import date
from app.database import get_connection

def create_coaching_call_tables():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coach_call_notes (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    call_date DATE NOT NULL,
                    week_start DATE,
                    summary TEXT,
                    wins TEXT,
                    barriers TEXT,
                    decisions TEXT,
                    next_focus TEXT,
                    client_message TEXT,
                    private_note TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_coach_call_notes_client_date
                ON coach_call_notes(client_id, call_date DESC, id DESC)
            """)

def save_call_note(client_id, call_date, week_start, summary=None, wins=None,
                   barriers=None, decisions=None, next_focus=None,
                   client_message=None, private_note=None):
    create_coaching_call_tables()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO coach_call_notes (
                    client_id, call_date, week_start, summary, wins, barriers,
                    decisions, next_focus, client_message, private_note
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING *
            """, (client_id, call_date, week_start, summary, wins, barriers,
                  decisions, next_focus, client_message, private_note))
            return dict(cursor.fetchone())

def get_call_notes(client_id, limit=30):
    create_coaching_call_tables()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM coach_call_notes
                WHERE client_id=%s
                ORDER BY call_date DESC, id DESC
                LIMIT %s
            """, (client_id, limit))
            return [dict(row) for row in (cursor.fetchall() or [])]

def get_latest_call_note(client_id):
    rows = get_call_notes(client_id, 1)
    return rows[0] if rows else None

def get_workflow_timeline(client_id, limit=40):
    events=[]
    for note in get_call_notes(client_id, limit):
        detail = note.get("summary") or "Call notes recorded"
        if note.get("next_focus"):
            detail += " · Next focus: " + note["next_focus"]
        events.append({
            "event_date": note["call_date"],
            "event_type": "call",
            "label": "Coaching call",
            "detail": detail,
            "created_at": note.get("created_at"),
        })
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS(
                  SELECT 1 FROM information_schema.tables
                  WHERE table_name='client_nudges'
                ) AS exists
            """)
            exists = bool((cursor.fetchone() or {}).get("exists"))
            if exists:
                cursor.execute("""
                    SELECT reason, created_at FROM client_nudges
                    WHERE client_id=%s ORDER BY created_at DESC LIMIT %s
                """, (client_id, limit))
                for row in cursor.fetchall() or []:
                    created=row.get("created_at")
                    events.append({
                        "event_date": created.date() if created else date.today(),
                        "event_type": "nudge",
                        "label": "Gentle nudge",
                        "detail": (row.get("reason") or "check_in").replace("_"," ").title(),
                        "created_at": created,
                    })
    events.sort(key=lambda x: (x.get("event_date") or date.min, str(x.get("created_at") or "")), reverse=True)
    return events[:limit]
