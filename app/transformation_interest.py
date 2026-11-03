from fastapi import APIRouter, Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import SESSION_SECRET, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, APP_BASE_URL
from pydantic import BaseModel, Field
from app.database import (
    save_transformation_interest,
    get_transformation_interest_payment,
    create_transformation_interest_payment_record,
    mark_transformation_interest_paid,
    promote_transformation_interest_if_qualified,
)
from app.email import send_transformation_interest_notification
import os
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

    return {"status": "saved", "interest_id": interest_id, "name": submission.name.strip()}


CLARITY_CALENDAR_ID = "IBwI80BhwMVqhD9qvMXF"


def qualify_transformation_interest_if_ready(
    *,
    interest_id: int | None = None,
    phone: str | None = None,
) -> dict | None:
    qualified = promote_transformation_interest_if_qualified(
        interest_id=interest_id,
        phone=phone,
        clarity_calendar_id=CLARITY_CALENDAR_ID,
    )
    if not qualified:
        return None

    send_transformation_interest_notification(
        interest_id=qualified["id"],
        name=qualified.get("name") or "",
        phone=qualified.get("phone") or "",
        occupation=qualified.get("occupation") or "",
        goals=qualified.get("goals") or [],
        frustration=qualified.get("frustration") or "",
        readiness=qualified.get("readiness") or "",
        timeline=qualified.get("timeline") or "",
        why_now=qualified.get("why_now") or "",
        source=qualified.get("source") or "direct",
    )
    return qualified


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


def _sync_payment_from_razorpay(
    payment: dict,
    callback_payment_id: str | None = None,
) -> bool:
    """Verify payment with Razorpay and sync our local payment record.

    We never trust the browser callback parameters by themselves.  We use
    Razorpay's server-side API to verify either the Payment Link status or,
    when available, the specific payment returned by the callback.
    """
    link_id = payment.get("razorpay_payment_link_id")
    payment_id = callback_payment_id

    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return payment.get("status") == "paid"

    try:
        # First verify the specific payment returned by Razorpay's callback.
        # This is useful because the Payment Link status can briefly lag the
        # payment itself.
        if payment_id:
            payment_response = requests.get(
                f"https://api.razorpay.com/v1/payments/{payment_id}",
                auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
                timeout=15,
            )

            if payment_response.ok:
                payment_data = payment_response.json()
                payment_status = str(payment_data.get("status", "")).lower()

                if payment_status in {"captured", "authorized"}:
                    marked = mark_transformation_interest_paid(
                        payment_link_id=link_id,
                        reference_id=payment.get("reference_id"),
                        payment_id=payment_id,
                        amount=payment_data.get("amount"),
                    )
                    if marked:
                        qualify_transformation_interest_if_ready(interest_id=marked)
                        return True

        # Fall back to the authoritative Payment Link status.
        if not link_id:
            return payment.get("status") == "paid"

        response = requests.get(
            f"https://api.razorpay.com/v1/payment_links/{link_id}",
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            timeout=15,
        )

        if not response.ok:
            return payment.get("status") == "paid"

        data = response.json()
        link_status = str(data.get("status", "")).lower()

        if link_status != "paid":
            return payment.get("status") == "paid"

        # The Payment Link response may include the payment ID. Prefer it,
        # otherwise keep the ID supplied by the callback.
        link_payments = data.get("payments")
        if isinstance(link_payments, list) and link_payments:
            first_payment = link_payments[0]
            if isinstance(first_payment, dict):
                payment_id = payment_id or first_payment.get("id")

        marked = mark_transformation_interest_paid(
            payment_link_id=link_id,
            reference_id=payment.get("reference_id"),
            payment_id=payment_id,
            amount=data.get("amount"),
        )
        if marked:
            qualify_transformation_interest_if_ready(interest_id=marked)

        return bool(marked) or payment.get("status") == "paid"

    except Exception:
        # The frontend will keep polling payment-status.  A temporary
        # Razorpay/API failure should never falsely unlock booking.
        return payment.get("status") == "paid"


def _payment_amount_paise() -> int:
    """Use ₹1 only when explicitly enabled for testing; otherwise use ₹499."""
    return 100 if os.getenv("RAZORPAY_TEST_MODE", "").strip().lower() == "true" else 49900


@router.post("/transformation-interest/payment-link")
def create_transformation_interest_payment(interest_id: int):
    from app.database import get_transformation_interest_by_id

    interest = get_transformation_interest_by_id(interest_id)
    if not interest:
        raise HTTPException(status_code=404, detail="Transformation enquiry not found.")

    existing = get_transformation_interest_payment(interest_id)
    if existing and existing.get("status") == "paid":
        return {
            "status": "paid",
            "payment_url": existing.get("payment_url"),
            "interest_id": interest_id,
            "amount_rupees": int(existing.get("amount") or 49900) / 100,
        }
    if existing and existing.get("status") in {"created", "issued"} and existing.get("payment_url"):
        return {
            "status": existing.get("status"),
            "payment_url": existing.get("payment_url"),
            "interest_id": interest_id,
            "amount_rupees": int(existing.get("amount") or _payment_amount_paise()) / 100,
        }

    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay API credentials are not configured on the server.")

    amount_paise = _payment_amount_paise()
    reference_id = f"nourisher_interest_{interest_id}"
    payload = {
        "amount": amount_paise,
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

    # Keep the stored amount aligned with the actual Razorpay amount when the DB
    # function uses its default value for the initial insert.
    try:
        from app.database import get_connection
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE transformation_interest_payments
                    SET amount = %s, updated_at = NOW()
                    WHERE interest_id = %s
                    """,
                    (amount_paise, interest_id),
                )
            connection.commit()
    except Exception:
        # The payment link was created successfully; don't turn that into a
        # false frontend failure. The amount returned below still reflects the
        # actual Razorpay link.
        pass

    return {
        "status": "created",
        "payment_url": data["short_url"],
        "interest_id": interest_id,
        "amount_rupees": amount_paise / 100,
    }


@router.get("/transformation-interest/payment-status")
def transformation_interest_payment_status(interest_id: int):
    payment = get_transformation_interest_payment(interest_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    paid = _sync_payment_from_razorpay(payment)
    return {
        "status": "paid" if paid else payment.get("status"),
        "paid": paid,
        "payment_url": payment.get("payment_url"),
        "interest_id": interest_id,
    }


@router.get("/transformation-interest/payment-callback")
def transformation_interest_payment_callback(
    interest_id: int,
    razorpay_payment_id: str | None = None,
    razorpay_payment_link_id: str | None = None,
    razorpay_payment_link_reference_id: str | None = None,
    razorpay_payment_link_status: str | None = None,
    razorpay_signature: str | None = None,
):
    """Confirm the Razorpay payment server-side.

    Razorpay opens this URL in the payment tab. The original enquiry tab
    polls /payment-status, so it can unlock booking without relying on
    cross-tab browser communication.
    """
    payment = get_transformation_interest_payment(interest_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    paid = _sync_payment_from_razorpay(
        payment,
        callback_payment_id=razorpay_payment_id,
    )
    if paid:
        return {
            "status": "paid",
            "message": "Payment received. Return to the original Eat Well Live Well tab to book your Clarity Call.",
        }

    return {
        "status": "received",
        "message": "Payment is being confirmed. Return to the original Eat Well Live Well tab; it will unlock once Razorpay confirms payment.",
    }
