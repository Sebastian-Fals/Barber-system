from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import Appointment, Customer, Barber, AppointmentStatus
from app.services.whatsapp_service import whatsapp_service
from app.core.logging_config import logger
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
        # Window: 23h to 25h from now (2 hour window to catch everything safely)
        start_win_24 = now + datetime.timedelta(hours=23)
        end_win_24 = now + datetime.timedelta(hours=25)
        
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
        # Window: 45m to 75m from now (30 min window for robustness)
        start_win_1 = now + datetime.timedelta(minutes=45)
        end_win_1 = now + datetime.timedelta(minutes=75)

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
        logger.error(f"Error in Scheduler: {e}", exc_info=True)
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
        
def cleanup_processed_messages():
    """
    Deletes processed messages older than 3 days to keep DB clean.
    """
    db: Session = SessionLocal()
    try:
        from app.models.models import ProcessedMessage
        limit_date = datetime.datetime.now() - datetime.timedelta(days=3)
        
        deleted_count = db.query(ProcessedMessage).filter(
            ProcessedMessage.created_at < limit_date
        ).delete()
        
        db.commit()
        if deleted_count > 0:
            logger.info(f"Cleanup: Deleted {deleted_count} old processed messages.")
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(check_upcoming_appointments, 'interval', minutes=10) # Run every 10 mins
        scheduler.add_job(cleanup_processed_messages, 'interval', hours=24) # Run daily
        scheduler.start()
        logger.info("Scheduler started!")
