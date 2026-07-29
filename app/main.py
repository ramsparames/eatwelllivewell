from app.database import create_database, save_snapshot
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="NourisHer Backend")

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
    submission_id = save_snapshot(
        name=submission.name,
        email=submission.email,
        answers=submission.answers
    )

    print("Snapshot saved with ID:", submission_id)

    return {
        "status": "saved",
        "submission_id": submission_id,
        "name": submission.name,
        "answer_count": len(submission.answers)
    }
