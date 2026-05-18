# External Integrations

**Analysis Date:** 2026-05-18

## APIs & External Services

**Telegram Bot API:**
- **Telegram Bot** - Handles user music uploads (under 20MB) and links users to the desktop application using a unique QR code.
  - SDK/Client: `aiogram 3.x`
  - Auth: API token loaded via `TELEGRAM_TOKEN` environment variable.
  - Endpoints used: `get_file`, `download_file`, `send_message`.
  - Integration path: Background polling in [telegram_handler.py](file:///Users/apfanom/audaci-apt/core/telegram_handler.py) (client) and [central_bot_server.py](file:///Users/apfanom/audaci-apt/central_bot_server.py) (central server).

**Metadata & Vibe Fetching:**
- **Last.fm API** - Resolves track names/artists to retrieve tags (e.g. happy, sad, chill) for newly added music.
  - Integration: `track.gettoptags` REST API.
  - Client: `aiohttp` for async, `requests` for sync.
  - Auth: API key (fallback: `d0f09e818ba58229da96d69c73328e39` loaded in [tag_fetcher.py](file:///Users/apfanom/audaci-apt/core/tag_fetcher.py)).
  - Usage: Async polling upon folder scanning inside watchdog and scanner threads.

**Lyrics Database:**
- **LRCLIB API** - Fetches synchronized scrolling lyrics in LRC format.
  - Endpoint: `https://lrclib.net/api/get` (REST via `requests`).
  - Auth: None (public database).
  - Timeout: Configured at 10 seconds to tolerate high response latencies.
  - Parsing: custom regex parser converting `[mm:ss.xx] Text` to millisecond-sorted ranges in [lyrics_handler.py](file:///Users/apfanom/audaci-apt/core/lyrics_handler.py).

## Data Storage

**Client Database (SQLite3):**
- **SQLite3 Local Library** - Manages tracks, folders, track play counts, vibe categories, and listening history.
  - File Location: `~/.audaci/audaci_library.db` (overrideable via `AUDACI_DB_DIR` env var).
  - Client: Python standard library `sqlite3` using check_same_thread=False.
  - Transaction Handler: Context manager `db_session()` in [db.py](file:///Users/apfanom/audaci-apt/core/db.py) handling concurrent writes, automated rollbacks, and connection cleanups.

**Server Database (SQLite3):**
- **SQLite3 Sync Queue** - Stores Telegram user IDs, sync codes, and a FIFO queue of uploaded files.
  - File Location: `server_data/audaci_server.db` relative to server execution path.
  - Implementation: SQLite3 session wrapper in [central_bot_server.py](file:///Users/apfanom/audaci-apt/central_bot_server.py) initializing `users` and `queue` tables.

## Synchronization Protocols

**Real-Time WebSocket Sync:**
- WebSocket route `ws://[server]/api/ws/sync/{sync_code}` establishes long-running socket between client and server.
- Whenever a user uploads a track to the Telegram bot, the server writes it to database and notifies the active client via:
  ```json
  {"event": "new_track"}
  ```

**File Transfer HTTP:**
- Client fetches and downloads newly queued tracks from `/api/sync/{sync_code}/download`.
- Server wraps file transmission in FastAPI `FileResponse` and adds a `BackgroundTasks` cleanup function to delete the file from the server's local disk right after completion to keep memory stateless.

## Environment Configuration

**Client:**
- `AUDACI_DB_DIR`: Directory override for `.audaci` hidden user settings and library database files.
- `LASTFM_API_KEY`: API Key for mood tag fetching.

**Central Server:**
- `TELEGRAM_TOKEN`: Authorization key to poll Telegram servers.
- `PORT`: Server port binding (defaults to `8080`).

---

*Integration audit: 2026-05-18*
*Update when adding/removing external services*
