from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, EmailStr, Field
import base64
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from app.email import send_assessment_notification
from app.email import (
    send_application_confirmation,
    send_application_notification,
)
from app.database import (
    save_application,
    add_lead_event,
)
from app.synamate import sync_transformation_applicant

router = APIRouter()

# Lightweight bot protection. Uses the existing SESSION_SECRET when available.
# A random fallback is created per process so protection still works without setup.
_FORM_SECRET = (os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)).encode("utf-8")
_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_FORM_TOKEN_MAX_AGE = 2 * 60 * 60
_FORM_TOKEN_MIN_AGE = 3


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _sign_form_token(timestamp: int, purpose: str) -> str:
    body = f"{timestamp}:{purpose}"
    sig = hmac.new(_FORM_SECRET, body.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{body}:{sig}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _verify_form_token(token: str, purpose: str) -> bool:
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        ts_text, token_purpose, supplied_sig = decoded.split(":", 2)
        ts = int(ts_text)
    except Exception:
        return False

    if token_purpose != purpose:
        return False

    age = int(time.time()) - ts
    if age < _FORM_TOKEN_MIN_AGE or age > _FORM_TOKEN_MAX_AGE:
        return False

    expected = hmac.new(
        _FORM_SECRET,
        f"{ts}:{purpose}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, supplied_sig)


def _rate_limit(key: str, *, limit: int, window_seconds: int) -> bool:
    now = time.time()
    bucket = _RATE_BUCKETS[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


@router.get("/form-token/{purpose}")
def issue_form_token(purpose: str):
    if purpose not in {"application", "event", "assessment"}:
        raise HTTPException(status_code=404, detail="Unknown form")
    return {
        "token": _sign_form_token(int(time.time()), purpose),
        "purpose": purpose,
    }


class TransformationApplicationSubmission(BaseModel):
    snapshot_id: int | None = None

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30)
    age_range: str = Field(min_length=1, max_length=20)

    why_now: str = Field(min_length=3, max_length=3000)
    tried: str = Field(min_length=1, max_length=3000)
    success_goal: str = Field(min_length=3, max_length=3000)
    support_needed: str = Field(min_length=1, max_length=500)

    application_data: dict = Field(default_factory=dict)

    consent: bool
    form_token: str = Field(min_length=20, max_length=500)
    website: str = Field(default="", max_length=200)


class EventLeadSubmission(BaseModel):
    """Short lead capture used at in-person Eat Well Live Well events."""
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    email: EmailStr | None = None
    age_range: str = Field(min_length=1, max_length=20)
    interests: list[str] = Field(default_factory=list)
    other_interest: str = Field(default="", max_length=500)
    consent: bool
    form_token: str = Field(min_length=20, max_length=500)
    website: str = Field(default="", max_length=200)


@router.post("/event-lead")
def receive_event_lead(request: Request, submission: EventLeadSubmission):
    if submission.website.strip():
        raise HTTPException(status_code=400, detail="Submission rejected.")
    if not _verify_form_token(submission.form_token, "event"):
        raise HTTPException(status_code=400, detail="Please refresh the page and try again.")
    ip = _client_ip(request)
    if not _rate_limit(f"event-ip:{ip}", limit=60, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again later.")

    if not submission.consent:
        return {
            "status": "error",
            "message": "Consent is required.",
        }

    interests = [
        str(item).strip()
        for item in submission.interests
        if str(item).strip()
    ]
    if submission.other_interest.strip():
        interests.append(submission.other_interest.strip())

    concern_summary = ", ".join(interests) if interests else "General health conversation"

    application_id = save_application(
        snapshot_id=None,
        name=submission.name.strip(),
        email=(str(submission.email).strip().lower() if submission.email else ""),
        phone=submission.phone.strip(),
        age_range=submission.age_range.strip(),
        why_now="Met Sushma at an Eat Well Live Well event and requested a follow-up conversation.",
        tried="Quick event lead form – not asked at the stall.",
        success_goal=concern_summary,
        support_needed="A short 1:1 follow-up conversation with Sushma.",
        consent=submission.consent,
        application_data={
            "form_type": "event_lead",
            "lead_source": "weekend_stall",
            "interests": interests,
        },
    )

    add_lead_event(
        snapshot_id=None,
        application_id=application_id,
        event_type="event_lead_captured",
        title="Weekend stall lead captured",
        details=f"Interested in: {concern_summary}",
    )

    return {
        "status": "saved",
        "lead_id": application_id,
        "name": submission.name,
    }


@router.post("/application")
def receive_application(
    request: Request,
    submission: TransformationApplicationSubmission,
):
    # Honeypot: genuine visitors never see/fill this field.
    if submission.website.strip():
        raise HTTPException(status_code=400, detail="Submission rejected.")

    # A valid token proves the browser loaded the real form first, and the
    # minimum token age blocks instant scripted posts.
    if not _verify_form_token(submission.form_token, "application"):
        raise HTTPException(status_code=400, detail="Please refresh the application page and try again.")

    ip = _client_ip(request)
    if not _rate_limit(f"application-ip:{ip}", limit=6, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Too many applications. Please try again later.")

    email_key = str(submission.email).strip().lower()
    if not _rate_limit(f"application-email:{email_key}", limit=2, window_seconds=86400):
        raise HTTPException(status_code=429, detail="This application has already been submitted.")

    if not submission.consent:
        return {
            "status": "error",
            "message": "Consent is required.",
        }

    application_id = save_application(
        snapshot_id=submission.snapshot_id,
        name=submission.name.strip(),
        email=str(submission.email).strip().lower(),
        phone=submission.phone.strip(),
        age_range=submission.age_range.strip(),
        why_now=submission.why_now.strip(),
        tried=submission.tried.strip(),
        success_goal=submission.success_goal.strip(),
        support_needed=submission.support_needed.strip(),
        consent=submission.consent,
        application_data=submission.application_data,
    )
    add_lead_event(
    snapshot_id=submission.snapshot_id,
    application_id=application_id,
    event_type="application_submitted",
    title="Transformation application submitted",
    details="Completed the NourisHer Transformation application.",
    )
    sync_transformation_applicant(
    application_id=application_id,
    name=submission.name,
    email=str(submission.email),
    phone=submission.phone,
    )
    
    send_application_notification(
        application_id=application_id,
        name=submission.name,
        email=str(submission.email),
        phone=submission.phone,
        age_range=submission.age_range,
        why_now=submission.why_now,
    )
    send_application_confirmation(
    recipient_email=str(submission.email),
    name=submission.name,
    )
    return {
        "status": "saved",
        "application_id": application_id,
        "name": submission.name,
    }
