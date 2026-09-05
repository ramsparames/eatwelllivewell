"""One-time Sanghamee Week 3 data correction."""
import os
from datetime import timedelta
import psycopg
from psycopg.rows import dict_row

CLIENT = "Sanghammee"
REMOVE = "Stand and move for 2-3 minutes every hour during work"
COPY_MATCH = "chia seed 2 tsp and flax seed 1 tsp"

def norm(s):
    return " ".join((s or "").strip().lower().split())

url = os.environ.get("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL is not set")

with psycopg.connect(url, row_factory=dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id,name,start_date FROM clients "
            "WHERE LOWER(BTRIM(name))=LOWER(%s) ORDER BY id",
            (CLIENT,),
        )
        clients = cur.fetchall()
        if len(clients) != 1:
            raise RuntimeError(
                f"Expected exactly one Sanghamee client; found {len(clients)}. No changes made."
            )

        client = clients[0]
        if not client["start_date"]:
            raise RuntimeError("Sanghamee has no start_date. No changes made.")

        cid = client["id"]
        w3s = client["start_date"] + timedelta(days=14)
        w3e = w3s + timedelta(days=6)
        w4s = client["start_date"] + timedelta(days=21)
        w4e = w4s + timedelta(days=6)

        def actions_between(start, end):
            cur.execute(
                """SELECT * FROM client_action_plans
                   WHERE client_id=%s
                     AND start_date <= %s
                     AND (end_date IS NULL OR end_date >= %s)
                   ORDER BY id""",
                (cid, end, start),
            )
            return cur.fetchall()

        w3 = actions_between(w3s, w3e)
        remove = [a for a in w3 if norm(a["action_name"]) == norm(REMOVE)]
        if len(remove) != 1:
            raise RuntimeError(
                f"Expected exactly one Week 3 stand/move action; found {len(remove)}. No changes made."
            )

        w4 = actions_between(w4s, w4e)
        source = [a for a in w4 if COPY_MATCH in norm(a["action_name"])]
        if len(source) != 1:
            raise RuntimeError(
                f"Expected exactly one Week 4 chia/flax action; found {len(source)}. No changes made."
            )
        source = source[0]

        if any(COPY_MATCH in norm(a["action_name"]) for a in w3):
            raise RuntimeError("Chia/flax action already exists in Week 3. No changes made.")

        cur.execute(
            """SELECT EXISTS (
                 SELECT 1 FROM information_schema.columns
                 WHERE table_name='client_action_plans' AND column_name='action_key'
               ) AS yes"""
        )
        has_action_key = cur.fetchone()["yes"]

        cur.execute("DELETE FROM client_action_plans WHERE id=%s", (remove[0]["id"],))

        if has_action_key:
            cur.execute(
                """INSERT INTO client_action_plans
                   (client_id,checkin_id,action_name,action_key,target_count,target_unit,
                    start_date,end_date,status)
                   VALUES (%s,NULL,%s,%s,%s,%s,%s,%s,'active')
                   RETURNING id""",
                (cid, source["action_name"], source.get("action_key"),
                 source.get("target_count"), source.get("target_unit"), w3s, w3e),
            )
        else:
            cur.execute(
                """INSERT INTO client_action_plans
                   (client_id,checkin_id,action_name,target_count,target_unit,
                    start_date,end_date,status)
                   VALUES (%s,NULL,%s,%s,%s,%s,%s,'active')
                   RETURNING id""",
                (cid, source["action_name"], source.get("target_count"),
                 source.get("target_unit"), w3s, w3e),
            )
        new_id = cur.fetchone()["id"]

        final = actions_between(w3s, w3e)
        if any(norm(a["action_name"]) == norm(REMOVE) for a in final):
            raise RuntimeError("Verification failed: removed action still appears.")
        if not any(COPY_MATCH in norm(a["action_name"]) for a in final):
            raise RuntimeError("Verification failed: new action is missing.")

        conn.commit()

        print(f"SUCCESS: Sanghamee (client {cid})")
        print(f"Week 3: {w3s} to {w3e}")
        print(f"Deleted action id {remove[0]['id']}: {remove[0]['action_name']}")
        print(f"Added action id {new_id}: {source['action_name']}")
        print("Week 4 unchanged.")
