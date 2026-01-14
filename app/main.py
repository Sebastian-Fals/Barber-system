from fastapi import FastAPI
from app.core.config import settings
from app.api import webhook

from contextlib import asynccontextmanager
from app.services.scheduler_service import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown (Scheduler shuts down with process usually, or can be explicit)

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.include_router(webhook.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "WhatsApp Appointment System is Running"}
