import os
from dotenv import load_dotenv

load_dotenv()
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SESSION_SECRET = os.getenv("SESSION_SECRET")

COACH_USERNAME = os.getenv("COACH_USERNAME")
COACH_PASSWORD_SALT = os.getenv("COACH_PASSWORD_SALT")
COACH_PASSWORD_HASH = os.getenv("COACH_PASSWORD_HASH")
COACH_NOTIFICATION_EMAIL = os.getenv("COACH_NOTIFICATION_EMAIL")
SYNAMATE_API_TOKEN=os.getenv("SYNAMATE_API_TOKEN")
SYNAMATE_LOCATION_ID=os.getenv("SYNAMATE_LOCATION_ID")
SYNAMATE_SECRET_WEBHOOK = os.getenv(
    "SYNAMATE_SECRET_WEBHOOK",
    "",
)

APP_BASE_URL = os.getenv(
    "APP_BASE_URL",
    "http://127.0.0.1:8000",
)

RESEND_FROM_EMAIL = os.getenv(
    "RESEND_FROM_EMAIL",
    "NourisHer <onboarding@resend.dev>",
)

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
