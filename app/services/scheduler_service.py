from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import Appointment, Customer, Barber, AppointmentStatus
from app.services.whatsapp_service import whatsapp_service
import datetime

scheduler = BackgroundScheduler()

def check_upcoming_appointments():
    """
    Checks for appointments happening in 24 hours or 1 hour 
    and sends reminders if not already sent.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.datetime.now()
        
        # 1. Check 24 Hour Reminders
        # Window: 23.5h to 24.5h from now (loose check to catch them)
        start_win_24 = now + datetime.timedelta(hours=23, minutes=30)
        end_win_24 = now + datetime.timedelta(hours=24, minutes=30)
        
        # Appointments in this window that are CONFIRMED and NOT reminded
        upcoming_24 = db.query(Appointment).filter(
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.reminded_24h == False,
            Appointment.start_time >= start_win_24,
            Appointment.start_time <= end_win_24
        ).all()
        
        for appt in upcoming_24:
            send_reminder_24h(appt)
            appt.reminded_24h = True
            db.commit()
            
        # 2. Check 1 Hour Reminders
        # Window: 55m to 65m from now
        start_win_1 = now + datetime.timedelta(minutes=55)
        end_win_1 = now + datetime.timedelta(minutes=65)

        upcoming_1 = db.query(Appointment).filter(
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.reminded_1h == False,
            Appointment.start_time >= start_win_1,
            Appointment.start_time <= end_win_1
        ).all()

        for appt in upcoming_1:
            send_reminder_1h(appt)
            appt.reminded_1h = True
            db.commit()

    except Exception as e:
        print(f"Error in Scheduler: {e}")
    finally:
        db.close()

def send_reminder_24h(appt: Appointment):
    customer = appt.customer
    barber = appt.barber
    
    # 24h Message with Options
    msg = f"🔔 *Recordatorio de Cita Mañana*\n\nHola {customer.name}, te recordamos tu cita:\n💈 {barber.name}\n📅 {appt.start_time.strftime('%Y-%m-%d')}\n⏰ {appt.start_time.strftime('%H:%M')}\n\n¿Nos confirmas tu asistencia?"
    
    buttons = [
        {"id": f"rem_confirm_{appt.id}", "title": "✅ Confirmar"},
        {"id": f"rem_reschedule_{appt.id}", "title": "🔄 Cambiar"},
        {"id": f"rem_cancel_{appt.id}", "title": "❌ Cancelar"}
    ]
    # Note: WhatsApp allows max 3 buttons.
    
    # We need to access phone_number_id. 
    # Assumption: Business phone id is linked to Barber's Business.
    # In this MVP, we might need to fetch business or pass it.
    # Let's assume singular business for now or fetch via Barber.
    business = barber.business
    if business:
        whatsapp_service.send_interactive_button(business.phone_number_id, customer.phone, msg, buttons)

def send_reminder_1h(appt: Appointment):
    customer = appt.customer
    barber = appt.barber
    business = barber.business
    
    msg = f"⏳ *Tu cita es en 1 hora*\n\nNos vemos pronto en {business.name} con {barber.name}."
    if business:
        whatsapp_service.send_message(business.phone_number_id, customer.phone, msg)

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(check_upcoming_appointments, 'interval', minutes=10) # Run every 10 mins
        scheduler.start()
        print("Scheduler started!")
