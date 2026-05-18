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

### Active

- [ ] **UI-SCALE-01**: Solve bottom button overflow/cut-off in Fullscreen / Focus Mode on smaller windows by dynamically adjusting sizes.
- [ ] **UI-SCALE-02**: Prevent the `focus_btn` from being clipped/cut off upon regular window startup.
- [ ] **BOT-COVER-01**: Query Last.fm's track.getInfo API, download image bytes, and automatically embed cover art in track metadata if a Telegram uploaded track lacks cover art.
- [ ] **BOT-KEYBOARD-01**: Add a rich interactive keyboard layout in Telegram for synchronized and unsynchronized states.
- [ ] **BOT-STATUS-01**: Display active desktop player connection status (`🟢 В сети (Подключено)` or `🔴 Оффлайн (Не в сети)`) inside the Telegram bot.
- [ ] **BOT-UNLINK-01**: Add unlinking support directly from the Telegram bot.
- [ ] **CONFIG-PATH-01**: Move settings and playlists JSON files to standard hidden folder `~/.audaci/` to adhere to Rule 5 of the architectural rules.

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
| Use Last.fm for Missing Cover Art | Robust, globally available metadata provider that doesn't require complex image scraping | — Pending |
| Standardize Paths to ~/.audaci/ | Avoid polluting home directory and comply with user-defined rules | — Pending |

---
*Last updated: 2026-05-18 after Milestone 1 setup*
