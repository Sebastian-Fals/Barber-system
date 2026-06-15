# Tasks: Mejora del Flujo de Usuario

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~920-1150 total (4 chained PRs) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR#0 (multi-tenant) → PR#1 (bugs+security) → PR#2 (booking-flow) → PR#3 (message-processing) |
| Delivery strategy | ask-always |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | PR | Base | Lines |
|------|------|-----|------|-------|
| 0 | Multi-tenant foundation: business_id en 4 tablas, scoping, webhook | PR#0 | `feature/mejora-flujo-usuario` (tracker) | ~350-400 |
| 1 | TOCTOU lock, encryption validation, secrets, PII, cancel | PR#1 | PR#0 branch | ~250-350 |
| 2 | SELECT_SERVICE, Service model, botones unificados AI/no-AI | PR#2 | PR#1 branch | ~200-250 |
| 3 | Remove debounce, cooldown 500ms, refactor, dead code | PR#3 | PR#2 branch | ~120-150 |

## Fase 0: Multi-Tenant Foundation (~350-400 líneas)

- [x] 0.1 **RED** `tests/unit/models/test_customer.py`: unique compuesto `(phone_hash, business_id)` — mismo phone en 2 businesses sin conflicto; mismo phone + mismo business → IntegrityError
- [x] 0.2 **RED** `tests/unit/models/test_processed_message.py`: dedup por `(msg_id, business_id)` — B1 msg_id no bloquea B2; `tests/unit/repositories/test_customer_repo.py`: `get_by_phone` scoped, solo devuelve cliente del business correcto
- [x] 0.3 **RED** `tests/unit/api/test_webhook.py`: `phone_number_id` desconocido → 200 sin DB writes; `tests/unit/repositories/test_business_repo.py`: `get_by_phone_number_id` devuelve business o None
- [x] 0.4 **GREEN** `app/models/models.py`: `business_id` FK + unique compuesto en Customer, Appointment, ProcessedMessage, ConversationHistory
- [x] 0.5 **GREEN** `alembic/versions/xxx_multi_tenant.py`: add nullable columns → backfill vía Barber.business_id → NOT NULL → FKs → composite unique constraints
- [x] 0.6 **GREEN** `app/features/business/repository.py`: `get_by_phone_number_id(phone_number_id)`; `app/features/customers/repository.py`: `get_by_phone(from_number, business_id)`, `create()` con `business_id`
- [x] 0.7 **GREEN** `app/api/webhook.py`: resolver `phone_number_id → business_id` temprano, dedup query con `(msg_id, business_id)`, propagar a `ConversationService`
- [x] 0.8 **GREEN** `app/features/communication/conversation_service.py`: constructor `(db, phone_number_id, business_id)`, handlers + `BufferService` reciben `business_id`

## Fase 1: Bugs + Security (~250-350 líneas)

- [x] 1.1 **RED** `tests/unit/core/test_security.py`: `validate_encryption_key()` con key válida → no exception, key inválida → ValueError, key missing → ValueError
- [x] 1.2 **RED** `tests/unit/features/calendar/test_service.py`: credenciales desde `GOOGLE_APPLICATION_CREDENTIALS_JSON` válido, missing, JSON malformado
- [x] 1.3 **RED** `tests/unit/features/appointments/test_service.py`: 2 threads concurrentes mismo slot → 1 success + 1 `SlotOccupiedError`; `tests/unit/services/handlers/test_booking_handler.py`: "cancelar" texto → state=IDLE, `conversation_data` cleared
- [x] 1.4 **GREEN** `app/core/security.py`: `validate_encryption_key()` con sentinel round-trip, remover `try/except` silencioso en `decrypt()`; `app/main.py`: lifespan llama `validate_encryption_key()`
- [x] 1.5 **GREEN** `app/core/config.py`: `GOOGLE_APPLICATION_CREDENTIALS_JSON`; `app/features/calendar/service.py`: `_authenticate()` con `json.loads(env_var)` y `from_service_account_info`; `.env.example` actualizado; borrar `credentials.json`
- [x] 1.6 **GREEN** `app/features/appointments/service.py`: `create_appointment` con `SELECT ... FOR UPDATE` (PG) / `BEGIN IMMEDIATE` (SQLite); `SlotOccupiedError` con mensaje humano
- [x] 1.7 **GREEN** `app/services/handlers/booking_handler.py`: handle "cancelar" texto → `_update_state(IDLE, {})`; `app/core/logging_config.py`: sanitizar PII (nombres, teléfonos) en logs

## Fase 2: Unified Booking UX (~200-250 líneas)

- [x] 2.1 **RED** `tests/unit/models/test_service.py`: Service model creation + SQLite constraint tests; `tests/unit/repositories/test_service_repo.py`: `get_by_business` filtering
- [x] 2.2 **RED** `tests/unit/services/handlers/test_welcome_handler.py`: `_start_booking_flow` envía service buttons, state=SELECT_SERVICE; `tests/unit/.../test_booking_handler.py`: `service_X` interactive → SELECT_BARBER con barber buttons
- [x] 2.3 **GREEN** `app/models/models.py`: `Service` model (id, business_id FK, name, duration_minutes); `app/features/business/service_repository.py` (new): `get_by_business(business_id)`
- [x] 2.4 **GREEN** `app/services/handlers/welcome_handler.py`: `_start_booking_flow` → SELECT_SERVICE; `booking_handler.py`: `_handle_service_selection` → barber buttons, routing `service_` prefix, botón Cancelar en cada step
- [x] 2.5 **GREEN** `app/services/handlers/query_handler.py`: `_smart_booking_transition` → SELECT_SERVICE con botones interactivos; PROVIDE_NAME y FALLBACK intents; `conversation_service.py`: `_route_interactive_message` agrega `service_` prefix routing

## Fase 3: Message Processing (~120-150 líneas)

- [x] 3.1 **RED** `tests/unit/api/test_webhook.py`: mensaje procesado sin `BufferService.add_message`, dedup vía `ProcessedMessage` sigue funcionando; `tests/unit/features/communication/test_conversation_service.py`: cooldown 500ms bloquea mensajes consecutivos <500ms
- [x] 3.2 **GREEN** `app/api/webhook.py`: `process_background_message` procesa directo sin `BufferService`; `app/features/communication/conversation_service.py`: cooldown check 500ms en `handle_incoming_message`
- [x] 3.3 **GREEN** `app/services/buffer_service.py`: eliminar archivo; `app/models/models.py`: eliminar `MessageBuffer` model; limpiar imports huérfanos en webhook y conversation_service
- [x] 3.4 **GREEN** Documentar key immutability: `ENCRYPTION_KEY` no debe cambiarse post-deploy; limpiar dead code y comentarios obsoletos
