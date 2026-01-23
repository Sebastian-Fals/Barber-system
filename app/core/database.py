import pytz
from sqlalchemy import DateTime, String, TypeDecorator, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.datetime_utils import to_utc
from app.core.security import decrypt, encrypt

# For SQLite, we need to disable checking for same thread
# For Postgres, remove connect_args
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}


engine_kwargs = {
    "connect_args": connect_args,
    "pool_recycle": 300,  # Recycle every 5 minutes (safer for Neon/Serverless)
    "pool_pre_ping": True,  # Critical: Test connection before use to catch closed SSL sockets
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

engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class UTCDateTime(TypeDecorator):
    """
    TypeDecorator that ensures datetimes are always stored as UTC-aware (or naive UTC for SQLite) in the DB
    and returned as UTC-aware objects.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # Convert to UTC before saving
        return to_utc(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # Ensure returned value is UTC aware
        if value.tzinfo is None:
            return pytz.UTC.localize(value)
        return value.astimezone(pytz.UTC)


class EncryptedString(TypeDecorator):
    """
    TypeDecorator that encrypts data before saving to DB and decrypts when retrieving.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value)
