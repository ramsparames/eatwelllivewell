from fastapi import APIRouter, Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import SESSION_SECRET
from pydantic import BaseModel, Field
from app.database import save_transformation_interest
from app.email import send_transformation_interest_notification

router = APIRouter()

class TransformationInterestSubmission(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    age_range: str = Field(min_length=1, max_length=30)
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
        age_range=submission.age_range.strip(),
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


_APPLICATION_TOKEN_MAX_AGE = 60 * 60 * 24 * 90


def _application_link_serializer():
    return URLSafeTimedSerializer(
        SESSION_SECRET,
        salt="nourisher-transformation-application",
    )


def make_interest_application_token(interest_id: int) -> str:
    return _application_link_serializer().dumps({"interest_id": int(interest_id)})


def read_interest_application_token(token: str) -> int:
    try:
        payload = _application_link_serializer().loads(
            token,
            max_age=_APPLICATION_TOKEN_MAX_AGE,
        )
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(
            status_code=400,
            detail="This application link is invalid or has expired.",
        ) from exc

    try:
        return int(payload["interest_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="This application link is invalid.") from exc



@router.get("/transformation-interest/application-prefill")
def transformation_interest_application_prefill(token: str):
    from app.database import get_transformation_interest_by_id

    interest_id = read_interest_application_token(token)
    interest = get_transformation_interest_by_id(interest_id)
    if not interest:
        raise HTTPException(status_code=404, detail="Transformation enquiry not found.")

    return {
        "interest_id": interest["id"],
        "snapshot_id": interest.get("snapshot_id"),
        "name": interest.get("name") or "",
        "phone": interest.get("phone") or "",
        "occupation": interest.get("occupation") or "",
        "goals": interest.get("goals") or [],
        "why_now": interest.get("why_now") or "",
    }
