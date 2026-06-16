# Proposal: Migrate WhatsApp to Evolution API

## Intent

Replace Meta Cloud API with self-hosted Evolution API (Baileys engine) to eliminate per-conversation costs and Meta vendor lock-in. Clean cut — no backward compatibility.

## Scope

### In Scope
- Rewrite `whatsapp_service.py` for Evolution endpoints (`sendText`, `sendList`)
- Rewrite `webhook.py` parser; drop Meta `GET` verification entirely
- Migrate `Business` model: rename `phone_number_id` → `instance_name`, add encrypted `instance_apikey`
- Convert all handlers from `send_interactive_button` → `send_list` (~35 call sites)
- Alembic migration, seed script updates, `docker-compose.yml` for Evolution container
- Rewrite test payloads and mocks for Evolution format

### Out of Scope
- Automated instance creation via `/instance/create` (manual Dashboard workflow)
- Dual Meta/Evolution support during transition
- `WHATSAPP-BUSINESS` mode (Evolution as Meta proxy — defeats cost elimination)
- Message queues or throttling (low volume for MVP)

## Capabilities

### New Capabilities
- `whatsapp-evolution-integration`: Send/receive WhatsApp messages via self-hosted Evolution API (Baileys). Text messages via `sendText`, interactive menus via `sendList`. Multi-instance routing by `instance_name` with per-instance `apikey` header auth.

### Modified Capabilities
None — no existing specs.

## Approach

**Single cutover, no conditional branches.** Delete all Meta code, rebuild on Evolution.

1. **Infra**: Add Evolution API Docker service
2. **Config**: Replace `WHATSAPP_API_TOKEN`/`WHATSAPP_VERIFY_TOKEN` with `EVOLUTION_API_URL`
3. **DB**: Rename column, add `instance_apikey` (EncryptedString), Alembic migration
4. **Send**: `send_message()` → `/message/sendText/{instance}`; new `send_list()` → `/message/sendList/{instance}` (replaces interactive buttons)
5. **Receive**: Parse Evolution `{instance, event, data.key.id, data.messageType}`; resolve business via `get_by_instance_name()`
6. **Handlers**: Propagate `instance_name` + `instance_apikey` through `ConversationService` → all handlers
7. **Tests**: Rewrite webhook payloads and handler mocks

## Affected Areas

| Area | Impact |
|------|--------|
| `app/core/config.py`, `.env.example` | Remove Meta vars; add `EVOLUTION_API_URL` |
| `docker-compose.yml` | New Evolution API service |
| `app/models/models.py` | Rename `phone_number_id` → `instance_name`, add `instance_apikey` |
| `app/features/business/repository.py` | `get_by_phone_number_id` → `get_by_instance_name` |
| `app/features/communication/` (whatsapp_service, conversation_service) | Rewrite send layer; per-instance auth |
| `app/api/webhook.py` | Rewrite parser; drop `GET` verification |
| `app/services/handlers/` (base, welcome, booking, query) | `phone_number_id` → `instance_name`; 35+ button→list conversions |
| `app/features/scheduling/service.py` | Reminders use `send_list` |
| `alembic/versions/` | New migration |
| `scripts/` (add_business, create_business, admin_cli, seed_full) | Field rename references |
| `tests/` (test_webhook, test_conversation_service, test_*_handler, conftest) | Evolution payloads, mocks, fixtures |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Send List instability (Evolution marks it "testing") | Medium | Full handler suite validation in dev first |
| Instance disconnection (QR expiry, logout) | Medium | Evolution auto-reconnects; monitor via `CONNECTION_UPDATE` webhook |
| WhatsApp Web rate limits (~50 msg/min) | Low | Current volume well under limit; add queue only if needed |
| Manual onboarding friction (Dashboard + DB) | Low | 1–3 businesses; documented setup guide |

## Rollback Plan

1. Archive old service files in `_legacy/` until verified
2. Keep Meta webhook configured; Evolution runs in parallel
3. DB migration is reversible: `alembic downgrade -1`
4. Full rollback: restore old files, point webhook to Meta, revert env vars, downgrade migration

## Success Criteria

- [ ] `sendText` delivers text messages end-to-end
- [ ] `sendList` delivers interactive menus; user selections parsed correctly
- [ ] Webhook routes `messages.upsert` to correct `Business` by `instance_name`
- [ ] All handler flows (welcome, booking, query, reminders) work with List UX
- [ ] `python -m pytest` passes with updated Evolution payloads
- [ ] `alembic upgrade head` succeeds on production schema
- [ ] `WHATSAPP_API_TOKEN` and `WHATSAPP_VERIFY_TOKEN` removed from all config

## Alternatives Considered

| Alternative | Rejected because |
|-------------|-----------------|
| Gradual dual Meta+Evolution migration | User chose clean cut; dual paths add complexity with no long-term value |
| `WHATSAPP-BUSINESS` mode (Evolution as proxy) | Keeps Meta costs; defeats purpose |
| Hack Evolution to support legacy buttons | Buttons discontinued in Baileys; no official path |
| Automated `/instance/create` in code | User chose manual Dashboard workflow |
