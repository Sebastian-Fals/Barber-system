import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import Barber, Business  # noqa: E402


def add_barber():
    print("💈 --- Add New Barber ---")

    db = SessionLocal()
    try:
        # List Businesses
        businesses = db.query(Business).all()
        if not businesses:
            print("❌ No businesses found. Run add_business.py first.")
            return

        print("\nSelect Business:")
        for b in businesses:
            print(f"   [{b.id}] {b.name} ({b.phone_number_id})")

        try:
            business_id = int(input("\nEnter Business ID: ").strip())
        except ValueError:
            print("❌ Invalid ID.")
            return

        # Verify Business
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            print("❌ Business not found.")
            return

        print(f"\nAdding Barber to: {business.name}")
        name = input("Enter Barber Name: ").strip()
        if not name:
            print("❌ Name is required.")
            return

        phone = input("Enter Barber Phone (will be encrypted): ").strip() or None
        calendar_id = input("Enter Barber's Google Calendar ID (optional): ").strip() or None

        new_barber = Barber(
            name=name,
            phone=phone,  # EncryptedString in model handles logic
            calendar_id=calendar_id,
            business_id=business.id,
        )

        db.add(new_barber)
        db.commit()
        db.refresh(new_barber)

        print(f"\n✅ Barber '{new_barber.name}' added successfully!")
        print(f"   ID: {new_barber.id}")
        print(f"   Business: {business.name}")
        if new_barber.phone:
            print("   Phone stored securely.")

    except Exception as e:
        print(f"❌ Error adding barber: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    add_barber()
