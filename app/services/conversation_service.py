import json
import datetime
from sqlalchemy.orm import Session
from app.models.models import Customer, Business, Barber, CustomerData, Appointment, AppointmentStatus
from app.services.whatsapp_service import whatsapp_service
from app.services.calendar_service import calendar_service
from app.services.llm_service import llm_service
from app.services.booking_service import BookingService
from app.services.flow_service import FlowManager
from app.core.logging_config import logger

class ConversationService:
    def __init__(self, db: Session, phone_number_id: str):
        self.db = db
        self.phone_number_id = phone_number_id
        self.business = db.query(Business).filter(Business.phone_number_id == phone_number_id).first()
        self.booking_service = BookingService(db)
        self.flow_manager = FlowManager(db)

    def handle_incoming_message(self, from_number: str, message_body: str, message_type: str = "text", interactive_id: str = None):
        if not self.business: 
            logger.error(f"No business found for phone_number_id: {self.phone_number_id}")
            return
        
        # Log Incoming
        logger.info(f"Msg from {from_number} | Type: {message_type} | ID: {interactive_id} | Body: {message_body}")

        # Ignore empty inputs
        if not message_body and not interactive_id:
            logger.warning(f"Ignored empty message from {from_number}")
            return

        # 1. Get/Create Customer
        customer = self.db.query(Customer).filter(Customer.phone == from_number).first()
        if not customer:
            logger.info(f"New Customer detected: {from_number}")
            customer = Customer(phone=from_number, name="Cliente Nuevo")
            self.db.add(customer); self.db.commit()

        # Handling Interactive payloads directly
        if interactive_id:
            self._handle_interactive(customer, interactive_id, from_number)
            return

        # 2. Deterministic / Fast Path Logic
        low_body = message_body.lower().strip()
        keywords = ["hola", "menu", "inicio", "empezar", "reset", "cancelar"]
        is_keyword = any(low_body == k for k in keywords)

        # Logic Gate: AI Enabled check
        ai_enabled = self.business.ai_enabled if hasattr(self.business, 'ai_enabled') else True
        
        # If AI is disabled, we force valid keywords or Show Menu helper
        if not ai_enabled:
             if is_keyword:
                 self.flow_manager.update_state(customer, CustomerData.IDLE, {})
                 self._send_welcome_menu(customer)
             else:
                 # Fallback for Deterministic Mode
                 self._send_deterministic_fallback(customer)
             return

        # If AI is enabled, keywords still take precedence for reset/menu
        if is_keyword:
            self.flow_manager.update_state(customer, CustomerData.IDLE, {})
            self._send_welcome_menu(customer)
            return

        # 3. AI Hybrid Path (Only if enabled and not a keyword)
        # Build Context for LLM
        barbers = self.db.query(Barber).filter(Barber.business_id == self.business.id).all()
        barber_names = [b.name for b in barbers]
        today = datetime.date.today()
        days_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        
        current_data = self.flow_manager.get_data(customer)
        history = current_data.get("history", [])
        
        # Append User Message
        history.append({"role": "user", "content": message_body})
        if len(history) > 10: history = history[-10:]

        context = {
            "current_state": customer.conversation_state,
            "business_name": self.business.name,
            "today": today.strftime("%Y-%m-%d"),
            "day_name": days_es[today.weekday()],
            "barbers": barber_names,
            "history": history
        }

        # LLM Analysis
        try:
            analysis = llm_service.analyze_message(message_body, context)
            self._process_llm_response(customer, analysis, current_data, history, from_number)
            
        except Exception as e:
            logger.error(f"CRITICAL ERROR handling message: {e}", exc_info=True)
            self.flow_manager.update_state(customer, customer.conversation_state, current_data)
            whatsapp_service.send_message(self.phone_number_id, from_number, "Tuve un error interno 😵‍💫. Intenta con 'Menu'.")

    def _handle_interactive(self, customer, interactive_id, from_number):
        if interactive_id.startswith("time_"):
            time_str = interactive_id.split("_")[1]
            data = self.flow_manager.get_data(customer)
            self._confirm_time(customer, data, time_str)
            return

        if interactive_id.startswith("barber_"):
            self._handle_barber_selection(customer, interactive_id)
            return

        if interactive_id.startswith("date_"):
             if interactive_id == "date_today": self._handle_date_selection(customer, "hoy")
             elif interactive_id == "date_tomorrow": self._handle_date_selection(customer, "mañana")
             elif interactive_id == "date_other":
                  whatsapp_service.send_message(self.phone_number_id, from_number, "Escribe la fecha que prefieras (ej: 'El viernes')")
             return
         
        if interactive_id == "confirm_yes":
            self._finalize_booking(customer)
            return
            
        if interactive_id == "confirm_no":
            self.flow_manager.update_state(customer, CustomerData.IDLE, {})
            whatsapp_service.send_message(self.phone_number_id, from_number, "Cancelado. ¿En qué más puedo ayudarte?")
            return
            
        if interactive_id.startswith("rem_cancel_"):
            appt_id = int(interactive_id.split("_")[2])
            if self.booking_service.cancel_appointment(appt_id):
                 whatsapp_service.send_message(self.phone_number_id, from_number, "Tu cita ha sido cancelada correctamente.")
            else:
                 whatsapp_service.send_message(self.phone_number_id, from_number, "No encontré esa cita.")
            return

        if interactive_id.startswith("page_"):
             self._handle_pagination(customer, interactive_id)
             return

    def _process_llm_response(self, customer, analysis, current_data, history, from_number):
        intent = analysis.get("intent", "UNKNOWN")
        extracted = analysis.get("extracted", {})
        reply = analysis.get("reply", "No entendí.")
        
        # Guard clause for empty/malformed analysis
        if not isinstance(extracted, dict): extracted = {}

        history.append({"role": "assistant", "content": reply})
        current_data["history"] = history
        
        logger.info(f"Intent: {intent} | Extracted: {extracted}")

        if intent == "FALLBACK":
             whatsapp_service.send_message(self.phone_number_id, from_number, "Problemas de conexión 🧠.")
             self._send_welcome_menu(customer)
             return

        if intent == "PROVIDE_NAME" or (customer.conversation_state == "ASK_NAME" and len(reply) > 2): # Heuristic
            name = extracted.get("customer_name") or reply # Simplification
            customer.name = name
            self.flow_manager.update_state(customer, CustomerData.IDLE, {})
            whatsapp_service.send_message(self.phone_number_id, from_number, f"Gracias {name}.")
            return

        elif intent == "CHITCHAT":
             whatsapp_service.send_message(self.phone_number_id, from_number, reply)
             if any(k in reply.lower() for k in ["adios", "bye", "chao"]): # Loose check
                  self.flow_manager.update_state(customer, CustomerData.IDLE, {})
             else:
                  self.flow_manager.update_state(customer, customer.conversation_state, current_data)
             return

        elif intent == "BOOK_APPOINTMENT":
            self._process_booking_intent(customer, extracted, current_data, from_number, reply)
            
        elif intent == "CONFIRM_APPOINTMENT":
             if customer.conversation_state == CustomerData.CONFIRM_BOOKING:
                  self._finalize_booking(customer)
             else:
                  self.flow_manager.update_state(customer, customer.conversation_state, current_data)
                  whatsapp_service.send_message(self.phone_number_id, from_number, "No hay cita pendiente.")

        elif intent == "CANCEL_INTENT":
             # List active appointments to cancel
             appts = self.db.query(Appointment).filter(
                 Appointment.customer_id == customer.id, 
                 Appointment.status == AppointmentStatus.CONFIRMED,
                 Appointment.start_time > datetime.datetime.utcnow()
             ).all()
             
             if not appts:
                 whatsapp_service.send_message(self.phone_number_id, from_number, "No tienes citas activas para cancelar.")
             else:
                 msg = "Selecciona la cita que deseas cancelar:"
                 buttons = []
                 for appt in appts[:3]: # Limit 3
                     display = appt.start_time.strftime("%d/%m %H:%M")
                     buttons.append({"id": f"rem_cancel_{appt.id}", "title": display})
                 whatsapp_service.send_interactive_button(self.phone_number_id, from_number, msg, buttons)
                 self.flow_manager.update_state(customer, CustomerData.IDLE, {})

        else:
            self.flow_manager.update_state(customer, customer.conversation_state, current_data)
            whatsapp_service.send_message(self.phone_number_id, from_number, reply)
            if intent == "UNKNOWN": self._send_welcome_menu(customer)

    def _process_booking_intent(self, customer, extracted, data, from_number, reply):
        # Update Data
        if extracted.get("barber_name"):
            barbers = self.db.query(Barber).filter(Barber.business_id == self.business.id).all()
            found = next((b for b in barbers if b.name.lower() == extracted["barber_name"].lower()), None)
            if found: data["barber_id"] = found.id
        
        if extracted.get("date"): data["date"] = extracted["date"]
        if extracted.get("time"): data["time"] = extracted["time"]
        if extracted.get("time_period"): data["time_period"] = extracted["time_period"]

        self.flow_manager.update_state(customer, CustomerData.SELECT_BARBER, data)

        # Validation
        if "barber_id" not in data:
            msg = "¿Con quién te gustaría agendar?"
            barbers = self.db.query(Barber).filter(Barber.business_id == self.business.id).all()
            buttons = [{"id": f"barber_{b.id}", "title": b.name} for b in barbers[:3]]
            whatsapp_service.send_interactive_button(self.phone_number_id, from_number, msg, buttons)
            return

        if "date" not in data:
            whatsapp_service.send_message(self.phone_number_id, from_number, "¿Para qué fecha?")
            self.flow_manager.update_state(customer, CustomerData.SELECT_DATE, data)
            return

        # Availability Check
        try:
            target_date = datetime.datetime.strptime(data["date"], "%Y-%m-%d").date()
        except ValueError:
            whatsapp_service.send_message(self.phone_number_id, from_number, "Fecha inválida.")
            return

        slots = self.booking_service.get_available_slots(data["barber_id"], target_date)
        if data.get("time_period"):
            slots = self.booking_service.filter_slots_by_period(slots, data["time_period"])

        if not slots:
             whatsapp_service.send_message(self.phone_number_id, from_number, "No hay disponibilidad.")
             return

        if "time" in data:
            target_h = int(data["time"].split(":")[0])
            matched = next((s for s in slots if s.hour == target_h), None)
            if matched:
                self._confirm_time(customer, data, matched.strftime("%H:%M"))
            else:
                 self._send_slot_menu(customer, target_date, slots, header=f"A las {target_h} no se puede. Mira estos:")
        else:
            self._send_slot_menu(customer, target_date, slots)

    def _send_welcome_menu(self, customer, page=0, message_body=None):
        barbers = self.db.query(Barber).filter(Barber.business_id == self.business.id).all()
        start = page * 2; end = start + 2
        batch = barbers[start:end]
        
        buttons = []
        for b in batch: buttons.append({"id": f"barber_{b.id}", "title": b.name})
        
        msg = message_body if message_body else f"Hola {customer.name or 'amigo'}! Bienvenido a *{self.business.name}*."
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)
        self.flow_manager.update_state(customer, CustomerData.SELECT_BARBER, {"page": page})

    def _handle_barber_selection(self, customer, interactive_id):
        b_id = int(interactive_id.split("_")[1])
        data = self.flow_manager.get_data(customer)
        data["barber_id"] = b_id
        
        self.flow_manager.update_state(customer, CustomerData.SELECT_DATE, data)
        barber = self.db.query(Barber).filter(Barber.id == b_id).first()
        
        msg = f"Has elegido a *{barber.name}*. ¿Para qué día?"
        buttons = [{"id": "date_today", "title": "Hoy"}, {"id": "date_tomorrow", "title": "Mañana"}]
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _handle_date_selection(self, customer, date_alias):
        target_date = datetime.date.today()
        if "mañana" in date_alias: target_date += datetime.timedelta(days=1)
        
        data = self.flow_manager.get_data(customer)
        if "barber_id" not in data:
             self._send_welcome_menu(customer)
             return

        slots = self.booking_service.get_available_slots(data["barber_id"], target_date)
        if not slots:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "Sin disponibilidad.")
             return

        self._send_slot_menu(customer, target_date, slots)

    def _send_deterministic_fallback(self, customer):
        msg = f"Hola {customer.name or 'amigo'}. Para ayudarte, por favor selecciona una opción del menú 👇"
        self._send_welcome_menu(customer, message_body=msg)

    def _send_slot_menu(self, customer, target_date, slots, page=0, header=None):
        start = page * 3 # limit 3 for buttons
        limit = 3 if (len(slots) - start) <= 3 else 2
        subset = slots[start : start + limit]
        
        buttons = []
        for slot in subset:
            time_str = slot.strftime("%H:%M")
            display = slot.strftime("%I:%M%p").lower().lstrip("0")
            buttons.append({"id": f"time_{time_str}", "title": display})
            
        if len(slots) - start > 3:
             buttons.append({"id": f"page_{page+1}", "title": "Ver más ⬇️"})

        msg = header if header else f"Horarios para el {target_date.strftime('%d/%m')}:"
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)
        
        data = self.flow_manager.get_data(customer)
        data["last_slots_date"] = target_date.strftime("%Y-%m-%d") # Cache for pagination
        self.flow_manager.update_state(customer, CustomerData.SELECT_SLOT, data)

    def _handle_pagination(self, customer, interactive_id):
        page = int(interactive_id.split("_")[1])
        data = self.flow_manager.get_data(customer)
        
        if "last_slots_date" not in data: return
        target_date = datetime.datetime.strptime(data["last_slots_date"], "%Y-%m-%d").date()
        
        slots = self.booking_service.get_available_slots(data["barber_id"], target_date)
        if data.get("time_period"):
            slots = self.booking_service.filter_slots_by_period(slots, data["time_period"])
            
        self._send_slot_menu(customer, target_date, slots, page=page)

    def _confirm_time(self, customer, data, time_str):
        data["time"] = time_str
        self.flow_manager.update_state(customer, CustomerData.CONFIRM_BOOKING, data)
        barber = self.db.query(Barber).filter(Barber.id == data["barber_id"]).first()
        
        msg = f"Resumen:\nB: {barber.name}\nD: {data['date']}\nH: {time_str}\n\n¿Confirmar?"
        buttons = [{"id": "confirm_yes", "title": "Si"}, {"id": "confirm_no", "title": "No"}]
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _finalize_booking(self, customer):
        data = self.flow_manager.get_data(customer)
        appt = self.booking_service.create_appointment(customer, data["barber_id"], data["date"], data["time"])
        
        if appt:
             self.flow_manager.update_state(customer, CustomerData.IDLE, {})
             whatsapp_service.send_message(self.phone_number_id, customer.phone, f"✅ Cita confirmada!")
        else:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "Error al crear la cita.")
