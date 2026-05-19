# Requirements: Audaci

**Defined:** 2026-05-18
**Core Value:** Simple, responsive, and seamless cross-device synchronization of a user's local music library using a Telegram bot.

## v1 Requirements

### UI Scalability (Regular & Focus Mode)

- [x] **UI-SCALE-01**: Playback controls (buttons, title, cover) in Focus Mode dynamically resize when window height is small (`h < 750`), ensuring no clipping.
- [x] **UI-SCALE-02**: The fullscreen focus mode button (`focus_btn`) is fully visible and not cut off on regular application startup.

### Telegram Bot Music Synchronization

- [x] **BOT-COVER-01**: Downloader automatically checks if track has cover art; if missing, it fetches the highest resolution album art from Last.fm and embeds it via Mutagen.
- [x] **BOT-KEYBOARD-01**: Synced and unsynchronized states in Telegram bot render custom reply/inline keyboards.
- [x] **BOT-STATUS-01**: User can query player connection status in Telegram bot (`🟢 В сети (Подключено)` or `🔴 Оффлайн (Не в сети)`).
- [x] **BOT-UNLINK-01**: User can safely unlink their desktop client from the Telegram bot.

### Codebase & Settings Path Compliance

- [x] **CONFIG-PATH-01**: Settings (`.audaci_settings.json`) and playlists (`.audaci_playlists.json`) JSON files are relocated to standard hidden folder `~/.audaci/`.

## v2 Requirements

### UI & Playlists Premium Features

- [ ] **UI-PREMIUM-01**: Implement light/dark theme switching that instantly updates the UI, sidebar, and playlist views.
- [ ] **PLAYLIST-BOT-01**: Allow users to query and view their desktop playlist names and track counts directly via the Telegram bot.
- [ ] **BOT-CONTROL-01**: Implement playback remote control (Play/Pause, Next, Prev) triggers sent from Telegram bot to Flet client via WebSocket.
- [ ] **BOT-NOWPLAYING-01**: Allow users to retrieve the currently playing track info ("Now Playing") from Flet client to Telegram bot via WebSocket.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-SCALE-01 | Phase 2 | Passed |
| UI-SCALE-02 | Phase 2 | Passed |
| BOT-COVER-01 | Phase 2 | Passed |
| BOT-KEYBOARD-01 | Phase 2 | Passed |
| BOT-STATUS-01 | Phase 2 | Passed |
| BOT-UNLINK-01 | Phase 2 | Passed |
| CONFIG-PATH-01 | Phase 2 | Passed |
| UI-PREMIUM-01 | Phase 3 | Pending |
| PLAYLIST-BOT-01 | Phase 3 | Pending |
| BOT-CONTROL-01 | Phase 3 | Pending |
| BOT-NOWPLAYING-01 | Phase 3 | Pending |

**Coverage:**
- v1 & v2 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-18*
*Last updated: 2026-05-19 after Phase 3 definition*
