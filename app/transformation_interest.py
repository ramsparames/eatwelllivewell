from fastapi import APIRouter, Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import SESSION_SECRET, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, APP_BASE_URL
from pydantic import BaseModel, Field
from app.database import save_transformation_interest, get_transformation_interest_payment, create_transformation_interest_payment_record
from app.email import send_transformation_interest_notification
import requests

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


@router.post("/transformation-interest/payment-link")
def create_transformation_interest_payment(interest_id: int):
    from app.database import get_transformation_interest_by_id

    interest = get_transformation_interest_by_id(interest_id)
    if not interest:
        raise HTTPException(status_code=404, detail="Transformation enquiry not found.")

    existing = get_transformation_interest_payment(interest_id)
    if existing and existing.get("status") == "paid":
        return {"status": "paid", "payment_url": existing.get("payment_url"), "interest_id": interest_id}
    if existing and existing.get("status") in {"created", "issued"} and existing.get("payment_url"):
        return {"status": existing.get("status"), "payment_url": existing.get("payment_url"), "interest_id": interest_id}

    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay API credentials are not configured on the server.")

    reference_id = f"nourisher_interest_{interest_id}"
    payload = {
        "amount": 49900,
        "currency": "INR",
        "accept_partial": False,
        "description": "NourisHer Clarity Call with Sushma",
        "reference_id": reference_id,
        "customer": {
            "name": interest.get("name") or "NourisHer enquiry",
            "contact": interest.get("phone") or "",
        },
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "callback_url": f"{APP_BASE_URL.rstrip('/')}/transformation-interest/payment-callback?interest_id={interest_id}",
        "callback_method": "get",
        "notes": {"interest_id": str(interest_id), "purpose": "NourisHer Clarity Call"},
    }

    try:
        response = requests.post(
            "https://api.razorpay.com/v1/payment_links",
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            json=payload,
            timeout=15,
        )
        data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to create the Razorpay payment link right now.") from exc

    if response.status_code >= 400 or not data.get("id") or not data.get("short_url"):
        detail = data.get("error", {}).get("description") if isinstance(data, dict) else None
        raise HTTPException(status_code=502, detail=detail or "Razorpay could not create the payment link.")

    create_transformation_interest_payment_record(
        interest_id=interest_id,
        razorpay_payment_link_id=str(data["id"]),
        payment_url=str(data["short_url"]),
        reference_id=reference_id,
    )

    return {"status": "created", "payment_url": data["short_url"], "interest_id": interest_id}


@router.get("/transformation-interest/payment-status")
def transformation_interest_payment_status(interest_id: int):
    payment = get_transformation_interest_payment(interest_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    return {
        "status": payment.get("status"),
        "paid": payment.get("status") == "paid",
        "payment_url": payment.get("payment_url"),
        "interest_id": interest_id,
    }


@router.get("/transformation-interest/payment-callback")
def transformation_interest_payment_callback(interest_id: int):
    payment = get_transformation_interest_payment(interest_id)
    if payment and payment.get("status") == "paid":
        return {"status": "paid", "message": "Payment received. Return to the original Eat Well Live Well tab to book your Clarity Call."}
    return {"status": "received", "message": "Payment is being confirmed. Return to the original Eat Well Live Well tab; it will unlock once Razorpay confirms payment."}
