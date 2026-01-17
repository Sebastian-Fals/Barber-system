from app.core.database import SessionLocal
from app.models.models import Barber, Business


def create_barber(business_name, barber_name, calendar_id):
    db = SessionLocal()
    try:
        business = db.query(Business).filter(Business.name == business_name).first()
        if not business:
            print("Business not found.")
            return

        new_barber = Barber(business_id=business.id, name=barber_name, calendar_id=calendar_id, phone="000")
        db.add(new_barber)
        db.commit()
        print(f"Barber '{barber_name}' created for '{business_name}'.")
    except Exception as e:
        print(e)
    finally:
        db.close()


if __name__ == "__main__":
    print("--- Crear Barbero ---")
    b_bus = input("Nombre del Negocio (ej: PeluqueriaSebastian): ")
    b_name = input("Nombre del Barbero: ")
    c_id = input("ID Calendario Barbero (email): ")
    create_barber(b_bus, b_name, c_id)
