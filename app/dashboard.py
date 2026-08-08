from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.database import get_all_leads
from app.services.client_service import ClientService


router = APIRouter()

templates: Jinja2Templates | None = None


def set_templates(template_engine: Jinja2Templates) -> None:
    global templates
    templates = template_engine


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
def dashboard_home(request: Request):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    if templates is None:
        raise RuntimeError("Templates are not configured")

    clients = ClientService.dashboard_clients()
    calls_today = ClientService.calls_today()
    calls_this_week = ClientService.calls_this_week()

    active_clients = [
        client
        for client in clients
        if client.get("status") == "active"
    ]

    clients_without_next_call = [
        client
        for client in active_clients
        if not client.get("next_call_date")
    ]

    all_leads = get_all_leads()

    new_leads = 0
    lead_followups_due = 0
    today = date.today()

    for lead in all_leads:
        status = (
            lead.get("application_status")
            or lead.get("status")
            or "new"
        )

        if status == "new":
            new_leads += 1

        follow_up_date = (
            lead.get("application_follow_up_date")
            or lead.get("follow_up_date")
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
            lead_followups_due += 1

    return templates.TemplateResponse(
        "coach/dashboard.html",
        {
            "request": request,
            "active_nav": "today",
            "today": today,
            "active_clients": active_clients,
            "calls_today": calls_today,
            "calls_this_week": calls_this_week,
            "clients_without_next_call": clients_without_next_call,
            "new_leads": new_leads,
            "lead_followups_due": lead_followups_due,
        },
    )
