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

                total_score INTEGER NOT NULL,

                recovery INTEGER NOT NULL,
                metabolic INTEGER NOT NULL,
                nutrition INTEGER NOT NULL,
                behaviour INTEGER NOT NULL,
                confidence INTEGER NOT NULL,

                opportunity TEXT NOT NULL,
                strength TEXT NOT NULL,

                body_profile TEXT,
                feeling TEXT,

                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def save_snapshot(
    name: str,
    email: str,
    answers: dict[str, str],
    result: dict,
) -> int:

    answers_json = json.dumps(answers)
    d = result["dimensions"]

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO snapshot_submissions (
                name,
                email,
                answers,

                total_score,

                recovery,
                metabolic,
                nutrition,
                behaviour,
                confidence,

                opportunity,
                strength,

                body_profile,
                feeling
            )
            VALUES (
                ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                name,
                email,
                answers_json,

                result["total"],

                d["recovery"],
                d["metabolic"],
                d["nutrition"],
                d["behaviour"],
                d["confidence"],

                result["opportunity"],
                result["strength"],

                result["bodyProfile"],
                result["feeling"],
            ),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError("Snapshot could not be saved")

        return cursor.lastrowid
