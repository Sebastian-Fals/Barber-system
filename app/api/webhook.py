from fastapi import APIRouter, Request, HTTPException, Depends, Body
from app.core.config import settings
from app.core.database import get_db
from sqlalchemy.orm import Session
import logging
from app.services.conversation_service import ConversationService

router = APIRouter()
logger = logging.getLogger(__name__)

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
def receive_webhook(db: Session = Depends(get_db), body: dict = Body(...)):
    """
    Receives incoming messages from WhatsApp.
    """
    # body is already a dict, no need to await
    
    # Check if it's a message
    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                
                phone_number_id = value.get("metadata", {}).get("phone_number_id")
                
                # Check for Messages
                if params_messages := value.get("messages", []):
                    for message in params_messages:
                        from_number = message.get("from")
                        msg_type = message.get("type")
                        
                        msg_body = ""
                        interactive_id = None

                        if msg_type == "text":
                            msg_body = message.get("text", {}).get("body")
                        elif msg_type == "interactive":
                            # Button reply
                            interactive_id = message.get("interactive", {}).get("button_reply", {}).get("id")
                            # Or list reply if implemented
                        
                        logger.info(f"Received from {from_number} for Business ID {phone_number_id}")

                        # Create Service and Handle
                        service = ConversationService(db, phone_number_id)
                        service.handle_incoming_message(from_number, msg_body, msg_type, interactive_id)
    
    return {"status": "received"}
