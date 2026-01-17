from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.models.models import Customer, CustomerData
from app.repositories.business_repository import BusinessRepository
from app.repositories.customer_repository import CustomerRepository
from app.services.handlers.booking_handler import BookingHandler
from app.services.handlers.query_handler import QueryHandler
from app.services.handlers.welcome_handler import WelcomeHandler
from app.services.whatsapp_service import whatsapp_service


class ConversationService:
    """
    Refactored ConversationService acting as a Router/Dispatcher.
    It delegates logic to specialized Handlers based on conversation state and input type.
    """

    def __init__(self, db: Session, phone_number_id: str):
        self.db = db
        self.phone_number_id = phone_number_id

        # Repositories
        self.customer_repo = CustomerRepository(db)
        self.business_repo = BusinessRepository(db)

        # Handlers
        self.welcome_handler = WelcomeHandler(db, phone_number_id)
        self.booking_handler = BookingHandler(db, phone_number_id)
        self.query_handler = QueryHandler(db, phone_number_id)

    def handle_incoming_message(
        self, from_number: str, message_body: str, message_type: str = "text", interactive_id: str = None
    ):
        """
        Main entry point. Routes the message to the appropriate handler.
        """
        # 1. Get or Create Customer
        customer = self.customer_repo.get_by_phone(from_number)
        if not customer:
            # Create with default name "Usuario"
            customer = self.customer_repo.create({"phone": from_number, "name": "Usuario"})
            # Initiate Name Collection Flow
            self.customer_repo.update_state(customer, CustomerData.WAITING_NAME)
            from app.core.i18n import message_loader

            whatsapp_service.send_message(self.phone_number_id, from_number, message_loader.get("welcome_ask_name"))
            return

        try:
            if message_type == "text":
                self._route_text_message(customer, message_body)
            elif message_type == "interactive":
                self._route_interactive_message(customer, interactive_id)
            else:
                logger.warning(f"Unsupported message type: {message_type}")
                self.welcome_handler.handle_message(customer, "")  # Fallback

        except Exception as e:
            logger.error(f"Error handling message for {from_number}: {e}", exc_info=True)
            whatsapp_service.send_message(self.phone_number_id, from_number, "Lo siento, tuve un error interno. 😔")

    def _route_text_message(self, customer: Customer, message_body: str):
        text = message_body.lower().strip()
        state = customer.conversation_state

        # 1. Global Commands (ALWAYS Check First)
        # These keywords should trigger a reset regardless of AI status.
        if text in ["hola", "hi", "menu", "inicio", "start", "cancelar", "reset"]:
            # 'cancelar' can be handled by QueryHandler for "smart cancel" or strict reset.
            # If strict reset is preferred:
            self.customer_repo.update_state(customer, CustomerData.IDLE)
            self.customer_repo.update_data(customer, "{}")  # Clear data!

            # If it's a cancellation request, strictly handle it or let AI acknowledge?
            # If we return, AI doesn't run. The user WANTS AI to run.

            # NOTE: If we want AI to handle the *response* (e.g. "Hola! soy Ana"),
            # we must NOT return here. We just do the SIDE EFFECT (Reset).

            # Exception: "Cancelar" might need immediate feedback if AI is disabled?
            # But if AI is enabled, let AI handle "Cancelar" text generation.

            # So, we REMOVE the return for AI flow.
            # But we must ensure we don't double-reply if AI is disabled.
            pass  # Fall through to AI check

        # 2. Check AI Status (Global Context)
        business = self.business_repo.get_by_phone_number_id(self.phone_number_id)
        enable_ai = business.ai_enabled if business else False

        if enable_ai:
            # AI handles almost everything else
            self.query_handler.handle_message(customer, message_body)
            return

        # --- LEGACY / NON-AI FLOW BELOW ---

        # State-based Routing
        if state == CustomerData.WAITING_NAME:
            # Update Name
            new_name = message_body.strip().title()
            self.customer_repo.update(customer, {"name": new_name})
            self.customer_repo.update_state(customer, CustomerData.IDLE)

            # Proceed to Welcome Menu
            self.welcome_handler.handle_message(customer, "menu")
            return

        if state == CustomerData.IDLE:
            # AI Disabled -> Simple Menu Loop
            self.welcome_handler.handle_message(customer, message_body)

        elif state in [
            CustomerData.SELECT_SERVICE,
            CustomerData.SELECT_BARBER,
            CustomerData.SELECT_DATE,
            CustomerData.SELECT_SLOT,
            CustomerData.CONFIRM_BOOKING,
        ]:
            # Active Booking Flow -> BookingHandler
            handled = self.booking_handler.handle_message(customer, message_body)
            if not handled:
                # Fallback
                # If AI is enabled, try AI. Else, reiterate instruction.
                business = self.business_repo.get_by_phone_number_id(self.phone_number_id)
                enable_ai = business.ai_enabled if business else False

                if enable_ai:
                    logger.info(f"BookingHandler did not handle text in state {state}. Delegating to QueryHandler.")
                    self.query_handler.handle_message(customer, message_body)
                else:
                    whatsapp_service.send_message(
                        self.phone_number_id, customer.phone, "Por favor, usa los botones del menú. 🙏"
                    )

        else:
            # Fallback
            self.welcome_handler.handle_message(customer, message_body)

    def _route_interactive_message(self, customer: Customer, interactive_id: str):
        # Routing based on ID prefix or State

        # Booking Flow IDs
        if any(
            interactive_id.startswith(p) for p in ["barber_", "date_", "time_", "page_", "confirm_", "cancel_appt_"]
        ):
            self.booking_handler.handle_interactive(customer, interactive_id, {})
            return

        # Welcome/Menu IDs
        if interactive_id in ["menu_book", "menu_my_appts", "menu_info"]:
            self.welcome_handler.handle_interactive(customer, interactive_id, {})
            return

        # Default Fallback: Check state
        state = customer.conversation_state
        if state != CustomerData.IDLE:
            self.booking_handler.handle_interactive(customer, interactive_id, {})
        else:
            self.welcome_handler.handle_interactive(customer, interactive_id, {})
