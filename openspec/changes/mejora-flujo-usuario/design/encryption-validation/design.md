# Design: Encryption Key Validation at Startup (Fase 1)

## Technical Approach

Add `validate_encryption_key()` to `security.py` that encrypts a known sentinel value (`"__KEY_CHECK__"`) and verifies round-trip decrypt. Call it during FastAPI `lifespan` startup — before any DB operations. If validation fails, crash immediately with a clear log message. Remove the silent `[Error: Decryption Failed]` fallback from `decrypt()`.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Validate at import time (module level) | Fast, but crash happens before logging is configured | Rejected |
| Validate in `lifespan` startup | After logging/DB setup, clear error output | **Chosen** |
| Skip validation, keep silent fallback | Data corruption invisible to ops | Rejected — violates spec |

## Component Changes

### `app/core/security.py`

```python
def validate_encryption_key() -> None:
    sentinel = "__KEY_CHECK__"
    encrypted = encrypt(sentinel)
    decrypted = decrypt(encrypted)
    if decrypted != sentinel:
        raise ValueError(
            "ENCRYPTION_KEY validation FAILED. "
            "Key mismatch — all encrypted data is unreadable. "
            "Do NOT change ENCRYPTION_KEY after initial deployment."
        )
```

Also: remove `try/except` in `decrypt()` that returns `"[Error: Decryption Failed]"` — let the `InvalidToken` exception propagate. Callers must handle it.

### `app/main.py` (or wherever `lifespan` is defined)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.security import validate_encryption_key
    validate_encryption_key()  # Crash early if key invalid
    logger.info("Encryption key validated successfully")
    yield
```

## Flow

```
FastAPI start
    │
    ▼
lifespan: validate_encryption_key()
    │
    ├── encrypt("__KEY_CHECK__") with Fernet(ENCRYPTION_KEY)
    ├── decrypt(result)
    ├── compare round-trip
    │
    ├── MATCH → "Encryption key validated" → continue
    └── MISMATCH → ValueError with explicit message → crash (exit 1)
```

## Error Handling

| Case | Behavior |
|------|----------|
| `ENCRYPTION_KEY` not set | `ValueError` from `encrypt()` → crash: "Encryption not configured (Missing ENCRYPTION_KEY)" |
| Invalid key format | `Fernet()` raises `ValueError` → crash with key format error |
| Valid key, wrong data | `decrypt()` raises `InvalidToken` → crash with "Key mismatch" message |
| Silent `[Error: Decryption Failed]` | **Removed** — `decrypt()` now raises `InvalidToken` |

## Testing Strategy

| Layer | Test | Approach |
|-------|------|----------|
| Unit | `validate_encryption_key()` with valid key | No exception raised |
| Unit | `validate_encryption_key()` with wrong key | `ValueError` raised, message contains "Key mismatch" |
| Unit | `validate_encryption_key()` with missing key | `ValueError` raised, message contains "Missing" |
| Unit | `decrypt()` with corrupted ciphertext | `InvalidToken` raised (not silent fallback) |

## Rollback

Restore `try/except` in `decrypt()` with `"[Error: Decryption Failed]"`. Remove `validate_encryption_key()` call from lifespan.

## Open Questions

None.
