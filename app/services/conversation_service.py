import json
import datetime
from sqlalchemy.orm import Session
from app.models.models import Customer, Business, Barber, CustomerData, Appointment, AppointmentStatus
from app.services.whatsapp_service import whatsapp_service
from app.services.calendar_service import calendar_service
import dateparser
from app.utils.nlp import correct_typos

class ConversationService:
    def __init__(self, db: Session, phone_number_id: str):
        self.db = db
        self.phone_number_id = phone_number_id
        # Context: Identify Business
        self.business = db.query(Business).filter(Business.phone_number_id == phone_number_id).first()

    def handle_incoming_message(self, from_number: str, message_body: str, message_type: str = "text", interactive_id: str = None):
        if not self.business:
            print(f"ErrorContext: No business found for {self.phone_number_id}")
            return

        # 1. Get or Create Customer
        customer = self.db.query(Customer).filter(Customer.phone == from_number).first()
        if not customer:
            # Multi-tenancy: default name is None or generic, we trigger ASK_NAME later
            customer = Customer(phone=from_number, name="Cliente Nuevo")
            self.db.add(customer)
            self.db.commit()
            print(f"Created new customer: {from_number}")

        # State Machine Logic
        state = customer.conversation_state
        print(f"DEBUG: Processing message from {from_number} in state {state}")

        # RESET COMMAND (For testing)
        if message_type == "text" and message_body.lower() in ["reset", "hola", "inicio", "menu"]:
            self._update_state(customer, CustomerData.IDLE, {})
            self._send_welcome_menu(customer)
            return

        # GLOBAL INTERACTIVE HANDLERS (Stateless guards)
        # Fix for pagination buttons falling through if state is somehow wrong
        if interactive_id and interactive_id.startswith("slotpage_"):
            self._handle_slot_selection(customer, interactive_id)
            return
        if interactive_id and interactive_id.startswith("page_"):
            self._handle_barber_selection(customer, interactive_id)
            return
            
        # Reminder Actions
        if interactive_id and any(interactive_id.startswith(x) for x in ["rem_confirm_", "rem_reschedule_", "rem_cancel_"]):
            self._handle_reminder_action(customer, interactive_id)
            return

        if state == "ASK_NAME":
            # Save Name
            name = message_body.strip()
            if len(name) < 2:
                whatsapp_service.send_message(self.phone_number_id, from_number, "Por favor, escribe tu nombre real para poder atenderte mejor.")
                return
            
            customer.name = name
            self._update_state(customer, CustomerData.IDLE, {})
            whatsapp_service.send_message(self.phone_number_id, from_number, f"Un gusto, {name}! Ahora si, empecemos.")
            self._send_welcome_menu(customer)
            return

        if state == CustomerData.IDLE:
            # CHECK NAME FIRST
            if customer.name == "Cliente Nuevo" or not customer.name:
                 self._update_state(customer, "ASK_NAME", {})
                 whatsapp_service.send_message(self.phone_number_id, from_number, "Hola! 👋 Antes de empezar, ¿cual es tu nombre?")
                 return

            # SILENT MODE: Only respond to keywords
            keywords = ["hola", "menu", "inicio", "agendar", "cita", "buenos", "buenas"]
            if any(k in message_body.lower() for k in keywords) or interactive_id:
                self._send_welcome_menu(customer)
            else:
                # Do nothing (Silent)
                print(f"Ignored non-keyword message in IDLE: {message_body}")
                pass
        
        elif state == CustomerData.SELECT_BARBER:
            if interactive_id:
                self._handle_barber_selection(customer, interactive_id)
            else:
                whatsapp_service.send_message(self.phone_number_id, from_number, "Por favor, selecciona una opción del menú de barberos.")

        elif state == CustomerData.SELECT_DATE:
            # Simple text input for date YYYY-MM-DD
            self._handle_date_selection(customer, message_body)

        elif state == CustomerData.SELECT_SLOT:
            # Allow both interactivity and text
            if interactive_id:
                self._handle_slot_selection(customer, interactive_id)
            else:
                # Text input (e.g. "2pm")
                self._handle_slot_selection(customer, message_body)

        elif state == CustomerData.CONFIRM_BOOKING:
            if interactive_id == "confirm_yes":
                self._finalize_booking(customer)
            else:
                self._update_state(customer, CustomerData.IDLE, {})
                whatsapp_service.send_message(self.phone_number_id, from_number, "Reserva cancelada.")

    # --- Helpers ---
    def _update_state(self, customer, new_state, data):
        customer.conversation_state = new_state
        customer.conversation_data = json.dumps(data)
        self.db.commit()

    def _get_data(self, customer):
        return json.loads(customer.conversation_data)

    def _get_available_slots(self, barber_id, target_date):
        barber = self.db.query(Barber).filter(Barber.id == barber_id).first()
        # Dynamic Business Hours
        open_h = self.business.open_hour if self.business and self.business.open_hour is not None else 9
        close_h = self.business.close_hour if self.business and self.business.close_hour is not None else 18

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
                    if slot_start_aware < b_end and slot_end_aware > b_start:
                        is_free = False; break
                except: is_free = False
            if is_free: available_slots.append(current_slot)
            current_slot = slot_end
        return available_slots

    # --- Actions ---
    def _send_welcome_menu(self, customer, page=0):
        # List Barbers
        print(f"DEBUG: Fetching barbers for business_id: {self.business.id if self.business else 'None'}")
        barbers = self.db.query(Barber).filter(Barber.business_id == self.business.id).all()
        print(f"DEBUG: Found {len(barbers)} barbers.")
        
        if not barbers:
            print("DEBUG: No barbers found, sending apology.")
            whatsapp_service.send_message(self.phone_number_id, customer.phone, "Lo sentimos, no hay barberos disponibles en este momento. Intenta mas tarde.")
            return

        ITEMS_PER_PAGE = 2 
        start = page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        current_batch = barbers[start:end]
        print(f"DEBUG: Showing page {page}, items {start} to {end}: {current_batch}")
        
        buttons = []
        for b in current_batch:
            buttons.append({"id": f"barber_{b.id}", "title": f"{b.name}"})

        if end < len(barbers):
            buttons.append({"id": f"page_{page+1}", "title": "Ver mas"})

        msg = f"Hola {customer.name or 'amigo'}! Bienvenido a *{self.business.name}*.\n\nSoy tu asistente virtual. Con que profesional te gustaria agendar hoy?"
        if page > 0: msg = "Aqui tienes mas profesionales disponibles:"

        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)
        self._update_state(customer, CustomerData.SELECT_BARBER, {"page": page})

    def _handle_reminder_action(self, customer, interactive_id):
        # Format: rem_action_id
        try:
            parts = interactive_id.split("_")
            # rem, action, id
            action = parts[1]
            appt_id = int(parts[2])
        except (IndexError, ValueError):
            print(f"Error parse reminder ID: {interactive_id}")
            return

        appt = self.db.query(Appointment).filter(Appointment.id == appt_id).first()
        
        if not appt:
            whatsapp_service.send_message(self.phone_number_id, customer.phone, "No encontre esa cita.")
            return

        if action == "confirm":
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "Gracias por confirmar. Nos vemos! 👋")
        
        elif action == "cancel":
             appt.status = AppointmentStatus.CANCELLED
             if appt.barber.calendar_id and appt.google_event_id:
                 # Ideally delete from GCal too (not implemented fully yet)
                 pass
             self.db.commit()
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "Cita cancelada correctamente.")
             # Notify Barber
             if appt.barber.phone:
                 whatsapp_service.send_message(self.phone_number_id, appt.barber.phone, f"⚠️ Cita Cancelada por Cliente:\n{customer.name} para el {appt.start_time}")

        elif action == "reschedule":
             # Cancel old
             appt.status = AppointmentStatus.CANCELLED
             self.db.commit()
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "Entendido, vamos a reagendar. ¿Para qué fecha la quieres ahora?")
             # Set state to SELECT_DATE. Need to prep data.
             # We need barber_id to continue
             data = {"barber_id": appt.barber_id}
             self._update_state(customer, CustomerData.SELECT_DATE, data)
             
             # Notify Barber
             if appt.barber.phone:
                 whatsapp_service.send_message(self.phone_number_id, appt.barber.phone, f"⚠️ El cliente {customer.name} está reagendando su cita del {appt.start_time}")

    def _handle_barber_selection(self, customer, interactive_id):
        if interactive_id.startswith("page_"):
            next_page = int(interactive_id.split("_")[1])
            self._send_welcome_menu(customer, page=next_page)
            return

        b_id = int(interactive_id.split("_")[1])
        data = self._get_data(customer)
        data["barber_id"] = b_id
        
        self._update_state(customer, CustomerData.SELECT_DATE, data)
        whatsapp_service.send_message(self.phone_number_id, customer.phone, "Excelente eleccion!\n\nPara que dia te gustaria la cita? \n\nPuedes decirme:\n- 'Hoy'\n- 'Manana'\n- 'El viernes'\n- O una fecha y hora completa: 'Manana a las 10am'")

    def _handle_date_selection(self, customer, date_str):
        clean_date_str = correct_typos(date_str)
        print(f"DEBUG: Date processing '{date_str}' -> '{clean_date_str}'")
        
        settings = {'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': datetime.datetime.now(), 'DATE_ORDER': 'DMY', 'RETURN_AS_TIMEZONE_AWARE': False}
        parsed_dt = dateparser.parse(clean_date_str, languages=['es'], settings=settings)
        
        if not parsed_dt:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "🤔 No entendí bien la fecha. ¿Podrías intentar de nuevo? \nEjemplo: 'Mañana', 'Lunes' o '20/01'.")
             return
             
        target_date = parsed_dt.date()
        if target_date < datetime.date.today():
             whatsapp_service.send_message(self.phone_number_id, customer.phone, f"La fecha {target_date} ya paso. Por favor elige una fecha futura.")
             return

        # 2. Advanced Time Logic
        has_time = False
        target_time = None
        
        # If input has time separators or keywords
        time_keywords = [":", "am", "pm", " a las ", "alas", " de la ", "media"]
        if any(x in clean_date_str.lower() for x in time_keywords):
             # Trust parser or re-parse only time if dateparser failed to catch time
             if parsed_dt.time() != datetime.time(0,0):
                 target_time = parsed_dt.time()
                 has_time = True
             else:
                 # Fallback: Try parsing just the string as time
                 # Sometimes "Hoy a las 2pm" parses date correctly but time as 00:00
                 # Let's try parsing just the time part? 
                 # dateparser is usually good. Let's force it to be smarter.
                 # Let's try parsing with 'PREFER_DAY_OF_MONTH' = 'current'
                 pass

        # Availability Check
        data = self._get_data(customer)
        available_slots = self._get_available_slots(data["barber_id"], target_date)

        if not available_slots:
             barber = self.db.query(Barber).filter(Barber.id == data["barber_id"]).first()
             whatsapp_service.send_message(self.phone_number_id, customer.phone, f"Lo siento, {barber.name} tiene la agenda llena el {target_date}. Podrias probar otro dia?")
             return

        if has_time:
            # Flexible Match (Hour only)
            user_hour = target_time.hour
            matched_slot = None
            for slot in available_slots:
                if slot.hour == user_hour:
                    matched_slot = slot; break
            
            if matched_slot:
                time_str = matched_slot.strftime("%H:%M")
                data["date"] = target_date.strftime("%Y-%m-%d")
                data["time"] = time_str
                self._update_state(customer, CustomerData.CONFIRM_BOOKING, data)
                barber = self.db.query(Barber).filter(Barber.id == data["barber_id"]).first()
                msg = f"Perfecto! Encontre disponibilidad.\n\n*Confirmar Cita:*\nPro: {barber.name}\nDia: {data['date']}\nHora: {time_str}\n\nAgendamos?"
                buttons = [{"id": "confirm_yes", "title": "Si, agendar"}, {"id": "confirm_no", "title": "Cancelar"}]
                whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)
                return
            else:
                 whatsapp_service.send_message(self.phone_number_id, customer.phone, f"Uff, a las {target_time.strftime('%H:%M')} no se puede. Pero mira lo que tengo libre:")
        
        self._send_slot_menu(customer, target_date, available_slots, page=0)
        data["date"] = target_date.strftime("%Y-%m-%d")
        self._update_state(customer, CustomerData.SELECT_SLOT, data)

    def _send_slot_menu(self, customer, target_date, slots, page=0):
        print(f"DEBUG: _send_slot_menu | Page: {page} | Total Slots: {len(slots)}")
        
        ITEMS_PER_PAGE = 2
        start = page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        print(f"DEBUG: Indices {start} to {end}")
        
        buttons = []
        subset = slots[start:end]
        print(f"DEBUG: Subset size: {len(subset)}")
        
        for slot in subset:
            time_str = slot.strftime("%H:%M")
            buttons.append({"id": f"time_{time_str}", "title": f"{time_str}"})
            
        if end < len(slots):
            print("DEBUG: Adding Next Button")
            buttons.append({"id": f"slotpage_{page+1}", "title": "Mas horas"})
            
        msg = f"Horarios libres para el {target_date}:\nSelecciona una hora:"
        if page > 0: msg = "Mas horarios disponibles:"
        
        if not buttons:
             print("ERROR: No buttons generated! sending error text.")
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "Error tecnico: No pude mostrar los horarios. Intenta 'hoy' o 'manana'.")
             return

        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _handle_slot_selection(self, customer, input_data):
        print(f"DEBUG: _handle_slot_selection input: {input_data}")
        # Determine if input is text or interactive_id
        data = self._get_data(customer)
        target_date = datetime.datetime.strptime(data["date"], "%Y-%m-%d").date()
        
        # 1. Pagination Check
        if isinstance(input_data, str) and input_data.startswith("slotpage_"):
            page = int(input_data.split("_")[1])
            print(f"DEBUG: Handle Slot Page {page}")
            # Ensure we fetch slots again
            available_slots = self._get_available_slots(data["barber_id"], target_date)
            print(f"DEBUG: Refetched {len(available_slots)} slots for pagination")
            self._send_slot_menu(customer, target_date, available_slots, page=page)
            return

        # 2. Time Selection (Button)
        if isinstance(input_data, str) and input_data.startswith("time_"):
            t_str = input_data.split("_")[1]
            self._confirm_time(customer, data, t_str)
            return
            
        # 3. Text Input (e.g. "2pm", "14:00")
        # Parse ONLY time. We prepend a dummy date to ensure time parsing works
        dummy_date = f"{data['date']} {input_data}"
        # Force Spanish to avoid AM/PM confusion if any
        parsed = dateparser.parse(dummy_date, languages=['es'])
        
        if not parsed:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "🤔 No entendí la hora. Selecciona una opción o escribe '2pm'.")
             return
             
        # Check against available slots
        available_slots = self._get_available_slots(data["barber_id"], target_date)
        user_hour = parsed.time().hour
        
        matched_slot = None
        for slot in available_slots:
            if slot.hour == user_hour:
                matched_slot = slot; break
                
        if matched_slot:
             self._confirm_time(customer, data, matched_slot.strftime("%H:%M"))
        else:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, f"⚠️ A las {parsed.strftime('%H:%M')} no está disponible.")

        # 2. Time Selection (Button)
        if isinstance(input_data, str) and input_data.startswith("time_"):
            t_str = input_data.split("_")[1]
            self._confirm_time(customer, data, t_str)
            return
            
        # 3. Text Input (e.g. "2pm", "14:00")
        # Parse ONLY time. We prepend a dummy date to ensure time parsing works
        dummy_date = f"{data['date']} {input_data}"
        parsed = dateparser.parse(dummy_date)
        
        if not parsed:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, "🤔 No entendí la hora. Selecciona una opción o escribe '2pm'.")
             return
             
        # Check against available slots
        available_slots = self._get_available_slots(data["barber_id"], target_date)
        user_hour = parsed.time().hour
        
        matched_slot = None
        for slot in available_slots:
            if slot.hour == user_hour:
                matched_slot = slot; break
                
        if matched_slot:
             self._confirm_time(customer, data, matched_slot.strftime("%H:%M"))
        else:
             whatsapp_service.send_message(self.phone_number_id, customer.phone, f"⚠️ A las {parsed.strftime('%H:%M')} no está disponible.")

    def _confirm_time(self, customer, data, time_str):
        data["time"] = time_str
        self._update_state(customer, CustomerData.CONFIRM_BOOKING, data)
        barber = self.db.query(Barber).filter(Barber.id == data["barber_id"]).first()
        msg = f"*Confirma tu cita:*\n\nPro: {barber.name}\nDia: {data['date']}\nHora: {time_str}\n\nTe parece bien?"
        buttons = [{"id": "confirm_yes", "title": "Si, confirmar"}, {"id": "confirm_no", "title": "Cancelar"}]
        whatsapp_service.send_interactive_button(self.phone_number_id, customer.phone, msg, buttons)

    def _finalize_booking(self, customer):
        data = self._get_data(customer)
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
        self._update_state(customer, CustomerData.IDLE, {})
        whatsapp_service.send_message(self.phone_number_id, customer.phone, f"Cita Confirmada con {barber.name} el {data['date']} a las {data['time']}!")
        # End of flow. State is IDLE. System stays silent until next keyword.

