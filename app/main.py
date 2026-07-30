from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.database import create_database, save_snapshot
from app.scoring import calculate_score
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

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
    email: str
    answers: dict[str, str]

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "NourisHer backend is running"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/snapshot")
def receive_snapshot(submission: SnapshotSubmission):
    result = calculate_score(submission.answers)

    submission_id = save_snapshot(
        name=submission.name,
        email=submission.email,
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
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request
        }
    )
