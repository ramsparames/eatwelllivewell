import hashlib
import hmac

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import (
    COACH_PASSWORD_HASH,
    COACH_PASSWORD_SALT,
    COACH_USERNAME,
)


router = APIRouter()

templates: Jinja2Templates | None = None


def set_templates(template_engine: Jinja2Templates) -> None:
    global templates
    templates = template_engine


def verify_coach_password(password: str) -> bool:
    if not COACH_PASSWORD_HASH or not COACH_PASSWORD_SALT:
        return False

    calculated_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(COACH_PASSWORD_SALT),
        600_000,
    ).hex()

    return hmac.compare_digest(
        calculated_hash,
        COACH_PASSWORD_HASH,
    )


def coach_is_logged_in(request: Request) -> bool:
    return request.session.get("coach_authenticated") is True


@router.get("/coach/login", response_class=HTMLResponse)
def coach_login_page(request: Request):
    if templates is None:
        raise RuntimeError("Templates are not configured")

    if coach_is_logged_in(request):
        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None,
        },
    )


@router.post("/coach/login", response_class=HTMLResponse)
def coach_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if templates is None:
        raise RuntimeError("Templates are not configured")

    if (
        COACH_USERNAME
        and hmac.compare_digest(username, COACH_USERNAME)
        and verify_coach_password(password)
    ):
        request.session["coach_authenticated"] = True

        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "The username or password is incorrect.",
        },
        status_code=401,
    )


@router.get("/coach/logout")
def coach_logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        "/coach/login",
        status_code=303,
    )
