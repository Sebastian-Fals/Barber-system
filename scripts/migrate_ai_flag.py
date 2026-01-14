import sys
import os
from sqlalchemy import create_engine, text

# Add parent dir to path to find app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings

def migrate():
    print(f"Connecting to database: {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # Check if column exists
            print("Checking if column 'ai_enabled' exists in 'businesses'...")
            # SQLite specific check
            result = conn.execute(text("PRAGMA table_info(businesses)"))
            columns = [row[1] for row in result]
            
            if "ai_enabled" in columns:
                print("Column 'ai_enabled' already exists. Skipping.")
            else:
                print("Adding column 'ai_enabled' to 'businesses'...")
                conn.execute(text("ALTER TABLE businesses ADD COLUMN ai_enabled BOOLEAN DEFAULT 1"))
                print("Column added successfully.")
                
        except Exception as e:
            print(f"Error during migration: {e}")
            raise

if __name__ == "__main__":
    migrate()
