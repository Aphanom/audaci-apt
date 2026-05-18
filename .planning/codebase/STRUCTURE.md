# Codebase Structure

**Analysis Date:** 2026-05-18

## Directory Layout

```
audaci-apt/
├── assets/                 # Icons and theme visual assets
├── core/                   # Backend engines, helpers, and API servers
│   ├── api_server.py       # FastAPI local streaming server
│   ├── db.py               # SQLite3 CRUD and vibe mapping queries
│   ├── lyrics_handler.py   # LRCLIB API lyrics downloader
│   ├── metadata_handler.py # Mutagen tag reader & covers optimizer
│   ├── nlu.py              # Rapidfuzz voice intent matcher
│   ├── player.py           # VLC playback control wrapper
│   ├── tag_fetcher.py      # Last.fm mood tag downloader
│   └── voice_cmd.py        # Vosk Speech-to-Text handler
├── scratch/                # Developer diagnostic scripts
│   └── check_track.py      # Mutagen extraction checker
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest fixtures and mock setups
│   ├── test_telegram.py    # Telegram handlers unit tests
│   ├── test_db.py          # SQLite track operations testing
│   └── test_bot_server.py  # Websocket sync server test suite
├── ui/                     # Specialized Flet layout components
│   ├── karaoke.py          # LRC synchronized lyrics scroll panel
│   ├── playlist_menu.py    # Playlists menu overlay
│   └── twa_view.py         # Mobile web-app Flet mock
├── central_bot_server.py   # Central synchronization backend
├── main.py                 # Core Flet Desktop app entry point
├── theme.py                # Global layout color configurations
└── requirements.txt        # Third-party dependency checklist
```

---

## Directory Purposes

**core/**
- Purpose: Application backend modules (audio playback, persistence, network APIs, speech recognition).
- Contains: `*.py` core logic classes.
- Key files:
  - [player.py](file:///Users/apfanom/audaci-apt/core/player.py) - Playback control.
  - [db.py](file:///Users/apfanom/audaci-apt/core/db.py) - Persistent storage operations.
  - [api_server.py](file:///Users/apfanom/audaci-apt/core/api_server.py) - REST endpoints.

**ui/**
- Purpose: Customized view panels, widgets, and user interface models.
- Contains: Flet components (`ft.Container`, `ft.Column`).
- Key files:
  - [karaoke.py](file:///Users/apfanom/audaci-apt/ui/karaoke.py) - Dynamic scrolling lyrics column.
  - [playlist_menu.py](file:///Users/apfanom/audaci-apt/ui/playlist_menu.py) - Playlist management tiles.

**tests/**
- Purpose: Comprehensive verification and quality control of functional components.
- Contains: `test_*.py` files, test data, and fixtures.
- Key files:
  - [conftest.py](file:///Users/apfanom/audaci-apt/tests/conftest.py) - Environment isolation mocks.
  - [test_telegram.py](file:///Users/apfanom/audaci-apt/tests/test_telegram.py) - Bot download handlers tests.

---

## Key File Locations

**Entry Points:**
- [main.py](file:///Users/apfanom/audaci-apt/main.py): Launches the desktop GUI and spawns background tasks.
- [central_bot_server.py](file:///Users/apfanom/audaci-apt/central_bot_server.py): Executable for the central bot server backend.

**Theme:**
- [theme.py](file:///Users/apfanom/audaci-apt/theme.py): Holds common HSL color palettes and custom gradients.

---

## Naming Conventions

**Files:**
- `snake_case.py` - Standard python files (e.g. `metadata_handler.py`).
- `test_*.py` - Test files in `tests/` directory (e.g. `test_telegram.py`).

**Variables and Functions:**
- `snake_case` - Used for functions, arguments, variables, and database column names.
- `camelCase` / `snake_case` - Event handlers in Flet often utilize snake_case, but python code follows PEP-8: `def handle_audio(message)`.
- `UPPER_SNAKE_CASE` - Constants, such as `DB_PATH`, `API_KEY`, `APP_DIR`.

**Classes:**
- `PascalCase` - Standard python class names (e.g. `AudioPlayer`, `VoiceController`, `KaraokePanel`).

---

## Where to Add New Code

**New UI component:**
- Add widget inside `ui/` directory.
- Reference and instantiate inside the page layouts in [main.py](file:///Users/apfanom/audaci-apt/main.py).

**New Local API route:**
- Append endpoint to FastAPI router in [core/api_server.py](file:///Users/apfanom/audaci-apt/core/api_server.py).
- Verify access check limits to prevent directory listing escapes.
- Add integration test to `tests/test_architectural_fixes.py`.

**New Persistence helper:**
- Add SQLite command handler to [core/db.py](file:///Users/apfanom/audaci-apt/core/db.py).
- Wrap SQL commands under the transactional `db_session()` helper.
- Verify coverage inside `tests/test_db.py`.

---

*Structure analysis: 2026-05-18*
*Update when directory structure changes*
