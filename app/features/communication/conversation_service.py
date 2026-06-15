from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.features.business.repository import BusinessRepository
from app.features.communication.whatsapp_service import whatsapp_service
from app.features.customers.repository import CustomerRepository
from app.models.models import Customer, CustomerData
from app.services.handlers.booking_handler import BookingHandler
from app.services.handlers.query_handler import QueryHandler
from app.services.handlers.welcome_handler import WelcomeHandler


class ConversationService:
    """
    Refactored ConversationService acting as a Router/Dispatcher.
    It delegates logic to specialized Handlers based on conversation state and input type.
    """

    def __init__(self, db: Session, phone_number_id: str, business_id: int):
        self.db = db
        self.phone_number_id = phone_number_id
        self.business_id = business_id

        # Repositories
        self.customer_repo = CustomerRepository(db)
        self.business_repo = BusinessRepository(db)

        # Handlers — propagate business_id so they don't re-resolve it
        self.welcome_handler = WelcomeHandler(db, phone_number_id, business_id)
        self.booking_handler = BookingHandler(db, phone_number_id, business_id)
        self.query_handler = QueryHandler(db, phone_number_id, business_id)

    def handle_incoming_message(
        self, from_number: str, message_body: str, message_type: str = "text", interactive_id: str = None
    ):
        """
        Main entry point. Routes the message to the appropriate handler.
        """
        # 1. Get or Create Customer (scoped by business_id)
        customer = self.customer_repo.get_by_phone(from_number, self.business_id)
        if not customer:
            # Create with default name "Usuario"
            customer = self.customer_repo.create(
                {"phone": from_number, "name": "Usuario", "business_id": self.business_id}
            )
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

        # 0. Enforce Name Collection for Existing Users with Default Name
        # If we have a "legacy" user or one who acted weirdly, make sure we get the name.
        if (not customer.name or customer.name == "Usuario") and state != CustomerData.WAITING_NAME:
            # If they are erroneously in another state, reset to WAITING_NAME
            self.customer_repo.update_state(customer, CustomerData.WAITING_NAME)
            from app.core.i18n import message_loader

            whatsapp_service.send_message(self.phone_number_id, customer.phone, message_loader.get("welcome_ask_name"))
            return

        # 1. Global Commands (ALWAYS Check First)
        # These keywords should trigger a reset regardless of AI status.
        if text in ["hola", "hi", "menu", "inicio", "start", "cancelar"]:
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

        # 2. State-based Routing (Prioritized States)
        # We must handle WAITING_NAME *before* AI because it's a specific data collection step.
        if state == CustomerData.WAITING_NAME:
            # Update Name
            new_name = message_body.strip()

            # Validation: Prevent "Hola", "Menu", etc. being saved as name
            invalid_names = [
                "hola",
                "hi",
                "bot",
                "usuario",
                "si",
                "no",
                "cancelar",
                "menu",
                "dia",
                "tarde",
                "noche",
                "start",
                "inicio",
            ]
            if len(new_name) < 3 or new_name.lower() in invalid_names:
                whatsapp_service.send_message(
                    self.phone_number_id,
                    customer.phone,
                    "Hmm, ese no parece un nombre o es muy corto. 🤔\n¿Podrías decirme tu nombre real?",
                )
                return

            new_name = new_name.title()
            self.customer_repo.update(customer, {"name": new_name})
            self.customer_repo.update_state(customer, CustomerData.IDLE)

            # Check AI
            business = self.business_repo.get_by_id(self.business_id)
            enable_ai = business.ai_enabled if business else False

            if enable_ai:
                # Delegate to AI for the response (Natural Flow)
                # We pass the message so AI can analyze intent (PROVIDE_NAME) and generate a greeting.
                self.query_handler.handle_message(customer, message_body)
            else:
                # Legacy: Proceed to Welcome Menu
                self.welcome_handler.handle_message(customer, "menu")

            return

        # 3. Check AI Status (Global Context)
        business = self.business_repo.get_by_id(self.business_id)
        enable_ai = business.ai_enabled if business else False

        if enable_ai:
            # AI handles almost everything else
            self.query_handler.handle_message(customer, message_body)
            return

        # --- LEGACY / NON-AI FLOW BELOW ---

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
            interactive_id.startswith(p)
            for p in ["service_", "barber_", "date_", "time_", "page_", "confirm_", "cancel_appt_", "cancel_flow"]
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
