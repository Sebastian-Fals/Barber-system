import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from app.core.database import SessionLocal
from app.models.models import Business


def create_business(name, instance_name, instance_apikey, calendar_id):
    db = SessionLocal()
    try:
        # Check if exists
        existing = db.query(Business).filter(Business.instance_name == instance_name).first()
        if existing:
            print(f"Error: A business with instance '{instance_name}' already exists ({existing.name}).")
            return

        new_business = Business(
            name=name,
            instance_name=instance_name,
            instance_apikey=instance_apikey,
            calendar_id=calendar_id,
        )
        db.add(new_business)
        db.commit()
        print(f"Success! Business '{name}' created with instance '{instance_name}'.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("--- Registrador Manual de Negocios ---")
    i_name = input("Introduce el 'Instance Name' de Evolution API: ").strip()
    i_apikey = input("Introduce el 'API Key' de la instancia: ").strip()
    b_name = input("Nombre del Negocio: ").strip()
    c_id = input("ID del Calendario (email): ").strip()

    if i_name and i_apikey and b_name:
        create_business(b_name, i_name, i_apikey, c_id)
    else:
        print("Faltan datos.")
