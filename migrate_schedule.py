from app.core.database import engine
from sqlalchemy import text

def run_migration():
    with engine.connect() as conn:
        try:
            # Add schedule column (JSON string)
            # Default schedule: Mon-Sat 9-18
            conn.execute(text("ALTER TABLE businesses ADD COLUMN schedule VARCHAR DEFAULT '{}'"))
            print("Added schedule column")
        except Exception as e:
            print(f"Error (maybe exists): {e}")
        
        conn.commit()

if __name__ == "__main__":
    run_migration()
