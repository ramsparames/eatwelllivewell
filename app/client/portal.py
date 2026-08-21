from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.macro_tracking_service import (
    create_macro_tracking_tables,
    get_macro_history,
    get_macro_log,
    get_macro_settings,
    save_macro_log,
)

from app.services.workout_service import (
    complete_workout,
    create_workout_tables,
    get_client_workout_assignment,
    get_client_workouts,
    reopen_workout,
    save_set_log,
)

from app.services.phase_a_service import (
    create_phase_a_tables,
    get_client_resources,
)

from app.services.client_portal_service import (
    create_portal_tables,
    get_action_logs_for_date,
    get_active_actions,
    get_actions_for_date,
    get_editable_week_dates,
    get_client_by_token,
    get_daily_tracking_for_date,
    get_week_completion,
    get_current_week_measurement,
    get_next_client_call,
    get_coaching_week_view,
    get_client_history_grid,
    is_portal_day_submitted,
    save_action_logs,
    save_client_daily_entry,
    save_weekly_measurements,
)

from app.services.coaching_insights_service import get_previous_exercise_performance

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

create_portal_tables()
create_macro_tracking_tables()
create_workout_tables()
create_phase_a_tables()


@router.get(
    "/client/{access_token}",
    response_class=HTMLResponse,
)
def client_home(request: Request, access_token: str):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    try:
        client_tz = ZoneInfo(client.get("timezone") or "Asia/Kolkata")
    except Exception:
        client_tz = ZoneInfo("Asia/Kolkata")
    today = datetime.now(client_tz).date()

    current_week_completion = get_week_completion(
        client["id"],
        on_date=today,
    )
    current_week_number = current_week_completion["week_number"]

    requested_week = request.query_params.get("week")
    try:
        selected_week_number = (
            int(requested_week)
            if requested_week
            else current_week_number
        )
    except ValueError:
        selected_week_number = current_week_number

    selected_week_number = max(
        1,
        min(selected_week_number, current_week_number + 1),
    )

    week_view = get_coaching_week_view(
        client["id"],
        selected_week_number,
        on_date=today,
    )

    requested_day = request.query_params.get("day")
    selected_date = (
        today
        if selected_week_number == current_week_number
        else week_view["week_start"]
    )

    if requested_day:
        try:
            candidate = date.fromisoformat(requested_day)
            if (
                week_view["week_start"]
                <= candidate
                <= week_view["week_end"]
            ):
                selected_date = candidate
        except ValueError:
            pass

    selected_day = next(
        (
            day
            for day in week_view["days"]
            if day["date"] == selected_date
        ),
        week_view["days"][0],
    )

    selected_state = selected_day["browser_state"]
    selected_is_editable = selected_day["editable"]

    editable_dates = [
        day["date"]
        for day in week_view["days"]
        if day["editable"]
    ]

    actions = get_actions_for_date(client["id"], selected_date)
    logs = (
        get_action_logs_for_date(client["id"], selected_date)
        if not week_view["is_future"]
        else {}
    )

    for action in actions:
        action["completed_selected"] = bool(
            logs.get(action["id"], False)
        )

    daily_entry = (
        get_daily_tracking_for_date(client["id"], selected_date)
        if not week_view["is_future"]
        else None
    )
    macro_settings = get_macro_settings(client["id"])
    macro_entry = (
        get_macro_log(client["id"], selected_date)
        if macro_settings.get("enabled") and not week_view["is_future"]
        else None
    )

    client_history_grid = get_client_history_grid(
        client["id"],
        on_date=today,
    )

    macro_history = get_macro_history(
        client["id"],
        client.get("start_date"),
        today,
    )

    if macro_settings.get("enabled"):
        for row in client_history_grid.get("rows") or []:
            row["macro"] = macro_history["by_date"].get(row["date"])

    assigned_workouts = get_client_workouts(client["id"])

    return templates.TemplateResponse(
        "client/home.html",
        {
            "request": request,
            "client": client,
            "access_token": access_token,
            "today": today,
            "selected_date": selected_date,
            "selected_state": selected_state,
            "selected_is_editable": selected_is_editable,
            "editable_dates": editable_dates,
            "actions": actions,
            "daily_entry": daily_entry,
            "macro_settings": macro_settings,
            "macro_entry": macro_entry,
            "client_history_grid": client_history_grid,
            "week_completion": current_week_completion,
            "week_view": week_view,
            "weekly_measurement": get_current_week_measurement(client["id"], on_date=today),
            "next_call": get_next_client_call(client),
            "assigned_resources": get_client_resources(client["id"]),
            "assigned_workouts": assigned_workouts,
            "saved": request.query_params.get("saved") == "1",
            "measurement_saved":
                request.query_params.get("measurement_saved") == "1",
            "measurement_error":
                request.query_params.get("measurement_error"),
        },
    )


@router.get(
    "/client/{access_token}/workouts",
    response_class=HTMLResponse,
)
def client_workouts_page(
    request: Request,
    access_token: str,
):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    workouts = get_client_workouts(client["id"])

    requested = request.query_params.get("workout")
    selected_assignment_id = None
    if requested:
        try:
            selected_assignment_id = int(requested)
        except ValueError:
            selected_assignment_id = None

    valid_ids = {row["assignment_id"] for row in workouts}
    if selected_assignment_id not in valid_ids:
        selected_assignment_id = (
            workouts[0]["assignment_id"] if workouts else None
        )

    selected_workout = (
        get_client_workout_assignment(
            selected_assignment_id,
            client["id"],
        )
        if selected_assignment_id
        else None
    )

    if selected_workout:
        for exercise in selected_workout.get("exercises", []):
            exercise["previous_performance"] = (
                get_previous_exercise_performance(
                    client["id"],
                    selected_workout["id"],
                    exercise["title"],
                )
            )

    try:
        client_tz = ZoneInfo(client.get("timezone") or "Asia/Kolkata")
    except Exception:
        client_tz = ZoneInfo("Asia/Kolkata")
    today = datetime.now(client_tz).date()

    return templates.TemplateResponse(
        "client/workouts.html",
        {
            "request": request,
            "client": client,
            "access_token": access_token,
            "workouts": workouts,
            "selected_workout": selected_workout,
            "selected_assignment_id": selected_assignment_id,
            "today": today,
            "saved": request.query_params.get("saved") == "1",
        },
    )


@router.get(
    "/client/{access_token}/workouts/{assignment_id}",
)
def legacy_client_workout_page(
    access_token: str,
    assignment_id: int,
):
    return RedirectResponse(
        f"/client/{access_token}/workouts?workout={assignment_id}",
        status_code=303,
    )


@router.post("/client/{access_token}/workouts/{assignment_id}/set")
def save_client_workout_set(
    access_token: str,
    assignment_id: int,
    exercise_id: int = Form(...),
    set_number: int = Form(...),
    weight_kg: str = Form(""),
    reps: str = Form(""),
    completed: bool = Form(False),
):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    def optional_float(value: str):
        return float(value) if value.strip() else None

    def optional_int(value: str):
        return int(value) if value.strip() else None

    ok = save_set_log(
        assignment_id=assignment_id,
        client_id=client["id"],
        exercise_id=exercise_id,
        set_number=set_number,
        weight_kg=optional_float(weight_kg),
        reps=optional_int(reps),
        completed=completed,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Workout set not found")

    return RedirectResponse(
        f"/client/{access_token}/workouts?workout={assignment_id}&saved=1",
        status_code=303,
    )


@router.post("/client/{access_token}/workouts/{assignment_id}/complete")
def complete_client_workout(
    access_token: str,
    assignment_id: int,
    workout_date: str = Form(...),
):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    try:
        client_tz = ZoneInfo(client.get("timezone") or "Asia/Kolkata")
    except Exception:
        client_tz = ZoneInfo("Asia/Kolkata")
    today = datetime.now(client_tz).date()

    try:
        actual_workout_date = date.fromisoformat(workout_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workout date")

    if actual_workout_date > today:
        raise HTTPException(
            status_code=400,
            detail="Workout date cannot be in the future",
        )

    complete_workout(
        assignment_id,
        client["id"],
        actual_workout_date,
    )
    return RedirectResponse(
        f"/client/{access_token}/workouts?workout={assignment_id}",
        status_code=303,
    )


@router.post("/client/{access_token}/workouts/{assignment_id}/reopen")
def reopen_client_workout(access_token: str, assignment_id: int):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")
    reopen_workout(assignment_id, client["id"])
    return RedirectResponse(
        f"/client/{access_token}/workouts?workout={assignment_id}",
        status_code=303,
    )


@router.post("/client/{access_token}/daily")
def save_client_day(
    access_token: str,
    tracked_on: str = Form(...),
    selected_week_number: int = Form(...),
    completed_action_ids: list[int] = Form(default=[]),
    steps: str = Form(""),
    weight_kg: str = Form(""),
    protein_g: str = Form(""),
    carbs_g: str = Form(""),
    fat_g: str = Form(""),
):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    try:
        client_tz = ZoneInfo(client.get("timezone") or "Asia/Kolkata")
    except Exception:
        client_tz = ZoneInfo("Asia/Kolkata")
    today = datetime.now(client_tz).date()

    try:
        selected_date = date.fromisoformat(tracked_on)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid check-in date")

    editable_dates = get_editable_week_dates(client["id"], today)
    if selected_date not in editable_dates:
        raise HTTPException(
            status_code=400,
            detail="Only dates in the current coaching week up to today can be edited",
        )

    actions = get_actions_for_date(client["id"], selected_date)
    active_ids = [action["id"] for action in actions]
    valid_completed = [
        action_id
        for action_id in completed_action_ids
        if action_id in active_ids
    ]

    def parse_int(value: str):
        return int(value) if value.strip() else None

    def parse_float(value: str):
        return float(value) if value.strip() else None

    save_action_logs(
        client_id=client["id"],
        tracked_on=selected_date,
        active_action_ids=active_ids,
        completed_action_ids=valid_completed,
    )

    save_client_daily_entry(
        client_id=client["id"],
        tracked_on=selected_date,
        steps=parse_int(steps),
        weight_kg=parse_float(weight_kg),
    )
    macro_settings = get_macro_settings(client["id"])
    if macro_settings.get("enabled"):
        save_macro_log(
            client_id=client["id"],
            tracked_on=selected_date,
            protein_g=parse_float(protein_g),
            carbs_g=parse_float(carbs_g),
            fat_g=parse_float(fat_g),
        )

    return RedirectResponse(
        f"/client/{access_token}?saved=1&week={selected_week_number}&day={selected_date.isoformat()}",
        status_code=303,
    )


@router.post("/client/{access_token}/measurements")
def save_client_measurements(
    access_token: str,
    measured_on: str = Form(...),
    upper_arm: str = Form(""),
    chest: str = Form(""),
    waist: str = Form(""),
    lower_abdomen: str = Form(""),
    hip: str = Form(""),
    thigh: str = Form(""),
    measurement_unit: str = Form("cm"),
):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    try:
        client_tz = ZoneInfo(client.get("timezone") or "Asia/Kolkata")
    except Exception:
        client_tz = ZoneInfo("Asia/Kolkata")
    today = datetime.now(client_tz).date()

    def parse_float(value: str):
        return float(value) if value.strip() else None

    try:
        saved = save_weekly_measurements(
            client_id=client["id"],
            measured_on=date.fromisoformat(measured_on),
            on_date=today,
            upper_arm=parse_float(upper_arm),
            chest=parse_float(chest),
            waist=parse_float(waist),
            lower_abdomen=parse_float(lower_abdomen),
            hip=parse_float(hip),
            thigh=parse_float(thigh),
            measurement_unit=measurement_unit,
        )
    except (ValueError, TypeError):
        return RedirectResponse(
            f"/client/{access_token}?measurement_error=1",
            status_code=303,
        )

    if not saved:
        return RedirectResponse(
            f"/client/{access_token}?measurement_error=already_saved",
            status_code=303,
        )

    return RedirectResponse(
        f"/client/{access_token}?measurement_saved=1",
        status_code=303,
    )

