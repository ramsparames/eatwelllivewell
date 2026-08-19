import hashlib
import uuid

from app.database import get_connection


LEGACY_CUSTOM_ALIAS_GROUPS = {
    "custom:badam-ghee": [
        "4-5 soaked badam or 1 tsp ghee",
        "add four to five soaked badam or 1 tsp ghee",
    ],
    "custom:lunch-carb-protein": [
        "100-150 gms cooked rice / millet / barley (or) 2 chappathis for lunch with any one protein source",
        "100-150 grams cooked rice/millet/barley or two chappatis for lunch with any one protein source",
    ],
}


def normalize_action_name(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def new_custom_action_key() -> str:
    return f"custom:{uuid.uuid4().hex}"


def legacy_custom_key(action_name: str) -> str:
    normalized = normalize_action_name(action_name)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"custom:legacy:{digest}"


def ensure_action_identity_schema(action_library_by_key: dict) -> None:
    """
    Add stable identity to historical client_action_plans and backfill it.

    Library actions -> their fixed ACTION_LIBRARY key.
    Custom actions -> stable custom keys.
    Known historical wording variants can be merged once here.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                ALTER TABLE client_action_plans
                ADD COLUMN IF NOT EXISTS action_key TEXT
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_client_action_plans_action_key
                ON client_action_plans (client_id, action_key)
            """)

            # Backfill canonical library actions by exact normalized title.
            cursor.execute("""
                SELECT id, action_name, action_key
                FROM client_action_plans
                WHERE action_key IS NULL OR BTRIM(action_key) = ''
            """)
            rows = cursor.fetchall() or []

            library_by_name = {
                normalize_action_name(item["name"]): key
                for key, item in action_library_by_key.items()
            }

            alias_by_name = {}
            for stable_key, aliases in LEGACY_CUSTOM_ALIAS_GROUPS.items():
                for alias in aliases:
                    alias_by_name[normalize_action_name(alias)] = stable_key

            for row in rows:
                name = row.get("action_name") or ""
                normalized = normalize_action_name(name)
                stable_key = library_by_name.get(normalized)
                if not stable_key:
                    stable_key = alias_by_name.get(normalized)
                if not stable_key:
                    stable_key = legacy_custom_key(name)

                cursor.execute("""
                    UPDATE client_action_plans
                    SET action_key = %s
                    WHERE id = %s
                """, (stable_key, row["id"]))


def set_action_key(
    client_id: int,
    action_name: str,
    start_date,
    end_date,
    action_key: str,
) -> None:
    """Attach identity to the newest matching action plan row."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE client_action_plans
                SET action_key = %s
                WHERE id = (
                    SELECT id
                    FROM client_action_plans
                    WHERE client_id = %s
                      AND action_name = %s
                      AND start_date = %s
                      AND end_date = %s
                    ORDER BY id DESC
                    LIMIT 1
                )
            """, (
                action_key,
                client_id,
                action_name,
                start_date,
                end_date,
            ))
