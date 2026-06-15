import datetime
import json

# import pytz # Unused
from dateutil.parser import ParserError, parse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import get_local_timezone, now_local, to_local  # , to_utc
from app.core.exceptions import BusinessCalendarError, ServiceValidationError, SlotOccupiedError
from app.core.logging_config import logger
from app.features.appointments.repository import AppointmentRepository
from app.features.business.barber_repository import BarberRepository
from app.features.business.repository import BusinessRepository
from app.features.calendar.service import calendar_service
from app.features.customers.repository import CustomerRepository
from app.models.models import AppointmentStatus, Business, Customer


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
        # Dependencies: Import at top level in real code, but here we assume imports are added.
        # Check imports for this chunk.

        barber = self.barber_repo.get_by_id(barber_id)
        if not barber:
            raise ServiceValidationError(f"Barber {barber_id} not found")

        # Robust Parsing
        try:
            # Date Parsing
            if isinstance(date_str, datetime.date):
                target_date = date_str
            else:
                target_date = parse(str(date_str)).date()

            # Time Parsing
            target_time = None
            if isinstance(time_str, datetime.time):
                target_time = time_str
            else:
                target_time = parse(str(time_str)).time()

        except (ValueError, ParserError) as e:
            logger.error(f"Date/Time parsing error: {e}")
            raise ServiceValidationError(f"Invalid date/time format: {date_str} {time_str}")

        # Construct aware datetime
        local_tz = get_local_timezone()
        naive_start = datetime.datetime.combine(target_date, target_time)
        start_time = local_tz.localize(naive_start)

        end_time = start_time + datetime.timedelta(hours=1)
        summary = f"Cita: {customer.name} - {customer.phone}"

        business = self.business_repo.get_by_id(barber.business_id)
        if not business:
            logger.error(f"Barber {barber.id} has no associated business")
            raise ServiceValidationError("Data corruption: Barber has no business")

        # 1. Validate Business Hours (outside transaction — cheap check)
        start_h, end_h = self.get_business_hours(business, start_time.date())
        if start_time.hour < start_h or start_time.hour >= end_h:
            logger.warning(f"Attempt to book outside business hours: {start_time}")
            raise BusinessCalendarError("El horario solicitado está fuera de horas laborales.")

        # 2. Atomic availability check + insert (TOCTOU protection)
        # PostgreSQL: SELECT ... FOR UPDATE locks matching rows
        # SQLite: BEGIN IMMEDIATE prevents concurrent writes to the table
        try:
            if "sqlite" in settings.DATABASE_URL:
                self.db.execute(text("BEGIN IMMEDIATE"))

            existing = self.appointment_repo.get_overlapping_confirmed(barber_id, start_time, end_time, for_update=True)
            if existing:
                self.db.rollback()
                logger.warning(f"Slot already taken: barber={barber_id} {start_time}")
                raise SlotOccupiedError("Este horario ya no está disponible. Por favor elegí otro.")

            # Slot is free → insert within the same locked transaction
            appt_data = {
                "customer_id": customer.id,
                "barber_id": barber.id,
                "business_id": barber.business_id,
                "start_time": start_time,
                "end_time": end_time,
                "status": AppointmentStatus.CONFIRMED.value,
                "google_barber_event_id": None,
                "google_business_event_id": None,
            }
            new_appointment = self.appointment_repo.create(appt_data)
            self.db.commit()
        except (OperationalError, Exception) as e:
            self.db.rollback()
            if isinstance(e, SlotOccupiedError):
                raise
            logger.error(f"Lock/transaction error: {e}")
            raise SlotOccupiedError("Intenta de nuevo en un momento. El horario pudo haber sido tomado.")

        # 3. Calendar Sync (after commit — non-critical, best-effort)
        barber_event_id = None
        business_event_id = None

        if barber.calendar_id:
            try:
                # Create event in Barber's calendar
                barber_event_id = calendar_service.create_event(barber.calendar_id, summary, start_time, end_time)
            except Exception as e:
                logger.error(f"Error creating barber calendar event: {e}")
                # We could raise error here if strictly required, or fail soft.
                # Current logic was soft fail. Let's keep it soft but logged, OR raise BusinessCalendarError?
                # If calendar fails, double booking is possible if we fallback to local only.
                # Safer: Fail if calendar is required.
                # But let's stick to fail soft for now as it's an external dependency.
                pass

        # Try to sync with Business Calendar (Duplicate Event Strategy due to Service Account 403 on Attendees)
        if business.calendar_id:
            try:
                business_event_id = calendar_service.create_event(
                    business.calendar_id, f"[{barber.name}] {summary}", start_time, end_time
                )
            except Exception as e:
                logger.error(f"Error creating business calendar event: {e}")

        # Update the appointment with calendar event IDs (post-commit, best-effort)
        if barber_event_id or business_event_id:
            try:
                if barber_event_id:
                    new_appointment.google_barber_event_id = barber_event_id
                if business_event_id:
                    new_appointment.google_business_event_id = business_event_id
                self.db.commit()
            except Exception as e:
                logger.error(f"Error updating calendar event IDs: {e}")
                self.db.rollback()

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
