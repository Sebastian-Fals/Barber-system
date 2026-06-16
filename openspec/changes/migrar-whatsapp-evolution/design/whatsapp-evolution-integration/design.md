# Design: WhatsApp Evolution API Integration

## Technical Approach

Cutover from Meta Cloud API to self-hosted Evolution API (Baileys). Delete all Meta code, rebuild on Evolution endpoints. Per-instance `apikey` header auth replaces global `Bearer` token. Interactive buttons become Lists (`rowId`-based selection). No dual-mode or backward compatibility.

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|----------|--------|----------|-----------|
| Auth model | Per-call params `(instance_name, apikey)` | Lookup inside WhatsAppService | Service stays stateless; handlers already hold business context |
| Handler constructor | Add `instance_apikey` to BaseHandler | Resolve via `self.business` on every call | Avoids redundant DB hits across ~50 send sites |
| List shape | Single section per call (`values[0].rows[]`) | Multi-section grouping | Every existing flow presents one category at a time |
| `send_message` rename | Keep name, change signature. Add `send_list`. | Rename to `send_text` | Minimizes conceptual diff |
| Webhook GET | Delete entirely | Keep with 404 | Evolution has no `hub.verify_token` challenge |

## Data Flow

```
WhatsApp User → Evolution → POST /api/v1/webhook
  → parse body.event, body.instance, body.data.{key.id, messageType}
  → BusinessRepository.get_by_instance_name(instance) → business (id, apikey)
  → ProcessedMessage dedup by (msg_id, business_id)
  → process_background_message(instance_name, apikey, from, body, type, interactive_id, business_id)
    → ConversationService(db, instance_name, apikey, business_id)
      → Handler(db, instance_name, apikey, business_id)
        → whatsapp_service.send_list(instance_name, apikey, to, title, desc, btnText, footer, rows)
          → POST {EVOLUTION_API_URL}/message/sendList/{instance_name}
            Headers: apikey: {apikey}
```

## Component Changes

### WhatsAppService (`whatsapp_service.py`) — Full Rewrite

Remove `self.token` and Meta `base_url`. Init reads `settings.EVOLUTION_API_URL`.

**`send_message(instance_name, apikey, to, body)`**: `POST /message/sendText/{instance_name}`, header `apikey`. Body: `{"number": to, "text": body}`.

**`send_list(instance_name, apikey, to, title, description, button_text, footer_text, rows)`**: `POST /message/sendList/{instance_name}`. Body includes `values: [{"title": "Opciones", "rows": rows}]`. Each row: `{"title": "...", "rowId": "service_1"}`.

Errors: HTTP non-2xx → log body, return `None`. `RequestException` → log, return `None`.

### Webhook (`webhook.py`) — Full Rewrite

Delete `GET /webhook`. Rewrite `POST`:

1. Extract `event = body.get("event")`. Non-`messages.upsert` → `{"status": "ignored"}`.
2. `instance_name = body.get("instance")`. Resolve via `get_by_instance_name()`. Unknown → log, return 200.
3. `data = body.get("data", {})`. `msg_id = data.get("key", {}).get("id")`. Phone: `remoteJid.split("@")[0]`.
4. Parse by `data.get("messageType")`:
   - `"conversation"` → text body from `message.conversation`
   - `"listResponse"` → `interactive_id = message.listResponseMessage.singleSelectReply.selectedRowId`
5. Dedup unchanged. Dispatch: `process_background_message(instance_name, business.instance_apikey, ...)`.

`process_background_message` signature adds `instance_apikey: str`.

### Business Model (`models.py`)

Rename `phone_number_id` → `instance_name` (String, unique, index, nullable=False). Add `instance_apikey = Column(EncryptedString, nullable=False)`.

### BusinessRepository (`repository.py`)

`get_by_phone_number_id` → `get_by_instance_name(self, instance_name: str)`.

### BaseHandler (`base_handler.py`)

Constructor: `(self, db, instance_name: str, instance_apikey: str, business_id: int)`.

### Handler Migration Pattern

Every `send_interactive_button(self.phone_number_id, to, body, buttons)` → `send_list(self.instance_name, self.instance_apikey, to, title, description, button_text, footer_text, rows)`.

`rows = [{"title": btn["title"], "description": "", "rowId": btn["id"]} for btn in buttons]`.

All handlers (~50 call sites across `welcome_handler`, `booking_handler`, `query_handler`) and `ConversationService` propagate `instance_name` + `instance_apikey` via constructor.

### Scheduling (`scheduling/service.py`)

`business.phone_number_id` → `business.instance_name` + `business.instance_apikey`. Reminder buttons → list rows.

### Config (`config.py`, `.env.example`)

Remove: `WHATSAPP_API_TOKEN`, `WHATSAPP_VERIFY_TOKEN`. Add: `EVOLUTION_API_URL: str`.

### Docker Compose (`docker-compose.yml` — new)

```yaml
services:
  evolution-api:
    image: atendai/evolution-api:v2.1.1
    ports: ["8080:8080"]
    environment:
      AUTHENTICATION_API_KEY: ${EVOLUTION_GLOBAL_API_KEY}
      SERVER_URL: http://localhost:8080
    volumes: [evolution_instances:/evolution/instances]
volumes: {evolution_instances:}
```

### Alembic Migration (`0003_evolution_migration.py`)

1. Rename column: `phone_number_id` → `instance_name`
2. Add `instance_apikey` (String, nullable)
3. Backfill: `UPDATE businesses SET instance_apikey = 'MIGRATE-ME' WHERE instance_apikey IS NULL`
4. Set NOT NULL on `instance_apikey`
5. Downgrade reverses each step.

## File Changes

| File | Action | Key Change |
|------|--------|------------|
| `app/core/config.py` | Modify | Remove Meta vars, add `EVOLUTION_API_URL` |
| `.env.example` | Modify | Evolution env vars replace WhatsApp section |
| `docker-compose.yml` | Create | Evolution API container |
| `app/models/models.py` | Modify | Rename column, add encrypted `instance_apikey` |
| `app/features/business/repository.py` | Modify | `get_by_instance_name` replaces phone lookup |
| `app/features/communication/whatsapp_service.py` | Rewrite | Evolution endpoints, per-call auth |
| `app/features/communication/conversation_service.py` | Modify | Constructor: `instance_name` + `apikey` |
| `app/api/webhook.py` | Rewrite | Evolution parser, drop GET, `instance` routing |
| `app/services/handlers/base_handler.py` | Modify | Add `instance_name`, `instance_apikey` params |
| `app/services/handlers/{welcome,booking,query}_handler.py` | Modify | `send_list` replaces buttons (~50 sites) |
| `app/features/scheduling/service.py` | Modify | `instance_name` + `apikey` for reminders |
| `alembic/versions/0003_evolution_migration.py` | Create | Column rename, `instance_apikey`, backfill |
| `scripts/*.py` (4 files) | Modify | Field rename references |
| `tests/conftest.py` | Modify | `sample_business` fixture: Evolution fields |
| `tests/unit/api/test_webhook.py` | Rewrite | Evolution payloads in all test cases |
| `tests/unit/features/communication/test_conversation_service.py` | Modify | Mocks for `instance_name` + `apikey` |
| `tests/unit/services/handlers/test_*_handler.py` (3 files) | Modify | Handler constructors, mock call assertions |

## Testing Strategy

| Layer | Focus | Approach |
|-------|-------|----------|
| Unit — Webhook | Payload parse, unknown instance, dedup | Evolution JSON fixtures; mock `BusinessRepository` |
| Unit — WhatsAppService | URL shape, headers, body structure | Mock `requests.post`; assert Evolution endpoint + `apikey` header |
| Unit — Handlers | `send_list` row mapping | Mock `whatsapp_service`; verify `rowId` matches legacy `button.id` |
| Unit — Model | `instance_apikey` encryption | `EncryptedString` roundtrip test |
| Integration | Migration | `alembic upgrade` + `downgrade` on test DB |

## Open Questions

- [ ] `footerText`: business name or empty? (UX — empty avoids clutter)
- [ ] Auto-restart policy for Evolution container? (recommend `restart: unless-stopped`)
- [ ] Exact title length limit from Evolution? (validate in dev before handler migration)
