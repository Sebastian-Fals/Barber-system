import os

from dotenv import load_dotenv

from app.core.database import Base, SessionLocal, engine
from app.models.models import Barber, Business, Customer

load_dotenv()

# Override engine if ADMIN_DATABASE_URL is present
admin_url = os.getenv("ADMIN_DATABASE_URL")
if admin_url:
    print("🛡️ Using ADMIN_DATABASE_URL for schema operations...")
    from sqlalchemy import create_engine

    engine = create_engine(admin_url)  # noqa: F811

# 1. Drop and Create
print("🗑️ Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("✨ Creating all tables...")
Base.metadata.create_all(bind=engine)

# 2. Seed Data
db = SessionLocal()

# Business
print("🌱 Seeding Business...")
business = Business(
    name="PeluqueriaSebastian",
    phone_number_id="86196104034",
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

# Barber
print("🌱 Seeding Barber Alejandro...")
barber = Barber(
    name="Alejandro",
    phone="3001234567",
    calendar_id="c14c89385ecab9b221f1b173c33cba7dfcfce2eb1f8ba91ff31d69b24822d3b0@group.calendar.google.com",
    business_id=business.id,
)
db.add(barber)
db.commit()

# Customer (Test Encryption)
print("🌱 Seeding Test Customer (Encryption Check)...")
# Note: Using property setter for phone!
customer = Customer(name="John Doe Encrypted", phone="573001234567", conversation_state="IDLE")
db.add(customer)
db.commit()

print("✅ Database reset complete!")

# Verification of Encryption (Raw SQL)
print("\n🔍 Verifying Encryption in DB (Raw SQL)...")
with engine.connect() as conn:
    from sqlalchemy import text

    result = conn.execute(
        text("SELECT phone_encrypted, name FROM customers WHERE phone_hash = :ph"), {"ph": customer.phone_hash}
    ).fetchone()
    if result:
        pe, nm = result
        print(f"   [RAW DB] phone_encrypted: {pe[:15]}... (Ciphertext)")
        print(f"   [RAW DB] name: {nm[:15]}... (Ciphertext)")
    else:
        print("❌ Could not find customer by hash!")

print("🔍 Verifying Decryption in App...")
print(f"   [APP] customer.phone: {customer.phone} (Plaintext)")
print(f"   [APP] customer.name: {customer.name} (Plaintext)")

print("✅ Database reset complete!")
db.close()
