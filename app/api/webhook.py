import asyncio

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.database import SessionLocal, get_db
from app.core.logging_config import logger
from app.features.business.repository import BusinessRepository
from app.features.communication.conversation_service import ConversationService
from app.models.models import ProcessedMessage

router = APIRouter()


async def process_background_message(
    instance_name: str,
    instance_apikey: str,
    from_number: str,
    msg_body: str,
    msg_type: str,
    interactive_id: str,
    business_id: int,
):
    try:

        def _process_direct():
            db = SessionLocal()
            try:
                service = ConversationService(db, instance_name, instance_apikey, business_id)
                service.handle_incoming_message(from_number, msg_body, msg_type, interactive_id)
            finally:
                db.close()

        await run_in_threadpool(_process_direct)

    except asyncio.CancelledError:
        logger.warning(f"Task cancelled for {from_number} (Server Shutdown/Reload)")
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)


@router.post("/webhook")
def receive_webhook(background_tasks: BackgroundTasks, body: dict = Body(...), db: Session = Depends(get_db)):
    """
    Receives incoming messages from Evolution API. Returns 200 OK immediately.

    Multi-tenant: resolves instance → business via get_by_instance_name().
    Unknown instance → silent ignore (200, no data created).
    """
    event = body.get("event")

    # Non-messages.upsert events → ignored
    if event != "messages.upsert":
        logger.debug(f"Ignoring non-message event: {event}")
        return {"status": "ignored"}

    instance_name = body.get("instance")
    if not instance_name:
        logger.warning("Webhook received without instance name")
        return {"status": "ignored"}

    # Resolve business by instance_name
    biz_repo = BusinessRepository(db)
    business = biz_repo.get_by_instance_name(instance_name)
    if not business:
        logger.warning(f"Unknown instance: {instance_name} — message ignored")
        return {"status": "received"}

    business_id = business.id
    instance_apikey = business.instance_apikey

    data = body.get("data", {})
    msg_id = data.get("key", {}).get("id")
    remote_jid = data.get("key", {}).get("remoteJid", "")
    from_number = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
    message_type = data.get("messageType")
    message = data.get("message", {})

    if not msg_id:
        logger.warning("Message received without id")
        return {"status": "received"}

    # Deduplication check
    try:
        exists = (
            db.query(ProcessedMessage)
            .filter(
                ProcessedMessage.message_id == msg_id,
                ProcessedMessage.business_id == business_id,
            )
            .first()
        )
        if exists:
            logger.info(f"Duplicate message ignored: {msg_id} (business {business_id})")
            return {"status": "received"}

        new_msg = ProcessedMessage(message_id=msg_id, business_id=business_id)
        db.add(new_msg)
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(f"Duplicate message detected (race condition): {msg_id}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error checking deduplication: {e}")
        pass

    # Parse message body / interactive_id based on messageType
    msg_body = ""
    interactive_id = None

    if message_type == "conversation":
        msg_body = message.get("conversation", "")
    elif message_type == "listResponse":
        list_response = message.get("listResponseMessage", {})
        single_select = list_response.get("singleSelectReply", {})
        interactive_id = single_select.get("selectedRowId")

    logger.info(f"Queuing message {msg_id} from {from_number} (business {business_id})")

    background_tasks.add_task(
        process_background_message,
        instance_name,
        instance_apikey,
        from_number,
        msg_body,
        message_type or "unknown",
        interactive_id,
        business_id,
    )

    return {"status": "received"}
