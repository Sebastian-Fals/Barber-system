from fastapi import APIRouter, Request, HTTPException, Depends, Body, BackgroundTasks
from app.core.config import settings
from app.core.database import SessionLocal 
from sqlalchemy.orm import Session
from app.core.logging_config import logger
import asyncio
from app.services.conversation_service import ConversationService
from collections import OrderedDict

router = APIRouter()

# Simple in-memory deduplication cache
# Key: Message ID, Value: Timestamp (or just presence)
# Limit size to prevent memory leaks
class RequestCache:
    def __init__(self, capacity=1000):
        self.cache = OrderedDict()
        self.capacity = capacity

    def is_processed(self, msg_id):
        if msg_id in self.cache:
            return True
        self.cache[msg_id] = True
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False) # Remove oldest
        return False

dedup_cache = RequestCache()

def process_background_message(phone_number_id: str, from_number: str, msg_body: str, msg_type: str, interactive_id: str):
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
def receive_webhook(background_tasks: BackgroundTasks, body: dict = Body(...)):
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
                        
                        # Deduplication Check
                        if dedup_cache.is_processed(msg_id):
                            logger.info(f"Duplicate message ignored: {msg_id}")
                            continue

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
                            process_background_message, 
                            phone_number_id, 
                            from_number, 
                            msg_body, 
                            msg_type, 
                            interactive_id
                        )
    
    return {"status": "received"}
