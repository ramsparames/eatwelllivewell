from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.database import (
    get_all_leads,
    get_lead_events,
    get_lead_profile,
    update_lead_crm,
)


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


CLOSED_STATUSES = {
    "joined_foundations",
    "joined_transformation",
    "closed",
}


def _lead_stage_label(status: str) -> str:
    labels = {
        "new": "New",
        "contacted": "Contacted",
        "clarity_call_booked": "Clarity Call",
        "joined_foundations": "Joined Foundations",
        "joined_transformation": "Joined Transformation",
        "follow_up_later": "Follow Up",
        "closed": "Closed",
    }
    return labels.get(
        status,
        status.replace("_", " ").title(),
    )


def _lead_stage_group(status: str) -> str:
    if status == "new":
        return "new"

    if status == "contacted":
        return "contacted"

    if status == "clarity_call_booked":
        return "clarity"

    if status in {
        "joined_foundations",
        "joined_transformation",
    }:
        return "joined"

    if status == "follow_up_later":
        return "followup"

    if status == "closed":
        return "closed"

    return "other"


def _prepare_lead_row(lead: dict, today: date) -> dict:
    item = dict(lead)

    status = (
        item.get("application_status")
        or item.get("status")
        or "new"
    )

    follow_up_date = (
        item.get("application_follow_up_date")
        or item.get("follow_up_date")
    )

    if item.get("application_id"):
        lead_type = "application"
        lead_id = item["application_id"]
        source = "Application"
    else:
        lead_type = "assessment"
        lead_id = item.get("snapshot_id")
        source = "Assessment"

    submitted_at = (
        item.get("application_submitted_at")
        or item.get("assessment_submitted_at")
    )

    item["effective_status"] = status
    item["stage_label"] = _lead_stage_label(status)
    item["stage_group"] = _lead_stage_group(status)
    item["effective_follow_up_date"] = follow_up_date
    item["lead_type"] = lead_type
    item["lead_id"] = lead_id
    item["source_label"] = source
    item["submitted_at"] = submitted_at
    item["follow_up_due"] = bool(
        follow_up_date
        and follow_up_date <= today
        and status not in CLOSED_STATUSES
    )
    item["follow_up_overdue"] = bool(
        follow_up_date
        and follow_up_date < today
        and status not in CLOSED_STATUSES
    )

    searchable_values = [
        item.get("name"),
        item.get("phone"),
        item.get("email"),
        item.get("opportunity"),
        item.get("strength"),
        status,
        item.get("age_range"),
        source,
    ]

    item["search_text"] = " ".join(
        str(value)
        for value in searchable_values
        if value is not None
    ).lower()

    return item


@router.get(
    "/dashboard/leads",
    response_class=HTMLResponse,
)
def leads_page(request: Request):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    today = date.today()

    leads = [
        _prepare_lead_row(lead, today)
        for lead in get_all_leads()
    ]

    total_leads = len(leads)

    new_leads = sum(
        1
        for lead in leads
        if lead["effective_status"] == "new"
    )

    clarity_calls = sum(
        1
        for lead in leads
        if lead["effective_status"]
        == "clarity_call_booked"
    )

    follow_ups_due = sum(
        1
        for lead in leads
        if lead["follow_up_due"]
    )

    joined = sum(
        1
        for lead in leads
        if lead["effective_status"] in {
            "joined_foundations",
            "joined_transformation",
        }
    )

    return templates.TemplateResponse(
        "coach/leads.html",
        {
            "request": request,
            "active_nav": "leads",
            "today": today,
            "leads": leads,
            "total_leads": total_leads,
            "new_leads": new_leads,
            "clarity_calls": clarity_calls,
            "follow_ups_due": follow_ups_due,
            "joined": joined,
        },
    )


@router.get(
    "/dashboard/leads/{lead_type}/{lead_id}",
    response_class=HTMLResponse,
)
def lead_workspace(
    request: Request,
    lead_type: str,
    lead_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    if lead_type == "assessment":
        lead = get_lead_profile(
            snapshot_id=lead_id
        )
    elif lead_type == "application":
        lead = get_lead_profile(
            application_id=lead_id
        )
    else:
        raise HTTPException(
            status_code=404,
            detail="Lead type not found",
        )

    if lead is None:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    lead = dict(lead)

    effective_status = (
        lead.get("application_status")
        if lead_type == "assessment"
        and lead.get("application_id")
        else lead.get("status")
    ) or "new"

    effective_follow_up = (
        lead.get("application_follow_up_date")
        if lead_type == "assessment"
        and lead.get("application_id")
        else lead.get("follow_up_date")
    )

    effective_notes = (
        lead.get("application_coach_notes")
        if lead_type == "assessment"
        and lead.get("application_id")
        else lead.get("coach_notes")
    )

    events = get_lead_events(
        snapshot_id=lead.get("snapshot_id")
        or (
            lead_id
            if lead_type == "assessment"
            else None
        ),
        application_id=lead.get("application_id")
        or (
            lead_id
            if lead_type == "application"
            else None
        ),
    )

    now = datetime.now(timezone.utc)
    today_date = now.date()
    yesterday_date = (
        today_date - timedelta(days=1)
    )

    timeline_groups = {
        "Today": [],
        "Yesterday": [],
        "Earlier": [],
    }

    for event in events:
        created_at = event.get("created_at")

        if not created_at:
            timeline_groups["Earlier"].append(
                event
            )
            continue

        event_date = created_at.date()

        if event_date == today_date:
            timeline_groups["Today"].append(
                event
            )
        elif event_date == yesterday_date:
            timeline_groups["Yesterday"].append(
                event
            )
        else:
            timeline_groups["Earlier"].append(
                event
            )

    return templates.TemplateResponse(
        "coach/lead_workspace.html",
        {
            "request": request,
            "active_nav": "leads",
            "lead": lead,
            "lead_type": lead_type,
            "lead_id": lead_id,
            "effective_status": effective_status,
            "stage_label": _lead_stage_label(
                effective_status
            ),
            "effective_follow_up": effective_follow_up,
            "effective_notes": effective_notes,
            "saved":
                request.query_params.get("saved")
                == "1",
            "events": events,
            "timeline_groups": timeline_groups,
        },
    )


@router.post(
    "/dashboard/leads/{lead_type}/{lead_id}/update"
)
def update_lead(
    request: Request,
    lead_type: str,
    lead_id: int,
    status: str = Form(...),
    coach_notes: str = Form(""),
    follow_up_date: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    try:
        updated = update_lead_crm(
            lead_type=lead_type,
            lead_id=lead_id,
            status=status,
            coach_notes=
                coach_notes.strip() or None,
            follow_up_date=
                follow_up_date or None,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return RedirectResponse(
        url=(
            f"/dashboard/leads/"
            f"{lead_type}/{lead_id}"
            "?saved=1"
        ),
        status_code=303,
    )
