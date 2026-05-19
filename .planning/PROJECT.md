# Audaci

## What This Is

Audaci is a cross-platform desktop music player written in Python utilizing the Flet GUI framework. It features robust background synchronization through a centralized Telegram bot server and a local FastAPI server, allowing users to effortlessly synchronize their local music libraries.

## Core Value

Simple, responsive, and seamless cross-device synchronization of a user's local music library using a Telegram bot.

## Requirements

### Validated

- ✓ Cross-platform audio player layout (Flet) — Phase 0
- ✓ Multi-threaded SQLite library scanning and tag extraction (Mutagen) — Phase 0
- ✓ Multi-threaded web lyrics lookup (LRCLIB) and vocal removal/karaoke overlay — Phase 0
- ✓ Basic Telegram audio file download receiver and socket polling sync system — Phase 0
- ✓ UI Scalability and Resizing (UI-SCALE-01, UI-SCALE-02) — Phase 1 & 2
- ✓ Last.fm Auto Cover Downloader & Injector (BOT-COVER-01) — Phase 1 & 2
- ✓ Telegram Interactive Options & Keyboard (BOT-KEYBOARD-01, BOT-STATUS-01, BOT-UNLINK-01) — Phase 1 & 2
- ✓ Centralized User Config Path Migration (CONFIG-PATH-01) — Phase 1 & 2
- ✓ Theme State Persistence (UI-PREMIUM-01) — Phase 3
- ✓ Remote Playlists & Now Playing Querying (PLAYLIST-BOT-01, BOT-NOWPLAYING-01) — Phase 3
- ✓ Playback Remote Control (BOT-CONTROL-01) — Phase 3

### Active

- None (All planned requirements for the current milestone are fully validated)

### Out of Scope

- Integrating a custom audio processing DSP (out of scope for this milestone)
- Multi-user authentication in the desktop client (out of scope, single client mode only)

## Context

Audaci utilizes:
- Flet for desktop UI rendering.
- Python-VLC for audio playback.
- Mutagen for audio file metadata parsing and editing.
- FastAPI / Uvicorn for local API and sync polling client.
- Aiogram 3.x for synchronization bot.
- SQLite for local track storage.

## Constraints

- **Thread Safety**: Flet event loops and WebSocket polling must never block the main thread (Rule 1).
- **Aiogram integration**: Polling in the background must not hijack termination signals (Rule 2).
- **Data storage**: All database, settings, and media files must reside inside `~/.audaci/` user directory (Rule 5).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use Last.fm for Missing Cover Art | Robust, globally available metadata provider that doesn't require complex image scraping | Implemented |
| Standardize Paths to ~/.audaci/ | Avoid polluting home directory and comply with user-defined rules | Implemented |

---
*Last updated: 2026-05-19 after Phase 3 completion*
