from fastapi import FastAPI

app = FastAPI(title="NourisHer Backend")


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "NourisHer backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
