## Verification Report

**Change**: mejora-flujo-usuario
**Version**: N/A
**Mode**: Strict TDD
**Test runner**: `python -m pytest`

---

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 22 |
| Tasks complete (checked) | 22 |
| Tasks incomplete | 0 |
| Tasks falsely marked complete | 1 (task 1.5 — `credentials.json` not deleted) |

> ⚠️ Task 1.5 is checked `[x]` but its instruction "borrar `credentials.json`" is NOT fulfilled — the file still exists on disk.

---

### Build & Tests Execution

**Build**: N/A (Python — no build step)
**Type Check**: ➖ Not available

**Tests**: ✅ 59 passed / ❌ 2 failed / ⚠️ 1 skipped

```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0
rootdir: C:\Users\Sebastian Fals\OneDrive\Documentos\Works\sistema-citas
collected 62 items

FAILED tests/test_booking_service.py::test_create_appointment_conflict
  → SlotOccupiedError raised; test expected result=None (old behavior)
FAILED tests/test_llm_service.py::TestLLMService::test_prompt_rendering
  → AssertionError: template not rendered; yaml mock uses {{ }} but code uses { }
SKIPPED tests/unit/features/appointments/test_service.py::test_concurrent_same_slot_no_double_booking
  → SQLite concurrent locking is timing-dependent

2 failed, 59 passed, 1 skipped in 8.91s
```

**Coverage**: ➖ Not available

---

### TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ❌ | No `apply-progress` artifact found — TDD Cycle Evidence table missing |
| All tasks have tests | ⚠️ | 20/22 tasks have RED tests; task 1.5 (`credentials.json` removal, `.env.example` update) and task 3.4 (documentation, dead code) are GREEN-only / documentation tasks |
| RED confirmed (tests exist) | ✅ | 20/20 RED test files verified on disk |
| GREEN confirmed (tests pass) | ❌ | 2 tests FAIL: `test_create_appointment_conflict`, `test_prompt_rendering` |
| Triangulation adequate | ⚠️ | Most behaviors have 1 test; concurrent double-booking scenario is SKIPPED (no runtime coverage) |
| Safety Net for modified files | ❌ | No apply-progress table → cannot verify safety net |

**TDD Compliance**: 2/6 checks passed

---

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 57 | 13 | `pytest` + `unittest.mock` |
| Integration | 5 | 1 | `fastapi.testclient.TestClient` (test_webhook.py) |
| E2E | 0 | 0 | — |
| **Total** | **62** | **14** | |

---

### Changed File Coverage

Coverage analysis skipped — no coverage tool detected.

---

### Spec Compliance Matrix

#### multi-tenant

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Business-scoped Customer Identity | Same phone across two businesses | `tests/unit/models/test_customer.py::test_same_phone_two_businesses_no_conflict` | ✅ COMPLIANT |
| Business-scoped Customer Identity | Duplicate phone within same business | `tests/unit/models/test_customer.py::test_duplicate_phone_same_business_integrity_error` | ✅ COMPLIANT |
| Business-scoped Customer Identity | Customer lookup scoped by business | `tests/unit/repositories/test_customer_repo.py::test_get_by_phone_scoped_returns_correct_business_customer` + `…does_not_return_other_business_customer` | ✅ COMPLIANT |
| Webhook Resolves Business ID First | Webhook with known phone_number_id | `tests/unit/api/test_webhook.py::test_known_phone_number_id_resolves_business` | ✅ COMPLIANT |
| Webhook Resolves Business ID First | Webhook with unknown phone_number_id | `tests/unit/api/test_webhook.py::test_unknown_phone_number_id_returns_200_no_db_write` | ✅ COMPLIANT |
| Message Deduplication Scoped by Business | Same msg_id across two businesses | `tests/unit/models/test_processed_message.py::test_same_msg_id_two_businesses_no_conflict` + `tests/unit/api/test_webhook.py::test_same_msg_id_different_business_not_deduplicated` | ✅ COMPLIANT |
| Message Deduplication Scoped by Business | Duplicate msg_id within same business | `tests/unit/models/test_processed_message.py::test_duplicate_msg_id_same_business_integrity_error` + `tests/unit/api/test_webhook.py::test_duplicate_message_dropped` | ✅ COMPLIANT |
| Appointment Data Scoped by Business | List appointments for one business | (none found — FK constraint exists but no query-level test) | ⚠️ PARTIAL |
| Conversation History Scoped by Business | Conversation history isolation | (no covering test found) | ❌ UNTESTED |

**multi-tenant compliance**: 7/9 scenarios compliant (1 PARTIAL, 1 UNTESTED)

#### booking-flow

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Unified Booking Flow Order | Happy path booking | `tests/unit/services/handlers/test_query_handler.py::test_smart_booking_starts_at_select_service` + `test_service_selection_transitions_to_select_barber` | ⚠️ PARTIAL (no end-to-end test of full SERVICE→BARBER→DATE→SLOT→CONFIRM chain) |
| Unified Booking Flow Order | User cancels mid-flow | `tests/unit/services/handlers/test_booking_handler.py::test_cancel_flow_interactive_resets_state` + `test_cancelar_text_during_booking_resets_to_idle` | ✅ COMPLIANT |
| Service Selection Step | Service options displayed | `tests/unit/services/handlers/test_welcome_handler.py::test_start_booking_flow_sends_service_buttons` | ✅ COMPLIANT |
| Service Selection Step | Invalid service selection | `tests/unit/services/handlers/test_booking_handler.py::test_invalid_service_selection_keeps_state` | ✅ COMPLIANT |
| AI and Non-AI Share Same UI | AI mode uses same buttons | `tests/unit/services/handlers/test_query_handler.py::test_smart_booking_ai_and_non_ai_use_same_button_ids` | ✅ COMPLIANT |
| AI and Non-AI Share Same UI | Non-AI mode uses same buttons | `tests/unit/services/handlers/test_welcome_handler.py::test_start_booking_flow_sends_service_buttons` (same button prefix `service_`) | ✅ COMPLIANT |

**booking-flow compliance**: 5/6 scenarios compliant (1 PARTIAL)

#### appointment-locking

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Atomic Slot Reservation | Single user reserves a slot | `tests/unit/features/appointments/test_service.py::test_single_booking_creates_appointment` | ✅ COMPLIANT |
| Atomic Slot Reservation | Two concurrent users race for same slot | `tests/unit/features/appointments/test_service.py::test_concurrent_same_slot_no_double_booking` | ❌ UNTESTED (SKIPPED — "SQLite concurrent locking is timing-dependent") |
| Atomic Slot Reservation | Slot becomes unavailable during transaction | `tests/unit/features/appointments/test_service.py::test_second_booking_same_slot_fails` | ✅ COMPLIANT |
| Rollback on Conflict | Rollback notification | `tests/unit/features/appointments/test_service.py::test_second_booking_same_slot_fails` (asserts `SlotOccupiedError`; message text not validated) | ⚠️ PARTIAL |

**appointment-locking compliance**: 2/4 scenarios compliant (1 UNTESTED, 1 PARTIAL)

#### encryption-validation

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Startup Encryption Key Validation | Valid encryption key | `tests/unit/core/test_security.py::test_valid_key_does_not_raise` | ✅ COMPLIANT |
| Startup Encryption Key Validation | Invalid or corrupted encryption key | `tests/unit/core/test_security.py::test_invalid_key_raises_value_error` | ✅ COMPLIANT |
| Startup Encryption Key Validation | Missing encryption key | `tests/unit/core/test_security.py::test_missing_key_raises_value_error` | ✅ COMPLIANT |
| Key Immutability Documentation | Developer reads docs before changing key | (doc warning in `security.py` line 46-47 + design doc; no automated test possible) | ✅ COMPLIANT (docs) |

**encryption-validation compliance**: 4/4 scenarios compliant

#### secret-management

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Google Credentials From Environment Variable | Valid JSON in environment variable | `tests/unit/features/calendar/test_service.py::test_valid_json_credentials_parsed_correctly` | ✅ COMPLIANT |
| Google Credentials From Environment Variable | Missing environment variable | `tests/unit/features/calendar/test_service.py::test_missing_env_var_service_none` | ✅ COMPLIANT |
| Google Credentials From Environment Variable | Invalid JSON in environment variable | `tests/unit/features/calendar/test_service.py::test_malformed_json_raises_decode_error` | ✅ COMPLIANT |
| Remove credentials.json From Disk | No credentials file on disk | (no test; file STILL EXISTS at `credentials.json`) | ❌ UNTESTED + NOT IMPLEMENTED |
| Updated .env.example | Developer reads .env.example | `.env.example` includes `GOOGLE_APPLICATION_CREDENTIALS_JSON` but still references legacy `GOOGLE_APPLICATION_CREDENTIALS` | ⚠️ PARTIAL |

**secret-management compliance**: 3/5 scenarios compliant (1 UNTESTED + NOT IMPLEMENTED, 1 PARTIAL)

#### message-processing

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Immediate Message Processing | Message processed immediately | `tests/unit/api/test_webhook.py::test_text_message_processed_directly_without_buffer` | ✅ COMPLIANT |
| Immediate Message Processing | Rapid consecutive messages from same user | `tests/unit/features/communication/test_conversation_service.py::test_messages_within_cooldown_are_dropped` (cooldown blocks <500ms, contradicting spec wording) | ⚠️ PARTIAL |
| Remove BufferService Debounce | Duplicate message is still caught | `tests/unit/api/test_webhook.py::test_duplicate_message_dropped` | ✅ COMPLIANT |
| Remove BufferService Debounce | Same msg_id for different businesses is NOT deduplicated | `tests/unit/api/test_webhook.py::test_same_msg_id_different_business_not_deduplicated` | ✅ COMPLIANT |
| Webhook Response Under 1 Second | Webhook response time | (no timing test) | ⚠️ PARTIAL |

**message-processing compliance**: 3/5 scenarios compliant (2 PARTIAL)

**Compliance summary**: 24/33 scenarios fully compliant (73%)

---

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| Customer composite unique `(phone_hash, business_id)` | ✅ Implemented | `app/models/models.py` + constraint tests pass |
| ProcessedMessage composite unique `(message_id, business_id)` | ✅ Implemented | `app/models/models.py` + constraint tests pass |
| Appointment `business_id` denormalized | ✅ Implemented | FK on Appointment model; scoped via `create_appointment` |
| ConversationHistory `business_id` | ✅ Implemented | Migration adds column + FK |
| Webhook resolves `phone_number_id → business_id` early | ✅ Implemented | `app/api/webhook.py` — `BusinessRepository.get_by_phone_number_id` |
| `create_appointment` with `SELECT ... FOR UPDATE` / `BEGIN IMMEDIATE` | ✅ Implemented | `app/features/appointments/service.py` lines 212-243 |
| `SlotOccupiedError` raised on conflict | ✅ Implemented | `app/core/exceptions.py` → `app/features/appointments/service.py` line 223 |
| Cancelación "cancelar" resets to IDLE | ✅ Implemented | `app/services/handlers/booking_handler.py` |
| SELECT_SERVICE step implemented | ✅ Implemented | `welcome_handler`, `booking_handler`, `query_handler` |
| Service model + repository | ✅ Implemented | `app/models/models.py` + `app/features/business/service_repository.py` |
| `validate_encryption_key()` in lifespan | ✅ Implemented | `app/core/security.py` line 40 + `app/main.py` line 21 |
| `decrypt()` no silent fallback | ✅ Implemented | `app/core/security.py` — raises `InvalidToken`, no `try/except` |
| Google credentials from `GOOGLE_APPLICATION_CREDENTIALS_JSON` | ✅ Implemented | `app/features/calendar/service.py` — `json.loads(env_var)` |
| PII sanitization in logs | ✅ Implemented | `app/core/logging_config.py` — `sanitize_pii_for_log()` |
| `BufferService` removed | ✅ Implemented | File deleted; `MessageBuffer` model removed; no imports remain |
| 500ms cooldown in `ConversationService` | ✅ Implemented | `app/features/communication/conversation_service.py` |
| **`credentials.json` deleted** | ❌ **NOT DONE** | File still at `C:\Users\Sebastian Fals\OneDrive\Documentos\Works\sistema-citas\credentials.json` |

---

### Coherence (Design)

| Design Decision | Doc | Followed? | Notes |
|-----------------|-----|-----------|-------|
| `business_id` per row (not PostgreSQL schemas) | `multi-tenant/design.md` | ✅ Yes | All 4 tables have `business_id` FK |
| Resolve `business_id` once at webhook entry | `multi-tenant/design.md` | ✅ Yes | `phone_number_id → business_id` before `ConversationService` |
| `SELECT ... FOR UPDATE` + SQLite `BEGIN IMMEDIATE` | `appointment-locking/design.md` | ✅ Yes | `create_appointment()` lines 212-243 |
| `Service` model as DB table (not hardcoded) | `booking-flow/design.md` | ✅ Yes | `Service` model + `ServiceRepository.get_by_business()` |
| AI + non-AI share same button payloads | `booking-flow/design.md` | ✅ Yes | `service_` prefix used in both `welcome_handler` and `query_handler` |
| Remove `BufferService`, keep DB dedup | `message-processing/design.md` | ✅ Yes | `MessageBuffer` gone; `ProcessedMessage` dedup maintained |
| Validate key in `lifespan` (not module import) | `encryption-validation/design.md` | ✅ Yes | `app/main.py` line 21 calls `validate_encryption_key()` |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` from env var | `secret-management/design.md` | ✅ Yes | `json.loads(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON)` used |
| Delete `credentials.json` after migration | `secret-management/design.md` | ❌ **No** | File still exists on disk |

---

### Assertion Quality

| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| `tests/test_booking_service.py` | 112 | `assert result is None` | Expects old behavior; implementation now raises `SlotOccupiedError` — test proves wrong thing | CRITICAL |
| `tests/test_llm_service.py` | 61 | `assert "Biz:  Barbería <script>…" in rendered_prompt` | template mock uses `{{ }}` but code uses `{ }` — test is testing wrong template syntax | CRITICAL |
| `tests/unit/features/appointments/test_service.py` | 119 | `pytest.skip("SQLite concurrent locking is timing-dependent")` | Spec scenario "Two concurrent users race" has no runtime coverage | CRITICAL (scenario UNTESTED) |
| `tests/unit/features/calendar/test_service.py` | 61 | `assert svc.service is None` | Type-only: checks service is `None` when env var missing — acceptable but no companion test validates log message | — |
| `tests/unit/services/handlers/test_booking_handler.py` | 93 | `assert result is False` | Correctly checks handler returns False for unrecognized text — valid behavioral assertion | — |
| `tests/unit/features/appointments/test_service.py` | 109 | `with pytest.raises(SlotOccupiedError)` | Correctly asserts exception type, but message text ("Este horario ya no está disponible…") not validated | SUGGESTION |

**Assertion quality**: 3 CRITICAL, 1 SUGGESTION

No tautologies, ghost loops, or smoke-test-only assertions found. Most assertions verify real behavior.

---

### Quality Metrics

**Linter**: ➖ Not available
**Type Checker**: ➖ Not available

---

### Issues Found

**CRITICAL**:

1. **`test_create_appointment_conflict` FAILS** — `tests/test_booking_service.py:112`. Old test expects `result is None` on conflict, but `create_appointment` now raises `SlotOccupiedError` (task 1.6). This pre-existing test was never updated for the new behavior. The implementation is correct per spec; the test is stale.

2. **`test_prompt_rendering` FAILS** — `tests/test_llm_service.py:61`. Test's yaml mock uses `{{ business_name }}` (Jinja2 double-brace syntax), but `LLMService.analyze_message()` uses `.replace("{business_name}", ...)` (single-brace). Either the test or the production code has the wrong template syntax. The test renders `{{ business_name }}` literally, causing the assertion to fail.

3. **`test_concurrent_same_slot_no_double_booking` SKIPPED** — `tests/unit/features/appointments/test_service.py:119`. The spec scenario "Two concurrent users race for same slot" has ZERO runtime verification. The sequential tests (`test_single_booking`, `test_second_booking_same_slot_fails`) verify atomic locking logic deterministically but do NOT exercise true concurrency. Skipped test = scenario UNTESTED.

4. **`credentials.json` NOT DELETED** — File still exists at `C:\Users\Sebastian Fals\OneDrive\Documentos\Works\sistema-citas\credentials.json`. Task 1.5 is marked `[x]` but its instruction "borrar `credentials.json`" is NOT fulfilled. Spec requirement "Remove credentials.json From Disk" is NOT implemented. Design decision "Delete `credentials.json` after migration" is NOT followed.

5. **No `apply-progress` artifact** — Strict TDD requires a TDD Cycle Evidence table in the apply-progress artifact. No such file exists at `openspec/changes/mejora-flujo-usuario/apply-progress.md`. Cannot verify RED/GREEN/TRIANGULATE/SAFETY NET evidence.

6. **Conversation History scoping UNTESTED** — Multi-tenant spec has an explicit scenario "Conversation history isolation" with no covering test. The `business_id` column exists in the model + migration, but no test validates queries are scoped correctly.

**WARNING**:

1. **Appointment scoping query UNTESTED** — Multi-tenant spec scenario "List appointments for one business" has no explicit query-level test. FK constraint exists but business-scoped filtering is not verified.

2. **Cooldown contradicts message-processing spec** — Spec says "no debounce blocks the second message" (scenario: "Rapid consecutive messages from same user"), but the 500ms cooldown DOES block messages within that window. The test `test_messages_within_cooldown_are_dropped` proves the cooldown blocks. Either the spec wording is imprecise or the cooldown should be removed.

3. **`.env.example` still references legacy `GOOGLE_APPLICATION_CREDENTIALS`** — Line 10: `# Ruta relativa o absoluta al archivo JSON de credenciales (legacy, prefer GOOGLE_APPLICATION_CREDENTIALS_JSON)` and line 11: `GOOGLE_APPLICATION_CREDENTIALS="credentials.json"`. The legacy field should be removed.

4. **`SlotOccupiedError` message not validated** — Tests only check `pytest.raises(SlotOccupiedError)` but never assert the human-readable message "Este horario ya no está disponible. Por favor elegí otro."

5. **Happy path end-to-end test missing** — No test exercises the complete booking chain SERVICE → BARBER → DATE → SLOT → CONFIRM. Individual step tests exist but integration is unverified.

6. **Webhook response time untested** — spec requirement "Webhook Response Under 1 Second" has no timing measurement.

**SUGGESTION**:

1. Add `SlotOccupiedError` message assertion to `test_second_booking_same_slot_fails`: `assert excinfo.value.args[0] == "Este horario ya no está disponible. Por favor elegí otro."`
2. Clean up dead comments in `tests/test_booking_service.py` (lines 7-37 have extensive comment blocks about patching strategies that are no longer relevant)
3. Add an integration test for the full booking flow chain
4. Remove legacy `GOOGLE_APPLICATION_CREDENTIALS` from `.env.example` and `app/core/config.py`
5. Consider adding a timing assertion (e.g., `time.monotonic()` diff) for the webhook response time scenario

---

### Verdict

**FAIL**

**Reason**: 6 CRITICAL issues — 2 failing tests, 1 skipped test (spec scenario UNTESTED), 1 spec requirement not implemented (`credentials.json` not deleted), no `apply-progress` artifact (Strict TDD violation), and 1 spec scenario with no covering test. Additionally, task 1.5 is falsely marked complete. The change cannot be archived in this state.
