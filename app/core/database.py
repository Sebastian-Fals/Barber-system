from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# For SQLite, we need to disable checking for same thread
# For Postgres, remove connect_args
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

from sqlalchemy.pool import NullPool

engine_kwargs = {
    "connect_args": connect_args,
    "pool_recycle": 300, # Recycle every 5 minutes (safer for Neon/Serverless)
    "pool_pre_ping": True # Critical: Test connection before use to catch closed SSL sockets
}

if "sqlite" in settings.DATABASE_URL:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10

# Handle 'postgres://' which is deprecated in SQLAlchemy 1.4+
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    db_url, 
    **engine_kwargs
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
