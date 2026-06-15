# Design: Unified Booking Flow with Service Selection (Fase 2)

## Technical Approach

Insert `SELECT_SERVICE` as the first step of the booking flow. The `CustomerData` enum already has `SELECT_SERVICE` defined — we wire it into `welcome_handler.py`, `booking_handler.py`, and `query_handler.py`. Both AI and non-AI modes share the same interactive button payloads. The LLM never generates UI markup.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Service as DB table (new) | Flexible, supports per-business services | **Chosen** — `Service` model with `name, business_id, duration` |
| Service as hardcoded enum | Zero migration, inflexible | Rejected — multi-tenant needs per-business customization |
| AI generates button markup | LLM hallucination risk, inconsistent UI | Rejected — buttons are static payloads shared by both modes |

## Data Model Changes

### New: `Service` model
```python
class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String, nullable=False)
    duration_minutes = Column(Integer, default=60)
```

### Existing: `CustomerData` enum
- `SELECT_SERVICE` already exists at line 56 of `models.py` — no change needed

## Component Changes

| File | Change |
|------|--------|
| `app/models/models.py` | Add `Service` model |
| `app/features/business/service_repository.py` (new) | `get_by_business(business_id)` |
| `app/services/handlers/welcome_handler.py` | `_start_booking_flow`: transition to `SELECT_SERVICE` instead of `SELECT_BARBER`; show service buttons |
| `app/services/handlers/booking_handler.py` | Add `_handle_service_selection` → transition to `SELECT_BARBER`; add to `handle_interactive` routing (`service_` prefix); add "Cancelar" button in every step's menu |
| `app/services/handlers/query_handler.py` | `_smart_booking_transition`: start at `SELECT_SERVICE` instead of `SELECT_BARBER` |

## Flow / Sequence

```
SELECT_SERVICE ─→ SELECT_BARBER ─→ SELECT_DATE ─→ SELECT_SLOT ─→ CONFIRM_BOOKING
      │                │               │              │               │
      │           [Cancelar]      [Cancelar]     [Cancelar]      [Cancelar]
      │                │               │              │               │
      └────────────────┴───────────────┴──────────────┴──────→ IDLE (reset)
```

- **Cancelar button**: Present in every step's interactive menu. Sets state to IDLE, clears `conversation_data`.
- **AI mode**: QueryHandler detects `BOOK_APPOINTMENT` intent → calls `_smart_booking_transition` which now starts at `SELECT_SERVICE` with service buttons.
- **Non-AI mode**: WelcomeHandler → `_start_booking_flow` sends service buttons. BookingHandler routes `service_*` IDs.

## Unified Button Payloads (AI + non-AI)

```python
# Both modes use identical payloads:
buttons = [{"id": f"service_{s.id}", "title": s.name} for s in services]
```

`_route_interactive_message` in `conversation_service.py` adds `service_` prefix to routing.

## Error Handling

- **Invalid service selection** (text that doesn't match): Re-prompt with available service buttons. BookingHandler stays in `SELECT_SERVICE` state.
- **Cancel mid-flow**: Button `cancel_flow` → `_update_state(IDLE, {})` → send welcome menu.

## Testing Strategy

| Layer | Test | Approach |
|-------|------|----------|
| Unit | `WelcomeHandler._start_booking_flow` | Verify sends service buttons, state = SELECT_SERVICE |
| Unit | `BookingHandler._handle_service_selection` | Verify transition to SELECT_BARBER with barber buttons |
| Unit | Cancel at each step | Inject state, send "cancelar", verify state = IDLE |
| Unit | AI + non-AI use same button IDs | Compare payloads from both handlers |

## Rollback

Revert ordering change: `_start_booking_flow` goes directly to `SELECT_BARBER`. Drop `Service` table via Alembic downgrade. Remove `service_` prefix routing.

## Open Questions

- [ ] Should each business configure its own services via admin panel, or seed via migration? Decision: seed via migration with defaults, admin CRUD later.
