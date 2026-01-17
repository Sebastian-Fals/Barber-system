import datetime
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api import calendar_webhook, webhook
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging_config import logger
from app.models.models import Barber, Business
from app.services.calendar_service import calendar_service
from app.services.scheduler_service import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()

    # --- Subscribe to Google Calendar Webhooks ---
    if settings.WEBHOOK_PUBLIC_URL:
        logger.info(f"Webhook URL configured: {settings.WEBHOOK_PUBLIC_URL}. Subscribing calendars...")
        db = SessionLocal()
        try:
            calendars_to_watch = set()

            # 1. Businesses
            for b in db.query(Business).filter(Business.calendar_id.isnot(None)):
                calendars_to_watch.add(b.calendar_id)

            # 2. Barbers
            for b in db.query(Barber).filter(Barber.calendar_id.isnot(None)):
                calendars_to_watch.add(b.calendar_id)

            # Watch
            for cal_id in calendars_to_watch:
                # Sanitize cal_id for channel ID (Must be [A-Za-z0-9\-_+/=]+)
                # Replace @ and . with _
                safe_cal_id = cal_id.replace("@", "_").replace(".", "_")

                # Generate strict channel ID: prefix__safeCalId__timestamp
                chan_id = f"watch__{safe_cal_id}__{uuid.uuid4().hex}"

                # Note: safe_cal_id is not the real cal_id, so the webhook logic needs to handle this or we fallback.
                # However, our webhook logic tries to extract. If we change this here, we must update the webhook extraction
                # OR just accept that extraction might fail and we sync based on lookup.
                # Given the regex constraints, we can't easily embed the full email if it has dots/ats without encoding.
                # Let's use base64 encoding for the cal_id part if we really want to preserve it,
                # OR just use a UUID map.
                #
                # DECISION: For MVP, I will sanitize.
                # And in the webhook, I will assume the "safe" ID is NOT enough to reconstruct the email directly without ambiguity,
                # BUT since we just need to identifying WHICH calendar to sync...
                # Actually, the simplest fix is to just Sync ALL business calendars when a webhook hits if we can't identify.
                # OR, I will try to reconstruct: replace _ back to... no that's ambiguous.
                #
                # Let's use Base64 URL Safe encoding for the calendar ID.
                import base64

                cal_id_b64 = base64.urlsafe_b64encode(cal_id.encode()).decode().rstrip("=")
                chan_id = f"watch__{cal_id_b64}__{uuid.uuid4().hex}"

                calendar_service.watch_calendar(cal_id, f"{settings.WEBHOOK_PUBLIC_URL}/api/v1/google-webhook", chan_id)

        except Exception as e:
            logger.error(f"Error subscribing to calendars: {e}")
        finally:
            db.close()
    else:
        logger.warning("⚠️ WEBHOOK_PUBLIC_URL not set. Skipping Google Calendar Watch.")
    # ---------------------------------------------

    yield
    # Shutdown (Scheduler shuts down with process usually, or can be explicit)


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.include_router(webhook.router, prefix="/api/v1")
app.include_router(calendar_webhook.router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "WhatsApp Appointment System is Running"}
