from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.i18n import message_loader
from app.core.logging_config import logger
from app.features.appointments.repository import AppointmentRepository
from app.features.business.barber_repository import BarberRepository
from app.features.communication.whatsapp_service import whatsapp_service
from app.models.models import Business, Customer, CustomerData
from app.services.handlers.base_handler import BaseHandler


class WelcomeHandler(BaseHandler):
    def __init__(self, db: Session, phone_number_id: str):
        super().__init__(db, phone_number_id)
        self.appt_repo = AppointmentRepository(db)
        self.barber_repo = BarberRepository(db)
        # We need business info for i18n context
        self.business = db.query(Business).filter(Business.phone_number_id == phone_number_id).first()

    def handle_message(self, customer: Customer, message_body: str) -> None:
        """
        Default entry point for IDLE state or unhandled messages in this scope.
        Sends the main menu.
        """
        self._send_welcome_menu(customer)

    def handle_interactive(self, customer: Customer, interactive_id: str, payload: Dict[str, Any]) -> None:
        if interactive_id == "menu_book":
            # Transition to Booking Flow
            self._start_booking_flow(customer)

        elif interactive_id == "menu_my_appts":
            self._show_my_appointments(customer)

        elif interactive_id == "menu_info":
            self._show_info(customer)

        else:
            # Fallback for unknown buttons in this context
            self._send_welcome_menu(customer)

    def _send_welcome_menu(self, customer: Customer, message_body: str = None):
        if not self.business:
            logger.error(f"No business found for {self.phone_number_id}")
            return

        # Prepare text
        if message_body:
            msg = message_body
        else:
            # Different welcome for new vs returning users could be handled here logic-wise
            # For now using generic welcome_menu from i18n
            msg = message_loader.get("welcome_menu", name=customer.name or "", business_name=self.business.name)

        buttons = [
            {"id": "menu_book", "title": message_loader.get("menu_book")},
            {"id": "menu_my_appts", "title": message_loader.get("menu_my_appts")},
            {"id": "menu_info", "title": message_loader.get("menu_info")},
        ]

        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

        # Ensure state is IDLE
        if customer.conversation_state != CustomerData.IDLE:
            # We assume there is a customer_repo available in the bigger context,
            # but here we might need to update it?
            # BaseHandler doesn't have repositories by default except what we init.
            # We should inject or use a repository to update state.
            # Let's add CustomerRepository usage or just direct update since we have DB session?
            # Better: Use CustomerRepository.
            from app.features.customers.repository import CustomerRepository

            CustomerRepository(self.db).update_state(customer, CustomerData.IDLE)

    def _start_booking_flow(self, customer: Customer):
        # 1. Update State
        from app.features.customers.repository import CustomerRepository

        CustomerRepository(self.db).update_state(customer, CustomerData.SELECT_BARBER)

        # 2. Show Barbers (First step of booking)
        barbers = self.barber_repo.get_by_business(self.business.id)

        msg = message_loader.get("booking_ask_barber")
        buttons = [{"id": f"barber_{b.id}", "title": b.name} for b in barbers[:3]]

        # Pagination could be added here similar to legacy code
        # For MVP refactor, limiting to 3 is fine, or add "Next"

        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _show_my_appointments(self, customer: Customer):
        appts = self.appt_repo.get_active_for_customer(customer.id)

        if not appts:
            msg = message_loader.get("no_active_appts")
            # Return to menu
            self._send_welcome_menu(customer, message_body=f"{msg}\n\n¿Deseas agendar?")
        else:
            msg = "*Tus Citas Pendientes:*\n"
            for appt in appts:
                # Format date?
                # Simple strftime for now
                date_str = appt.start_time.strftime("%d/%m %H:%M")
                msg += f"- {date_str} con {appt.barber.name}\n"

            whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)
            self._send_welcome_menu(customer, message_body="¿Algo más?")

    def _show_info(self, customer: Customer):
        msg = message_loader.get("info_message", business_name=self.business.name, phone=self.business.phone)
        whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)
        self._send_welcome_menu(customer, message_body="¿En qué más te puedo ayudar?")
