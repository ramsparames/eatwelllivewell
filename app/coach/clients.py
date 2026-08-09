from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.services.client_service import ClientService


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


ACTION_LIBRARY = [
    {
        "category": "Nutrition",
        "items": [
            {
                "key": "protein_first_meal",
                "name": "Protein in the first meal",
                "target_count": 7,
                "target_unit": "days",
            },
            {
                "key": "protein_each_meal",
                "name": "Include a protein source in each main meal",
                "target_count": 7,
                "target_unit": "days",
            },
            {
                "key": "veg_lunch",
                "name": "Fill half the lunch plate with vegetables",
                "target_count": 5,
                "target_unit": "days",
            },
            {
                "key": "planned_evening_snack",
                "name": "Have a planned protein-rich evening snack",
                "target_count": 5,
                "target_unit": "days",
            },
            {
                "key": "slow_eating",
                "name": "Take at least 20 minutes to finish one main meal",
                "target_count": 5,
                "target_unit": "days",
            },
        ],
    },
    {
        "category": "Movement",
        "items": [
            {
                "key": "post_meal_walk",
                "name": "Walk 5–10 minutes after one meal",
                "target_count": 5,
                "target_unit": "days",
            },
            {
                "key": "strength_training",
                "name": "Complete a strength-training session",
                "target_count": 3,
                "target_unit": "sessions",
            },
            {
                "key": "movement_breaks",
                "name": "Stand and move for 2–3 minutes every hour",
                "target_count": 5,
                "target_unit": "days",
            },
            {
                "key": "step_target",
                "name": "Meet the agreed daily step target",
                "target_count": 5,
                "target_unit": "days",
            },
        ],
    },
    {
        "category": "Hydration",
        "items": [
            {
                "key": "water_2l",
                "name": "Drink at least 2 litres of water",
                "target_count": 7,
                "target_unit": "days",
            },
            {
                "key": "water_morning",
                "name": "Start the day with water before the first meal",
                "target_count": 7,
                "target_unit": "days",
            },
        ],
    },
    {
        "category": "Sleep & Recovery",
        "items": [
            {
                "key": "sleep_routine",
                "name": "Follow the agreed wind-down routine",
                "target_count": 5,
                "target_unit": "days",
            },
            {
                "key": "morning_sunlight",
                "name": "Get 10 minutes of morning sunlight",
                "target_count": 5,
                "target_unit": "days",
            },
            {
                "key": "screen_cutoff",
                "name": "Keep screens away for 30 minutes before bed",
                "target_count": 5,
                "target_unit": "days",
            },
        ],
    },
    {
        "category": "Mindset & Consistency",
        "items": [
            {
                "key": "pause_before_eating",
                "name": "Pause and check hunger before unplanned eating",
                "target_count": 5,
                "target_unit": "times",
            },
            {
                "key": "meditation",
                "name": "Do 5–10 minutes of breathing or meditation",
                "target_count": 5,
                "target_unit": "days",
            },
            {
                "key": "daily_checkin",
                "name": "Complete the daily habit check-in",
                "target_count": 7,
                "target_unit": "days",
            },
        ],
    },
]


ACTION_LIBRARY_BY_KEY = {
    item["key"]: item
    for category in ACTION_LIBRARY
    for item in category["items"]
}


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
    calls_this_week = ClientService.calls_this_week()

    today = date.today()

    for client in clients:
        checkins = ClientService.checkins(
            client["id"]
        )

        latest_checkin = (
            checkins[0]
            if checkins
            else None
        )

        # Intake is Week 0. Each saved weekly check-in advances
        # the coaching week: first check-in = Week 1.
        client["current_week"] = len(checkins)

        client["last_checkin_date"] = (
            latest_checkin.get("call_date")
            if latest_checkin
            else None
        )

        # Some summary queries already provide these fields.
        # Fill them from the latest check-in only when needed.
        if latest_checkin:
            if client.get(
                "current_weight_kg"
            ) is None:
                client["current_weight_kg"] = (
                    latest_checkin.get(
                        "weight_kg"
                    )
                )

            if not client.get(
                "next_call_date"
            ):
                client["next_call_date"] = (
                    latest_checkin.get(
                        "next_call_date"
                    )
                )

            if not client.get(
                "next_call_time"
            ):
                client["next_call_time"] = (
                    latest_checkin.get(
                        "next_call_time"
                    )
                )

        status = client.get("status")

        if status != "active":
            client["health_key"] = "neutral"
            client["health_label"] = (
                status.title()
                if status
                else "Inactive"
            )

        elif not latest_checkin:
            client["health_key"] = "new"
            client["health_label"] = "New"

        elif not client.get(
            "next_call_date"
        ):
            client["health_key"] = "attention"
            client["health_label"] = (
                "Needs attention"
            )

        else:
            last_checkin_date = (
                client[
                    "last_checkin_date"
                ]
            )

            days_since_checkin = None

            if last_checkin_date:
                days_since_checkin = (
                    today
                    - last_checkin_date
                ).days

            if (
                days_since_checkin
                is not None
                and days_since_checkin > 14
            ):
                client["health_key"] = (
                    "attention"
                )
                client["health_label"] = (
                    "Needs attention"
                )

            elif (
                days_since_checkin
                is not None
                and days_since_checkin > 8
            ):
                client["health_key"] = (
                    "watch"
                )
                client["health_label"] = (
                    "Watch"
                )

            else:
                client["health_key"] = (
                    "on_track"
                )
                client["health_label"] = (
                    "On track"
                )

        # Values used by the browser-side table sorter.
        client["sort_name"] = (
            client.get("name")
            or ""
        ).lower()

        client["sort_week"] = (
            client.get("current_week")
            or 0
        )

        client["sort_next_call"] = (
            client.get(
                "next_call_date"
            ).isoformat()
            if client.get(
                "next_call_date"
            )
            else "9999-12-31"
        )

        client["sort_last_checkin"] = (
            client.get(
                "last_checkin_date"
            ).isoformat()
            if client.get(
                "last_checkin_date"
            )
            else "0000-00-00"
        )

    active_clients = [
        client
        for client in clients
        if client.get("status") == "active"
    ]

    needs_attention = [
        client
        for client in active_clients
        if client.get("health_key")
        == "attention"
    ]

    return templates.TemplateResponse(
        "coach/clients.html",
        {
            "request": request,
            "active_nav": "clients",
            "clients": clients,
            "active_clients": active_clients,
            "calls_today": calls_today,
            "calls_this_week": calls_this_week,
            "needs_attention": needs_attention,
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

    profile = ClientService.profile(client_id)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Client not found",
        )

    # Before the first weekly check-in, use the intake measurement
    # as the visible current weight.
    if (
        profile.get("current_weight") is None
        and profile.get("measurements")
    ):
        latest_measurement = profile["measurements"][0]

        if latest_measurement.get("weight_kg") is not None:
            profile["current_weight"] = (
                latest_measurement.get("weight_kg")
            )

    # Intake is Week 0. The first saved weekly check-in is Week 1.
    profile["current_week"] = len(
        profile.get("checkins") or []
    )

    return templates.TemplateResponse(
        "coach/client_workspace.html",
        {
            "request": request,
            "active_nav": "clients",
            "action_library": ACTION_LIBRARY,
            **profile,
        },
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
    present_weight_kg: str = Form(""),
    goal_weight_kg: str = Form(""),
    coach_focus: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    parsed_present_weight = (
        float(present_weight_kg)
        if present_weight_kg.strip()
        else None
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

    # Treat intake as the client's baseline / Week 0.
    # Store the present weight as the initial measurement so
    # it becomes part of the client's progress history.
    if parsed_present_weight is not None:
        ClientService.add_measurement(
            client_id=client_id,
            measured_on=intake_date,
            weight_kg=parsed_present_weight,
            measurement_unit="kg",
            checkin_id=None,
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
    action_keys: list[str] = Form(default=[]),
    custom_action_name: str = Form(""),
    custom_target_count: str = Form(""),
    custom_target_unit: str = Form(""),
    next_call_date: str = Form(""),
    next_call_time: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    def parse_float(value: str):
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
        improvements_needed=improvements_needed.strip() or None,
        coach_support=coach_support.strip() or None,
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

    action_start_date = date.fromisoformat(
        call_date
    )
    action_end_date = (
        action_start_date
        + timedelta(days=6)
    )

    for action_key in action_keys:
        library_action = (
            ACTION_LIBRARY_BY_KEY.get(
                action_key
            )
        )

        if not library_action:
            continue

        ClientService.add_action(
            client_id=client_id,
            action_name=library_action["name"],
            target_count=library_action[
                "target_count"
            ],
            target_unit=library_action[
                "target_unit"
            ],
            start_date=action_start_date,
            end_date=action_end_date,
            checkin_id=checkin_id,
        )

    if custom_action_name.strip():
        parsed_custom_target = (
            int(custom_target_count)
            if custom_target_count.strip()
            else None
        )

        ClientService.add_action(
            client_id=client_id,
            action_name=
                custom_action_name.strip(),
            target_count=
                parsed_custom_target,
            target_unit=
                custom_target_unit.strip()
                or None,
            start_date=action_start_date,
            end_date=action_end_date,
            checkin_id=checkin_id,
        )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )
