from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date
from app.auth import coach_is_logged_in
from app.database import get_all_leads, get_lead_profile
from app.database import (
    get_all_leads,
    get_lead_profile,
    get_lead_events,
    update_lead_crm,
)
from fastapi import Form

router = APIRouter()

templates: Jinja2Templates | None = None


def set_templates(template_engine: Jinja2Templates) -> None:
    global templates
    templates = template_engine


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    q: str = "",
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    if templates is None:
        raise RuntimeError("Templates are not configured")

    all_leads = get_all_leads()
    today = date.today()

    total_leads = len(all_leads)

    total_applications = sum(
        1
        for lead in all_leads
        if lead.get("has_application")
    )

    new_leads = sum(
        1
        for lead in all_leads
        if (
            lead.get("application_status")
            or lead.get("status")
            or "new"
        ) == "new"
    )

    clarity_calls_booked = sum(
        1
        for lead in all_leads
        if (
            lead.get("application_status")
            or lead.get("status")
        ) == "clarity_call_booked"
    )

    follow_ups_due = 0

    for lead in all_leads:
        follow_up_date = (
            lead.get("application_follow_up_date")
            or lead.get("follow_up_date")
        )

        status = (
            lead.get("application_status")
            or lead.get("status")
            or "new"
        )

        if (
            follow_up_date
            and follow_up_date <= today
            and status not in {
                "joined_foundations",
                "joined_transformation",
                "closed",
            }
        ):
            follow_ups_due += 1

    search_query = q.strip().lower()
    leads = all_leads

    if search_query:
        filtered_leads = []

        for lead in leads:
            searchable_values = [
                lead.get("name"),
                lead.get("phone"),
                lead.get("email"),
                lead.get("opportunity"),
                lead.get("strength"),
                lead.get("status"),
                lead.get("application_status"),
            ]

            searchable_text = " ".join(
                str(value)
                for value in searchable_values
                if value is not None
            ).lower()

            if search_query in searchable_text:
                filtered_leads.append(lead)

        leads = filtered_leads

    today_focus = []

    if follow_ups_due:
        today_focus.append(
            f"🔴 {follow_ups_due} follow-up"
            + ("s" if follow_ups_due != 1 else "")
            + " due"
        )

    if clarity_calls_booked:
        today_focus.append(
            f"📞 {clarity_calls_booked} clarity call"
            + ("s" if clarity_calls_booked != 1 else "")
            + " booked"
        )

    if new_leads:
        today_focus.append(
            f"🆕 {new_leads} new lead"
            + ("s" if new_leads != 1 else "")
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "leads": leads,
            "search_query": q,
            "total_leads": total_leads,
            "total_applications": total_applications,
            "new_leads": new_leads,
            "clarity_calls_booked": clarity_calls_booked,
            "follow_ups_due": follow_ups_due,
            "today": today,
            "today_focus": today_focus,
        },
    )
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    if templates is None:
        raise RuntimeError("Templates are not configured")

    leads = get_all_leads()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "leads": leads,
            "today_focus": today_focus,
        },
    )


@router.get("/dashboard/leads/{lead_type}/{lead_id}", response_class=HTMLResponse)
def lead_profile(
    request: Request,
    lead_type: str,
    lead_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    if templates is None:
        raise RuntimeError("Templates are not configured")

    if lead_type == "assessment":
        lead = get_lead_profile(snapshot_id=lead_id)
    elif lead_type == "application":
        lead = get_lead_profile(application_id=lead_id)
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
    events = get_lead_events(
        snapshot_id=lead.get("snapshot_id"),
        application_id=lead.get("application_id"),
    )
    
    return templates.TemplateResponse(
        "lead.html",
        {
            "request": request,
            "lead": lead,
            "lead_type": lead_type,
            "lead_id": lead_id,
            "saved": request.query_params.get("saved") == "1",
            "events": events,
        },
    )
@router.post("/dashboard/leads/{lead_type}/{lead_id}/update")
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
            coach_notes=coach_notes.strip() or None,
            follow_up_date=follow_up_date or None,
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
        url=f"/dashboard/leads/{lead_type}/{lead_id}?saved=1",
        status_code=303,
    )
