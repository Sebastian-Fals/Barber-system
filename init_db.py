from app.core.database import Base, engine
from app.models.models import Business, Barber, Customer, Appointment

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")

if __name__ == "__main__":
    init_db()
