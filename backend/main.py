from fastapi import FastAPI
from app.api.report import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AEO Report Generator"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def home():
    return {
        "status": "running",
        "message": "AEO Report Generator API"
    }