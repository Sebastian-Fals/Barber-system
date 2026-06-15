# Design: Multi-Tenant Foundation (Fase 0)

## Technical Approach

Add `business_id` FK column to `Customer`, `Appointment`, `ProcessedMessage`, and `ConversationHistory`. Resolve `phone_number_id → business_id` at webhook entry and propagate it through all downstream components. All repository queries become business-scoped.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `business_id` per row | Simple, portable across DBs | **Chosen** |
| PostgreSQL schemas per business | Complex ops, no SQLite fallback | Rejected |
| Lazy resolution (in handlers) | Duplicated logic, fragile | Rejected — resolve once at webhook |

## Data Model Changes

### `Customer`
- **Drop**: `phone_hash` unique constraint (single-column)
- **Add**: `business_id` FK → `businesses.id`, `UniqueConstraint(phone_hash, business_id)`
- `get_by_phone(from_number, business_id)` now requires both params

### `Appointment`
- **Add**: `business_id` FK → `businesses.id` (denormalized — avoids JOIN through barber)

### `ProcessedMessage`
- **Drop**: `message_id` unique constraint (global)
- **Add**: `business_id` FK → `businesses.id`, `UniqueConstraint(message_id, business_id)`

### `ConversationHistory`
- **Add**: `business_id` FK → `businesses.id`
- Scoped implicitly via `Customer.business_id`, but explicit column enables future queries without JOIN to Customer

## Component Changes

| File | Change |
|------|--------|
| `app/models/models.py` | Add `business_id` columns, FKs, composite unique constraints |
| `app/api/webhook.py` | Resolve `phone_number_id → business_id` before dedup/processing; pass `business_id` to `ConversationService`; dedup query scoped by `business_id` |
| `app/features/communication/conversation_service.py` | Constructor: `(db, phone_number_id, business_id)`. Propagate to all handlers |
| `app/features/customers/repository.py` | `get_by_phone(from_number, business_id)`; `create()` receives `business_id` |
| `app/features/appointments/repository.py` | All queries scoped by `business_id` |
| `app/services/handlers/*` | All handlers receive `business_id` in constructor |
| `app/services/buffer_service.py` | `add_message` receives `business_id` |
| `alembic/versions/` (new) | Migration: add columns → populate from barber/customer relations → add FKs → add unique constraints |

## Flow / Sequence

```
WhatsApp Webhook
    │
    ▼
webhook.py: extract phone_number_id
    │
    ▼
BusinessRepository.get_by_phone_number_id(phone_number_id)
    │
    ├── found → business_id resolved
    │       │
    │       ▼
    │   dedup: ProcessedMessage(msg_id, business_id)
    │       │
    │       ▼
    │   ConversationService(db, phone_number_id, business_id)
    │       │
    │       ▼
    │   handlers receive business_id → all queries scoped
    │
    └── NOT found → return 200 (silent ignore, no data created)
```

## Error Handling

- **Unknown `phone_number_id`**: Silent ignore (return 200). No un-scoped data. Log warning.
- **`IntegrityError` on dedup**: Already handled; now scoped by `(msg_id, business_id)`.
- **FK violation**: Only possible during migration — migration runs on clean DB or handles ordering.

## Alembic Migration Strategy

1. Add nullable `business_id` columns to all 4 tables
2. Backfill `Appointment.business_id` via `Barber.business_id`
3. Backfill `Customer.business_id` and `ConversationHistory.business_id` via existing relations
4. Backfill `ProcessedMessage.business_id` via message context (nullable if unknown)
5. Add `NOT NULL` constraints
6. Add FKs and composite unique constraints
7. **Downgrade**: reverse order — drop unique constraints, drop FKs, drop columns

## Testing Strategy

| Layer | Test | Approach |
|-------|------|----------|
| Unit | `CustomerRepository.get_by_phone` scoped | 2 businesses, same phone → each returns own customer |
| Unit | `ProcessedMessage` dedup | Same msg_id for B1 + B2 → B2 message processed |
| Unit | Webhook unknown `phone_number_id` | Returns 200, no DB writes |
| Unit | Migration up/down | Alembic test, verify constraints |

## Rollback

Alembic `downgrade` → drop constraints, drop columns. No production data to preserve (DB reset).

## Open Questions

- [ ] `ProcessedMessage` backfill: if a message can't be mapped to a business, set `business_id=NULL` temporarily? Or drop old messages? Decision needed.
