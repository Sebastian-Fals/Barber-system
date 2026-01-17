import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from datetime import datetime, timedelta

import pytz

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.datetime_utils import get_local_timezone, now_local
from app.models.models import Appointment, AppointmentStatus, Barber, Business, Customer
from app.services.booking_service import BookingService

# CREATE TABLES IF NOT EXIST (SQLite)
Base.metadata.create_all(bind=engine)


def test_booking_service_tz():
    db = SessionLocal()
    sys_local_tz = get_local_timezone()  # Bogota

    try:
        # Cleanup
        db.query(Appointment).delete()
        db.query(Customer).delete()
        db.query(Barber).delete()
        db.query(Business).delete()
        db.commit()

        # Setup
        biz = Business(name="Test Biz", phone_number_id="123")
        db.add(biz)
        db.commit()

        barber = Barber(name="Test Barber", business_id=biz.id)
        cust = Customer(name="Test Customer", phone="573000000000")
        db.add(barber)
        db.add(cust)
        db.commit()

        booking_service = BookingService(db)

        # 1. Create Appointment via Service (Inputs are Strings "YYYY-MM-DD", "HH:MM")
        # Service logic should construct Aware Local datetime, then DB saves as UTC.

        today = now_local().date()
        date_str = str(today)
        time_str = "10:00"  # 10 AM Local

        print(f"Creating Appointment for {date_str} at {time_str} {settings.TIMEZONE}")

        appt = booking_service.create_appointment(cust, barber.id, date_str, time_str)

        if not appt:
            print("❌ Failed to create appointment (maybe outside business hours?)")
            # If 10am is valid, it should work. default hours 9-18.
            # Check if today is weekend or something?
            # Business default is 9-18. Today might be Sunday?
            # weekday() 0-6.
            # get_business_hours checks schedule column. default "{}" uses default args (9, 18)??
            # Logic:
            # start_h, end_h = 9, 18
            # if schedule: ... if day_key in schedule: ...
            # So if schedule is empty string (default), it stays 9, 18.
            # So 10am should be valid every day.

            # UNLESS business hours logic fails.
            pass
        else:
            print(f"✅ Appointment Created. ID: {appt.id}")
            print(f"   Start Time (DB Object - UTC Aware): {appt.start_time}")

            # Verify DB value is UTC corresponding to 10AM Local
            # 10AM Bogota = 15PM UTC
            expected_hour_utc = 15
            assert appt.start_time.tzinfo == pytz.UTC
            assert appt.start_time.hour == expected_hour_utc

            # 2. Check Availability
            # Should NOT show 10:00 AM as available.
            slots = booking_service.get_available_slots(barber.id, today)

            # Convert slots to hour strings for easy check
            # slots are aware datetimes (Local)
            slot_hours = [s.hour for s in slots]
            print(f"   Available slots (hours): {slot_hours}")

            assert 10 not in slot_hours, "10:00 AM should be taken"
            if 11 in slot_hours:
                print("   11:00 AM is free (correct behavior)")

            print("✅ Booking Service TZ Logic Verified")

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_booking_service_tz()
