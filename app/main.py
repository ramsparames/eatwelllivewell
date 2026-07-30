from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.database import (
    create_database,
    save_snapshot,
    get_all_leads,
    get_lead_by_id,
)

from app.scoring import calculate_score
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi import HTTPException
from fastapi.templating import Jinja2Templates

from fastapi.staticfiles import StaticFiles
from pathlib import Path
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)
@app.get("/foundations")
def foundations():
    return FileResponse(BASE_DIR / "foundations.html")


@app.get("/success-stories")
def success_stories():
    return FileResponse(BASE_DIR / "success-stories.html")


@app.get("/journal")
def journal():
    return FileResponse(BASE_DIR / "journal.html")


@app.get("/assessment")
def assessment():
    return FileResponse(BASE_DIR / "assessment.html")


@app.get("/results")
def results():
    return FileResponse(BASE_DIR / "results.html")


@app.get("/join")
def join():
    return FileResponse(BASE_DIR / "join.html")


@app.get("/thank-you")
def thank_you():
    return FileResponse(BASE_DIR / "thank-you.html")


@app.get("/welcome")
def welcome():
    return FileResponse(BASE_DIR / "welcome.html")
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
def startup():
    create_database()
    
class SnapshotSubmission(BaseModel):
    name: str
    phone: str
    answers: dict[str, str]

from fastapi.responses import FileResponse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@app.get("/")
def root():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/snapshot")
def receive_snapshot(submission: SnapshotSubmission):
    result = calculate_score(submission.answers)

    submission_id = save_snapshot(
        name=submission.name,
        phone=submission.phone,
        answers=submission.answers,
        result=result,
    )

    print("Snapshot saved with ID:", submission_id)
    print("Calculated score:", result)

    return {
        "status": "saved",
        "submission_id": submission_id,
        "name": submission.name,
        "result": result,
    }
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):

    leads = get_all_leads()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "leads": leads
        }
    )
@app.get("/dashboard/leads/{lead_id}", response_class=HTMLResponse)
def lead_detail(request: Request, lead_id: int):

    lead = get_lead_by_id(lead_id)

    if lead is None:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    return templates.TemplateResponse(
        "lead.html",
        {
            "request": request,
            "lead": lead
        }
    )
