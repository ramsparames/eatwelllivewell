from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
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




class EventLeadSubmission(BaseModel):
    """Short lead capture used at in-person Eat Well Live Well events."""
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    email: EmailStr | None = None
    age_range: str = Field(min_length=1, max_length=20)
    interests: list[str] = Field(default_factory=list)
    other_interest: str = Field(default="", max_length=500)
    consent: bool


@router.post("/event-lead")
def receive_event_lead(submission: EventLeadSubmission):
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
    submission: TransformationApplicationSubmission,
):
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
