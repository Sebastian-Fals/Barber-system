from abc import ABC, abstractmethod
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.features.communication.whatsapp_service import whatsapp_service
from app.models.models import Customer

# Future: from app.services.whatsapp_service import whatsapp_service (Handlers likely need to send messages)


class BaseHandler(ABC):
    """
    Abstract base class for all conversation handlers.
    Each handler is responsible for a specific subset of the conversation flow.
    """

    def __init__(self, db: Session, instance_name: str, instance_apikey: str, business_id: int):
        self.db = db
        self.instance_name = instance_name
        self.instance_apikey = instance_apikey
        self.business_id = business_id

    def _send_list_from_buttons(self, to: str, body_text: str, buttons: list, *, footer_text: str = ""):
        """Convert legacy button dicts to Evolution send_list rows and send."""
        rows = [{"title": btn["title"], "description": "", "rowId": btn["id"]} for btn in buttons]
        whatsapp_service.send_list(
            self.instance_name,
            self.instance_apikey,
            to,
            title=body_text,
            description="",
            button_text="Seleccionar",
            footer_text=footer_text,
            rows=rows,
        )

    def _send_text(self, to: str, body: str):
        """Send a simple text message via Evolution API."""
        whatsapp_service.send_message(
            self.instance_name,
            self.instance_apikey,
            to,
            body,
        )

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
