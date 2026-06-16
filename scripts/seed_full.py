import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import Barber, Business, Customer


def seed_data():
    db = SessionLocal()
    try:
        print("🌱 Seeding Initial Data...")

        # 1. Business
        instance_name = "barberia-latino"
        instance_apikey = "MIGRATE-ME"
        existing_biz = db.query(Business).filter(Business.instance_name == instance_name).first()

        if not existing_biz:
            business = Business(
                name="PeluqueriaSebastian",
                instance_name=instance_name,
                instance_apikey=instance_apikey,
                phone="3001234567",
                calendar_id="sebastian.fals.lopez@gmail.com",
                ai_enabled=True,
                schedule=(
                    '{"0": {"start": 9, "end": 18}, "1": {"start": 9, "end": 18}, "2": {"start": 9, "end": 18}, '
                    '"3": {"start": 9, "end": 18}, "4": {"start": 9, "end": 18}, "5": {"start": 9, "end": 18}}'
                ),
            )
            db.add(business)
            db.commit()
            db.refresh(business)
            print("   ✅ Business 'PeluqueriaSebastian' created.")
        else:
            business = existing_biz
            print("   ℹ️ Business already exists.")

        # 2. Barber
        barber_cal = "c14c89385ecab9b221f1b173c33cba7dfcfce2eb1f8ba91ff31d69b24822d3b0@group.calendar.google.com"
        existing_barber = db.query(Barber).filter(Barber.calendar_id == barber_cal).first()

        if not existing_barber:
            barber = Barber(
                name="Alejandro",
                phone="3001234567",
                calendar_id=barber_cal,
                business_id=business.id,
            )
            db.add(barber)
            db.commit()
            print("   ✅ Barber 'Alejandro' created.")
        else:
            print("   ℹ️ Barber already exists.")

        # 3. Customer
        cust_phone = "573001234567"
        # Since phone is encrypted, we can't search by it lightly unless we hash.
        # But we can try to add and catch integrity error or just rely on 'phone_hash' if we had it exposed easily.
        # For seeding, we'll blindly try creating a new one or ignore.

        # Actually checking by hash is cleaner if we import hash_value
        from app.core.security import hash_value

        ph_hash = hash_value(cust_phone)

        existing_cust = db.query(Customer).filter(Customer.phone_hash == ph_hash).first()

        if not existing_cust:
            customer = Customer(name="John Doe Seed", phone=cust_phone, conversation_state="IDLE")
            db.add(customer)
            db.commit()
            print("   ✅ Test Customer created.")
        else:
            print("   ℹ️ Test Customer already exists.")

    except Exception as e:
        print(f"❌ Error seeding data: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
