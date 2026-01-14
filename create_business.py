from app.core.database import SessionLocal
from app.models.models import Business
import sys

def create_business(name, phone_id, calendar_id):
    db = SessionLocal()
    try:
        # Check if exists
        existing = db.query(Business).filter(Business.phone_number_id == phone_id).first()
        if existing:
            print(f"Error: A business with ID {phone_id} already exists ({existing.name}).")
            return

        new_business = Business(
            name=name,
            phone_number_id=phone_id,
            calendar_id=calendar_id
        )
        db.add(new_business)
        db.commit()
        print(f"Success! Business '{name}' created with WhatsApp ID '{phone_id}'.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("--- Registrador Manual de Negocios ---")
    p_id = input("Introduce el 'Phone Number ID' de WhatsApp (copialo de Meta): ").strip()
    b_name = input("Nombre del Negocio: ").strip()
    c_id = input("ID del Calendario (email): ").strip()
    
    if p_id and b_name:
        create_business(b_name, p_id, c_id)
    else:
        print("Faltan datos.")
