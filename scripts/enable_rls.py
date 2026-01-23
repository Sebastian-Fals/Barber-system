import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def enable_rls():
    # Must use ADMIN credentials to change policies
    admin_db_url = os.getenv("ADMIN_DATABASE_URL")

    if not admin_db_url:
        print("❌ Error: ADMIN_DATABASE_URL is not set in .env")
        return

    print("🔌 Connecting as Admin...")
    engine = create_engine(admin_db_url, isolation_level="AUTOCOMMIT")

    # Tables to protect
    tables = ["businesses", "barbers", "customers", "appointments", "processed_messages"]

    with engine.connect() as conn:
        print("🔒 Enabling RLS and setting policies...")

        for table in tables:
            try:
                # 1. Enable RLS
                print(f"   - {table}: Enabling RLS")
                conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

                # 2. Checks if policy exists (Postgres doesn't have CREATE POLICY IF NOT EXISTS until v17? or so)
                # Instead we drop validation because we want to overwrite/ensure it exists.
                # Drop existing policy to be safe
                conn.execute(text(f'DROP POLICY IF EXISTS "Backend Access" ON {table}'))

                # 3. Create Policy
                # Allow 'app_user' to do EVERYTHING.
                # using (true) means all rows are visible/writable by this user.
                print(f"   - {table}: Creating 'Backend Access' policy for app_user")
                sql = f"""
                CREATE POLICY "Backend Access" ON {table}
                FOR ALL
                TO app_user
                USING (true)
                WITH CHECK (true);
                """
                conn.execute(text(sql))

            except Exception as e:
                print(f"⚠️ Error on table {table}: {e}")

        print("✅ RLS Enabled. 'app_user' has full access via Policy.")


if __name__ == "__main__":
    enable_rls()
