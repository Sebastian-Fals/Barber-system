import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from sqlalchemy import text

def run_migration():
    with engine.connect() as conn:
        stmts = [
            "ALTER TABLE customers ADD COLUMN conversation_state VARCHAR DEFAULT 'IDLE'",
            "ALTER TABLE customers ADD COLUMN conversation_data VARCHAR DEFAULT '{}'",
            "ALTER TABLE appointments ADD COLUMN reminded_24h BOOLEAN DEFAULT 0",
            "ALTER TABLE appointments ADD COLUMN reminded_1h BOOLEAN DEFAULT 0",
            "ALTER TABLE businesses ADD COLUMN open_hour INTEGER DEFAULT 9",
            "ALTER TABLE businesses ADD COLUMN close_hour INTEGER DEFAULT 18",
            "CREATE TABLE IF NOT EXISTS processed_messages (id INTEGER PRIMARY KEY, message_id VARCHAR UNIQUE, created_at DATETIME)"
        ]
        
        for s in stmts:
            try:
                conn.execute(text(s))
                print(f"Executed: {s}")
            except Exception as e:
                print(f"Skipped: {s} | Error: {e}")
        
        conn.commit()

if __name__ == "__main__":
    run_migration()
