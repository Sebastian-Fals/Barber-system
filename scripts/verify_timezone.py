import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from datetime import datetime, timedelta

import pytz

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.datetime_utils import to_local
from app.models.models import Appointment, AppointmentStatus, Barber, Business, Customer

# CREATE TABLES IF NOT EXIST (SQLite)
Base.metadata.create_all(bind=engine)


def test_timezone_storage():
    db = SessionLocal()
    try:
        # Cleanup
        db.query(Appointment).delete()
        db.query(Customer).delete()
        db.query(Barber).delete()
        db.query(Business).delete()
        db.commit()

        # Setup dependencies
        biz = Business(name="Test Biz", phone_number_id="123")
        db.add(biz)
        db.commit()

        barber = Barber(name="Test Barber", business_id=biz.id)
        cust = Customer(name="Test Customer", phone="573000000000")
        db.add(barber)
        db.add(cust)
        db.commit()

        # TEST 1: Save Naive Datetime (Simulating Local Input 10:00 AM Bogota)
        # Assuming system/config local timezone is Bogota (UTC-5)
        # 10:00 AM Bogota -> 15:00 UTC
        naive_start = datetime(2025, 1, 1, 10, 0, 0)

        appt = Appointment(
            customer_id=cust.id,
            barber_id=barber.id,
            start_time=naive_start,  # Naive!
            end_time=naive_start + timedelta(hours=1),
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)

        print(f"Stored Start Time (DB): {appt.start_time} | tzinfo: {appt.start_time.tzinfo}")

        # Verify it came back as UTC Aware
        assert appt.start_time.tzinfo is not None, "Should be timezone aware"
        assert appt.start_time.tzinfo == pytz.UTC, "Should be UTC"

        # Verify conversion logic (10am local -> 15pm UTC)
        # We need to know what 'local' means for the system.
        local_tz = pytz.timezone(settings.TIMEZONE)
        expected_utc = local_tz.localize(naive_start).astimezone(pytz.UTC)

        assert appt.start_time == expected_utc, f"Expected {expected_utc}, got {appt.start_time}"

        # Verify Conversion back to local
        local_dt = to_local(appt.start_time)
        print(f"Converted Back to Local: {local_dt}")
        assert local_dt.hour == 10, f"Expected 10 AM, got {local_dt.hour}"
        assert str(local_dt.tzinfo) == settings.TIMEZONE

        print("✅ TEST PASSED: Naive -> UTC Storage -> Local Retrieval working correctly.")

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_timezone_storage()
