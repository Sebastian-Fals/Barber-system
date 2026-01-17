from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.logging_config import logger
from app.services.calendar_service import calendar_service

router = APIRouter()


@router.post("/google-webhook")
async def google_calendar_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_channel_id: str = Header(None),
    x_goog_resource_state: str = Header(None),
    x_goog_resource_id: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Receives Push Notifications from Google Calendar.
    """
    # 1. Verification (Basic)
    # Ideally verify X-Goog-Channel-Token if we set it.

    logger.info(f"Google Webhook: Channel={x_goog_channel_id} State={x_goog_resource_state} ResID={x_goog_resource_id}")

    if x_goog_resource_state == "sync":
        logger.info("Channel Sync Successful")
        return {"status": "ok"}

    if x_goog_resource_state == "exists":
        # Something changed in the calendar.

        # EXTRACT Calendar ID from Channel ID
        # Convention: "watch_{calendar_email_sanitized}_{timestamp}"
        # This is tricky if email has special chars.
        # Better strategy: We can't easily extract perfectly if we don't store mapping.
        # Fallback for MVP: Iterate all businesses/barbers and find who has this calendar_id?
        # No, we don't have calendar_id in headers, only Resource ID which we don't store upfront correctly.

        # PROPOSAL: Put the actual ID in the token or just encoded in channel ID with a specific separator.
        # Let's try to parse channel_id if it follows "watch__<cal_id>__<timestamp>"

        calendar_id = None
        if x_goog_channel_id and "__" in x_goog_channel_id:
            try:
                parts = x_goog_channel_id.split("__")
                # parts[0] = prefix, parts[1] = cal_id_b64, parts[2] = timestamp
                if len(parts) >= 2:
                    import base64

                    # Add padding back if needed (though we stripped it, b64decode might need it if strict,
                    # but usually urlsafe_b64decode handles it or we add padding)
                    b64_str = parts[1]
                    padding = 4 - (len(b64_str) % 4)
                    if padding != 4:
                        b64_str += "=" * padding

                    calendar_id = base64.urlsafe_b64decode(b64_str).decode()
            except Exception as e:
                logger.warning(f"Error decoding calendar ID from channel: {e}")

        if calendar_id:
            logger.info(f"Syncing Calendar events for: {calendar_id} (Background)")
            # Pass None for db so it creates its own session in the background thread
            background_tasks.add_task(calendar_service.sync_events, calendar_id, None)
        else:
            logger.warning(f"Could not parse Calendar ID from Channel: {x_goog_channel_id}")

    return {"status": "ok"}
