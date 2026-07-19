import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers.auth import router as auth_router
from app.routers.chats import router as chats_router
from app.routers.doctors import router as doctors_router
from app.routers.health import router as health_router
from app.routers.reports import router as reports_router


load_dotenv()

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="Patient Intake Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(reports_router)
app.include_router(doctors_router)
