import json
import datetime
from sqlalchemy.orm import Session
from app.models.models import Customer, Business, Barber, CustomerData, Appointment, AppointmentStatus
from app.services.whatsapp_service import whatsapp_service
from app.services.calendar_service import calendar_service
from app.services.llm_service import llm_service
from app.core.logging_config import logger

class ConversationService:
    def __init__(self, db: Session, phone_number_id: str):
        self.db = db
        self.phone_number_id = phone_number_id
        self.business = db.query(Business).filter(Business.phone_number_id == phone_number_id).first()

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

        # Context Building
        barbers = self.db.query(Barber).filter(Barber.business_id == self.business.id).all()
        barber_names = [b.name for b in barbers]
        
        today = datetime.date.today()
        # Spanish day name map
        days_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        
        context = {
            "current_state": customer.conversation_state,
            "business_name": self.business.name,
            "today": today.strftime("%Y-%m-%d"),
            "day_name": days_es[today.weekday()],
            "barbers": barber_names
        }

        # Handling Interactive payloads purely as shortcuts (bypass LLM if specific ID)
        if interactive_id:
             if interactive_id.startswith("time_"):
                self._handle_slot_selection(customer, interactive_id) 
                return
             if interactive_id.startswith("barber_"):
                self._handle_barber_selection(customer, interactive_id)
                return
             if interactive_id.startswith("date_"):
                 # Handle date shortcuts
                 if interactive_id == "date_today": self._handle_date_selection(customer, "hoy")
                 elif interactive_id == "date_tomorrow": self._handle_date_selection(customer, "mañana")
                 elif interactive_id == "date_other":
                      whatsapp_service.send_message(self.phone_number_id, from_number, "Escribe la fecha que prefieras (ej: 'El viernes')")
                 return
             
             if interactive_id == "confirm_yes":
                self._finalize_booking(customer)
                return
             if interactive_id == "confirm_no":
                self._update_state(customer, CustomerData.IDLE, {})
                whatsapp_service.send_message(self.phone_number_id, from_number, "Cancelado. ¿En qué más puedo ayudarte?")
                return
                
             # Reminder Actions
             if interactive_id.startswith("rem_confirm_"):
                 appt_id = int(interactive_id.split("_")[2])
                 # Logic to mark confirmed? For now, just say thanks.
                 # Ideally update status to 'RECONFIRMED' if model supports it, or just log it.
                 logger.info(f"Appointment {appt_id} confirmed by user.")
                 whatsapp_service.send_message(self.phone_number_id, from_number, "¡Gracias! Tu asistencia ha sido confirmada. Nos vemos. 💈")
                 return
                 
             if interactive_id.startswith("rem_cancel_"):
                 appt_id = int(interactive_id.split("_")[2])
                 # Cancel appointment
                 appt = self.db.query(Appointment).filter(Appointment.id == appt_id).first()
                 if appt:
                     appt.status = AppointmentStatus.CANCELLED
                     # Remove from GCal?
                     if appt.google_event_id and appt.barber.calendar_id:
                          calendar_service.delete_event(appt.barber.calendar_id, appt.google_event_id)
                     self.db.commit()
                     whatsapp_service.send_message(self.phone_number_id, from_number, "Tu cita ha sido cancelada correctamente.")
                 else:
                     whatsapp_service.send_message(self.phone_number_id, from_number, "No encontré esa cita, pero no te preocupes.")
                 return
                 
             if interactive_id.startswith("rem_reschedule_"):
                  # Trigger reschedule flow
                  # Use LLM context or manual flow? Manual is safer.
                  # Just send them to select date again.
                  whatsapp_service.send_message(self.phone_number_id, from_number, "Claro, busquemos otro horario. ¿Para qué fecha te gustaría?")
                  # Need to know which barber? Assuming current context or ask again.
                  # Safer: Update state to SELECT_DATE if we know barber, else IDLE.
                  # Try to get barber from appt if possible, but simpler to just ask date and let NLU pick it up or button flow.
                  self._update_state(customer, CustomerData.IDLE, {}) # Reset to let them talk naturally
                  return

        # 2. Fast Path (Bypass LLM for basic actions)
        low_body = message_body.lower().strip()
        keywords = ["hola", "menu", "inicio", "empezar", "reset", "cancelar"]
        if any(low_body == k for k in keywords):
            logger.info(f"FAST PATH Triggered: {low_body}")
            self._update_state(customer, CustomerData.IDLE, {})
            self._send_welcome_menu(customer)
            return

        # Prepare Context & History
        # Load conversation data to get history
        current_data = self._get_data(customer)
        history = current_data.get("history", [])
        
        # Append User Message
        history.append({"role": "user", "content": message_body})
        # Keep only last 10 messages to avoid token bloat
        if len(history) > 10: history = history[-10:]

        context["history"] = history

        # LLM Analysis
        try:
            logger.info("Calling LLM...")
            analysis = llm_service.analyze_message(message_body, context)
            
            # Guard: Ensure analysis is a dict (LLM might return a list)
            if isinstance(analysis, list):
                analysis = analysis[0] if analysis else {}
            if not isinstance(analysis, dict):
                analysis = {}
                
            intent = analysis.get("intent", "UNKNOWN")
            extracted = analysis.get("extracted", {})
            
            # Guard: Ensure extracted is a dict
            if isinstance(extracted, list):
                extracted = {}
            reply = analysis.get("reply", "No entendí.")
            
            # Append Assistant Reply to History
            history.append({"role": "assistant", "content": reply})
            current_data["history"] = history
            
            logger.info(f"LLM RESULT: Intent={intent} | Extracted={extracted}")
            
            # 3. Handle Fallback (LLM Down/RateLimit)
            if intent == "FALLBACK" or intent == "OFFLINE":
                 whatsapp_service.send_message(self.phone_number_id, from_number, "Estoy teniendo problemas de conexión con mi cerebro 🧠. Pero aquí tienes el menú:")
                 self._send_welcome_menu(customer)
                 return
    
            # Intent Routing
            if intent == "PROVIDE_NAME" or (customer.conversation_state == "ASK_NAME" and len(message_body) > 2):
                # Special case for name
                name = extracted.get("customer_name") or message_body
                customer.name = name
                self._update_state(customer, CustomerData.IDLE, {})
                whatsapp_service.send_message(self.phone_number_id, from_number, f"Gracias {name}. ¿En qué te ayudo hoy?")
                return
    
            elif intent == "CHITCHAT":
                 whatsapp_service.send_message(self.phone_number_id, from_number, reply)
                 # Heuristic: If reply indicates closure or user said bye/thanks, clear history to be clean.
                 # Simple check on user body or intent subtype (not available).
                 # Check against keywords in message_body
                 closing_keywords = ["gracias", "adios", "bye", "chao", "hasta luego", "listo"]
                 if any(k in message_body.lower() for k in closing_keywords):
                      logger.info("Closing conversation (CHITCHAT). Clearing history.")
                      self._update_state(customer, CustomerData.IDLE, {})
                 else:
                      self._update_state(customer, customer.conversation_state, current_data) # Save history
                 return
    
            elif intent == "BOOK_APPOINTMENT":
                # 1. Update Conversation Data with what we found
                current_data = self._get_data(customer)
                
                # Barber?
                if extracted.get("barber_name"):
                    # Find ID
                    found = next((b for b in barbers if b.name.lower() == extracted["barber_name"].lower()), None)
                    if found: current_data["barber_id"] = found.id
                
                # Date?
                if extracted.get("date"):
                    current_data["date"] = extracted["date"]
                
                # Time?
                if extracted.get("time"):
                    current_data["time"] = extracted["time"]
                
                # Period? (Morning/Afternoon)
                if extracted.get("time_period"):
                    current_data["time_period"] = extracted["time_period"]
    
                self._update_state(customer, CustomerData.SELECT_BARBER, current_data) # Intermediate state
    
                # 2. Validation Flow
                if "barber_id" not in current_data:
                    # Ask based on LLM reply or default
                    msg = reply if "barbero" in reply.lower() else "¿Con quién te gustaría agendar?"
                    # Send buttons
                    buttons = [{"id": f"barber_{b.id}", "title": b.name} for b in barbers[:3]]
                    whatsapp_service.send_interactive_button(self.phone_number_id, from_number, msg, buttons)
                    return
                    
                if "date" not in current_data:
                    # Ask date
                    whatsapp_service.send_message(self.phone_number_id, from_number, "Entendido. ¿Para qué fecha lo necesitas?")
                    self._update_state(customer, CustomerData.SELECT_DATE, current_data)
                    return
    
                # Check Availability with Date
                try:
                    target_date = datetime.datetime.strptime(current_data["date"], "%Y-%m-%d").date()
                except ValueError:
                    # Date parsing failed?
                    whatsapp_service.send_message(self.phone_number_id, from_number, "La fecha no es válida. ¿Podrías decirla de nuevo? (Ej: Mañana)")
                    return

                available_slots = self._get_available_slots(current_data["barber_id"], target_date)
                
                # Filter by Time Period if set
                period = current_data.get("time_period")
                if period == "morning":
                    available_slots = [s for s in available_slots if s.hour < 12]
                elif period == "afternoon":
                    available_slots = [s for s in available_slots if s.hour >= 12 and s.hour < 18]
                elif period == "evening":
                    available_slots = [s for s in available_slots if s.hour >= 18]

                if not available_slots:
                    msg = "Ese día no hay disponibilidad."
                    if period: msg = f"No hay horarios disponibles en la {period.replace('morning','mañama').replace('afternoon','tarde').replace('evening','noche')} para ese día."
                    whatsapp_service.send_message(self.phone_number_id, from_number, msg)
                    return
    
                if "time" in current_data:
                    # Verify exact slot
                    target_h = int(current_data["time"].split(":")[0])
                    
                    # Loose matching (just hour)
                    matched = next((s for s in available_slots if s.hour == target_h), None)
                    if matched:
                        # Success -> Confirm
                        self._confirm_time(customer, current_data, matched.strftime("%H:%M"))
                    else:
                        # Slot busy -> Show options
                         self._send_slot_menu(customer, target_date, available_slots, header=f"A las {current_data['time']} está ocupado. Mira estos horarios:")
                else:
                    # No time -> Show options
                    self._send_slot_menu(customer, target_date, available_slots)
            
            elif intent == "CONFIRM_APPOINTMENT":
                 if customer.conversation_state == CustomerData.CONFIRM_BOOKING:
                      self._finalize_booking(customer)
                 else:
                      self._update_state(customer, customer.conversation_state, current_data) # Save history
                      whatsapp_service.send_message(self.phone_number_id, from_number, "No hay ninguna cita pendiente de confirmar. ¿Quieres agendar una nueva?")
                 return

            else:
                # Fallback for UNKNOWN or other intents
                self._update_state(customer, customer.conversation_state, current_data) # Save history
                whatsapp_service.send_message(self.phone_number_id, from_number, reply)
                if intent == "UNKNOWN":
                     self._send_welcome_menu(customer)
        
        except Exception as e:
            logger.error(f"CRITICAL ERROR handling message: {e}", exc_info=True)
            self._update_state(customer, customer.conversation_state, current_data) # Save history (even on error if possible)
            whatsapp_service.send_message(self.phone_number_id, from_number, "Tuve un error interno 😵‍💫. ¿Podrías intentar de nuevo o escribir 'Menu'?")


    # --- Helpers (Stripped down) ---
    def _update_state(self, customer, new_state, data):
        customer.conversation_state = new_state
        # Ensure we don't accidentally nest JSON strings
        if isinstance(data, str):
             try: data = json.loads(data)
             except: pass
        customer.conversation_data = json.dumps(data)
        self.db.commit()

    def _get_data(self, customer):
        try: return json.loads(customer.conversation_data)
        except: return {}

    def _get_business_hours(self, target_date):
        start_h, end_h = 9, 18
        if self.business.schedule:
            try:
                schedule = json.loads(self.business.schedule)
                day_key = str(target_date.weekday())
                if day_key in schedule:
                    start_h = schedule[day_key].get("start", 9)
                    end_h = schedule[day_key].get("end", 18)
            except: pass
        return start_h, end_h

    def _get_available_slots(self, barber_id, target_date):
        barber = self.db.query(Barber).filter(Barber.id == barber_id).first()
        open_h, close_h = self._get_business_hours(target_date)

        day_start = datetime.datetime(target_date.year, target_date.month, target_date.day, open_h, 0, 0)
        day_end = datetime.datetime(target_date.year, target_date.month, target_date.day, close_h, 0, 0)

        busy_intervals = []
        if barber.calendar_id:
             busy_intervals = calendar_service.get_busy_slots(barber.calendar_id, day_start, day_end)

        available_slots = []
        current_slot = day_start
        while current_slot < day_end:
            slot_end = current_slot + datetime.timedelta(hours=1)
            is_free = True
            for b_start_str, b_end_str in busy_intervals:
                try:
                    b_start = datetime.datetime.fromisoformat(b_start_str.replace("Z", "+00:00"))
                    b_end = datetime.datetime.fromisoformat(b_end_str.replace("Z", "+00:00"))
                    
                    slot_start_aware = current_slot.replace(tzinfo=datetime.timezone.utc)
                    slot_end_aware = slot_end.replace(tzinfo=datetime.timezone.utc)
                    
                    if (slot_start_aware < b_end) and (slot_end_aware > b_start):
                        is_free = False; break
                except: is_free = False
            
            if is_free: available_slots.append(current_slot)
            current_slot = slot_end
        return available_slots

    def _send_slot_menu(self, customer, target_date, slots, page=0, header=None):
        ITEMS_PER_PAGE = 3
        start = page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        subset = slots[start:end]
        
        buttons = []
        for slot in subset:
            time_str = slot.strftime("%H:%M")
            display_str = slot.strftime("%I:%M%p").lower().lstrip("0")
            buttons.append({"id": f"time_{time_str}", "title": f"{display_str}"})
            
        msg = header if header else f"Horarios libres para el {target_date.strftime('%d/%m')}:"
        if not buttons:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "No hay mas horarios disponibles.")
             return

        # Improved Date Formatting
        days_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        months_es = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        day_str = days_es[target_date.weekday()]
        month_str = months_es[target_date.month]
        nice_date = f"{day_str} {target_date.day} de {month_str}"

        msg = header if header else f"Horarios libres para el {nice_date}:"

        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)
        
        # Pagination Logic
        if end < len(slots):
             # We should attach a "Next" button in a separate message or as part of the list?
             # Interactive buttons limit is 3. We usually used 3 slots.
             # If we want pagination, we might need to send 2 slots + 1 "Next" button, OR send a separate menu.
             # Current code sends up to 3 slots.
             pass 
             
        # Correction: To support pagination with WhatsApp buttons (limit 3), we need a strategy.
        # Strategy: display 2 slots + "Ver más" if there are more.
        
        # Let's re-do the list slice for pagination support
        buttons = []
        
        # Check if we need pagination (more items than page size)
        # We can show 3 items if that's all. If more, show 2 + Next.
        remaining = len(slots) - start
        
        limit = 3
        if remaining > 3:
            limit = 2
            
        subset = slots[start : start + limit]
        
        for slot in subset:
            time_str = slot.strftime("%H:%M")
            display_str = slot.strftime("%I:%M%p").lower().lstrip("0")
            buttons.append({"id": f"time_{time_str}", "title": f"{display_str}"})
            
        if remaining > 3:
             buttons.append({"id": f"page_{page+1}", "title": "Ver más ⬇️"})
             
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)
        
        # Save state so pagination works if added later
        data = self._get_data(customer); data["date"] = target_date.strftime("%Y-%m-%d"); data["barber_id"]=data.get("barber_id")
        self._update_state(customer, CustomerData.SELECT_SLOT, data)

    def _handle_slot_selection(self, customer, input_data):
        # Fallback for button clicks
        if isinstance(input_data, str):
            if input_data.startswith("time_"):
                parts = input_data.split("_")
                time_str = parts[1]
                data = self._get_data(customer)
                self._confirm_time(customer, data, time_str)
            elif input_data.startswith("page_"):
                # Handle Pagination
                page = int(input_data.split("_")[1])
                data = self._get_data(customer)
                # Re-fetch slots? Ideally we persist the available slots or re-fetch.
                # Re-fetching is safer/stateless.
                # We need date and barber from data.
                target_date = datetime.datetime.strptime(data["date"], "%Y-%m-%d").date()
                barber_id = data.get("barber_id")
                # Need to apply same filters (period)?
                # Simplification: just re-fetch all for day. 
                # (Refining: if we filtered by period, we lose that state unless saved. 
                #  Let's persist 'time_period' in data so we can re-filter)
                
                available_slots = self._get_available_slots(barber_id, target_date)
                
                # Re-filter 
                period = data.get("time_period")
                if period == "morning":
                    available_slots = [s for s in available_slots if s.hour < 12]
                elif period == "afternoon":
                    available_slots = [s for s in available_slots if s.hour >= 12 and s.hour < 18]
                elif period == "evening":
                    available_slots = [s for s in available_slots if s.hour >= 18]

                self._send_slot_menu(customer, target_date, available_slots, page=page)

    def _confirm_time(self, customer, data, time_str):
        data["time"] = time_str
        self._update_state(customer, CustomerData.CONFIRM_BOOKING, data)
        barber = self.db.query(Barber).filter(Barber.id == data["barber_id"]).first()
        
        dt_obj = datetime.datetime.strptime(time_str, "%H:%M")
        display_time = dt_obj.strftime("%I:%M %p").lstrip("0")
        
        msg = f"*Confirma tu cita:*\n\nPro: {barber.name}\nDia: {data['date']}\nHora: {display_time}\n\nTe parece bien?"
        buttons = [{"id": "confirm_yes", "title": "Si, confirmar"}, {"id": "confirm_no", "title": "Cancelar"}]
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _finalize_booking(self, customer):
        data = self._get_data(customer)
        if "barber_id" not in data: return
        
        barber = self.db.query(Barber).filter(Barber.id == data["barber_id"]).first()
        
        date_parts = list(map(int, data["date"].split("-")))
        time_parts = list(map(int, data["time"].split(":")))
        start_time = datetime.datetime(date_parts[0], date_parts[1], date_parts[2], time_parts[0], time_parts[1])
        end_time = start_time + datetime.timedelta(hours=1)
        summary = f"Cita: {customer.name} - {customer.phone}"
        
        if barber.calendar_id: calendar_service.create_event(barber.calendar_id, summary, start_time, end_time)
        business = self.db.query(Business).filter(Business.id == barber.business_id).first()
        if business and business.calendar_id: calendar_service.create_event(business.calendar_id, f"[{barber.name}] {summary}", start_time, end_time)

        new_appointment = Appointment(customer_id=customer.id, barber_id=barber.id, start_time=start_time, end_time=end_time, status="confirmed", google_event_id="dual_created")
        self.db.add(new_appointment)
        
        display_time = start_time.strftime("%I:%M %p").lstrip("0")
        
        self._update_state(customer, CustomerData.IDLE, {})
        whatsapp_service.send_message(self.phone_number_id, customer.phone, f"✅ Cita Confirmada con {barber.name} el {data['date']} a las {display_time}!")

    def _send_welcome_menu(self, customer, page=0):
        barbers = self.db.query(Barber).filter(Barber.business_id == self.business.id).all()
        if not barbers:
            whatsapp_service.send_message(self.phone_number_id, customer.phone, "Lo sentimos, no hay barberos disponibles.")
            return

        ITEMS_PER_PAGE = 2 
        start = page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        current_batch = barbers[start:end]
        
        buttons = []
        for b in current_batch:
            buttons.append({"id": f"barber_{b.id}", "title": f"{b.name}"})

        msg = f"Hola {customer.name or 'amigo'}! Bienvenido a *{self.business.name}*.\n\nSoy tu asistente virtual. ¿Con qué profesional te gustaría agendar hoy?"
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)
        self._update_state(customer, CustomerData.SELECT_BARBER, {"page": page})

    def _handle_barber_selection(self, customer, interactive_id):
        if interactive_id.startswith("page_"):
            next_page = int(interactive_id.split("_")[1])
            self._send_welcome_menu(customer, page=next_page)
            return

        b_id = int(interactive_id.split("_")[1])
        data = self._get_data(customer)
        data["barber_id"] = b_id
        
        self._update_state(customer, CustomerData.SELECT_DATE, data)
        barber = self.db.query(Barber).filter(Barber.id == b_id).first()
        
        msg = f"Has elegido a *{barber.name}*. Excelente!\n\n¿Para qué día te gustaría la cita?"
        buttons = [
            {"id": "date_today", "title": "Hoy"},
            {"id": "date_tomorrow", "title": "Mañana"},
            {"id": "date_other", "title": "Otra fecha"}
        ]
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _handle_date_selection(self, customer, date_str):
        clean_date_str = str(date_str)
        # Assuming simple mapping for now since it's button driven usually
        target_date = datetime.date.today()
        if "manana" in clean_date_str or "mañana" in clean_date_str:
            target_date = target_date + datetime.timedelta(days=1)
            
        # For now, just show slots for that date
        data = self._get_data(customer)
        if "barber_id" not in data:
             self._update_state(customer, CustomerData.IDLE, {})
             self._send_welcome_menu(customer)
             return

        available_slots = self._get_available_slots(data["barber_id"], target_date)
        if not available_slots:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "Ese dia no hay disponibilidad.")
             return

        self._send_slot_menu(customer, target_date, available_slots)
        data["date"] = target_date.strftime("%Y-%m-%d")
        self._update_state(customer, CustomerData.SELECT_SLOT, data)
