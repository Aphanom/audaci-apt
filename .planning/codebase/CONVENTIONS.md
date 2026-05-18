# Coding Conventions

**Analysis Date:** 2026-05-18

## Architectural Constraints (audaci-core.md Rules)

### 1. Concurrency and Thread Isolation (Rule 1)
- The main event loop driving Flet GUI must **never** be blocked by synchronous CPU-bound operations.
- Heavy computational tasks (such as loading Vosk acoustic models, downloading metadata via Last.fm, or parsing files using Mutagen) **must** be offloaded to thread pools using `asyncio.to_thread()` or `concurrent.futures.ThreadPoolExecutor`.
- Web server loops (Uvicorn/FastAPI) and Telegram bots (Aiogram) must be initiated in detached background threads.

### 2. Signal Handling (Rule 2)
- Telegram Bot polling loops **must** pass `handle_signals=False` to the dispatcher:
  ```python
  await dp.start_polling(bot, handle_signals=False)
  ```
  This ensures that background workers do not hijack OS system signals (like `SIGINT` / `SIGTERM`) meant for Flet's parent process.

### 3. State Management safety (Rule 3)
- FastAPI routes must utilize registered thread-safe callbacks (`control_callback` in [api_server.py](file:///Users/apfanom/audaci-apt/core/api_server.py)) to alter the active state of Flet's desktop elements. Direct cross-thread updates of UI references are strictly forbidden.

### 4. Paths Resolution (Rule 5)
- **Rule 5: Oперируй путями исключительно через модуль pathlib.**
- Never hardcode dynamic string paths. Keep all database, configurations, and downloaded music files inside user home subdirectories managed exclusively via `pathlib.Path`:
  ```python
  APP_DIR = Path.home() / ".audaci"
  DB_PATH = APP_DIR / "audaci_library.db"
  ```

---

## Coding Style

### Naming Patterns
- **Files:** `snake_case.py` exclusively.
- **Classes:** `PascalCase` matching PEP-8 recommendations.
- **Functions & Variables:** `snake_case`. Private helper methods or fields must be prefixed with a single leading underscore (e.g. `_cover_cache`).
- **Constants:** `UPPER_SNAKE_CASE` (e.g. `SERVER_PORT`, `COVERS_DIR`).

### Import Organization
**Standard Import Sequence:**
1. Standard library imports (e.g., `os`, `sys`, `pathlib`).
2. Third-party core imports (e.g., `flet`, `fastapi`, `aiogram`, `vlc`).
3. Internal module references (e.g., `core.db`, `core.player`).

---

## Error Handling & Resiliency

### 1. Defensive try-except Blocks (Rule 6)
- Third-party packages (such as Vosk, VLC, and Mutagen) are prone to failing on corrupt or malformed files.
- Wrap all media readings in try-except structures. Log failures cleanly rather than letting exceptions cascade:
  ```python
  try:
      audio = File(file_path)
  except Exception as e:
      logger.error(f"[meta] Failed to read mutagen tags: {e}")
  ```

### 2. Database Transaction Isolation
- SQL write queries must utilize context managers to prevent data corruption.
- Connections must be cleanly committed on success or rolled back on exceptions using the `db_session()` pattern:
  ```python
  @contextmanager
  def db_session():
      conn = sqlite3.connect(DB_PATH)
      try:
          yield conn
          conn.commit()
      except Exception:
          conn.rollback()
          raise
      finally:
          conn.close()
  ```

---

*Convention analysis: 2026-05-18*
*Update when patterns change*
