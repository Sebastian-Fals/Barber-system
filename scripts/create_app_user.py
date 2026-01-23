import os
import secrets
import string
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def generate_secure_password(length=32):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for i in range(length))


def create_app_user():
    # 1. Get Admin Connection
    current_db_url = os.getenv("DATABASE_URL")
    admin_db_url = os.getenv("ADMIN_DATABASE_URL")

    # Prefer ADMIN_DATABASE_URL if set, otherwise use DATABASE_URL (assuming it is currently admin)
    db_url = admin_db_url or current_db_url

    if not db_url or "postgres" not in db_url:
        print("⚠️  WARNING: Could not find a likely admin connection string (user 'postgres').")
        print("Please ensure DATABASE_URL or ADMIN_DATABASE_URL is set to the superuser connection.")
        # Continue anyway in case they are using a different superuser name

    print("🔌 Connecting to DB...")

    try:
        # Create engine with isolation_level="AUTOCOMMIT" to allow CREATE ROLE
        engine = create_engine(db_url, isolation_level="AUTOCOMMIT")

        with engine.connect() as conn:
            # 2. Define new user credentials
            new_user = "app_user"
            new_pass = generate_secure_password()

            # 3. Create Role
            print(f"👤 Creating role '{new_user}'...")
            try:
                # Check if exists
                exists = conn.execute(text(f"SELECT 1 FROM pg_roles WHERE rolname='{new_user}'")).scalar()
                if exists:
                    print(f"   Role '{new_user}' already exists. Updating password.")
                    conn.execute(text(f"ALTER USER {new_user} WITH PASSWORD '{new_pass}'"))
                else:
                    conn.execute(text(f"CREATE USER {new_user} WITH PASSWORD '{new_pass}'"))
            except Exception as e:
                print(f"❌ Error creating role: {e}")
                return

            # 4. Grant Privileges
            print("🔑 Granting privileges...")

            # Connect
            conn.execute(text(f"GRANT CONNECT ON DATABASE postgres TO {new_user}"))

            # Usage on Schema
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {new_user}"))

            # CRUD on Tables
            conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {new_user}"))

            # Default privileges for future tables
            conn.execute(
                text(
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {new_user}"
                )
            )

            # Sequences (Critical for auto-increment)
            conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {new_user}"))
            conn.execute(
                text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {new_user}")
            )

            print("✅ User setup complete.")
            print("-" * 50)
            print(f"NEW_USER: {new_user}")
            print(f"NEW_PASS: {new_pass}")
            print("-" * 50)
            print("📝 Please update your .env file separately.")

            # Construct new URL for display
            # Parse old URL to get host/port/db
            # Simple string replacement for demo (be careful with complex URLs)
            # Assuming format: postgresql://user:pass@host:port/db

            # Robust URL construction not strictly necessary for the script output,
            # but helpful to print the Connection String for the user.

            print("\nConstructed Connection String for .env:")
            # We can't easily parse without a library like alembic/sqlalchemy URL object,
            # but we can instruct the user to replace it.
            print(f"postgresql://{new_user}:{new_pass}@<HOST>:<PORT>/<DB>")

    except Exception as e:
        print(f"❌ Critical Error: {e}")


if __name__ == "__main__":
    create_app_user()
