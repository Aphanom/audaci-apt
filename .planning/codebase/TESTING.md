# Testing Patterns

**Analysis Date:** 2026-05-18

## Test Framework

**Runner:**
- **Pytest** with **pytest-asyncio** for asynchronous test runner support.
- Configured with `setup_test_env` inside [conftest.py](file:///Users/apfanom/audaci-apt/tests/conftest.py).

**Mocking Utilities:**
- `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`) is utilized to stub hardware-bound dependencies (such as VLC players, sound devices, and Telegram servers).

**Commands:**
```bash
pytest                                       # Run all unit and integration tests
pytest tests/test_telegram.py                # Run tests inside a single module
pytest -k "test_lfi_streaming_security"      # Run a specific test case by name
pytest -v                                    # Verbose logging output
```

---

## Test File Organization

**Location:**
- Stored inside the absolute root `/tests/` directory to isolate tests from runtime code.

**Naming:**
- Filenames must follow `test_*.py` format (e.g. `test_telegram.py`, `test_db.py`).

**Structure:**
```
tests/
├── conftest.py                   # Global fixtures and environment sandbox
├── test_architectural_fixes.py   # LFI, transactions, and fallback tests
├── test_bot_server.py            # API websockets and FIFO queue tests
├── test_db.py                    # SQLite CRUD integrity tests
└── test_telegram.py              # Download sanitization and covers embedding tests
```

---

## Mocking & Sandbox Isolation

### 1. File Sandbox Fixture
- Direct modifications to user files are forbidden in tests.
- Global path variables (`DB_PATH` in `core/db.py` and `COVERS_DIR` in `core/metadata_handler.py`) are patched dynamically within a `session` scoped fixture in `conftest.py` to target local `/tests/test_data/` sandboxes.
- Connections are automatically rolled back and directories swept clean after completions.

### 2. Mutagen / Telegram Mocking
- Test cases mock standard audio properties to test coverage:
  ```python
  mock_mp3 = MagicMock()
  mock_mp3.tags = MagicMock()
  
  with patch("mutagen.mp3.MP3", return_value=mock_mp3) as mock_class:
      embed_cover_in_audio(Path("test.mp3"), b"fake_bytes")
      mock_class.assert_called_once()
      mock_mp3.tags.add.assert_called_once()
      mock_mp3.save.assert_called_once()
  ```

### 3. FastAPI Client & WebSockets Mocking
- `fastapi.testclient.TestClient` is used to test REST endpoints and real-time Websocket events safely:
  ```python
  client = TestClient(app)
  
  # Connect to WebSocket sync endpoint
  with client.websocket_connect(f"/api/ws/sync/{sync_code}") as websocket:
      # Emit events and assert responses
      websocket.send_text("ping")
  ```

---

## Common Verification Patterns

### Async Event Handlers Testing
```python
@pytest.mark.asyncio
async def test_handle_audio_logic():
    bot = AsyncMock()
    message = MagicMock()
    message.answer = AsyncMock() # Required for async event handlers
    message.audio.file_id = "test_file_id"
    
    telegram_dir = Path("/tmp/audaci_test")
    await handle_audio(message, bot, telegram_dir)
    
    bot.download_file.assert_called_once()
```

---

*Testing analysis: 2026-05-18*
*Update when test patterns change*
