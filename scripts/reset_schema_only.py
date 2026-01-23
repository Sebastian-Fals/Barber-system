import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base  # noqa: E402

# Import all models to ensure metadata is populated
# Import all models to ensure metadata is populated
# noqa: F401
from app.models.models import Appointment, Barber, Business, Customer, ProcessedMessage  # noqa: E402, F401

load_dotenv()


def reset_schema_only():
    admin_url = os.getenv("ADMIN_DATABASE_URL")
    if not admin_url:
        print("❌ Error: ADMIN_DATABASE_URL is not set in .env")
        return

    print("🛡️ Connecting with Admin credentials...")
    engine = create_engine(admin_url)

    print("🗑️ Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    print("✨ Creating empty tables...")
    Base.metadata.create_all(bind=engine)

    print("✅ Schema reset complete. Database is empty (No Data).")
    print("⚠️  Remember to re-enable RLS policies!")


if __name__ == "__main__":
    reset_schema_only()
