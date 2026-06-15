from datetime import datetime, timedelta
from typing import Any, Dict

import pytz
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessCalendarError, ServiceValidationError, SlotOccupiedError
from app.core.i18n import message_loader
from app.core.logging_config import logger
from app.features.appointments.repository import AppointmentRepository
from app.features.appointments.service import BookingService
from app.features.business.barber_repository import BarberRepository
from app.features.business.repository import BusinessRepository
from app.features.communication.llm_service import llm_service
from app.features.communication.whatsapp_service import whatsapp_service
from app.features.customers.repository import CustomerRepository
from app.models.models import Business, ConversationHistory, Customer, CustomerData
from app.services.handlers.base_handler import BaseHandler


class QueryHandler(BaseHandler):
    def __init__(self, db: Session, phone_number_id: str, business_id: int):
        super().__init__(db, phone_number_id, business_id)
        self.customer_repo = CustomerRepository(db)
        self.barber_repo = BarberRepository(db)
        self.business_repo = BusinessRepository(db)
        self.appt_repo = AppointmentRepository(db)
        self.booking_service = BookingService(db)
        # Context — resolved by ID (already known from webhook)
        self.business = db.query(Business).filter(Business.id == business_id).first()

    def handle_message(self, customer: Customer, message_body: str) -> None:
        """
        Process free-text message using LLM.
        """
        # 1. Manage History Expiration (Lazy)
        self._manage_history_expiration(customer.id)

        # 2. Log Incoming Message
        self._log_message(customer.id, "user", message_body)

        # 0. Intercept CONFIRM_BOOKING state Manually (Optimize Latency & Avoid LLM)
        if customer.conversation_state == CustomerData.CONFIRM_BOOKING:
            msg_lower = message_body.strip().lower()
            affirmative = ["si", "sí", "claro", "yes", "confirmar", "correcto", "ok", "dale"]
            negative = ["no", "cancelar", "espera", "mal", "corregir"]

            logger.info(f"Processing Confirmation for {customer.phone}: '{message_body}'")

            if any(x in msg_lower for x in affirmative):
                # Create Appointment
                import json

                try:
                    logger.info("Do Booking Confirmation - Data Payload Analysis:")
                    raw_data = customer.conversation_data
                    logger.info(f"Raw conversation_data: {raw_data}")

                    data = json.loads(raw_data) if raw_data else {}

                    # Validate Data
                    if not data.get("barber_id") or not data.get("date") or not data.get("time"):
                        logger.error(f"Missing booking data in confirmation payload: {data}")
                        whatsapp_service.send_message(
                            self.phone_number_id,
                            customer.phone,
                            "Lo siento, hubo un error con los datos de la cita. Por favor iniciemos de nuevo.",
                        )
                        self.customer_repo.update_state(customer, CustomerData.IDLE)
                        return

                    try:
                        appt = self.booking_service.create_appointment(
                            customer, data.get("barber_id"), data.get("date"), data.get("time")
                        )
                        logger.info(f"Booking created: {appt.id}")
                        whatsapp_service.send_message(
                            self.phone_number_id, customer.phone, message_loader.get("booking_confirmed")
                        )
                        self.customer_repo.update_state(customer, CustomerData.IDLE)
                        self.customer_repo.update_data(customer, "{}")

                    except (SlotOccupiedError, BusinessCalendarError) as e:
                        logger.warning(f"Booking failed: {e}")
                        whatsapp_service.send_message(
                            self.phone_number_id,
                            customer.phone,
                            f"No se pudo agendar: {e} 📅",
                        )
                        self.customer_repo.update_state(customer, CustomerData.IDLE)
                    except ServiceValidationError as e:
                        logger.error(f"Validation error: {e}")
                        whatsapp_service.send_message(
                            self.phone_number_id,
                            customer.phone,
                            "Hubo un problema con los datos recibidos. Por favor intenta de nuevo.",
                        )
                        self.customer_repo.update_state(customer, CustomerData.IDLE)
                except Exception as e:
                    logger.error(f"Error finalizing booking in QueryHandler: {e}", exc_info=True)
                    whatsapp_service.send_message(
                        self.phone_number_id,
                        customer.phone,
                        "Ocurrió un error al procesar tu confirmación. Intenta de nuevo.",
                    )
                return

            elif any(x in msg_lower for x in negative):
                # Reset
                whatsapp_service.send_message(
                    self.phone_number_id, customer.phone, "Entendido, no agendamos nada. ¿Qué necesitas?"
                )
                self.customer_repo.update_state(customer, CustomerData.IDLE)
                self.customer_repo.update_data(customer, "{}")
                return
            else:
                # Ambiguous -> Fall through to LLM (e.g. "Wait, can I change info?")
                # Or just ask again? "Responde Sí o No"
                pass

        # Prepare Context for LLM
        context = self._build_llm_context(customer)

        # Call LLM
        analysis = llm_service.analyze_message(message_body, context)
        intent = analysis.get("intent", "UNKNOWN")
        reply = analysis.get("reply", "")

        logger.info(f"LLM Analysis for {customer.phone}: Intent={intent}")

        # Note: We removed the check here since it's now at the top.

        if intent == "BOOK_APPOINTMENT":
            # Extract possible entities
            extracted = analysis.get("extracted", {})

            # Start Booking Flow (Smart Transition)
            self._smart_booking_transition(customer, extracted, reply)

        elif intent == "CANCEL_APPOINTMENT":
            # Handle Cancellation
            extracted = analysis.get("extracted", {})
            self._handle_cancellation_intent(customer, reply, extracted)

        elif intent == "CANCEL_CONVERSATION":
            # Explicit Reset/Stop
            if reply:
                self._send_and_log(customer, reply)

            # Purge History
            self._purge_history(customer.id)

            self.customer_repo.update_state(customer, CustomerData.IDLE)
            self.customer_repo.update_data(customer, "{}")

        elif intent == "MY_APPOINTMENTS":
            # Show appointments
            self._handle_my_appointments(customer, reply)

        elif intent == "WHO_AM_I":
            # Answer about identity
            # Answer about identity
            if reply:
                self._send_and_log(customer, reply)
            else:
                self._send_and_log(customer, f"Te tengo registrado como {customer.name}.")

            # Update Customer Name
            extracted = analysis.get("extracted", {})
            new_name = extracted.get("customer_name")

            # Sanity Check for Names
            invalid_names = ["hola", "hi", "bot", "usuario", "si", "no", "cancelar", "menu", "dia", "tarde", "noche"]
            if new_name and new_name.lower().strip() not in invalid_names and len(new_name) > 2:
                self.customer_repo.update(customer, {"name": new_name})
            else:
                logger.warning(f"Ignored invalid name update attempt: {new_name}")

            # Reply with LLM's message (which should be "Nice to meet you X")
            # Reply with LLM's message (which should be "Nice to meet you X")
            if reply:
                self._send_and_log(customer, reply)
            else:
                self._send_and_log(customer, "¡Gracias! He actualizado tu nombre.")

        elif intent == "PROVIDE_NAME":
            # User is providing their name
            extracted = analysis.get("extracted", {})
            new_name = extracted.get("customer_name")

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
            ]
            if new_name and new_name.lower().strip() not in invalid_names and len(new_name) > 2:
                self.customer_repo.update(customer, {"name": new_name.title()})
                if reply:
                    self._send_and_log(customer, reply)
                else:
                    self._send_and_log(
                        customer,
                        f"¡Gracias {new_name.title()}! He actualizado tu nombre. ¿En qué puedo ayudarte?",
                    )
            else:
                logger.warning(f"Ignored invalid name update attempt: {new_name}")
                if reply:
                    self._send_and_log(customer, reply)

        elif intent == "FALLBACK":
            # LLM couldn't determine intent — provide helpful fallback
            if reply:
                self._send_and_log(customer, reply)
            else:
                self._send_and_log(
                    customer,
                    "No entendí bien tu mensaje. ¿Podrías usar el menú o ser más específico? 🤔",
                )

        elif intent == "CHITCHAT":
            # Just reply directly ("Hola", "Gracias", Info del negocio)
            # Ana answers directly now.
            if reply:
                self._send_and_log(customer, reply)
            else:
                self._send_and_log(customer, "¡Hola! ¿En qué puedo ayudarte?")

        else:
            # General Q&A or Unknown
            if reply:
                self._send_and_log(customer, reply)
            else:
                self._send_and_log(customer, message_loader.get("error_fallback"))

    def handle_interactive(self, customer: Customer, interactive_id: str, payload: Dict[str, Any]) -> None:
        # Delegate all booking-related button clicks to BookingHandler
        # so AI and non-AI modes share the same interactive handling.
        from app.services.handlers.booking_handler import BookingHandler

        booking_handler = BookingHandler(self.db, self.phone_number_id, self.business_id)
        booking_handler.handle_interactive(customer, interactive_id, payload)

    def _build_llm_context(self, customer: Customer) -> Dict[str, Any]:
        """
        Constructs the context dictionary required by LLMService.
        """
        barbers = self.barber_repo.get_by_business(self.business.id) if self.business else []
        barber_names = [b.name for b in barbers]

        # Build Business Info String
        if self.business:
            # We can expand this with address if added to model, using phone/schedule for now
            schedule_str = "Lun-Dom: 9am-6pm"  # Placeholder if schedule is complex JSON
            if self.business.schedule:
                # Naive parse or static text. Let's provide static "Consultar disponibilidad"
                pass
            info = f"Nombre: {self.business.name}. Teléfono: {self.business.phone}. Horario: {schedule_str}."
        else:
            info = "Información no disponible."

        # Simple history - in a real app check conversation_data or a message log table
        history = []

        # Load Recent History from DB
        try:
            hist_rows = (
                self.db.query(ConversationHistory)
                .filter(ConversationHistory.customer_id == customer.id)
                .order_by(ConversationHistory.created_at.asc())
                .limit(15)
                .all()
            )

            history = [{"role": h.role, "content": h.message} for h in hist_rows]
        except Exception as e:
            logger.error(f"Error fetching conversation history: {e}")
            history = []

        from app.core.datetime_utils import now_local

        local_now = now_local()
        return {
            "business_name": self.business.name if self.business else "Barbería",
            "business_info": info,
            "today": local_now.strftime("%Y-%m-%d %H:%M"),
            "day_name": self._get_spanish_day_name(),
            "customer_name": customer.name,
            "barbers": barber_names,
            "current_state": customer.conversation_state,
            "history": history,
        }

    def _smart_booking_transition(self, customer: Customer, extracted: Dict[str, Any], reply_text: str):
        """
        Transition to booking flow using interactive buttons, same as non-AI mode.
        Flow order: SERVICE → BARBER → DATE → SLOT → CONFIRM.
        Entity extraction skips steps when info is already known.
        """
        import json

        barber_name = extracted.get("barber_name")
        date_str = extracted.get("date")

        # 1. Try to resolve Barber
        selected_barber = None
        if barber_name:
            barbers = self.barber_repo.get_by_business(self.business.id) if self.business else []
            for b in barbers:
                if (
                    b.name.strip().lower() in barber_name.strip().lower()
                    or barber_name.strip().lower() in b.name.strip().lower()
                ):
                    selected_barber = b
                    break

        # Prepare current data
        try:
            if customer.conversation_state == CustomerData.IDLE:
                data = {}
            else:
                data = json.loads(customer.conversation_data) if customer.conversation_data else {}
        except (ValueError, TypeError):
            data = {}

        if selected_barber:
            if not date_str:
                data.pop("date", None)
                data.pop("selected_date", None)
            data["barber_id"] = selected_barber.id

        if date_str:
            data["date"] = date_str

        # Determine goal state based on what we have
        # Order: SERVICE → BARBER → DATE → SLOT → CONFIRM
        has_service = "service_id" in data
        has_barber = "barber_id" in data
        has_date = "date" in data
        has_time = "time" in data

        if not has_service:
            next_state = CustomerData.SELECT_SERVICE
        elif not has_barber:
            next_state = CustomerData.SELECT_BARBER
        elif not has_date:
            next_state = CustomerData.SELECT_DATE
        elif not has_time:
            next_state = CustomerData.SELECT_SLOT
        else:
            next_state = CustomerData.CONFIRM_BOOKING

        # Save data and state
        self.customer_repo.update_data(customer, json.dumps(data))
        self.customer_repo.update_state(customer, next_state)

        # Show interactive buttons for the target state
        header = reply_text if reply_text else ""

        if next_state == CustomerData.SELECT_SERVICE:
            self._show_service_buttons(customer, header)

        elif next_state == CustomerData.SELECT_BARBER:
            self._show_barber_buttons(customer, header)

        elif next_state == CustomerData.SELECT_DATE:
            self._show_date_buttons(customer, header)

        elif next_state == CustomerData.SELECT_SLOT:
            self._show_slot_buttons(customer, data, header)

        elif next_state == CustomerData.CONFIRM_BOOKING:
            self._show_confirmation(customer, data, header)

    def _show_service_buttons(self, customer: Customer, header: str = ""):
        """Send interactive service selection buttons (same as non-AI mode)."""
        from app.features.business.service_repository import ServiceRepository

        svc_repo = ServiceRepository(self.db)
        services = svc_repo.get_by_business(self.business_id)
        msg = header or message_loader.get("booking_ask_service")
        buttons = [{"id": f"service_{s.id}", "title": s.name} for s in services[:3]]
        buttons.append({"id": "cancel_flow", "title": "Cancelar"})
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _show_barber_buttons(self, customer: Customer, header: str = ""):
        """Send interactive barber selection buttons."""
        barbers = self.barber_repo.get_by_business(self.business_id) if self.business_id else []
        msg = header or message_loader.get("booking_ask_barber")
        buttons = [{"id": f"barber_{b.id}", "title": b.name} for b in barbers[:3]]
        buttons.append({"id": "cancel_flow", "title": "Cancelar"})
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _show_date_buttons(self, customer: Customer, header: str = ""):
        """Send interactive date selection buttons."""
        msg = header or message_loader.get("booking_ask_specific_date", barber_name="")
        buttons = [
            {"id": "date_today", "title": message_loader.get("btn_today")},
            {"id": "date_tomorrow", "title": message_loader.get("btn_tomorrow")},
            {"id": "cancel_flow", "title": "Cancelar"},
        ]
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _show_slot_buttons(self, customer: Customer, data: dict, header: str = ""):
        """Send interactive slot selection buttons."""
        import datetime

        try:
            target_date_str = data.get("date")
            if not target_date_str:
                raise ValueError("No date found")
            target_date_obj = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
            slots = self.booking_service.get_available_slots(data["barber_id"], target_date_obj)

            if not slots:
                whatsapp_service.send_message(
                    self.phone_number_id,
                    customer.phone,
                    "No hay horarios disponibles para esa fecha. ¿Te va bien otro día?",
                )
                return

            msg = header or message_loader.get(
                "booking_ask_time_header",
                date=target_date_obj.strftime("%d/%m"),
            )
            buttons = []
            for slot in slots[:3]:
                time_str = slot.strftime("%H:%M")
                display = slot.strftime("%I:%M%p").lower().lstrip("0")
                buttons.append({"id": f"time_{time_str}", "title": display})

            buttons.append({"id": "cancel_flow", "title": "Cancelar"})
            whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

        except Exception as e:
            logger.error(f"Error showing slot buttons: {e}")
            whatsapp_service.send_message(
                self.phone_number_id,
                customer.phone,
                "Por favor, indícame para qué fecha buscas.",
            )

    def _show_confirmation(self, customer: Customer, data: dict, header: str = ""):
        """Send interactive confirmation buttons."""
        barber = self.barber_repo.get_by_id(data.get("barber_id"))
        barber_name = barber.name if barber else "?"

        msg = header or message_loader.get(
            "booking_summary",
            barber_name=barber_name,
            date=data.get("date", "?"),
            time=data.get("time", "?"),
        )
        buttons = [
            {"id": "confirm_yes", "title": message_loader.get("btn_yes")},
            {"id": "confirm_no", "title": message_loader.get("btn_no")},
            {"id": "cancel_flow", "title": "Cancelar"},
        ]
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _handle_my_appointments(self, customer: Customer, reply_text: str):
        """
        List active appointments for the customer.
        """
        # Fetch active appointments
        appts = self.appt_repo.get_active_for_customer(customer.id)

        if not appts:
            # Use LLM reply if friendly, else fallback
            msg = reply_text if reply_text else "No tienes citas programadas actualmente."
            whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)
            return

        # Build list
        msg = (reply_text + "\n\n") if reply_text else "📅 *Tus Citas Activas:*\n\n"

        from app.core.datetime_utils import format_12h_time, format_spanish_date, to_local

        for appt in appts:
            # Convert DB UTC to Local
            local_dt = to_local(appt.start_time)

            day_str = format_spanish_date(local_dt)
            time_str = format_12h_time(local_dt)

            msg += f"- *{day_str}, {time_str}* con {appt.barber.name}\n"

        msg += "\n(Escribe 'Cancelar' si deseas anular alguna)"
        whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)

    def _handle_cancellation_intent(self, customer: Customer, reply_text: str, extracted: Dict[str, Any] = None):
        # Text-Based Cancellation Flow
        appts = self.appt_repo.get_active_for_customer(customer.id)

        if not appts:
            whatsapp_service.send_message(
                self.phone_number_id, customer.phone, "No tienes citas activas para cancelar."
            )
            return

        # Check if specific date/time was mentioned
        target_date_str = extracted.get("date") if extracted else None
        target_time_str = extracted.get("time") if extracted else None

        from app.core.datetime_utils import format_12h_time, format_spanish_date, to_local

        if target_date_str:
            # Try to find match
            # This is simple fuzzy match. If user has multiple appts on same day, this cancels the first one found
            # unless time is also specified.
            # TODO: Improve robustness for multi-appt days.

            found_appt = None
            date_match_label = target_date_str

            for appt in appts:
                # CRITCAL: Convert DB UTC to Local before comparing date string
                # (YYYY-MM-DD from user implies local date)
                local_dt = to_local(appt.start_time)
                appt_date = local_dt.date().strftime("%Y-%m-%d")

                if appt_date == target_date_str:
                    date_match_label = format_spanish_date(local_dt)  # For success message

                    # Date matches. If time specified, check time.
                    if target_time_str:
                        appt_time = local_dt.strftime("%H:%M")
                        if appt_time == target_time_str:
                            found_appt = appt
                            break
                    else:
                        found_appt = appt
                        break

            if found_appt:
                success = self.booking_service.cancel_appointment(found_appt.id)
                if success:
                    whatsapp_service.send_message(
                        self.phone_number_id, customer.phone, f"✅ Cita del {date_match_label} cancelada correctamente."
                    )
                else:
                    whatsapp_service.send_message(
                        self.phone_number_id, customer.phone, "Hubo un error interno al cancelar. Intenta más tarde."
                    )
                return
            else:
                whatsapp_service.send_message(
                    self.phone_number_id,
                    customer.phone,
                    f"No encontré citas para el {target_date_str}. Revisemos tu lista:",
                )

        # Fallback: List appointments with Nice Formatting
        msg = "Tienes estas citas activas:\n"
        for appt in appts:
            local_dt = to_local(appt.start_time)
            day_str = format_spanish_date(local_dt)
            time_str = format_12h_time(local_dt)
            msg += f"- *{day_str}, {time_str}* con {appt.barber.name}\n"

        msg += "\nPara cancelar, dime qué día (ej: 'Cancelar la de mañana' o 'Cancelar la del sábado')."

        whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)

    def _get_spanish_day_name(self) -> str:
        days = {
            "Monday": "Lunes",
            "Tuesday": "Martes",
            "Wednesday": "Miércoles",
            "Thursday": "Jueves",
            "Friday": "Viernes",
            "Saturday": "Sábado",
            "Sunday": "Domingo",
        }
        from app.core.datetime_utils import now_local

        return days.get(now_local().strftime("%A"), "Hoy")

    def _manage_history_expiration(self, customer_id: int):
        """
        Check existing history and purge if inactivity > 24 hours.
        """
        try:
            last_msg = (
                self.db.query(ConversationHistory)
                .filter(ConversationHistory.customer_id == customer_id)
                .order_by(ConversationHistory.created_at.desc())
                .first()
            )

            if last_msg:
                now = datetime.now(pytz.UTC)
                # Ensure aware
                msg_time = last_msg.created_at
                if msg_time.tzinfo is None:
                    msg_time = pytz.UTC.localize(msg_time)

                if (now - msg_time) > timedelta(hours=24):
                    logger.info(f"Purging history for customer {customer_id} due to inactivity > 24h")
                    self._purge_history(customer_id)
        except Exception as e:
            logger.error(f"Error checking history expiration: {e}")

    def _purge_history(self, customer_id: int):
        try:
            self.db.query(ConversationHistory).filter(ConversationHistory.customer_id == customer_id).delete()
            self.db.commit()
            logger.info(f"History purged for customer {customer_id}")
        except Exception as e:
            logger.error(f"Error purging history: {e}")

    def _log_message(self, customer_id: int, role: str, message: str):
        try:
            entry = ConversationHistory(
                customer_id=customer_id, role=role, message=message, created_at=datetime.now(pytz.UTC)
            )
            self.db.add(entry)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error logging message to history: {e}")

    def _send_and_log(self, customer: Customer, message: str):
        """
        Helper to send via WhatsApp and log as assistant message.
        """
        # Send
        whatsapp_service.send_message(self.phone_number_id, customer.phone, message)

        # Log
        self._log_message(customer.id, "assistant", message)
