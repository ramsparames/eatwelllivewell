import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.services.client_service import ClientService
from app.client.portal import router as client_portal_router
from app.services.client_portal_service import (
    ensure_portal_access,
    get_portal_access,
    get_recent_client_activity,
    get_coach_week_review,
    build_call_prep,
    get_next_client_call,
)


router = APIRouter()

# Client-facing routes live in app/client/portal.py.
# Included here so no main.py change is required.
router.include_router(client_portal_router)

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

CALL_TIME_SLOTS = [
    {
        "value": f"{hour:02d}:{minute:02d}",
        "label": (
            f"{12 if hour % 12 == 0 else hour % 12}:{minute:02d} "
            f"{'AM' if hour < 12 else 'PM'}"
        ),
    }
    for hour in range(6, 23)
    for minute in (0, 30)
    if not (hour == 22 and minute == 30)
]


def _coaching_week_bounds(client: dict, on_date: date | None = None):
    """Return Week N and its real 7-day boundaries from clients.start_date."""
    on_date = on_date or date.today()
    start_date = client.get("start_date")

    if not start_date:
        return 0, None, None

    if on_date < start_date:
        return 1, start_date, start_date + timedelta(days=6)

    elapsed = (on_date - start_date).days
    week_number = (elapsed // 7) + 1
    week_start = start_date + timedelta(days=(week_number - 1) * 7)
    return week_number, week_start, week_start + timedelta(days=6)


def _action_week_bounds(client_id: int, on_date: date):
    client = ClientService.get(client_id) or {}
    _, week_start, week_end = _coaching_week_bounds(client, on_date)
    if week_start is None:
        week_start = on_date
        week_end = on_date + timedelta(days=6)
    return week_start, week_end




def _build_synamate_booking_url(
    base_url: str,
    client: dict,
) -> str:
    """
    Add NourisHer client identity to the Synamate public booking URL.

    Synamate's public help center documents the contact fields used by the
    calendar/contact system but does not publish a formal booking-URL query
    parameter contract. We therefore send the common contact field names in
    both full-name and split-name form. Existing query parameters are kept.
    """
    base_url = (base_url or "").strip()
    if not base_url:
        return ""

    full_name = (client.get("name") or "").strip()
    email = (client.get("email") or "").strip()
    phone = (client.get("phone") or "").strip()

    name_parts = full_name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    # Use setdefault so an intentionally configured value in the base URL wins.
    if full_name:
        query.setdefault("name", full_name)
        query.setdefault("full_name", full_name)
    if first_name:
        query.setdefault("first_name", first_name)
    if last_name:
        query.setdefault("last_name", last_name)
    if email:
        query.setdefault("email", email)
    if phone:
        query.setdefault("phone", phone)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
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

        week_number, week_start, week_end = _coaching_week_bounds(
            client,
            today,
        )
        client["current_week"] = week_number
        client["current_week_start"] = week_start
        client["current_week_end"] = week_end

        client["last_checkin_date"] = (
            latest_checkin.get("call_date")
            if latest_checkin
            else None
        )

        # Keep weight fallback from the latest weekly review.
        if latest_checkin and client.get("current_weight_kg") is None:
            client["current_weight_kg"] = latest_checkin.get("weight_kg")

        # Synamate is now the single source of truth for the next coaching call.
        # Populate the legacy display keys too so the existing Clients template
        # can show the synced appointment without needing a markup change.
        synced_call = get_next_client_call(client)

        client["next_synced_call"] = synced_call
        client["next_call_date"] = None
        client["next_call_time"] = None

        if synced_call and synced_call.get("local_start_time"):
            local_start = synced_call["local_start_time"]
            client["next_call_date"] = local_start.date()
            client["next_call_time"] = local_start.time().replace(tzinfo=None)
            client["next_call_source"] = "synamate"
        else:
            client["next_call_source"] = None

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

        elif not client.get("next_synced_call"):
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
            client["next_synced_call"]["local_start_time"].isoformat()
            if (
                client.get("next_synced_call")
                and client["next_synced_call"].get("local_start_time")
            )
            else "9999-12-31T23:59:59"
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
    country_code: str = Form("+91"),
    phone: str = Form(""),
    program: str = Form("Transformation"),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    clean_phone = phone.strip()
    if clean_phone and not clean_phone.startswith("+"):
        clean_phone = f"{country_code.strip()} {clean_phone}".strip()

    client_id = ClientService.create(
        name=name.strip(),
        email=email.strip() or None,
        phone=clean_phone or None,
        program=program,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/portal-access"
)
def create_client_portal_access(
    request: Request,
    client_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    ensure_portal_access(client_id)

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
        return RedirectResponse("/coach/login", status_code=303)

    profile = ClientService.profile(client_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if profile.get("current_weight") is None and profile.get("measurements"):
        latest_measurement = profile["measurements"][0]
        if latest_measurement.get("weight_kg") is not None:
            profile["current_weight"] = latest_measurement.get("weight_kg")

    week_number, week_start, week_end = _coaching_week_bounds(
        profile["client"],
        date.today(),
    )
    profile["current_week"] = week_number
    profile["current_week_start"] = week_start
    profile["current_week_end"] = week_end

    for entry in profile.get("tracking") or []:
        if entry.get("weight_kg") is not None:
            profile["current_weight"] = entry.get("weight_kg")
            break

    portal_access = get_portal_access(client_id)
    portal_activity = get_recent_client_activity(client_id, limit=14)

    week_review = None
    call_prep = None
    next_week_number = None
    next_week_start = None
    next_week_end = None
    next_week_actions = []

    if week_start and week_end:
        week_review = get_coach_week_review(client_id, week_start, week_end)
        call_prep = build_call_prep(client_id, week_start, week_end)
        next_week_number = week_number + 1
        next_week_start = week_end + timedelta(days=1)
        next_week_end = next_week_start + timedelta(days=6)
        next_week_actions = ClientService.actions(
            client_id,
            status="active",
            start_date=next_week_start,
            end_date=next_week_end,
        )

    next_synced_call = get_next_client_call(profile["client"])
    coaching_booking_base_url = os.getenv(
        "SYNAMATE_COACHING_CALL_URL",
        "",
    ).strip()
    coaching_booking_url = _build_synamate_booking_url(
        coaching_booking_base_url,
        profile["client"],
    )

    return templates.TemplateResponse(
        "coach/client_workspace.html",
        {
            "request": request,
            "active_nav": "clients",
            "action_library": ACTION_LIBRARY,
            "call_time_slots": CALL_TIME_SLOTS,
            "portal_access": portal_access,
            "portal_activity": portal_activity,
            "week_review": week_review,
            "call_prep": call_prep,
            "next_synced_call": next_synced_call,
            "coaching_booking_url": coaching_booking_url,
            "next_week_number": next_week_number,
            "next_week_start": next_week_start,
            "next_week_end": next_week_end,
            "next_week_action_names": {
                row.get("action_name") for row in next_week_actions
            },
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
    phone: str = Form(""),
    week_start_date: str = Form(...),
    current_situation: str = Form(""),
    primary_goal: str = Form(""),
    secondary_goals: str = Form(""),
    present_weight_kg: str = Form(""),
    goal_weight_kg: str = Form(""),
    coach_focus: str = Form(""),
    action_keys: list[str] = Form(default=[]),
    custom_action_name: str = Form(""),
    custom_target_count: str = Form(""),
    custom_target_unit: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    parsed_present_weight = (
        float(present_weight_kg) if present_weight_kg.strip() else None
    )
    parsed_goal_weight = (
        float(goal_weight_kg) if goal_weight_kg.strip() else None
    )
    parsed_week_start = date.fromisoformat(week_start_date)

    ClientService.set_phone(client_id, phone.strip() or None)
    ClientService.save_intake(
        client_id=client_id,
        intake_date=intake_date,
        current_situation=current_situation.strip() or None,
        primary_goal=primary_goal.strip() or None,
        secondary_goals=secondary_goals.strip() or None,
        goal_weight_kg=parsed_goal_weight,
        coach_focus=coach_focus.strip() or None,
    )
    ClientService.set_start_date(client_id, parsed_week_start)

    if parsed_present_weight is not None:
        ClientService.add_measurement(
            client_id=client_id,
            measured_on=intake_date,
            weight_kg=parsed_present_weight,
            measurement_unit="cm",
            checkin_id=None,
        )

    first_week_end = parsed_week_start + timedelta(days=6)
    added_names = set()

    for action_key in action_keys:
        library_action = ACTION_LIBRARY_BY_KEY.get(action_key)
        if not library_action or library_action["name"] in added_names:
            continue
        ClientService.add_action(
            client_id=client_id,
            action_name=library_action["name"],
            target_count=library_action["target_count"],
            target_unit=library_action["target_unit"],
            start_date=parsed_week_start,
            end_date=first_week_end,
        )
        added_names.add(library_action["name"])

    if custom_action_name.strip() and custom_action_name.strip() not in added_names:
        ClientService.add_action(
            client_id=client_id,
            action_name=custom_action_name.strip(),
            target_count=(
                int(custom_target_count)
                if custom_target_count.strip()
                else None
            ),
            target_unit=custom_target_unit.strip() or None,
            start_date=parsed_week_start,
            end_date=first_week_end,
        )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/week-start"
)
def save_week_start(
    request: Request,
    client_id: int,
    week_start_date: str = Form(...),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    parsed = date.fromisoformat(week_start_date)
    ClientService.set_start_date(client_id, parsed)

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
    action_key: str = Form(""),
    custom_action_name: str = Form(""),
    custom_target_count: str = Form(""),
    custom_target_unit: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    action_name = None
    target_count = None
    target_unit = None

    if action_key:
        library_action = ACTION_LIBRARY_BY_KEY.get(action_key)
        if library_action:
            action_name = library_action["name"]
            target_count = library_action["target_count"]
            target_unit = library_action["target_unit"]

    if not action_name and custom_action_name.strip():
        action_name = custom_action_name.strip()
        target_count = (
            int(custom_target_count)
            if custom_target_count.strip()
            else None
        )
        target_unit = custom_target_unit.strip() or None

    if action_name:
        existing_names = {
            row.get("action_name")
            for row in ClientService.actions(client_id, status="active")
        }

        if action_name not in existing_names:
            start_date, end_date = _action_week_bounds(
                client_id,
                date.today(),
            )
            ClientService.add_action(
                client_id=client_id,
                action_name=action_name,
                target_count=target_count,
                target_unit=target_unit,
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
        weight_kg=None,
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
    wins: str = Form(""),
    struggles: str = Form(""),
    improvements_needed: str = Form(""),
    coach_support: str = Form(""),
    action_keys: list[str] = Form(default=[]),
    custom_action_name: str = Form(""),
    custom_target_count: str = Form(""),
    custom_target_unit: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    checkin_id = ClientService.add_checkin(
        client_id=client_id,
        call_date=call_date,
        weight_kg=None,
        next_call_date=None,
        next_call_time=None,
        wins=wins.strip() or None,
        struggles=struggles.strip() or None,
        improvements_needed=improvements_needed.strip() or None,
        coach_support=coach_support.strip() or None,
    )

    client = ClientService.get(client_id) or {}
    _, _, current_week_end = _coaching_week_bounds(
        client,
        date.fromisoformat(call_date),
    )
    if current_week_end is None:
        current_week_end = date.fromisoformat(call_date)

    action_start_date = current_week_end + timedelta(days=1)
    action_end_date = action_start_date + timedelta(days=6)

    existing_action_names = {
        row.get("action_name")
        for row in ClientService.actions(
            client_id,
            status="active",
            start_date=action_start_date,
            end_date=action_end_date,
        )
    }

    for action_key in action_keys:
        library_action = ACTION_LIBRARY_BY_KEY.get(action_key)
        if not library_action:
            continue
        if library_action["name"] in existing_action_names:
            continue
        ClientService.add_action(
            client_id=client_id,
            action_name=library_action["name"],
            target_count=library_action["target_count"],
            target_unit=library_action["target_unit"],
            start_date=action_start_date,
            end_date=action_end_date,
            checkin_id=checkin_id,
        )
        existing_action_names.add(library_action["name"])

    if custom_action_name.strip() and custom_action_name.strip() not in existing_action_names:
        ClientService.add_action(
            client_id=client_id,
            action_name=custom_action_name.strip(),
            target_count=(
                int(custom_target_count)
                if custom_target_count.strip()
                else None
            ),
            target_unit=custom_target_unit.strip() or None,
            start_date=action_start_date,
            end_date=action_end_date,
            checkin_id=checkin_id,
        )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=weekly",
        status_code=303,
    )
