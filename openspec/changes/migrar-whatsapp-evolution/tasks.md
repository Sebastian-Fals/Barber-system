# Tasks: Migrate WhatsApp to Evolution API

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 800–1000 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Single PR with size exception |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: size-exception
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Docker + Config | PR 1 (same) | Foundation; no deps |
| 2 | Business Model + Migration | PR 1 (same) | DB schema; reversible via downgrade |
| 3 | WhatsAppService + Webhook Rewrite | PR 1 (same) | Core send/receive engine |
| 4 | Handler Migration (send_list) | PR 1 (same) | ~50 call sites; depends on Unit 3 |
| 5 | Full Test Suite Rewrite + Verify | PR 1 (same) | Evolution payloads and mocks |

## Phase 1: Infrastructure (Docker + Config)

- [x] 1.1 Create `docker-compose.yml` with Evolution API service (`atendai/evolution-api:v2.1.1`, port 8080, `AUTHENTICATION_API_KEY`, volume)
- [x] 1.2 Replace `WHATSAPP_API_TOKEN`/`WHATSAPP_VERIFY_TOKEN` with `EVOLUTION_API_URL` in `app/core/config.py` and `.env.example`

## Phase 2: Business Model + Migration

- [x] 2.1 RED: Write model test asserting `instance_name` (unique, indexed) + `instance_apikey` (EncryptedString); `phone_number_id` removed
- [x] 2.2 GREEN: Rename `phone_number_id` → `instance_name`; add `instance_apikey = Column(EncryptedString)` in `app/models/models.py`
- [x] 2.3 Rename `get_by_phone_number_id` → `get_by_instance_name` in `app/features/business/repository.py`
- [x] 2.4 Create Alembic migration `0003_evolution_migration.py`: rename column, add `instance_apikey`, backfill `MIGRATE-ME`, set NOT NULL
- [x] 2.5 Update field references in `scripts/{add_business,create_business,admin_cli,seed_full}.py`

## Phase 3: WhatsAppService + Webhook Rewrite

- [x] 3.1 RED: Write `test_whatsapp_service.py` — assert `send_message` POSTs to `/message/sendText/{instance}` with `apikey` header and `{number, text}` body; assert `send_list` body shape
- [x] 3.2 GREEN: Rewrite `app/features/communication/whatsapp_service.py` — `send_message(instance_name, apikey, to, body)` + `send_list(instance_name, apikey, to, title, desc, btnText, footer, rows)`
- [x] 3.3 RED: Write webhook parse tests with Evolution JSON fixtures — `messages.upsert` text, `listResponse`, `CONNECTION_UPDATE` ignored
- [x] 3.4 GREEN: Rewrite `app/api/webhook.py` — Evolution parser, drop GET, `get_by_instance_name` routing, `listResponseMessage.singleSelectReply.selectedRowId` extraction
- [x] 3.5 Update `BaseHandler.__init__` + `ConversationService.__init__` to accept and propagate `instance_name` + `instance_apikey`

## Phase 4: Handler Migration (send_list replaces buttons)

- [x] 4.1 RED: Test WelcomeHandler sends `send_list` with rows where `rowId` matches legacy button IDs
- [x] 4.2 GREEN: Migrate `app/services/handlers/welcome_handler.py` — ~15 `send_interactive_button` → `send_list`
- [x] 4.3 GREEN: Migrate `app/services/handlers/booking_handler.py` — ~20 button calls → `send_list`
- [x] 4.4 GREEN: Migrate `app/services/handlers/query_handler.py` — ~5 button calls → `send_list`
- [x] 4.5 Update `app/features/scheduling/service.py` — reminders use `business.instance_name` + `send_list`

## Phase 5: Full Test Suite + Verify

- [x] 5.1 Rewrite `tests/conftest.py` — `sample_business` fixture: `instance_name` + `instance_apikey`, no `phone_number_id`
- [x] 5.2 Rewrite `tests/unit/api/test_webhook.py` — all Evolution payloads matching spec scenarios
- [x] 5.3 Rewrite `tests/unit/features/communication/test_conversation_service.py` — mocks for new constructor signature
- [x] 5.4 Rewrite `tests/unit/services/handlers/test_{welcome,booking,query}_handler.py` — assert `send_list` calls with correct `rowId`
- [x] 5.5 Run `python -m pytest` — full suite green; run `alembic upgrade head && alembic downgrade -1` — verify reversible
