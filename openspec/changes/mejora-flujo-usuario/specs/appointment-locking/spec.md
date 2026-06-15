# appointment-locking Specification

## Purpose

Bloqueo atómico a nivel base de datos para prevenir double-booking (TOCTOU race condition) durante la creación de citas.

## Requirements

### Requirement: Atomic Slot Reservation

Al crear una cita, el sistema DEBE verificar disponibilidad y reservar el slot en UNA SOLA transacción atómica. En PostgreSQL, esto DEBE usar `SELECT ... FOR UPDATE`.

#### Scenario: Single user reserves a slot

- GIVEN slot "2026-06-20 10:00" is available for barber "Carlos"
- WHEN a user creates an appointment for that slot
- THEN the slot is verified as available and reserved atomically
- AND no other user can book the same slot

#### Scenario: Two concurrent users race for same slot

- GIVEN slot "2026-06-20 10:00" is available for barber "Carlos"
- WHEN User A and User B simultaneously attempt to book the same slot
- THEN exactly ONE user succeeds
- AND the other user receives a "slot unavailable" error
- AND no double-booking occurs

#### Scenario: Slot becomes unavailable during transaction

- GIVEN slot "2026-06-20 10:00" is available at the start of User A's transaction
- WHEN User B reserves the slot AFTER User A's availability check but BEFORE User A's insert commits
- THEN User A's transaction MUST roll back
- AND User A receives a clear "slot no longer available" response

### Requirement: Rollback on Conflict

Si dos usuarios intentan reservar el mismo slot concurrentemente, la transacción de quien llegue segundo DEBE hacer rollback automático y notificar al usuario.

#### Scenario: Rollback notification

- GIVEN User A is mid-transaction reserving slot "2026-06-20 10:00"
- WHEN User B's concurrent reservation for the same slot commits first
- THEN User A's attempt rolls back
- AND User A receives a human-readable message: "Este horario ya no está disponible. Por favor elegí otro."
