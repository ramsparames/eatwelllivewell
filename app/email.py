import os

import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

if not RESEND_API_KEY:
    raise RuntimeError(
        "RESEND_API_KEY is not configured"
    )

resend.api_key = RESEND_API_KEY
