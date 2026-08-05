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
