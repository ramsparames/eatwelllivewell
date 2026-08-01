from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_all_leads, get_lead_by_id
from app.auth import coach_is_logged_in


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

if not coach_is_logged_in(request):
    return RedirectResponse(
        "/coach/login",
        status_code=303,
    )
    
@router.get("/dashboard/leads/{lead_id}", response_class=HTMLResponse)
def lead_detail(request: Request, lead_id: int):
    if templates is None:
        raise RuntimeError("Templates are not configured")

    lead = get_lead_by_id(lead_id)

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
        },
    )
