import datetime
import os
import sys

import pytz

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import AppointmentStatus, CustomerData
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.barber_repository import BarberRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.customer_repository import CustomerRepository


def verify_repositories():
    db = SessionLocal()
    try:
        print("--- Verifying Repositories ---")

        # 1. Customer Repository
        print("[1] Testing CustomerRepository...")
        customer_repo = CustomerRepository(db)
        test_phone = "573001234567"

        # Cleanup
        existing = customer_repo.get_by_phone(test_phone)
        if existing:
            db.delete(existing)
            db.commit()

        # Create
        new_customer = customer_repo.create({"phone": test_phone, "name": "Test Repository User"})
        print(f"    Created customer: {new_customer.id} - {new_customer.name}")

        # Get by Phone
        fetched = customer_repo.get_by_phone(test_phone)
        assert fetched is not None
        assert fetched.phone == test_phone
        print("    Get by Phone: PASSED")

        # Update State
        customer_repo.update_state(fetched, CustomerData.SELECT_DATE)
        print(f"    Updated State: {fetched.conversation_state}")
        assert fetched.conversation_state == CustomerData.SELECT_DATE
        print("    Update State: PASSED")

        # 2. Business & Barber Repository
        print("\n[2] Testing Business & Barber Repository...")
        business_repo = BusinessRepository(db)
        barber_repo = BarberRepository(db)

        # Get Business
        businesses = business_repo.get_all(limit=1)
        if not businesses:
            print("    Creating dummy business...")
            biz = business_repo.create({"name": "Test Barber", "phone_number_id": "12345"})
        else:
            biz = businesses[0]

        print(f"    Using Business: {biz.name} (ID: {biz.id})")

        # Get Barbers by Business
        barbers = barber_repo.get_by_business(biz.id)
        if not barbers:
            print("    Creating dummy barber...")
            barber_repo.create({"name": "Test Barber 1", "business_id": biz.id, "phone": "123"})
            barbers = barber_repo.get_by_business(biz.id)

        assert len(barbers) > 0
        print(f"    Fetched {len(barbers)} barbers for business {biz.id}")
        test_barber = barbers[0]
        print("    Get by Business: PASSED")

        # 3. Appointment Repository
        print("\n[3] Testing Appointment Repository...")
        appt_repo = AppointmentRepository(db)

        # Create Dummy Appointment
        start_time = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        end_time = start_time + datetime.timedelta(hours=1)

        appt_in = {
            "customer_id": new_customer.id,
            "barber_id": test_barber.id,
            "start_time": start_time,
            "end_time": end_time,
            "status": AppointmentStatus.CONFIRMED,
            "google_event_id": "test_repo",
        }

        appt = appt_repo.create(appt_in)
        print(f"    Created Appointment: {appt.id}")

        # Get Overlapping
        # Important: use utc times for overlap check logic if repo expects it
        overlap = appt_repo.get_overlapping_confirmed(
            test_barber.id, start_time + datetime.timedelta(minutes=10), end_time - datetime.timedelta(minutes=10)
        )
        assert overlap is not None
        assert overlap.id == appt.id
        print("    Get Overlapping: PASSED")

        # Get Active for Customer
        active = appt_repo.get_active_for_customer(new_customer.id)
        assert len(active) > 0
        assert active[0].id == appt.id
        print("    Get Active for Customer: PASSED")

        # Cleanup Appointment
        db.delete(appt)
        db.delete(new_customer)  # Cleanup customer too
        db.commit()
        print("    Cleanup Appointment: DONE")

        print("\n--- ALL REPOSITORY TESTS PASSED ---")

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    verify_repositories()
