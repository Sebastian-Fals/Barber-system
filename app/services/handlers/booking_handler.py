import datetime
import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessCalendarError, ServiceValidationError, SlotOccupiedError
from app.core.i18n import message_loader
from app.core.logging_config import logger
from app.features.appointments.service import BookingService
from app.features.business.barber_repository import BarberRepository
from app.features.business.repository import BusinessRepository
from app.features.communication.whatsapp_service import whatsapp_service
from app.features.customers.repository import CustomerRepository
from app.models.models import Business, Customer, CustomerData
from app.services.handlers.base_handler import BaseHandler

# We can probably move FlowManager logic into Repositories or usage here directly,
# but for now reusing FlowManager logic (which wraps customer.conversation_data) is fine
# to keep consistent with legacy while we refactor handlers.
# Actually, let's use the CustomerRepository methods `update_state` and `update_data` directly
# to decouple from the old FlowManager if possible.
# But FlowManager handles JSON serialization of `conversation_data`.
# Let's reproduce that small logic here or use FlowManager. Using FlowManager is safer for migration.
# Wait, I don't want to import FlowManager if I can avoid it.
# CustomerRepository has `update_data`. I just need to json load/dump.


class BookingHandler(BaseHandler):
    def __init__(self, db: Session, instance_name: str, instance_apikey: str, business_id: int):
        super().__init__(db, instance_name, instance_apikey, business_id)
        self.booking_service = BookingService(db)
        self.customer_repo = CustomerRepository(db)
        self.barber_repo = BarberRepository(db)
        self.business_repo = BusinessRepository(db)
        # Context — resolved by ID, not by phone_number_id query
        self.business = db.query(Business).filter(Business.id == business_id).first()

    def _get_data(self, customer: Customer) -> dict:
        try:
            return json.loads(customer.conversation_data) if customer.conversation_data else {}
        except (ValueError, TypeError):
            return {}

    def _update_state(self, customer: Customer, state: str, data: dict = None):
        if data is not None:
            self.customer_repo.update_data(customer, json.dumps(data))
        self.customer_repo.update_state(customer, state)

    def handle_message(self, customer: Customer, message_body: str) -> bool:
        """
        Handles text input during booking (e.g., "cancelar" or manual entry).
        Returns True if handled, False if ignored (fallback to LLM).
        """
        # Detect cancel request in any text form
        if message_body and message_body.strip().lower() in ("cancelar", "cancel", "cancelar cita"):
            self._update_state(customer, CustomerData.IDLE, {})
            whatsapp_service.send_message(
                self.instance_name,
                self.instance_apikey,
                customer.phone,
                "Proceso cancelado. ¿En qué más puedo ayudarte?",
            )
            return True

        # For MVP Refactor, strictly use buttons for booking flow steps.
        # If user sends text, we treat it as unhandled so QueryHandler (LLM) can try to interpret it.
        return False

    def handle_interactive(self, customer: Customer, interactive_id: str, payload: Dict[str, Any]) -> None:
        if interactive_id.startswith("service_"):
            self._handle_service_selection(customer, interactive_id)

        elif interactive_id.startswith("barber_"):
            self._handle_barber_selection(customer, interactive_id)

        elif interactive_id.startswith("date_"):
            self._handle_date_selection(customer, interactive_id)

        elif interactive_id.startswith("time_"):
            self._handle_time_selection(customer, interactive_id)

        elif interactive_id.startswith("page_"):
            self._handle_pagination(customer, interactive_id)

        elif interactive_id == "confirm_yes":
            self._finalize_booking(customer)

        elif interactive_id == "confirm_no":
            self._cancel_booking_process(customer)

        elif interactive_id == "cancel_flow":
            self._cancel_booking_process(customer)

        elif interactive_id.startswith("cancel_appt_"):
            self._finalize_cancellation(customer, interactive_id)

    def _handle_service_selection(self, customer: Customer, interactive_id: str):
        # ID format: service_{id}
        parts = interactive_id.split("_")
        if len(parts) < 2:
            return

        service_id = int(parts[1])
        data = self._get_data(customer)
        data["service_id"] = service_id

        # Next: Select Barber
        self._update_state(customer, CustomerData.SELECT_BARBER, data)

        barbers = self.barber_repo.get_by_business(self.business_id)
        msg = message_loader.get("booking_ask_barber")
        buttons = [{"id": f"barber_{b.id}", "title": b.name} for b in barbers[:3]]
        # Always include Cancel button
        buttons.append({"id": "cancel_flow", "title": "Cancelar"})

        self._send_list_from_buttons(customer.phone, msg, buttons)

    def _handle_barber_selection(self, customer: Customer, interactive_id: str):
        # ID format: barber_{id}
        parts = interactive_id.split("_")
        if len(parts) < 2:
            return

        barber_id = int(parts[1])
        data = self._get_data(customer)
        data["barber_id"] = barber_id

        barber = self.barber_repo.get_by_id(barber_id)
        if not barber:
            return  # Error

        # Next: Select Date
        self._update_state(customer, CustomerData.SELECT_DATE, data)

        msg = message_loader.get("booking_ask_specific_date", barber_name=barber.name)
        buttons = [
            {"id": "date_today", "title": message_loader.get("btn_today")},
            {"id": "date_tomorrow", "title": message_loader.get("btn_tomorrow")},
            {"id": "cancel_flow", "title": "Cancelar"},
        ]
        self._send_list_from_buttons(customer.phone, msg, buttons)

    def _handle_date_selection(self, customer: Customer, interactive_id: str):
        # ID: date_today, date_tomorrow
        target_date = datetime.date.today()
        if "tomorrow" in interactive_id:
            target_date += datetime.timedelta(days=1)

        data = self._get_data(customer)
        data["date"] = target_date.strftime("%Y-%m-%d")  # Store as string

        # Verify barber
        if "barber_id" not in data:
            self._cancel_booking_process(customer)
            return

        # Fetch Slots
        self._show_slots(customer, data, target_date)

    def _show_slots(self, customer: Customer, data: dict, target_date: datetime.date, page: int = 0):
        slots = self.booking_service.get_available_slots(data["barber_id"], target_date)

        if not slots:
            msg = message_loader.get("booking_no_slots")
            whatsapp_service.send_message(self.instance_name, self.instance_apikey, customer.phone, msg)
            # Could offer buttons to select another date here
            return

        # Pagination Logic: WhatsApp allows max 3 buttons.
        # If we have more slots than fits in this page, we need 1 slot for "Next".
        # So: if len(slots) > start + 3, we can only show 2 slots + Next.
        # If len(slots) <= start + 3, we can show all 3 (or fewer) remaining slots.

        start = page * 2  # Standardizing on 2 slots per page to allow space for "Next" if needed.
        # Actually logic below uses limit calculation.
        # Let's say page 0: start=0.
        # If slots > 3, show 2 + Next.
        # If slots <= 3, show 3.

        remaining = len(slots) - start
        if remaining > 3:
            limit = 2
        else:
            limit = 3

        subset = slots[start : start + limit]

        buttons = []
        for slot in subset:
            time_str = slot.strftime("%H:%M")
            display = slot.strftime("%I:%M%p").lower().lstrip("0")
            buttons.append({"id": f"time_{time_str}", "title": display})

        if remaining > 3:  # We check against 3 because if we had 3, we showed all (assuming strict pages/stream).
            # Wait, if remaining > 3, we showed 2, so there are remaining-2 left.
            # Logic check:
            # Total 4. Start 0. Remaining 4. > 3 is True. Limit 2. Show 0,1. Next button. Correct.
            # Total 3. Start 0. Remaining 3. > 3 is False. Limit 3. Show 0,1,2. No Next button. Correct.
            buttons.append({"id": f"page_{page+1}", "title": message_loader.get("booking_pagination_next")})

        data["last_slots_date"] = target_date.strftime("%Y-%m-%d")
        # Update State to SELECT_SLOT (if not already)
        self._update_state(customer, CustomerData.SELECT_SLOT, data)

        msg = message_loader.get("booking_ask_time_header", date=target_date.strftime("%d/%m"))
        self._send_list_from_buttons(customer.phone, msg, buttons)

    def _handle_time_selection(self, customer: Customer, interactive_id: str):
        # ID: time_14:00
        time_str = interactive_id.split("_")[1]
        data = self._get_data(customer)
        data["time"] = time_str

        self._update_state(customer, CustomerData.CONFIRM_BOOKING, data)

        # Summary
        barber = self.barber_repo.get_by_id(data["barber_id"])

        msg = message_loader.get("booking_summary", barber_name=barber.name, date=data["date"], time=time_str)

        buttons = [
            {"id": "confirm_yes", "title": message_loader.get("btn_yes")},
            {"id": "confirm_no", "title": message_loader.get("btn_no")},
            {"id": "cancel_flow", "title": "Cancelar"},
        ]
        self._send_list_from_buttons(customer.phone, msg, buttons)

    def _handle_pagination(self, customer: Customer, interactive_id: str):
        # ID: page_1
        page = int(interactive_id.split("_")[1])
        data = self._get_data(customer)

        if "last_slots_date" in data:
            try:
                target_date = datetime.datetime.strptime(data["last_slots_date"], "%Y-%m-%d").date()
                self._show_slots(customer, data, target_date, page)
            except (ValueError, TypeError):
                pass

    def _finalize_booking(self, customer: Customer):
        data = self._get_data(customer)

        try:
            self.booking_service.create_appointment(customer, data["barber_id"], data["date"], data["time"])
            whatsapp_service.send_message(
                self.instance_name, self.instance_apikey, customer.phone, message_loader.get("booking_confirmed")
            )
            # Reset state
            self._update_state(customer, CustomerData.IDLE, {})
        except (SlotOccupiedError, BusinessCalendarError) as e:
            whatsapp_service.send_message(self.instance_name, self.instance_apikey, customer.phone, f"⚠️ {e}")
            self._update_state(customer, CustomerData.IDLE, {})
        except ServiceValidationError as e:
            whatsapp_service.send_message(
                self.instance_name, self.instance_apikey, customer.phone, f"❌ Error en los datos: {e}"
            )
            self._update_state(customer, CustomerData.IDLE, {})
        except Exception as e:
            logger.error(f"Unexpected error in booking confirmation: {e}")
            whatsapp_service.send_message(
                self.instance_name, self.instance_apikey, customer.phone, message_loader.get("booking_error")
            )
            self._update_state(customer, CustomerData.IDLE, {})

    def _cancel_booking_process(self, customer: Customer):
        self._update_state(customer, CustomerData.IDLE, {})
        whatsapp_service.send_message(
            self.instance_name, self.instance_apikey, customer.phone, message_loader.get("btn_no") + " OK."
        )

    def _finalize_cancellation(self, customer: Customer, interactive_id: str):
        # ID: cancel_appt_{id}
        try:
            appt_id = int(interactive_id.split("_")[2])
            success = self.booking_service.cancel_appointment(appt_id)
            if success:
                whatsapp_service.send_message(
                    self.instance_name, self.instance_apikey, customer.phone, "✅ Cita cancelada correctamente."
                )
            else:
                whatsapp_service.send_message(
                    self.instance_name,
                    customer.phone,
                    "❌ No se pudo cancelar la cita (posiblemente ya pasada o inexistente).",
                )
        except Exception as e:
            logger.error(f"Cancellation error: {e}")
            whatsapp_service.send_message(self.instance_name, self.instance_apikey, customer.phone, "Error interno.")
