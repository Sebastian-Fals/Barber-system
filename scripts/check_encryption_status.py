import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def check_encryption():
    # Use ADMIN_URL to access raw DB (or normal URL)
    db_url = os.getenv("ADMIN_DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL found.")
        return

    engine = create_engine(db_url)

    with engine.connect() as conn:
        print("--- Checking Business Encryption ---")
        rows = conn.execute(text("SELECT name, phone, calendar_id FROM businesses")).fetchall()
        for r in rows:
            print(f"Name: {r[0]}")
            print(f"Phone (Raw): {r[1][:15]}...")
            print(f"CalID (Raw): {r[2][:15]}...")

        print("\n--- Checking Barber Encryption ---")
        rows = conn.execute(text("SELECT name, phone, calendar_id FROM barbers")).fetchall()
        for r in rows:
            print(f"Name: {r[0]}")
            # Phone might be null if not set
            p = r[1] if r[1] else "None"
            # CalID
            c = r[2] if r[2] else "None"

            print(f"Phone (Raw): {p[:15]}...")
            print(f"CalID (Raw): {c[:15]}...")


if __name__ == "__main__":
    check_encryption()
