import sys
import json
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import Business, Barber

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def print_header(title):
    print("\n" + "="*40)
    print(f" {title}")
    print("="*40)

def input_or_default(prompt, default):
    val = input(f"{prompt} [{default}]: ").strip()
    return val if val else default

# --- Business Logic ---
def manage_businesses(db: Session):
    while True:
        print_header("MANAGE BUSINESSES")
        print("1. List Businesses")
        print("2. Create Business")
        print("3. Edit Business")
        print("4. Back")
        
        choice = input("Option: ")
        
        if choice == "1":
            items = db.query(Business).all()
            for i in items:
                print(f"ID: {i.id} | Name: {i.name} | PhoneID: {i.phone_number_id}")
        
        elif choice == "2":
            name = input("Name: ")
            pid = input("WhatsApp Phone Number ID: ")
            cal_id = input("Google Calendar ID (optional): ")
            
            # Simple Schedule Builder
            print("\n--- Schedule Configuration (Default 9-18) ---")
            schedule = {}
            for day_idx, day_name in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]):
                resp = input(f"Open on {day_name}? (y/n) [y]: ").lower()
                if resp != 'n':
                    start = int(input_or_default(f"  Open Hour (0-23)", "9"))
                    end = int(input_or_default(f"  Close Hour (0-23)", "18"))
                    schedule[str(day_idx)] = {"start": start, "end": end}
                    
            b = Business(
                name=name, 
                phone_number_id=pid, 
                calendar_id=cal_id, 
                schedule=json.dumps(schedule),
                open_hour=9, # Legacy defaults
                close_hour=18
            )
            db.add(b)
            db.commit()
            print("Business Created!")
            
        elif choice == "3":
            b_id = input("Business ID to edit: ")
            b = db.query(Business).filter(Business.id == b_id).first()
            if not b:
                print("Not found.")
                continue
                
            print(f"Editing {b.name}...")
            b.name = input_or_default("Name", b.name)
            b.phone_number_id = input_or_default("PhoneID", b.phone_number_id)
            b.calendar_id = input_or_default("Calendar ID", b.calendar_id)
            
            if input("Edit Schedule? (y/n) [n]: ").lower() == 'y':
                schedule = {}
                for day_idx, day_name in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]):
                    resp = input(f"Open on {day_name}? (y/n) [y]: ").lower()
                    if resp != 'n':
                        start = int(input_or_default(f"  Open Hour (0-23)", "9"))
                        end = int(input_or_default(f"  Close Hour (0-23)", "18"))
                        schedule[str(day_idx)] = {"start": start, "end": end}
                b.schedule = json.dumps(schedule)
                
            db.commit()
            print("Business Updated!")
            
        elif choice == "4":
            break

# --- Barber Logic ---
def manage_barbers(db: Session):
    while True:
        print_header("MANAGE BARBERS")
        print("1. List Barbers")
        print("2. Create Barber")
        print("3. Edit Barber")
        print("4. Back")
        
        choice = input("Option: ")
        
        if choice == "1":
            print(f"{'ID':<5} | {'Name':<20} | {'Business':<20} | {'Phone'}")
            print("-" * 60)
            items = db.query(Barber).all()
            for i in items:
                b_name = i.business.name if i.business else "None"
                print(f"{i.id:<5} | {i.name:<20} | {b_name:<20} | {i.phone}")
        
        elif choice == "2":
            # List businesses first
            print("Available Businesses:")
            bizs = db.query(Business).all()
            for b in bizs: print(f"  {b.id}: {b.name}")
            
            bid = input("Business ID: ")
            name = input("Barber Name: ")
            phone = input("Barber Phone (e.g. 57300...): ")
            cal_id = input("Barber Calendar ID (optional): ")
            
            new_b = Barber(business_id=bid, name=name, phone=phone, calendar_id=cal_id)
            db.add(new_b)
            db.commit()
            print("Barber Created!")
            
        elif choice == "3":
            b_id = input("Barber ID to edit: ")
            barber = db.query(Barber).filter(Barber.id == b_id).first()
            if not barber:
                print("Not found.")
                continue
                
            print(f"Editing {barber.name}...")
            barber.name = input_or_default("Name", barber.name)
            barber.phone = input_or_default("Phone", barber.phone)
            barber.calendar_id = input_or_default("Calendar ID", barber.calendar_id)
            barber.business_id = input_or_default("Business ID", str(barber.business_id))
            
            db.commit()
            print("Barber Updated!")
            
        elif choice == "4":
            break

def main():
    db = next(get_db())
    while True:
        print_header("ADMIN CONSOLE")
        print("1. Manage Businesses")
        print("2. Manage Barbers")
        print("3. Exit")
        
        choice = input("Select: ")
        if choice == "1":
            manage_businesses(db)
        elif choice == "2":
            manage_barbers(db)
        elif choice == "3":
            print("Bye!")
            break
        else:
            print("Invalid.")

if __name__ == "__main__":
    main()
