import datetime
import json

# import pytz # Unused
from sqlalchemy.orm import Session

# from app.core.config import settings # Unused
from app.core.datetime_utils import get_local_timezone, now_local, to_local  # , to_utc
from app.core.logging_config import logger
from app.features.appointments.repository import AppointmentRepository
from app.features.business.barber_repository import BarberRepository
from app.features.business.repository import BusinessRepository
from app.features.calendar.service import calendar_service
from app.features.customers.repository import CustomerRepository
from app.models.models import AppointmentStatus, Business, Customer  # , Appointment, Barber


class BookingService:
    def __init__(self, db: Session):
        self.db: Session = db
        self.appointment_repo = AppointmentRepository(db)
        self.barber_repo = BarberRepository(db)
        self.business_repo = BusinessRepository(db)
        self.customer_repo = CustomerRepository(db)

    def get_business_hours(self, business: Business, target_date: datetime.date) -> tuple[int, int]:
        start_h, end_h = 9, 18
        if business.schedule:
            try:
                schedule = json.loads(business.schedule)
                day_key = str(target_date.weekday())
                if day_key in schedule:
                    start_h = schedule[day_key].get("start", 9)
                    end_h = schedule[day_key].get("end", 18)
            except Exception as e:
                logger.error(f"Error parsing business schedule: {e}")
        return start_h, end_h

    def get_available_slots(self, barber_id: int, target_date: datetime.date) -> list[datetime.datetime]:
        barber = self.barber_repo.get_by_id(barber_id)
        if not barber:
            return []

        business = self.business_repo.get_by_id(barber.business_id)
        open_h, close_h = self.get_business_hours(business, target_date)

        local_tz = get_local_timezone()
        # Create aware datetimes directly
        day_start = local_tz.localize(
            datetime.datetime(target_date.year, target_date.month, target_date.day, open_h, 0, 0)
        )
        day_end = local_tz.localize(
            datetime.datetime(target_date.year, target_date.month, target_date.day, close_h, 0, 0)
        )

        busy_intervals = []
        if barber.calendar_id:
            try:
                busy_intervals = calendar_service.get_busy_slots(barber.calendar_id, day_start, day_end)
            except Exception as e:
                logger.error(f"Error fetching calendar slots: {e}")

        available_slots = []
        current_slot = day_start

        # Get current time (Aware Local)
        now = now_local()

        while current_slot < day_end:
            slot_end = current_slot + datetime.timedelta(hours=1)

            # 1. Skip past slots if target_date is today
            if current_slot < now:
                current_slot = slot_end
                continue

            is_free = True
            for b_start_str, b_end_str in busy_intervals:
                try:
                    # Clean Zulu time if present
                    s_str = b_start_str.replace("Z", "+00:00")
                    e_str = b_end_str.replace("Z", "+00:00")

                    b_start = datetime.datetime.fromisoformat(s_str)
                    b_end = datetime.datetime.fromisoformat(e_str)

                    # If Google returned Aware time, convert to Bogota Local (Aware)
                    if b_start.tzinfo is not None:
                        b_start = to_local(b_start)
                        b_end = to_local(b_end)
                    else:
                        # Should not happen with Google, but if naive, localize it
                        b_start = to_local(b_start)
                        b_end = to_local(b_end)

                    # Now compare Aware vs Aware
                    if (current_slot < b_end) and (slot_end > b_start):
                        is_free = False
                        break
                except Exception as e:
                    logger.error(f"Error parsing slot: {e}")
                    is_free = False

            if is_free:
                available_slots.append(current_slot)
            current_slot = slot_end
        return available_slots

    def is_custom_slot_available(self, barber_id: int, target_date: datetime.date, time_obj: datetime.time) -> bool:
        """
        Checks if a specific time (e.g., 12:50) is free for 1 hour.
        """
        barber = self.barber_repo.get_by_id(barber_id)
        if not barber:
            return False

        business = self.business_repo.get_by_id(barber.business_id)
        start_h, end_h = self.get_business_hours(business, target_date)

        # 1. Business Hours Check (Simple for now, checks hour integer range)
        # Better: check actual times
        if time_obj.hour < start_h or time_obj.hour >= end_h:
            return False

        local_tz = get_local_timezone()
        start_dt = local_tz.localize(datetime.datetime.combine(target_date, time_obj))
        end_dt = start_dt + datetime.timedelta(hours=1)

        # 2. Check Past
        if start_dt < now_local():
            return False

        # 3. Check Google Calendar Overlaps
        if barber.calendar_id:
            try:
                # Query strictly this interval
                busy = calendar_service.get_busy_slots(barber.calendar_id, start_dt, end_dt)
                if busy:
                    return False
            except Exception as e:
                logger.error(f"Error checking custom slot: {e}")
                # Fail open or closed? Safe is closed.
                return False

        # 4. Check Local Overlaps
        existing = self.appointment_repo.get_overlapping_confirmed(barber_id, start_dt, end_dt)
        if existing:
            return False

        return True

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
        barber = self.barber_repo.get_by_id(barber_id)
        if not barber:
            return None

        # Robust Parsing
        try:
            # Date Parsing
            if isinstance(date_str, datetime.date):
                target_date = date_str
            else:
                target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

            # Time Parsing
            target_time = None
            if isinstance(time_str, datetime.time):
                target_time = time_str
            else:
                # Try formats: HH:MM:SS, HH:MM, HH:MM AM/PM
                formats = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"]
                for fmt in formats:
                    try:
                        target_time = datetime.datetime.strptime(str(time_str).strip(), fmt).time()
                        break
                    except ValueError:
                        continue
                if not target_time:
                    raise ValueError(f"Invalid time format: {time_str}")

        except ValueError as e:
            logger.error(f"Date/Time parsing error in create_appointment: {e}")
            return None

        # Construct aware datetime
        local_tz = get_local_timezone()
        naive_start = datetime.datetime.combine(target_date, target_time)
        start_time = local_tz.localize(naive_start)

        end_time = start_time + datetime.timedelta(hours=1)
        summary = f"Cita: {customer.name} - {customer.phone}"

        business = self.business_repo.get_by_id(barber.business_id)
        if not business:
            logger.error(f"Barber {barber.id} has no associated business")
            return None

        # 1. Validate Business Hours
        start_h, end_h = self.get_business_hours(business, start_time.date())
        if start_time.hour < start_h or start_time.hour >= end_h:
            logger.warning(f"Attempt to book outside business hours: {start_time}")
            return None  # Or raise specific error

        # 2. Validate Availability (Double Check)
        existing = self.appointment_repo.get_overlapping_confirmed(barber_id, start_time, end_time)
        if existing:
            logger.warning(f"Slot overlapping with local appointment {existing.id}")
            return None

        # 3. Calendar Sync
        barber_event_id = None
        business_event_id = None

        if barber.calendar_id:
            try:
                # Create event in Barber's calendar
                barber_event_id = calendar_service.create_event(barber.calendar_id, summary, start_time, end_time)
            except Exception as e:
                logger.error(f"Error creating barber calendar event: {e}")

        # Try to sync with Business Calendar (Duplicate Event Strategy due to Service Account 403 on Attendees)
        if business.calendar_id:
            try:
                business_event_id = calendar_service.create_event(
                    business.calendar_id, f"[{barber.name}] {summary}", start_time, end_time
                )
            except Exception as e:
                logger.error(f"Error creating business calendar event: {e}")

        appt_data = {
            "customer_id": customer.id,
            "barber_id": barber.id,
            "start_time": start_time,
            "end_time": end_time,
            "status": AppointmentStatus.CONFIRMED.value,
            "google_barber_event_id": barber_event_id,
            "google_business_event_id": business_event_id,
        }

        # Use repository create
        new_appointment = self.appointment_repo.create(appt_data)
        return new_appointment

    def cancel_appointment(self, appointment_id: int):
        appt = self.appointment_repo.get_by_id(appointment_id)
        if appt:
            appt.status = AppointmentStatus.CANCELLED

            # Delete from Barber Calendar
            if appt.google_barber_event_id and appt.barber.calendar_id:
                try:
                    calendar_service.delete_event(appt.barber.calendar_id, appt.google_barber_event_id)
                except Exception as e:
                    logger.error(f"Error deleting barber calendar event: {e}")

            # Delete from Business Calendar
            business = appt.barber.business
            if appt.google_business_event_id and business and business.calendar_id:
                try:
                    calendar_service.delete_event(business.calendar_id, appt.google_business_event_id)
                except Exception as e:
                    logger.error(f"Error deleting business calendar event: {e}")

            self.appointment_repo.db.commit()  # Or self.db.commit()
            return True
        return False
