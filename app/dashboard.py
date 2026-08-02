from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.database import get_all_leads, get_lead_profile
from app.database import (
    get_all_leads,
    get_lead_profile,
    update_lead_crm,
)
from fastapi import Form

router = APIRouter()

templates: Jinja2Templates | None = None


def set_templates(template_engine: Jinja2Templates) -> None:
    global templates
    templates = template_engine


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
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

    return templates.TemplateResponse(
        "lead.html",
        {
            "request": request,
            "lead": lead,
            "lead_type": lead_type,
            "lead_id": lead_id,
            "saved": request.query_params.get("saved") == "1",
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
        print("Status:", status)
        print("Notes:", coach_notes)
        print("Follow-up:", follow_up_date)
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
