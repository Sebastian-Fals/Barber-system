import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import Business  # noqa: E402


def add_business():
    print("🏢 --- Add New Business ---")

    name = input("Enter Business Name: ").strip()
    if not name:
        print("❌ Name is required.")
        return

    instance_name = input("Enter WhatsApp Instance Name (Evolution API): ").strip()
    if not instance_name:
        print("❌ Instance Name is required.")
        return

    instance_apikey = input("Enter Instance API Key: ").strip()
    if not instance_apikey:
        print("❌ API Key is required.")
        return

    phone = input("Enter Public Phone Number (optional): ").strip() or None
    calendar_id = input("Enter Google Calendar ID (optional): ").strip() or None

    print("\n--- Schedule Configuration ---")
    print("Press Enter to use default: {'0': {'start': 9, 'end': 18}, ... Mon-Sat}")
    schedule_input = input("Enter JSON Schedule (or leave empty): ").strip()

    default_schedule = (
        '{"0": {"start": 9, "end": 18}, "1": {"start": 9, "end": 18}, "2": {"start": 9, "end": 18}, '
        '"3": {"start": 9, "end": 18}, "4": {"start": 9, "end": 18}, "5": {"start": 9, "end": 18}}'
    )

    schedule = schedule_input if schedule_input else default_schedule

    db = SessionLocal()
    try:
        # Check existence
        existing = db.query(Business).filter(Business.instance_name == instance_name).first()
        if existing:
            print(
                f"⚠️ Business with instance '{instance_name}' already exists (ID: {existing.id}, Name: {existing.name})."
            )
            return

        new_business = Business(
            name=name,
            instance_name=instance_name,
            instance_apikey=instance_apikey,
            phone=phone,
            calendar_id=calendar_id,
            schedule=schedule,
            ai_enabled=True,  # Default to enabled
        )
        db.add(new_business)
        db.commit()
        db.refresh(new_business)

        print(f"\n✅ Business '{new_business.name}' created successfully!")
        print(f"   ID: {new_business.id}")
        print(f"   Instance: {new_business.instance_name}")

    except Exception as e:
        print(f"❌ Error adding business: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    add_business()
