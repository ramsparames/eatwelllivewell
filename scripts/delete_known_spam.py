"""Delete ONLY the clearly identified spam applications from the Sep 15 screenshot.

Preview:
    python scripts/delete_known_spam.py

Delete:
    python scripts/delete_known_spam.py --apply
"""
import sys
from app.database import get_connection

SPAM_EMAILS = [
    "an.d.rewuerl.ing.7@gmail.com",
    "qirongli@yahoo.com",
    "marion.tufttie@cogeco.ca",
    "marty.harris@rayonier.com",
    "graphicsgal1@hotmail.com",
    "tdkelley3@earthlink.net",
    "j.a.ck.a.s.hat.t.uck@gmail.com",
    "webandwork@web.de",
]

apply_delete = "--apply" in sys.argv

with get_connection() as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, email, submitted_at
            FROM transformation_applications
            WHERE LOWER(email) = ANY(%s)
            ORDER BY submitted_at DESC
            """,
            ([email.lower() for email in SPAM_EMAILS],),
        )
        rows = cursor.fetchall()

        print(f"Matched {len(rows)} application row(s):")
        for row in rows:
            print(f"  {row['id']} | {row['name']} | {row['email']} | {row['submitted_at']}")

        if not apply_delete:
            print("\\nPREVIEW ONLY. Nothing deleted.")
            print("If every row above is spam, run: python scripts/delete_known_spam.py --apply")
            raise SystemExit(0)

        ids = [row["id"] for row in rows]
        if not ids:
            print("Nothing to delete.")
            raise SystemExit(0)

        # Remove dependent lead timeline events first; application itself next.
        cursor.execute(
            "DELETE FROM lead_events WHERE application_id = ANY(%s)",
            (ids,),
        )
        cursor.execute(
            "DELETE FROM transformation_applications WHERE id = ANY(%s)",
            (ids,),
        )
        deleted = cursor.rowcount

    connection.commit()

print(f"Deleted {deleted} spam application row(s).")
