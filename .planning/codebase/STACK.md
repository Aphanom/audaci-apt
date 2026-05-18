# Technology Stack

**Analysis Date:** 2026-05-18

## Languages

**Primary:**
- **Python 3.10+** - All application logic, GUI layout (Flet), REST API (FastAPI), Telegram Bot (Aiogram), and audio control scripts.

**Secondary:**
- **SQL** - SQLite3 schema definition, track/history operations in [db.py](file:///Users/apfanom/audaci-apt/core/db.py).
- **JSON** - Configuration formats, LRC synchronized lyrics representation.

## Runtime

**Environment:**
- **Python 3.10+ Interpreter** - CPython runtime on local user machines.
- **LibVLC Shared Library** - Dynamic library dependency required on host machine for `python-vlc` bindings (wraps VLC Media Player engine).
- **Vosk STT Model** - Offline acoustic speech model required for voice recognition in `core/voice_cmd.py`.

**Package Manager:**
- **pip** - Standard Python package installer via `requirements.txt` (no lockfile present).

## Frameworks

**Core:**
- **Flet (0.22.1+)** - Flutter-based reactive UI framework for Python, running the desktop shell in [main.py](file:///Users/apfanom/audaci-apt/main.py).
- **FastAPI** - Async REST API server running on the local player to receive remote commands and stream files in [api_server.py](file:///Users/apfanom/audaci-apt/core/api_server.py).
- **Aiogram 3.x** - Async Telegram Bot API framework for bot polling in [telegram_handler.py](file:///Users/apfanom/audaci-apt/core/telegram_handler.py) and [central_bot_server.py](file:///Users/apfanom/audaci-apt/central_bot_server.py).
- **Uvicorn** - ASGI server implementation hosting FastAPI endpoints.

**Testing:**
- **Pytest** - Core test framework for running all tests.
- **Pytest-Asyncio** - Pytest plugin to support asynchronous test execution.
- **FastAPI TestClient** - Integration test utility for FastAPI endpoints and websockets.

## Key Dependencies

**Audio & Metadating:**
- **python-vlc** - Bindings to LibVLC for robust multi-format audio playback, volume normalization, and 10-band equalizer settings in [player.py](file:///Users/apfanom/audaci-apt/core/player.py).
- **mutagen** - Audio metadata tag parser extracting titles, artists, albums, duration, and embedded APIC/covr/FLAC pictures in [metadata_handler.py](file:///Users/apfanom/audaci-apt/core/metadata_handler.py).

**Speech & Logic:**
- **vosk** - Offline voice recognition using pre-trained speech models inside [voice_cmd.py](file:///Users/apfanom/audaci-apt/core/voice_cmd.py).
- **sounddevice** - PortAudio-based microphone audio stream recording.
- **rapidfuzz** - Fast phonetic and string distance matching for Cyrillic-to-Latin speech command translation in [nlu.py](file:///Users/apfanom/audaci-apt/core/nlu.py).
- **aiohttp / requests** - HTTP client libraries for async fetching of Last.fm tags in [tag_fetcher.py](file:///Users/apfanom/audaci-apt/core/tag_fetcher.py) and LRCLIB lyrics in [lyrics_handler.py](file:///Users/apfanom/audaci-apt/core/lyrics_handler.py).

## Configuration

**Environment:**
- `TELEGRAM_TOKEN` - Standard bot API token for Telegram polling.
- `AUDACI_DB_DIR` - Override user storage path (defaults to hidden user directory `~/.audaci/`).
- `LASTFM_API_KEY` - Last.fm integration token (fallback key hardcoded in [tag_fetcher.py](file:///Users/apfanom/audaci-apt/core/tag_fetcher.py)).
- `PORT` - Port binding for the central synchronization server.

**Platform Settings:**
- Hidden directory `~/.audaci/` holds SQLite database `audaci_library.db`, cache, and `covers/` subdirectory.
- Native config `~/.audaci_settings.json` controls volume levels, audio devices, and custom settings.

## Platform Requirements

**Development & Production:**
- **macOS / Linux / Windows** - Dynamic OS compatibility.
- Special Astras/Linux hooks in [main.py](file:///Users/apfanom/audaci-apt/main.py) check environment to deactivate GPU rendering and bind `VLC_PLUGIN_PATH` / `PYTHON_VLC_LIB_PATH` to local paths if needed.
- Microphone permissions required for Vosk speech control.

---

*Stack analysis: 2026-05-18*
*Update after major dependency changes*
