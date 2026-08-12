import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.auth import coach_is_logged_in
from app.database import (
    get_all_leads,
    get_lead_profile,
    get_lead_events,
    update_lead_crm,
    get_synamate_appointments_between,
    get_next_synamate_appointment_for_person,
    get_synamate_calendar_summary,
    get_synamate_calendar_resolution,
    resolve_synamate_calendar_id,
)
from app.services.client_service import ClientService
from app.services.client_portal_service import get_client_operations_status
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

    # Detail lists for clickable lead summary cards.
    new_lead_items = []
    application_leads = []

    for lead in all_leads:
        status = (
            lead.get("application_status")
            or lead.get("status")
            or "new"
        )

        if lead.get("snapshot_id"):
            lead_type = "assessment"
            lead_id = lead["snapshot_id"]
        else:
            lead_type = "application"
            lead_id = lead.get("application_id")

        item = {
            "name": lead.get("name") or "Lead",
            "email": lead.get("email"),
            "phone": lead.get("phone"),
            "status": status,
            "lead_type": lead_type,
            "lead_id": lead_id,
            "submitted_at": (
                lead.get("application_submitted_at")
                or lead.get("assessment_submitted_at")
            ),
        }

        if status == "new":
            new_lead_items.append(item)

        if lead.get("has_application"):
            application_leads.append(item)

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
        "coach/leads.html",
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
            "new_lead_items": new_lead_items,
            "application_leads": application_leads,
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
    clarity_booking_url = os.getenv("SYNAMATE_CLARITY_CALL_URL", "").strip()
    clarity_calendar_id = resolve_synamate_calendar_id(
        role="clarity",
        expected_name=os.getenv(
            "SYNAMATE_CLARITY_CALENDAR_NAME",
            "Clarity Call with Sushma",
        ).strip(),
        explicit_calendar_id=os.getenv(
            "SYNAMATE_CLARITY_CALENDAR_ID",
            "",
        ).strip(),
    )

    next_clarity_call = (
        get_next_synamate_appointment_for_person(
            email=lead.get("email"),
            phone=lead.get("phone") or lead.get("application_phone"),
            calendar_id=clarity_calendar_id,
        )
        if clarity_calendar_id
        else None
    )
    if next_clarity_call and next_clarity_call.get("start_time"):
        next_clarity_call = dict(next_clarity_call)
        next_clarity_call["local_start_time"] = next_clarity_call["start_time"].astimezone(
            ZoneInfo("Asia/Kolkata")
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
        "coach/lead.html",
        {
            "request": request,
            "lead": lead,
            "lead_type": lead_type,
            "lead_id": lead_id,
            "saved": request.query_params.get("saved") == "1",
            "events": events,
            "timeline_groups": timeline_groups,
            "clarity_booking_url": clarity_booking_url,
            "next_clarity_call": next_clarity_call,
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
        return RedirectResponse("/coach/login", status_code=303)

    clients = ClientService.dashboard_clients()
    active_clients = [
        dict(client)
        for client in clients
        if client.get("status") == "active"
    ]

    clarity_calendar_id = resolve_synamate_calendar_id(
        role="clarity",
        expected_name=os.getenv(
            "SYNAMATE_CLARITY_CALENDAR_NAME",
            "Clarity Call with Sushma",
        ).strip(),
        explicit_calendar_id=os.getenv(
            "SYNAMATE_CLARITY_CALENDAR_ID",
            "",
        ).strip(),
    )

    coaching_calendar_id = resolve_synamate_calendar_id(
        role="coaching",
        expected_name=os.getenv(
            "SYNAMATE_COACHING_CALENDAR_NAME",
            "Coaching Call with Sushma",
        ).strip(),
        explicit_calendar_id=os.getenv(
            "SYNAMATE_COACHING_CALENDAR_ID",
            "",
        ).strip(),
    )

    local_tz = ZoneInfo("Asia/Kolkata")
    local_now = datetime.now(local_tz)
    local_start = datetime.combine(
        local_now.date(),
        datetime.min.time(),
        tzinfo=local_tz,
    )
    local_end = local_start + timedelta(days=1)

    calls_today = []

    def normalized_phone(value):
        return "".join(ch for ch in (value or "") if ch.isdigit())

    coaching_calls = (
        get_synamate_appointments_between(
            local_start.astimezone(timezone.utc),
            local_end.astimezone(timezone.utc),
            calendar_id=coaching_calendar_id,
        )
        if coaching_calendar_id
        else []
    )

    for call in coaching_calls:
        item = dict(call)
        local_start_time = item["start_time"].astimezone(local_tz)
        matched_client = None
        call_email = (item.get("email") or "").strip().lower()
        call_phone = normalized_phone(item.get("phone"))

        for client in active_clients:
            email_match = (
                call_email
                and (client.get("email") or "").strip().lower() == call_email
            )
            phone_match = (
                call_phone
                and normalized_phone(client.get("phone")) == call_phone
            )
            if email_match or phone_match:
                matched_client = client
                break

        item["name"] = (
            item.get("name")
            or (matched_client or {}).get("name")
            or "Coaching client"
        )
        item["next_call_time"] = local_start_time.strftime("%I:%M %p").lstrip("0")
        item["call_type"] = "Coaching Call"
        item["sort_time"] = local_start_time
        item["href"] = (
            f"/dashboard/clients/{matched_client['id']}?tab=weekly"
            if matched_client
            else "/dashboard/clients"
        )
        calls_today.append(item)

    clarity_calls = (
        get_synamate_appointments_between(
            local_start.astimezone(timezone.utc),
            local_end.astimezone(timezone.utc),
            calendar_id=clarity_calendar_id,
        )
        if clarity_calendar_id
        else []
    )

    for call in clarity_calls:
        item = dict(call)
        local_start_time = item["start_time"].astimezone(local_tz)
        item["name"] = item.get("name") or "Clarity Call"
        item["next_call_time"] = local_start_time.strftime("%I:%M %p").lstrip("0")
        item["call_type"] = "Clarity Call · Lead"
        item["sort_time"] = local_start_time
        item["href"] = "/dashboard/leads"
        calls_today.append(item)

    calls_today.sort(key=lambda item: item.get("sort_time") or local_now)

    week_start = local_start - timedelta(days=local_start.weekday())
    week_end = week_start + timedelta(days=7)

    coaching_week_calls = (
        get_synamate_appointments_between(
            week_start.astimezone(timezone.utc),
            week_end.astimezone(timezone.utc),
            calendar_id=coaching_calendar_id,
        )
        if coaching_calendar_id
        else []
    )
    clarity_week_calls = (
        get_synamate_appointments_between(
            week_start.astimezone(timezone.utc),
            week_end.astimezone(timezone.utc),
            calendar_id=clarity_calendar_id,
        )
        if clarity_calendar_id
        else []
    )

    # Build display-ready weekly schedule rows, not just raw appointment rows.
    calls_this_week = []

    for call in coaching_week_calls:
        item = dict(call)
        local_start_time = item["start_time"].astimezone(local_tz)
        matched_client = None
        call_email = (item.get("email") or "").strip().lower()
        call_phone = normalized_phone(item.get("phone"))

        for client in active_clients:
            email_match = (
                call_email
                and (client.get("email") or "").strip().lower() == call_email
            )
            phone_match = (
                call_phone
                and normalized_phone(client.get("phone")) == call_phone
            )
            if email_match or phone_match:
                matched_client = client
                break

        item["name"] = (
            item.get("name")
            or (matched_client or {}).get("name")
            or "Coaching client"
        )
        item["call_type"] = "Coaching Call"
        item["local_start_time"] = local_start_time
        item["date_label"] = local_start_time.strftime("%a, %d %b")
        item["time_label"] = local_start_time.strftime("%I:%M %p").lstrip("0")
        item["href"] = (
            f"/dashboard/clients/{matched_client['id']}?tab=weekly"
            if matched_client
            else "/dashboard/clients"
        )
        calls_this_week.append(item)

    for call in clarity_week_calls:
        item = dict(call)
        local_start_time = item["start_time"].astimezone(local_tz)
        item["name"] = item.get("name") or "Clarity Call"
        item["call_type"] = "Clarity Call · Lead"
        item["local_start_time"] = local_start_time
        item["date_label"] = local_start_time.strftime("%a, %d %b")
        item["time_label"] = local_start_time.strftime("%I:%M %p").lstrip("0")
        item["href"] = "/dashboard/leads"
        calls_this_week.append(item)

    calls_this_week.sort(
        key=lambda item: item.get("local_start_time") or local_now
    )

    # Production operations status: one rule set for dashboard + client list.
    needs_attention_clients = []
    clients_without_next_call = []
    missed_update_clients = []
    measurement_due_clients = []
    review_overdue_clients = []
    no_next_call_clients = []
    operations_counts = {
        "missed_daily": 0,
        "measurement_due": 0,
        "weekly_review_overdue": 0,
        "no_next_call": 0,
    }

    for client in active_clients:
        ops = get_client_operations_status(client, local_now.date())
        client["operations"] = ops
        client["current_week"] = ops["week_number"]
        client["has_synced_next_call"] = not ops["no_next_call"]

        if ops["no_next_call"]:
            clients_without_next_call.append(client)
            no_next_call_clients.append(client)
            operations_counts["no_next_call"] += 1
        if ops["missed_daily_count"] >= 2:
            missed_update_clients.append(client)
            operations_counts["missed_daily"] += 1
        if ops["measurement_due"]:
            measurement_due_clients.append(client)
            operations_counts["measurement_due"] += 1
        if ops["weekly_review_overdue"]:
            review_overdue_clients.append(client)
            operations_counts["weekly_review_overdue"] += 1
        if ops["health_key"] == "attention":
            needs_attention_clients.append(client)

    needs_attention_clients.sort(
        key=lambda client: (
            -client["operations"]["attention_count"],
            client.get("name") or "",
        )
    )

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
            "active_clients": active_clients,
            "clients_without_next_call": clients_without_next_call,
            "needs_attention_clients": needs_attention_clients,
            "operations_counts": operations_counts,
            "missed_update_clients": missed_update_clients,
            "measurement_due_clients": measurement_due_clients,
            "review_overdue_clients": review_overdue_clients,
            "no_next_call_clients": no_next_call_clients,
            "calls_today": calls_today,
            "calls_this_week": calls_this_week,
            "new_leads": new_leads,
            "today": local_now.date(),
            "synamate_calendar_configured": bool(
                clarity_calendar_id and coaching_calendar_id
            ),
        },
    )


@router.get("/dashboard/synamate-calendars", response_class=HTMLResponse)
def synamate_calendar_diagnostic(request: Request):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    rows = get_synamate_calendar_summary()
    resolution = get_synamate_calendar_resolution()
    clarity_id = resolution["clarity"]["calendar_id"]
    coaching_id = resolution["coaching"]["calendar_id"]

    body_rows = []
    for row in rows:
        role = "Unassigned"
        if row.get("calendar_id") == clarity_id:
            role = "Clarity Call"
        elif row.get("calendar_id") == coaching_id:
            role = "Coaching Call"

        body_rows.append(
            "<tr>"
            f"<td>{role}</td>"
            f"<td>{row.get('calendar_name') or '—'}</td>"
            f"<td><code>{row.get('calendar_id')}</code></td>"
            f"<td>{row.get('example_title') or '—'}</td>"
            f"<td>{row.get('appointment_count')}</td>"
            "</tr>"
        )

    html = (
        "<html><head><title>Synamate Calendars</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#29232e}"
        "table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left}"
        "code{background:#f6f1f8;padding:3px 6px;border-radius:5px}</style></head><body>"
        "<h1>Synamate calendar IDs</h1>"
        "<p>NourisHer automatically maps webhook calendars by name. Expected names: <b>Clarity Call with Sushma</b> and <b>Coaching Call with Sushma</b>.</p>"
        "<table><tr><th>Role</th><th>Calendar name</th><th>Calendar ID</th><th>Example appointment</th><th>Appointments</th></tr>"
        + "".join(body_rows)
        + "</table>"
        "<h2>Render environment variables</h2>"
        "<p><code>SYNAMATE_CLARITY_CALENDAR_ID</code></p>"
        "<p><code>SYNAMATE_COACHING_CALENDAR_ID</code></p>"
        "<p><a href='/dashboard'>← Back to dashboard</a></p>"
        "</body></html>"
    )
    return HTMLResponse(html)


