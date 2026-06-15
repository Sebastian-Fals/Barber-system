# Design: TOCTOU Appointment Locking (Fase 1)

## Technical Approach

Wrap availability check + insert in a single DB transaction using `SELECT ... FOR UPDATE` on the barber's appointment rows for the target time window. PostgreSQL locks the rows; SQLite falls back to `BEGIN IMMEDIATE`. If two users race, the second `SELECT ... FOR UPDATE` blocks until the first commits — then sees the slot is taken and raises `SlotOccupiedError`.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `SELECT ... FOR UPDATE` at DB level | Correct, portable to PostgreSQL, SQLite fallback possible | **Chosen** |
| In-memory mutex (per barber) | Not multi-worker safe | Rejected |
| Advisory lock (`pg_advisory_lock`) | PostgreSQL-only, extra complexity | Rejected — FOR UPDATE is sufficient |

## Component Changes

### `app/features/appointments/service.py` — `create_appointment()`

Current flow (lines 164–253) does availability check THEN insert in separate steps — TOCTOU window exists.

**New flow (atomic transaction)**:

```python
def create_appointment(self, customer, barber_id, date_str, time_str):
    # Lock barber's appointments for the target time window
    locked = (
        self.db.query(Appointment)
        .filter(
            Appointment.barber_id == barber_id,
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
            Appointment.status == AppointmentStatus.CONFIRMED,
        )
        .with_for_update()  # ← LOCKS matching rows
        .all()
    )
    if locked:
        raise SlotOccupiedError("Este horario ya no está disponible.")
    # Insert
    appt = Appointment(...)
    self.db.add(appt)
    self.db.commit()  # ← releases lock
```

The `with_for_update()` call requires `self.db` to be inside an active transaction (which it is for POST requests via `get_db`). No explicit `BEGIN` needed.

### SQLite fallback

SQLite's `FOR UPDATE` is a no-op. For SQLite, use `BEGIN IMMEDIATE` transaction mode:

```python
if "sqlite" in settings.DATABASE_URL:
    self.db.execute(text("BEGIN IMMEDIATE"))
```

This prevents concurrent writes to the same table, providing equivalent protection.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Slot free → lock acquired | Insert succeeds, commit, lock released |
| Slot taken → lock acquired, overlapping rows returned | `SlotOccupiedError: "Este horario ya no está disponible. Por favor elegí otro."` — rollback |
| DB lock timeout (PostgreSQL) | SQLAlchemy raises `OperationalError` → catch, return "Intenta de nuevo en un momento" |
| Concurrent insert in SQLite | `IntegrityError` caught → rollback, same user-facing message |

## Testing Strategy

| Layer | Test | Approach |
|-------|------|----------|
| Unit | Lock prevents double booking | Two threads, same slot, `concurrent.futures.ThreadPoolExecutor`, assert 1 success + 1 SlotOccupiedError |
| Unit | Lock timeout handling | Setup with short `lock_timeout`, assert graceful error message |
| Unit | SQLite fallback path | Patch `settings.DATABASE_URL` to sqlite, verify `BEGIN IMMEDIATE` execution |

## Rollback

Remove `with_for_update()` and `BEGIN IMMEDIATE` block. No schema changes to revert. Simple code revert.

## Open Questions

- [ ] What PostgreSQL `lock_timeout` value? Default is 0 (wait forever). Recommend `statement_timeout` 5s or explicit `lock_timeout` in session config.
