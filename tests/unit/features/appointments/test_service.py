"""
RED tests: TOCTOU race-condition prevention in create_appointment.

Spec: appointment-locking — Atomic Slot Reservation.
- Scenario: Two concurrent users race for the same slot → exactly ONE succeeds.
"""
import os
import tempfile
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import SlotOccupiedError
from app.features.appointments.service import BookingService
from app.models.models import Appointment, AppointmentStatus, Barber, Business, Customer


def _make_temp_db():
    """Create a fresh file-based SQLite DB (shared across threads)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False})
    from app.models.models import Base

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal, tmp.name


def _seed_data(db: Session):
    """Seed minimal data for booking test."""
    business = Business(name="Test Biz", instance_name="test-inst", instance_apikey="test-key")
    db.add(business)
    db.flush()

    barber = Barber(name="Carlos", business_id=business.id)
    db.add(barber)
    db.flush()

    customer_a = Customer(phone="+57000111", name="User A", business_id=business.id)
    customer_b = Customer(phone="+57000222", name="User B", business_id=business.id)
    db.add_all([customer_a, customer_b])
    db.flush()

    db.commit()
    return business, barber, customer_a, customer_b


def test_single_booking_creates_appointment():
    """
    Scenario: Single user reserves a slot.
    - GIVEN slot is available
    - WHEN a user creates an appointment for that slot
    - THEN the appointment is created successfully.
    """
    engine, SessionLocal, tmp_path = _make_temp_db()
    try:
        db = SessionLocal()
        _biz, barber, customer_a, _customer_b = _seed_data(db)
        barber_id = barber.id
        db.close()

        db2 = SessionLocal()
        try:
            service = BookingService(db2)
            local_customer = db2.merge(customer_a)
            result = service.create_appointment(local_customer, barber_id, date_str="2026-06-20", time_str="10:00")
            assert result is not None
            assert result.status == AppointmentStatus.CONFIRMED.value
        finally:
            db2.close()
    finally:
        engine.dispose()
        os.unlink(tmp_path)


def test_second_booking_same_slot_fails():
    """
    Scenario: Slot becomes unavailable during transaction.
    - GIVEN User A already booked slot "2026-06-20 10:00"
    - WHEN User B tries to book the same slot
    - THEN User B receives SlotOccupiedError.
    """
    engine, SessionLocal, tmp_path = _make_temp_db()
    try:
        db = SessionLocal()
        _biz, barber, customer_a, customer_b = _seed_data(db)
        barber_id = barber.id
        db.close()

        # First booking succeeds
        db2 = SessionLocal()
        try:
            service = BookingService(db2)
            local_a = db2.merge(customer_a)
            result = service.create_appointment(local_a, barber_id, date_str="2026-06-20", time_str="10:00")
            assert result is not None
        finally:
            db2.close()

        # Second booking for same slot must fail
        db3 = SessionLocal()
        try:
            service = BookingService(db3)
            local_b = db3.merge(customer_b)

            with pytest.raises(SlotOccupiedError):
                service.create_appointment(local_b, barber_id, date_str="2026-06-20", time_str="10:00")
        finally:
            db3.close()
    finally:
        engine.dispose()
        os.unlink(tmp_path)


def test_concurrent_same_slot_no_double_booking():
    """
    Scenario: Two concurrent users race for the same slot.
    - GIVEN slot "2026-06-20 10:00" is available
    - WHEN User A and User B simultaneously attempt to book the same slot
    - THEN no double-booking occurs in the database (invariant).
    - AND at least one user succeeds.

    Reliability note:
    - **SQLite**: Thread safety depends on `BEGIN IMMEDIATE` + `check_same_thread=False`.
      Under high contention the second thread's `BEGIN IMMEDIATE` may fail with
      `OperationalError` (caught and re-raised as `SlotOccupiedError`). This test
      uses `threading.Barrier` to maximize the race window and should pass reliably.
    - **PostgreSQL**: `SELECT ... FOR UPDATE` provides true row-level locking.
      The invariant holds with ACID guarantees — no timing caveats needed.
    - Sequential tests (`test_single_booking`, `test_second_booking_same_slot_fails`)
      verify the locking logic deterministically regardless of backend.
    """
    engine, SessionLocal, tmp_path = _make_temp_db()
    try:
        seed_db = SessionLocal()
        _business, barber, customer_a, customer_b = _seed_data(seed_db)
        barber_id = barber.id
        seed_db.close()

        results = {"success": 0, "error": 0, "error_type": None}
        barrier = threading.Barrier(2, timeout=10)

        def attempt_booking(customer):
            db = SessionLocal()
            try:
                service = BookingService(db)
                local_customer = db.merge(customer)
                barrier.wait(timeout=10)
                service.create_appointment(local_customer, barber_id, date_str="2026-06-20", time_str="10:00")
                results["success"] += 1
            except SlotOccupiedError:
                results["error"] += 1
                results["error_type"] = "SlotOccupiedError"
            except Exception as e:
                results["error"] += 1
                results["error_type"] = type(e).__name__
            finally:
                db.close()

        t1 = threading.Thread(target=attempt_booking, args=(customer_a,))
        t2 = threading.Thread(target=attempt_booking, args=(customer_b,))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        # Core invariant: NO double-booking
        verify_db = SessionLocal()
        try:
            count = (
                verify_db.query(Appointment)
                .filter(
                    Appointment.barber_id == barber_id,
                    Appointment.status == AppointmentStatus.CONFIRMED.value,
                )
                .count()
            )
            assert count == 1, (
                f"CRITICAL: Double-booking detected! Found {count} confirmed appointments. " f"Results: {results}"
            )
            assert results["success"] >= 1, f"Expected at least 1 success. Results: {results}"
        finally:
            verify_db.close()
    finally:
        engine.dispose()
        os.unlink(tmp_path)
