from sqlalchemy.orm import Session
from app.models.models import Business, Barber, Appointment, AppointmentStatus, Customer
from app.services.calendar_service import calendar_service
import datetime
import json
from app.core.logging_config import logger

class BookingService:
    def __init__(self, db: Session):
        self.db = db

    def get_business_hours(self, business: Business, target_date: datetime.date):
        start_h, end_h = 9, 18
        if business.schedule:
            try:
                schedule = json.loads(business.schedule)
                day_key = str(target_date.weekday())
                if day_key in schedule:
                    start_h = schedule[day_key].get("start", 9)
                    end_h = schedule[day_key].get("end", 18)
            except: pass
        return start_h, end_h

    def get_available_slots(self, barber_id: int, target_date: datetime.date):
        barber = self.db.query(Barber).filter(Barber.id == barber_id).first()
        if not barber: return []
        
        business = self.db.query(Business).filter(Business.id == barber.business_id).first()
        open_h, close_h = self.get_business_hours(business, target_date)

        day_start = datetime.datetime(target_date.year, target_date.month, target_date.day, open_h, 0, 0)
        day_end = datetime.datetime(target_date.year, target_date.month, target_date.day, close_h, 0, 0)

        busy_intervals = []
        if barber.calendar_id:
             try:
                busy_intervals = calendar_service.get_busy_slots(barber.calendar_id, day_start, day_end)
             except Exception as e:
                 logger.error(f"Error fetching calendar slots: {e}")

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

    def filter_slots_by_period(self, slots, period):
        p = period.lower() if period else ""
        if p in ["morning", "mañana"]:
            return [s for s in slots if s.hour < 12]
        elif p in ["afternoon", "tarde"]:
            return [s for s in slots if s.hour >= 12 and s.hour < 18]
        elif p in ["evening", "noche"]:
            return [s for s in slots if s.hour >= 18]
        return slots

    def create_appointment(self, customer: Customer, barber_id: int, date_str: str, time_str: str):
        barber = self.db.query(Barber).filter(Barber.id == barber_id).first()
        if not barber: return None

        date_parts = list(map(int, date_str.split("-")))
        time_parts = list(map(int, time_str.split(":")))
        start_time = datetime.datetime(date_parts[0], date_parts[1], date_parts[2], time_parts[0], time_parts[1])
        end_time = start_time + datetime.timedelta(hours=1)
        summary = f"Cita: {customer.name} - {customer.phone}"
        
        # Calendar Sync
        google_event_id = None
        if barber.calendar_id: 
            try:
                event = calendar_service.create_event(barber.calendar_id, summary, start_time, end_time)
                if event: google_event_id = event.get("id")
            except Exception as e:
                logger.error(f"Error creating barber calendar event: {e}")
            
        business = self.db.query(Business).filter(Business.id == barber.business_id).first()
        if business and business.calendar_id: 
            try:
                calendar_service.create_event(business.calendar_id, f"[{barber.name}] {summary}", start_time, end_time)
            except Exception as e:
                logger.error(f"Error creating business calendar event: {e}")

        new_appointment = Appointment(
            customer_id=customer.id, 
            barber_id=barber.id, 
            start_time=start_time, 
            end_time=end_time, 
            status=AppointmentStatus.CONFIRMED, 
            google_event_id=google_event_id or "local_only"
        )
        self.db.add(new_appointment)
        self.db.commit()
        return new_appointment

    def cancel_appointment(self, appointment_id: int):
        appt = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if appt:
            appt.status = AppointmentStatus.CANCELLED
            if appt.google_event_id and appt.barber.calendar_id:
                try:
                    calendar_service.delete_event(appt.barber.calendar_id, appt.google_event_id)
                except Exception as e:
                    logger.error(f"Error deleting calendar event: {e}")
            self.db.commit()
            return True
        return False
