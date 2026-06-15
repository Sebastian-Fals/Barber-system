# Proposal: Mejora del Flujo de Usuario

## Intent

Transformar el sistema single-tenant actual en multi-tenant, corregir bugs críticos, unificar la experiencia AI/no-AI, e implementar selección de servicio. Las tablas `Customer`, `Appointment`, `ProcessedMessage` y `ConversationHistory` carecen de `business_id`, lo que mezcla datos entre negocios y bloquea la operación independiente.

## Scope

### In Scope

| Fase | PR Base | Entregables |
|------|---------|-------------|
| **0** | `main` | **Multi-tenant foundation**: `business_id` en 4 entidades, constraints compuestos, scoping de repositorios, resolución temprana de `business_id` en webhook, Alembic migration |
| **1** | PR#0 | **Bugs + Seguridad**: TOCTOU lock, cancelación no-AI, decrypt validation, `.env` secrets, PII sanitization |
| **2** | PR#1 | **UX unificada**: SELECT_SERVICE, eliminar debounce 10s, PROVIDE_NAME/FALLBACK handlers, botones unificados AI/no-AI |
| **3** | PR#2 | **Deuda técnica**: Refactor BufferService, dead code cleanup, documentación de key immutability |

### Out of Scope
- Rotación de `ENCRYPTION_KEY` (solo validación + docs)
- Gestor de secretos externo (Vault, AWS)
- Migración de datos históricos (BD se resetea — drop/recreate)
- Múltiples servicios simultáneos en UI
- Alembic para datos existentes (solo versionado hacia adelante)

## Capabilities

### New Capabilities
- `multi-tenant`: Aislamiento de datos por negocio vía `business_id` en Customer, Appointment, ProcessedMessage, ConversationHistory; resolución temprana en webhook; dedup y scoping por negocio
- `booking-flow`: Flujo de reserva unificado AI/no-AI con paso SELECT_SERVICE
- `appointment-locking`: Bloqueo atómico contra double-booking (TOCTOU)
- `encryption-validation`: Validación de `ENCRYPTION_KEY` al iniciar
- `secret-management`: Google credentials vía `GOOGLE_APPLICATION_CREDENTIALS_JSON` en `.env`
- `message-processing`: Procesamiento inmediato sin debounce, deduplicación mantenida

### Modified Capabilities
- None (no existen specs previos en `openspec/specs/`)

## Approach

**Phasing chained PRs**: Cada fase es un PR independiente encadenado. Fase 0 es fundacional — todas las fases subsiguientes dependen de `business_id` en el modelo de datos.

**Principios técnicos Fase 0**:
- `Customer`: unique constraint compuesto `(phone_hash, business_id)`, `get_by_phone(from_number, business_id)`
- `Appointment`: `business_id` denormalizado para queries directas sin JOIN vía barber
- `ProcessedMessage`: dedup por `(msg_id, business_id)`, no global
- `ConversationHistory`: `business_id` para scoping de historial
- Webhook: resolver `phone_number_id` → `business_id` temprano (vía `BusinessRepository.get_by_phone_number_id`) y propagar a toda la cadena
- `CustomerRepository.create()` debe recibir y persistir `business_id`

**Fases 1-3** mantienen el approach original: `SELECT ... FOR UPDATE`, credenciales en memoria, validación de key al iniciar.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/models/models.py` | Modified | `business_id` FK en Customer, Appointment, ProcessedMessage, ConversationHistory; unique compuesto en Customer |
| `app/features/business/repository.py` | Modified | Agregar `get_by_phone_number_id` si no existe |
| `app/features/customers/repository.py` | Modified | `get_by_phone(from_number, business_id)`, `create` con `business_id` |
| `app/repositories/` | Modified | Queries de Appointment, ProcessedMessage, ConversationHistory scoped por `business_id` |
| `app/api/webhook.py` | Modified | Resolver `business_id` temprano, propagar a handlers y servicios |
| `app/services/conversation_service.py` | Modified | Recibir y usar `business_id` en lugar de resolverlo internamente |
| `app/services/buffer_service.py` | Modified | Recibir `business_id`, scoping de buffer por negocio |
| `app/services/handlers/*` | Modified | Todos los handlers reciben `business_id` |
| `alembic/versions/` | New | Migration inicial: columnas `business_id`, FKs, constraints compuestos |
| `app/features/appointments/service.py` | Modified | TOCTOU lock en `create_appointment` (Fase 1) |
| `app/core/security.py` | Modified | Validación de `ENCRYPTION_KEY` (Fase 1) |
| `app/core/config.py` | Modified | `GOOGLE_APPLICATION_CREDENTIALS_JSON` (Fase 1) |
| `app/core/logging_config.py` | Modified | Sanitizar PII (Fase 1) |
| `app/features/calendar/service.py` | Modified | Credenciales desde env var (Fase 1) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Migración con datos existentes rompe constraints | Medium | Drop/recreate DB; no hay datos de producción que preservar |
| Unique compuesto `(phone_hash, business_id)` diferente al actual global | Low | Validar en migration; sin datos existentes no hay conflicto |
| `get_by_phone_number_id` no existe en BusinessRepository | Medium | Agregar método con test; si el repo ya lo tiene, verificar firma |
| Regresión en single-tenant: queries sin `business_id` devuelven datos cruzados | High | Tests de integridad por negocio: 2 businesses, mismo teléfono, sin leaks |
| Lock advisory no portable a SQLite | Low | PostgreSQL (Supabase) es producción; SQLite es fallback dev |
| Eliminar debounce genera ruido | Medium | Mantener dedup DB + cooldown 500ms |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` muy largo para `.env` | Low | Validar límite de OS; alternativa: split en 2 vars |

## Rollback Plan

- **Fase 0**: Revert PR#0 — Alembic downgrade, restaurar queries sin `business_id`. Sin datos de producción que perder.
- **Fase 1**: Revert PR#1 — restaurar `credentials.json` + `ENCRYPTION_KEY` anterior
- **Fase 2**: Revert PR#2 — restaurar `BufferService` con debounce
- **Fase 3**: Revert PR#3 — reversible sin impacto en datos
- **DB**: Drop/recreate con Alembic `downgrade`

## Dependencies

- Alembic CLI (`pip install alembic`)
- PostgreSQL accesible en Supabase con permisos de drop/create
- Fase 0 debe completarse antes que cualquier otra — es fundacional

## Success Criteria

- [ ] **Multi-tenant**: Dos negocios pueden tener clientes con el mismo teléfono sin conflicto (unique compuesto)
- [ ] **Multi-tenant**: Mensajes duplicados entre negocios no se bloquean mutuamente (dedup por `msg_id + business_id`)
- [ ] **Multi-tenant**: `GET /customers?business_id=X` solo devuelve clientes de ese negocio
- [ ] TOCTOU: 2 usuarios simultáneos no reservan el mismo slot (test de concurrencia)
- [ ] Cancelación: `cancelar` funciona en flujo no-AI
- [ ] SELECT_SERVICE: El booking incluye selección de servicio antes de barbero
- [ ] Decrypt: `ENCRYPTION_KEY` cambiada → crash temprano con mensaje claro
- [ ] Secretos: `credentials.json` no existe en disco; credenciales desde env var
- [ ] PII: `app.log` sin nombres, teléfonos ni datos de clientes
- [ ] Debounce: Mensajes procesados en <1s
- [ ] Tests: Todos los handlers con cobertura unitaria (MagicMock)

## Alternatives Considered

| Alternativa | Decisión | Razón |
|-------------|----------|-------|
| Multi-tenancy vía schema por negocio (PostgreSQL schemas) | Rechazado | Mayor complejidad operacional; `business_id` por fila es más simple y suficiente |
| Multi-tenancy diferido a fase posterior | Rechazado | Los bugs actuales (datos mezclados) son consecuencia directa de single-tenant; resolverlo primero evita refactors dobles |
| Cambio monolítico (1 PR) | Rechazado | >400 líneas; chained PRs protegen carga cognitiva del revisor |
| SELECT_SERVICE diferido | Rechazado | Requerido ahora como paso del flujo |
| Mutex en memoria para TOCTOU | Rechazado | No escala a múltiples workers; lock a nivel BD es correcto |
| Seguir con `credentials.json` | Rechazado | Riesgo de commit accidental; `.env` ya en `.gitignore` |
