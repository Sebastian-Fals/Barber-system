import asyncio
from collections import OrderedDict

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.logging_config import logger
from app.services.conversation_service import ConversationService

router = APIRouter()

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import ProcessedMessage

# Removing in-memory cache


def process_background_message(
    phone_number_id: str, from_number: str, msg_body: str, msg_type: str, interactive_id: str
):
    # Create a NEW session for the background task
    db = SessionLocal()
    try:
        service = ConversationService(db, phone_number_id)
        service.handle_incoming_message(from_number, msg_body, msg_type, interactive_id)
    except asyncio.CancelledError:
        logger.warning(f"Task cancelled for {from_number} (Server Shutdown/Reload)")
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
    finally:
        db.close()


@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Verifies the webhook with WhatsApp.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    return {"status": "ok"}


@router.post("/webhook")
def receive_webhook(background_tasks: BackgroundTasks, body: dict = Body(...), db: Session = Depends(get_db)):
    """
    Receives incoming messages from WhatsApp. Returns 200 OK immediately.
    """
    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_number_id = value.get("metadata", {}).get("phone_number_id")

                if params_messages := value.get("messages", []):
                    for message in params_messages:
                        msg_id = message.get("id")

                        # Deduplication Check (DB Based)
                        try:
                            exists = db.query(ProcessedMessage).filter(ProcessedMessage.message_id == msg_id).first()
                            if exists:
                                logger.info(f"Duplicate message ignored: {msg_id}")
                                continue

                            # Log message as processed
                            new_msg = ProcessedMessage(message_id=msg_id)
                            db.add(new_msg)
                            db.commit()

                        except IntegrityError:
                            db.rollback()
                            logger.info(f"Duplicate message detected (race condition): {msg_id}")
                            continue
                        except Exception as e:
                            logger.error(f"Error checking deduplication: {e}")
                            # Continue processing even if DB check fails? Safer to fail open or closed?
                            # Failing open (processing) is better than dropping.
                            pass

                        from_number = message.get("from")
                        msg_type = message.get("type")
                        msg_body = ""
                        interactive_id = None

                        if msg_type == "text":
                            msg_body = message.get("text", {}).get("body")
                        elif msg_type == "interactive":
                            interactive_id = message.get("interactive", {}).get("button_reply", {}).get("id")

                        logger.info(f"Queuing message {msg_id} from {from_number}")

                        # Dispatch to Background
                        background_tasks.add_task(
                            process_background_message, phone_number_id, from_number, msg_body, msg_type, interactive_id
                        )

    return {"status": "received"}
