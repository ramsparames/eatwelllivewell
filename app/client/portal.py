from datetime import date
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.client_portal_service import (
    create_portal_tables,
    get_action_logs_for_date,
    get_active_actions,
    get_client_by_token,
    get_daily_tracking_for_date,
    get_week_completion,
    get_current_week_measurement,
    is_portal_day_submitted,
    save_action_logs,
    save_client_daily_entry,
    save_weekly_measurements,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

create_portal_tables()


@router.get(
    "/client/{access_token}",
    response_class=HTMLResponse,
)
def client_home(request: Request, access_token: str):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    today = date.today()
    actions = get_active_actions(client["id"])
    logs = get_action_logs_for_date(client["id"], today)

    for action in actions:
        action["completed_today"] = bool(logs.get(action["id"], False))

    return templates.TemplateResponse(
        "client/home.html",
        {
            "request": request,
            "client": client,
            "access_token": access_token,
            "today": today,
            "actions": actions,
            "daily_entry": get_daily_tracking_for_date(client["id"], today),
            "week_completion": get_week_completion(client["id"]),
            "weekly_measurement": get_current_week_measurement(client["id"]),
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
    completed_action_ids: list[int] = Form(default=[]),
    steps: str = Form(""),
    weight_kg: str = Form(""),
):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client access link not found")

    today = date.today()
    if is_portal_day_submitted(client["id"], today):
        return RedirectResponse(
            f"/client/{access_token}?saved=1",
            status_code=303,
        )

    actions = get_active_actions(client["id"])
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
        tracked_on=today,
        active_action_ids=active_ids,
        completed_action_ids=valid_completed,
    )

    save_client_daily_entry(
        client_id=client["id"],
        tracked_on=today,
        steps=parse_int(steps),
        weight_kg=parse_float(weight_kg),
    )

    return RedirectResponse(
        f"/client/{access_token}?saved=1",
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

    def parse_float(value: str):
        return float(value) if value.strip() else None

    try:
        saved = save_weekly_measurements(
            client_id=client["id"],
            measured_on=date.fromisoformat(measured_on),
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

