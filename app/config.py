import os


DATABASE_URL = os.getenv("DATABASE_URL")
SESSION_SECRET = os.getenv("SESSION_SECRET")

COACH_USERNAME = os.getenv("COACH_USERNAME")
COACH_PASSWORD_SALT = os.getenv("COACH_PASSWORD_SALT")
COACH_PASSWORD_HASH = os.getenv("COACH_PASSWORD_HASH")


def validate_required_settings() -> None:
    missing = []

    if not DATABASE_URL:
        missing.append("DATABASE_URL")

    if not SESSION_SECRET:
        missing.append("SESSION_SECRET")

    if not COACH_USERNAME:
        missing.append("COACH_USERNAME")

    if not COACH_PASSWORD_SALT:
        missing.append("COACH_PASSWORD_SALT")

    if not COACH_PASSWORD_HASH:
        missing.append("COACH_PASSWORD_HASH")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )
