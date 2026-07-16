from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.chats import router as chats_router
from app.routers.health import router as health_router


app = FastAPI(title="Patient Intake Assistant API")
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chats_router)
