from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from app.database import save_transformation_interest
from app.email import send_transformation_interest_notification

router = APIRouter()

class TransformationInterestSubmission(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    occupation: str = Field(min_length=1, max_length=120)
    goals: list[str] = Field(min_length=1, max_length=2)
    frustration: str = Field(min_length=1, max_length=500)
    readiness: str = Field(min_length=1, max_length=200)
    timeline: str = Field(min_length=1, max_length=100)
    why_now: str = Field(min_length=3, max_length=1200)
    source: str = Field(default="direct", max_length=120)
    snapshot_id: int | None = None
    website: str = ""

@router.post("/transformation-interest")
def receive_transformation_interest(request: Request, submission: TransformationInterestSubmission):
    if submission.website.strip():
        return {"status": "error", "message": "Submission rejected."}

    interest_id = save_transformation_interest(
        snapshot_id=submission.snapshot_id,
        name=submission.name.strip(),
        phone=submission.phone.strip(),
        occupation=submission.occupation.strip(),
        goals=submission.goals,
        frustration=submission.frustration.strip(),
        readiness=submission.readiness.strip(),
        timeline=submission.timeline.strip(),
        why_now=submission.why_now.strip(),
        source=submission.source.strip() or "direct",
    )

    send_transformation_interest_notification(
        interest_id=interest_id,
        name=submission.name.strip(),
        phone=submission.phone.strip(),
        occupation=submission.occupation.strip(),
        goals=submission.goals,
        frustration=submission.frustration.strip(),
        readiness=submission.readiness.strip(),
        timeline=submission.timeline.strip(),
        why_now=submission.why_now.strip(),
        source=submission.source.strip() or "direct",
    )

    return {"status": "saved", "interest_id": interest_id, "name": submission.name.strip()}
