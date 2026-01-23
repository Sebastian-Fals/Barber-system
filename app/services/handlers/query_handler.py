from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.i18n import message_loader
from app.core.logging_config import logger
from app.features.appointments.repository import AppointmentRepository
from app.features.appointments.service import BookingService
from app.features.business.barber_repository import BarberRepository
from app.features.business.repository import BusinessRepository
from app.features.communication.llm_service import llm_service
from app.features.communication.whatsapp_service import whatsapp_service
from app.features.customers.repository import CustomerRepository
from app.models.models import Business, Customer, CustomerData
from app.services.handlers.base_handler import BaseHandler


class QueryHandler(BaseHandler):
    def __init__(self, db: Session, phone_number_id: str):
        super().__init__(db, phone_number_id)
        self.customer_repo = CustomerRepository(db)
        self.barber_repo = BarberRepository(db)
        self.business_repo = BusinessRepository(db)
        self.appt_repo = AppointmentRepository(db)
        self.booking_service = BookingService(db)
        self.business = db.query(Business).filter(Business.phone_number_id == phone_number_id).first()

    def handle_message(self, customer: Customer, message_body: str) -> None:
        """
        Process free-text message using LLM.
        """
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

                    appt = self.booking_service.create_appointment(
                        customer, data.get("barber_id"), data.get("date"), data.get("time")
                    )

                    if appt:
                        logger.info(f"Booking created: {appt.id}")
                        whatsapp_service.send_message(
                            self.phone_number_id, customer.phone, message_loader.get("booking_confirmed")
                        )
                        # Reset
                        self.customer_repo.update_state(customer, CustomerData.IDLE)
                        self.customer_repo.update_data(customer, "{}")
                    else:
                        logger.warning("Booking failed (Occupied?)")
                        whatsapp_service.send_message(
                            self.phone_number_id,
                            customer.phone,
                            "Error al crear la cita. El horario podría estar ocupado.",
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
                whatsapp_service.send_message(self.phone_number_id, customer.phone, reply)
            self.customer_repo.update_state(customer, CustomerData.IDLE)
            self.customer_repo.update_data(customer, "{}")

        elif intent == "MY_APPOINTMENTS":
            # Show appointments
            self._handle_my_appointments(customer, reply)

        elif intent == "WHO_AM_I":
            # Answer about identity
            if reply:
                whatsapp_service.send_message(self.phone_number_id, customer.phone, reply)
            else:
                whatsapp_service.send_message(
                    self.phone_number_id, customer.phone, f"Te tengo registrado como {customer.name}."
                )

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
            if reply:
                whatsapp_service.send_message(self.phone_number_id, customer.phone, reply)
            else:
                whatsapp_service.send_message(
                    self.phone_number_id, customer.phone, "¡Gracias! He actualizado tu nombre."
                )

        elif intent == "CHITCHAT":
            # Just reply directly ("Hola", "Gracias", Info del negocio)
            # Ana answers directly now.
            if reply:
                whatsapp_service.send_message(self.phone_number_id, customer.phone, reply)
            else:
                whatsapp_service.send_message(self.phone_number_id, customer.phone, "¡Hola! ¿En qué puedo ayudarte?")

        else:
            # General Q&A or Unknown
            if reply:
                whatsapp_service.send_message(self.phone_number_id, customer.phone, reply)
            else:
                whatsapp_service.send_message(
                    self.phone_number_id, customer.phone, message_loader.get("error_fallback")
                )

    def handle_interactive(self, customer: Customer, interactive_id: str, payload: Dict[str, Any]) -> None:
        # QueryHandler normally doesn't handle buttons unless we add "Are you sure?" flows here.
        pass

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
        Transition to booking flow, skipping steps if entities are present.
        Uses reply_text as the header for the next menu if applicable.
        """
        import json

        barber_name = extracted.get("barber_name")
        date_str = extracted.get("date")

        # 1. Try to resolve Barber
        selected_barber = None
        if barber_name:
            barbers = self.barber_repo.get_by_business(self.business.id) if self.business else []
            # Fuzzy match or exact match
            for b in barbers:
                if (
                    b.name.strip().lower() in barber_name.strip().lower()
                    or barber_name.strip().lower() in b.name.strip().lower()
                ):
                    selected_barber = b
                    break

        # Prepare current data
        # If we are starting from IDLE, we should clear old booking data to avoid "ghost" selections.
        # But we might want to keep other non-booking data if it exists (unlikely for now).
        # Safest is to reset if IDLE.
        try:
            if customer.conversation_state == CustomerData.IDLE:
                data = {}
            else:
                data = json.loads(customer.conversation_data) if customer.conversation_data else {}
        except (ValueError, TypeError):
            data = {}

        # 2. Logic to Jump Steps
        next_state = CustomerData.SELECT_BARBER

        if selected_barber:
            # Check if we are changing barber?
            # Or simply, if a barber is explicitly named, we should probably reset the date
            # unless the date is ALSO explicitly named in this message.
            # This prevents specific case: User selected "Today" with Barber A, then changed mind and said
            # "With Barber B" (implying start over for date?)
            # Or simpler: "Context Switch".

            # If we extracted a barber, and we did NOT extract a date, we should clear any previous date
            # to force the "When?" question.
            if not date_str:
                data.pop("date", None)
                data.pop("selected_date", None)

            data["barber_id"] = selected_barber.id  # Use consistent key "barber_id"
            data["selected_barber_id"] = selected_barber.id  # Keep compatibility if needed

        # 3. Determine Goal State based on unified Data
        # Order: Barber -> Date -> Slot
        next_state = CustomerData.SELECT_BARBER

        has_barber = "barber_id" in data or "selected_barber_id" in data
        has_date = "date" in data or "selected_date" in data

        # If we have extracted a new date, update it
        if date_str:
            data["date"] = date_str
            data["selected_date"] = date_str
            has_date = True

        if has_barber:
            next_state = CustomerData.SELECT_DATE
            if has_date:
                next_state = CustomerData.SELECT_SLOT

        # Save data
        self.customer_repo.update_data(customer, json.dumps(data))
        self.customer_repo.update_state(customer, next_state)

        # 3. Trigger Handler for Next State
        # We need to manually construct the UI for the target state

        if next_state == CustomerData.SELECT_BARBER:
            # Show Barber List (Text)
            msg_body = reply_text if reply_text else message_loader.get("booking_ask_barber")
            barbers = self.barber_repo.get_by_business(self.business.id) if self.business else []

            if barbers:
                barber_list = "\n".join([f"- {b.name}" for b in barbers])
                msg_body += f"\n\nBarberos disponibles:\n{barber_list}"

            whatsapp_service.send_message(self.phone_number_id, customer.phone, msg_body)

        elif next_state == CustomerData.SELECT_DATE:
            # Ask for Date (Text)
            msg_body = reply_text if reply_text else message_loader.get("booking_ask_date")
            whatsapp_service.send_message(self.phone_number_id, customer.phone, msg_body)

        elif next_state == CustomerData.SELECT_SLOT:
            # Handle Custom Time or Show Slots (Text Only)
            time_str = extracted.get("time")  # extracted HH:MM

            # 1. Try to Validate Custom Time if available
            if time_str:
                try:
                    import datetime

                    extracted_time = datetime.datetime.strptime(time_str, "%H:%M").time()

                    target_date_str = date_str if date_str else data.get("date")
                    if target_date_str:
                        target_date_obj = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()

                        is_free = self.booking_service.is_custom_slot_available(
                            data["barber_id"], target_date_obj, extracted_time
                        )

                        if is_free:
                            # Success! Skip Slot Menu and Go to Confirmation
                            data["time"] = time_str
                            self.customer_repo.update_data(customer, json.dumps(data))
                            self.customer_repo.update_state(customer, CustomerData.CONFIRM_BOOKING)

                            # Text Confirmation
                            from app.core.datetime_utils import format_12h_time, format_spanish_date

                            barber = self.barber_repo.get_by_id(data["barber_id"])
                            nice_date = format_spanish_date(target_date_str)
                            nice_time = format_12h_time(time_str)

                            msg = (
                                f"Perfecto. Resumen:\n📅 Fecha: {nice_date}\n⏰ Hora: {nice_time}\n"
                                f"💈 Barbero: {barber.name}\n\n¿Estás de acuerdo? (Responde 'Sí' o 'Más tarde')"
                            )
                            whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)
                            return  # Done, flow advanced.
                        else:
                            # Time not free. Inform user (continue to show slots)
                            whatsapp_service.send_message(
                                self.phone_number_id, customer.phone, f"Lo siento, las {time_str} ya está ocupado."
                            )
                except Exception as e:
                    logger.error(f"Custom time check failed: {e}")

            # 2. Fallback: Show Standard Slots (Text List)
            try:
                import datetime

                target_date_str = date_str if date_str else data.get("date")
                if not target_date_str:
                    raise ValueError("No date found")

                target_date_obj = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()

                # Fetch available slots
                slots = self.booking_service.get_available_slots(data["barber_id"], target_date_obj)

                if not slots:
                    whatsapp_service.send_message(
                        self.phone_number_id,
                        customer.phone,
                        "No hay horarios disponibles para esa fecha. ¿Te va bien otro día?",
                    )
                else:
                    # Limit to reasonable amount for text (e.g. 10)
                    # Format to 12h AM/PM
                    from app.core.datetime_utils import format_12h_time, format_spanish_date

                    display_slots = [format_12h_time(s) for s in slots[:12]]
                    slots_text = ", ".join(display_slots)

                    nice_date = format_spanish_date(target_date_obj)

                    msg = (
                        f"Tengo estos horarios libres para el {nice_date}:\n{slots_text}\n\n"
                        f"¿Cuál prefieres? (O escríbeme otra hora)"
                    )
                    whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)

            except Exception as e:
                logger.error(f"Error showing text slots: {e}")
                whatsapp_service.send_message(
                    self.phone_number_id, customer.phone, "Por favor, indícame para qué fecha buscas."
                )

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
