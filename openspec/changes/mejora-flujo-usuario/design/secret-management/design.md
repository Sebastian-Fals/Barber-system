# Design: Google Credentials from Environment Variable (Fase 1)

## Technical Approach

Replace file-based `credentials.json` with `GOOGLE_APPLICATION_CREDENTIALS_JSON` env var. Parse JSON in memory via `json.loads()`, pass to `service_account.Credentials.from_service_account_info()`. Delete `credentials.json` from disk after migration.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Env var with full JSON | Single string, `.env` stays in `.gitignore` | **Chosen** |
| Split into multiple env vars | Complicated parsing, no standard | Rejected |
| Keep `credentials.json` on disk | Risk of accidental commit | Rejected |

## Component Changes

### `app/core/config.py`

```python
GOOGLE_APPLICATION_CREDENTIALS_JSON: Optional[str] = None
```

Remove old `GOOGLE_APPLICATION_CREDENTIALS` (file path) field. Rename to avoid confusion.

### `app/features/calendar/service.py` — `_authenticate()`

Replace:

```python
if os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
    self.creds = service_account.Credentials.from_service_account_file(...)
```

With:

```python
import json
if settings.GOOGLE_APPLICATION_CREDENTIALS_JSON:
    try:
        creds_dict = json.loads(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON)
        self.creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=self.SCOPES
        )
        self.service = build("calendar", "v3", credentials=self.creds)
    except json.JSONDecodeError as e:
        print(f"FATAL: GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON: {e}")
        raise
else:
    print("FATAL: GOOGLE_APPLICATION_CREDENTIALS_JSON not set. Calendar disabled.")
```

No file I/O. Credentials live only in memory.

### `.env.example`

Add:
```
GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account",...}
```

### `credentials.json`

Delete after migration. Add to `.gitignore` if not already there.

## Error Handling

| Case | Behavior |
|------|----------|
| Var not set | Log: "GOOGLE_APPLICATION_CREDENTIALS_JSON not set. Calendar disabled." Service works but calendar integration inactive. |
| Invalid JSON | `json.JSONDecodeError` → crash with parse error message |
| Valid JSON, invalid credentials | Google API raises on first call → logged, handled by existing error paths |

## Testing Strategy

| Layer | Test | Approach |
|-------|------|----------|
| Unit | Valid JSON env var | Mock `settings.GOOGLE_APPLICATION_CREDENTIALS_JSON`, verify `from_service_account_info` called with dict |
| Unit | Missing env var | Verify service inits without crash, `self.service` is None |
| Unit | Malformed JSON | Verify `JSONDecodeError` raised |
| Unit | `.env.example` contains the var | Read file, assert key present |

## Rollback

Restore `credentials.json` on disk. Revert `_authenticate()` to `from_service_account_file()`. Remove `GOOGLE_APPLICATION_CREDENTIALS_JSON` from config.

## Open Questions

None.
