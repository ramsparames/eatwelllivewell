from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date, datetime, timedelta, timezone
from app.auth import coach_is_logged_in
from app.database import (
    get_all_leads,
    get_lead_profile,
    get_lead_events,
    update_lead_crm,
)
from app.services.client_service import ClientService
from fastapi import Form

router = APIRouter()

templates: Jinja2Templates | None = None


def set_templates(template_engine: Jinja2Templates) -> None:
    global templates
    templates = template_engine


@router.get("/dashboard/leads", response_class=HTMLResponse)
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

    new_leads = 0
    clarity_calls_booked = 0

    # These lists will power the new Action Centre.
    today_followups = []
    new_applications = []
    priority_applicants = []

    for lead in all_leads:
        status = (
            lead.get("application_status")
            or lead.get("status")
            or "new"
        )

        follow_up_date = (
            lead.get("application_follow_up_date")
            or lead.get("follow_up_date")
        )

        # Use the assessment route when an assessment exists.
        # Otherwise, open the direct application route.
        if lead.get("snapshot_id"):
            lead_type = "assessment"
            lead_id = lead["snapshot_id"]
        else:
            lead_type = "application"
            lead_id = lead.get("application_id")

        if status == "new":
            new_leads += 1

        if status == "clarity_call_booked":
            clarity_calls_booked += 1

        # Due today or overdue.
        if (
            follow_up_date
            and follow_up_date <= today
            and status not in {
                "joined_foundations",
                "joined_transformation",
                "closed",
            }
        ):
            today_followups.append(
                {
                    "name": lead.get("name") or "Lead",
                    "phone": lead.get("phone"),
                    "follow_up_date": follow_up_date,
                    "is_overdue": follow_up_date < today,
                    "lead_type": lead_type,
                    "lead_id": lead_id,
                }
            )

        # Newly submitted Transformation applications.
        if lead.get("has_application") and status == "new":
            new_applications.append(
                {
                    "name": lead.get("name") or "Lead",
                    "phone": lead.get("phone"),
                    "email": lead.get("email"),
                    "submitted_at": lead.get(
                        "application_submitted_at"
                    ),
                    "lead_type": lead_type,
                    "lead_id": lead_id,
                }
            )

        # Applicants with a lower assessment score may need
        # faster personal attention.
        total_score = lead.get("total_score")

        if (
            lead.get("has_application")
            and total_score is not None
            and total_score < 45
            and status not in {
                "joined_foundations",
                "joined_transformation",
                "closed",
            }
        ):
            priority_applicants.append(
                {
                    "name": lead.get("name") or "Lead",
                    "phone": lead.get("phone"),
                    "total_score": total_score,
                    "opportunity": lead.get("opportunity"),
                    "lead_type": lead_type,
                    "lead_id": lead_id,
                }
            )

    # Overdue follow-ups appear before today's follow-ups.
    today_followups.sort(
        key=lambda item: item["follow_up_date"]
    )

    new_applications.sort(
        key=lambda item: item["submitted_at"] or date.min,
        reverse=True,
    )

    priority_applicants.sort(
        key=lambda item: item["total_score"]
    )

    follow_ups_due = len(today_followups)

    search_query = q.strip().lower()
    leads = all_leads

    if search_query:
        filtered_leads = []

        for lead in all_leads:
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

            # New Action Centre data
            "today_followups": today_followups,
            "new_applications": new_applications,
            "priority_applicants": priority_applicants,
        },
    )
    
@router.get(
    "/dashboard/leads/{lead_type}/{lead_id}",
    response_class=HTMLResponse,
)
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
    now = datetime.now(timezone.utc)
    today_date = now.date()
    yesterday_date = today_date - timedelta(days=1)
    
    timeline_groups = {
        "Today": [],
        "Yesterday": [],
        "Earlier": [],
    }
    
    for event in events:
        created_at = event.get("created_at")
    
        if not created_at:
            timeline_groups["Earlier"].append(event)
            continue
    
        event_date = created_at.date()
    
        if event_date == today_date:
            timeline_groups["Today"].append(event)
    
        elif event_date == yesterday_date:
            timeline_groups["Yesterday"].append(event)
    
        else:
            timeline_groups["Earlier"].append(event)
    return templates.TemplateResponse(
        "lead.html",
        {
            "request": request,
            "lead": lead,
            "lead_type": lead_type,
            "lead_id": lead_id,
            "saved": request.query_params.get("saved") == "1",
            "events": events,
            "timeline_groups": timeline_groups,
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

    clients = ClientService.dashboard_clients()

    calls_today = ClientService.calls_today()

    calls_this_week = (
        ClientService.calls_this_week()
    )

    active_clients = [
        client
        for client in clients
        if client.get("status") == "active"
    ]

    all_leads = get_all_leads()

    new_leads = 0

    for lead in all_leads:
        status = (
            lead.get("application_status")
            or lead.get("status")
            or "new"
        )

        if status == "new":
            new_leads += 1

    return templates.TemplateResponse(
        "dashboard_home.html",
        {
            "request": request,
            "active_clients":
                active_clients,
            "calls_today":
                calls_today,
            "calls_this_week":
                calls_this_week,
            "new_leads":
                new_leads,
        },
    )
    
@router.get(
    "/dashboard/clients",
    response_class=HTMLResponse,
)
def clients_page(request: Request):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    clients = ClientService.dashboard_clients()

    calls_today = ClientService.calls_today()
    
    calls_this_week = (
        ClientService.calls_this_week()
    )
    
    active_clients = [
        client
        for client in clients
        if client["status"] == "active"
    ]

    return templates.TemplateResponse(
        "clients.html",
        {
            "request": request,
            "clients": clients,
            "active_clients": active_clients,
            "calls_today": calls_today,
            "calls_this_week": calls_this_week,
        },
    )

@router.post("/dashboard/clients")
def add_client(
    request: Request,
    name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    program: str = Form("Transformation"),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    client_id = ClientService.create(
        name=name.strip(),
        email=email.strip() or None,
        phone=phone.strip() or None,
        program=program,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )

@router.post(
    "/dashboard/clients/{client_id}/checkin"
)
def add_client_checkin(
    request: Request,
    client_id: int,
    call_date: str = Form(...),

    weight_kg: str = Form(""),

    upper_arm: str = Form(""),
    chest: str = Form(""),
    waist: str = Form(""),
    lower_abdomen: str = Form(""),
    hip: str = Form(""),
    thigh: str = Form(""),

    measurement_unit: str = Form("inches"),

    wins: str = Form(""),
    struggles: str = Form(""),
    improvements_needed: str = Form(""),
    coach_support: str = Form(""),

    next_call_date: str = Form(""),
    next_call_time: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    def parse_float(value):
        return (
            float(value)
            if value.strip()
            else None
        )

    parsed_weight = parse_float(weight_kg)

    checkin_id = ClientService.add_checkin(
        client_id=client_id,
        call_date=call_date,
        weight_kg=parsed_weight,
        next_call_date=next_call_date or None,
        next_call_time=next_call_time or None,
        wins=wins.strip() or None,
        struggles=struggles.strip() or None,
        improvements_needed=
            improvements_needed.strip() or None,
        coach_support=
            coach_support.strip() or None,
    )

    ClientService.add_measurement(
        client_id=client_id,
        checkin_id=checkin_id,
        measured_on=call_date,
        weight_kg=parsed_weight,
        upper_arm=parse_float(upper_arm),
        chest=parse_float(chest),
        waist=parse_float(waist),
        lower_abdomen=parse_float(lower_abdomen),
        hip=parse_float(hip),
        thigh=parse_float(thigh),
        measurement_unit=measurement_unit,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )
    
@router.post(
    "/dashboard/clients/{client_id}/actions"
)
def add_client_action(
        request: Request,
        client_id: int,
        action_name: str = Form(...),
        target_count: int | None = Form(None),
        target_unit: str | None = Form(None),
        start_date: str = Form(...),
        end_date: str | None = Form(None),
    ):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    ClientService.add_action(
        client_id=client_id,
        action_name=action_name.strip(),
        target_count=target_count,
        target_unit=(
            target_unit.strip()
            if target_unit
            else None
        ),
        start_date=start_date,
        end_date=end_date or None,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )
    
@router.get(
    "/dashboard/clients/{client_id}",
    response_class=HTMLResponse,
)
def client_profile(
    request: Request,
    client_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    profile = ClientService.profile(
        client_id
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Client not found",
        )

    return templates.TemplateResponse(
        "client.html",
        {
            "request": request,
            **profile,
        },
    )
@router.post(
    "/dashboard/clients/{client_id}/tracking"
)
def save_client_tracking(
    request: Request,
    client_id: int,
    tracked_on: str = Form(...),
    protein: bool = Form(False),
    water: bool = Form(False),
    steps: str = Form(""),
    strength_training: bool = Form(False),
    stress_score: str = Form(""),
    mood_score: str = Form(""),
    weight_kg: str = Form(""),
    note: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    parsed_steps = (
        int(steps)
        if steps.strip()
        else None
    )

    parsed_stress = (
        int(stress_score)
        if stress_score.strip()
        else None
    )

    parsed_mood = (
        int(mood_score)
        if mood_score.strip()
        else None
    )

    parsed_weight = (
        float(weight_kg)
        if weight_kg.strip()
        else None
    )

    ClientService.save_tracking(
        client_id=client_id,
        tracked_on=tracked_on,
        protein=protein,
        water=water,
        steps=parsed_steps,
        strength_training=strength_training,
        stress_score=parsed_stress,
        mood_score=parsed_mood,
        weight_kg=parsed_weight,
        note=note.strip() or None,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    ClientService.save_tracking(
        client_id=client_id,
        tracked_on=tracked_on,
        protein=protein,
        water=water,
        steps=steps,
        strength_training=strength_training,
        stress_score=stress_score,
        mood_score=mood_score,
        weight_kg=weight_kg,
        note=(
            note.strip()
            if note
            else None
        ),
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )

@router.post(
    "/dashboard/clients/{client_id}/intake"
)
def save_client_intake_route(
    request: Request,
    client_id: int,
    intake_date: str = Form(...),
    current_situation: str = Form(""),
    primary_goal: str = Form(""),
    secondary_goals: str = Form(""),
    goal_weight_kg: str = Form(""),
    coach_focus: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    parsed_goal_weight = (
        float(goal_weight_kg)
        if goal_weight_kg.strip()
        else None
    )

    ClientService.save_intake(
        client_id=client_id,
        intake_date=intake_date,
        current_situation=current_situation.strip() or None,
        primary_goal=primary_goal.strip() or None,
        secondary_goals=secondary_goals.strip() or None,
        goal_weight_kg=parsed_goal_weight,
        coach_focus=coach_focus.strip() or None,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )
