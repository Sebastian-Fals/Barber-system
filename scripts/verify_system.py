import datetime
import os
import sys

from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import hash_value  # noqa: E402
from app.models.models import Appointment, AppointmentStatus, Barber, Business, Customer  # noqa: E402


def log(msg, status="INFO"):
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}
    icon = icons.get(status, "ℹ️")
    print(f"{icon} [{status}] {msg}")


def verify_system():
    print("\n🔬 --- STARTING DEEP SYSTEM VERIFICATION ---")
    db = SessionLocal()

    try:
        # 1. Verify Database Connection
        log("Checking Database Connection...", "INFO")
        db.execute(text("SELECT 1"))
        log("Database connected successfully.", "SUCCESS")

        # 2. Verify Table Existence (Basic Check)
        log("Verifying Tables...", "INFO")
        tables = ["businesses", "barbers", "customers", "appointments"]
        with engine.connect() as conn:
            for t in tables:
                exists = conn.execute(text(f"SELECT to_regclass('public.{t}')")).scalar()
                if exists:
                    log(f"Table '{t}' exists.", "SUCCESS")
                else:
                    log(f"Table '{t}' MISSING!", "ERROR")

        # 3. Test Business Creation
        log("Testing Business Creation...", "INFO")
        test_biz = Business(
            name="Test Biz Auto",
            phone_number_id="123456789",
            phone="3000000000",
            calendar_id="test_calendar@group.calendar.google.com",
            ai_enabled=True,
            schedule="{}",
        )
        db.add(test_biz)
        db.commit()
        db.refresh(test_biz)
        log(f"Business created with ID: {test_biz.id}", "SUCCESS")

        # 4. Test Barber Creation (and automatic phone encryption)
        log("Testing Barber Creation...", "INFO")
        test_barber = Barber(
            name="Barber Test",
            phone="3009998877",  # Should be encrypted automatically
            calendar_id="barber_cal@group.calendar.google.com",
            business_id=test_biz.id,
        )
        db.add(test_barber)
        db.commit()
        db.refresh(test_barber)

        # Verify Barber Phone Encryption
        with engine.connect() as conn:
            raw_phone = conn.execute(text("SELECT phone FROM barbers WHERE id = :id"), {"id": test_barber.id}).scalar()
            if not raw_phone.startswith("gAAAA"):  # Basic Fernet check
                log(f"Barber phone NOT encrypted in DB! Value: {raw_phone}", "ERROR")
            else:
                log(f"Barber phone encrypted in DB: {raw_phone[:10]}...", "SUCCESS")

        if test_barber.phone == "3009998877":
            log(f"Barber phone decrypted correctly in App: {test_barber.phone}", "SUCCESS")
        else:
            log(f"Barber phone decryption FAILED! Got: {test_barber.phone}", "ERROR")

        # 5. Test Customer Creation (PII Encryption & Hashed Index)
        log("Testing Customer Creation (PII Security)...", "INFO")
        c_name = "Jane Doe Secure"
        c_phone = "573005551234"

        test_customer = Customer(name=c_name, phone=c_phone)  # setter handles hash + encrypt
        db.add(test_customer)
        db.commit()
        db.refresh(test_customer)

        # Verify Raw DB Data
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT name, phone_encrypted, phone_hash FROM customers WHERE id = :id"), {"id": test_customer.id}
            ).fetchone()
            r_name, r_phone, r_hash = row

            # Check Name Encryption
            if not r_name.startswith("gAAAA"):
                log(f"Customer Name NOT encrypted! {r_name}", "ERROR")
            else:
                log("Customer Name encrypted.", "SUCCESS")

            # Check Phone Encryption
            if not r_phone.startswith("gAAAA"):
                log(f"Customer Phone NOT encrypted! {r_phone}", "ERROR")
            else:
                log("Customer Phone encrypted.", "SUCCESS")

            # Check Hash
            expected_hash = hash_value(c_phone)
            if r_hash != expected_hash:
                log(f"Customer Phone Hash Mismatch! DB: {r_hash} vs Calc: {expected_hash}", "ERROR")
            else:
                log("Customer Phone Hash verified.", "SUCCESS")

        # Verify App Decryption
        if test_customer.name == c_name and test_customer.phone == c_phone:
            log("Customer data decrypted correctly in App.", "SUCCESS")
        else:
            log(f"Customer decryption failed! Name: {test_customer.name}, Phone: {test_customer.phone}", "ERROR")

        # 6. Test Appointment Logic
        log("Testing Appointment Creation...", "INFO")
        now = datetime.datetime.now()
        start = now + datetime.timedelta(days=1, hours=10)
        end = start + datetime.timedelta(hours=1)

        appt = Appointment(
            customer_id=test_customer.id,
            barber_id=test_barber.id,
            start_time=start,
            end_time=end,
            status=AppointmentStatus.CONFIRMED,
            google_barber_event_id="evt_barber_123",
            google_business_event_id="evt_biz_123",
        )
        db.add(appt)
        db.commit()
        log("Appointment created successfully.", "SUCCESS")

        # Verify Relationships (joinedload check simulation)
        appt_reload = db.query(Appointment).filter(Appointment.id == appt.id).first()
        if appt_reload.customer.name == c_name:
            log("Appointment -> Customer relationship working.", "SUCCESS")
        if appt_reload.barber.business.name == "Test Biz Auto":
            log("Appointment -> Barber -> Business relationship working.", "SUCCESS")

    except Exception as e:
        log(f"CRITICAL ERROR during verification: {e}", "ERROR")
        import traceback

        traceback.print_exc()
    finally:
        db.close()
        print("\n--- VERIFICATION COMPLETE ---")


if __name__ == "__main__":
    verify_system()
