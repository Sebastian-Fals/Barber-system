from abc import ABC, abstractmethod
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.models import Customer

# Future: from app.services.whatsapp_service import whatsapp_service (Handlers likely need to send messages)


class BaseHandler(ABC):
    """
    Abstract base class for all conversation handlers.
    Each handler is responsible for a specific subset of the conversation flow.
    """

    def __init__(self, db: Session, phone_number_id: str, business_id: int):
        self.db = db
        self.phone_number_id = phone_number_id
        self.business_id = business_id

    @abstractmethod
    def handle_message(self, customer: Customer, message_body: str) -> None:
        """
        Process a standard text message from the user.
        """
        pass

    @abstractmethod
    def handle_interactive(self, customer: Customer, interactive_id: str, payload: Dict[str, Any]) -> None:
        """
        Process an interactive response (button click, list selection).
        """
        pass
