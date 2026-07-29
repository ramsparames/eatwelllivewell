import json
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "nourisher.db"


def create_database():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshot_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                answers TEXT NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def save_snapshot(name: str, email: str, answers: dict[str, str]) -> int:
    answers_json = json.dumps(answers)

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO snapshot_submissions (name, email, answers)
            VALUES (?, ?, ?)
            """,
            (name, email, answers_json),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError("Snapshot could not be saved")

        return cursor.lastrowid
