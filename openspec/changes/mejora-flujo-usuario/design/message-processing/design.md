# Design: Immediate Message Processing (Fase 2)

## Technical Approach

Remove the 10-second `BufferService` debounce. Messages are processed directly on webhook receipt, with deduplication maintained via `ProcessedMessage` (now scoped by `business_id`). A 500ms cooldown per customer prevents rapid-fire duplicate processing without blocking.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Direct processing + DB dedup | Simple, fast | **Chosen** |
| Keep BufferService with shorter timeout | Still adds latency, extra DB table | Rejected |
| In-memory dedup cache | Not multi-worker safe | Rejected |

## Component Changes

### `app/api/webhook.py` — `process_background_message()`

```python
async def process_background_message(
    phone_number_id, from_number, msg_body, msg_type, interactive_id, business_id
):
    # No more BufferService.add_message — process directly
    if msg_type == "text":
        def _process():
            db = SessionLocal()
            try:
                service = ConversationService(db, phone_number_id, business_id)
                service.handle_incoming_message(from_number, msg_body, msg_type, interactive_id)
            finally:
                db.close()
        await run_in_threadpool(_process)
    else:
        # Interactive messages: same direct path (already bypassed buffer)
        ...
```

All messages now follow the same direct path — no `BufferService` branching.

### `app/services/buffer_service.py`

Marked for removal (Phase 3 in proposal). For now: keep file, remove usage from webhook. Phase 3 deletes `MessageBuffer` model and this file.

### Cooldown (500ms) — via `Customer.conversation_data`

```python
def _should_cooldown(customer: Customer) -> bool:
    data = json.loads(customer.conversation_data or "{}")
    last_msg_ts = data.get("_last_msg_ts", 0)
    now = time.time()
    if (now - last_msg_ts) < 0.5:
        return True
    data["_last_msg_ts"] = now
    customer.conversation_data = json.dumps(data)
    return False
```

Called in `ConversationService.handle_incoming_message()` before routing. If cooldown active, message is silently dropped (already deduped via `ProcessedMessage` at webhook level).

### `app/features/communication/conversation_service.py`

- Remove any buffer-related branching
- Add cooldown check at top of `handle_incoming_message()`

### Deduplication

Unchanged — `webhook.py` still checks `ProcessedMessage` before dispatching. With multi-tenant (Fase 0), dedup is now `(msg_id, business_id)` scoped per spec.

## Flow

```
Webhook recevied
    │
    ▼
db.query(ProcessedMessage).filter(msg_id=X, business_id=Y).first()
    │
    ├── exists → drop (duplicate)
    │
    └── new → insert ProcessedMessage → background task
                    │
                    ▼
            ConversationService.handle_incoming_message()
                    │
                    ▼
            cooldown check (500ms)
                    │
                    ├── within cooldown → drop
                    └── past cooldown → route to handler
```

## Testing Strategy

| Layer | Test | Approach |
|-------|------|----------|
| Unit | Messages processed <1s after webhook | Mock background task, assert ConversationService called without delay |
| Unit | 500ms cooldown blocks consecutive messages | Set `_last_msg_ts` to `now - 0.3s`, assert message dropped |
| Unit | Dedup still works | Insert ProcessedMessage, send same msg_id, verify dropped |
| Unit | BufferService NOT called | Verify no import/usage of BufferService in webhook flow |

## Rollback

Restore `BufferService.add_message` call in `process_background_message`. Remove cooldown check. Revert `ConversationService` to original routing.

## Open Questions

- [ ] Should cooldown be configurable per business? (Proposal says 500ms hardcoded — sufficient for now.)
