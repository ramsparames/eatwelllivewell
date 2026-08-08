from pathlib import Path

from fastapi import (
    APIRouter,
    Form,
    HTTPException,
    Request,
)

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.services.client_service import ClientService

BASE_DIR = Path(__file__).resolve().parent.parent.parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

router = APIRouter()

templates: Jinja2Templates | None = None

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
    target_count: str = Form(""),
    target_unit: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    start_date = date.today()
    end_date = start_date + timedelta(days=6)
    parsed_target_count = (
    int(target_count)
    if target_count.strip()
    else None
    )    

    ClientService.add_action(
        client_id=client_id,
        action_name=action_name.strip(),
        target_count=parsed_target_count,
        target_unit=target_unit.strip() or None,
        start_date=start_date,
        end_date=end_date,
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

