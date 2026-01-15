from app.core.database import SessionLocal
from app.models.models import Customer, Appointment

db = SessionLocal()
try:
    print("🗑️ Deleting all Appointments...")
    db.query(Appointment).delete()
    
    print("🗑️ Deleting all Customers...")
    db.query(Customer).delete()
    
    db.commit()
    print("✅ All customer data cleared.")
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
