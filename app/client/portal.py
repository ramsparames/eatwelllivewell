from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

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
    is_portal_day_submitted,
    save_action_logs,
    save_client_daily_entry,
    save_weekly_measurements,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

create_portal_tables()
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
            "week_completion": current_week_completion,
            "week_view": week_view,
            "weekly_measurement": get_current_week_measurement(client["id"], on_date=today),
            "next_call": get_next_client_call(client),
            "assigned_resources": get_client_resources(client["id"]),
            "saved": request.query_params.get("saved") == "1",
            "measurement_saved":
                request.query_params.get("measurement_saved") == "1",
            "measurement_error":
                request.query_params.get("measurement_error"),
        },
    )


@router.post("/client/{access_token}/daily")
def save_client_day(
    access_token: str,
    tracked_on: str = Form(...),
    selected_week_number: int = Form(...),
    completed_action_ids: list[int] = Form(default=[]),
    steps: str = Form(""),
    weight_kg: str = Form(""),
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

