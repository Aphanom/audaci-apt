# Requirements: Audaci

**Defined:** 2026-05-18
**Core Value:** Simple, responsive, and seamless cross-device synchronization of a user's local music library using a Telegram bot.

## v1 Requirements

### UI Scalability (Regular & Focus Mode)

- [ ] **UI-SCALE-01**: Playback controls (buttons, title, cover) in Focus Mode dynamically resize when window height is small (`h < 750`), ensuring no clipping.
- [ ] **UI-SCALE-02**: The fullscreen focus mode button (`focus_btn`) is fully visible and not cut off on regular application startup.

### Telegram Bot Music Synchronization

- [ ] **BOT-COVER-01**: Downloader automatically checks if track has cover art; if missing, it fetches the highest resolution album art from Last.fm and embeds it via Mutagen.
- [ ] **BOT-KEYBOARD-01**: Synced and unsynchronized states in Telegram bot render custom reply/inline keyboards.
- [ ] **BOT-STATUS-01**: User can query player connection status in Telegram bot (`🟢 В сети (Подключено)` or `🔴 Оффлайн (Не в сети)`).
- [ ] **BOT-UNLINK-01**: User can safely unlink their desktop client from the Telegram bot.

### Codebase & Settings Path Compliance

- [ ] **CONFIG-PATH-01**: Settings (`.audaci_settings.json`) and playlists (`.audaci_playlists.json`) JSON files are relocated to standard hidden folder `~/.audaci/`.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-SCALE-01 | Phase 1 | Pending |
| UI-SCALE-02 | Phase 1 | Pending |
| BOT-COVER-01 | Phase 1 | Pending |
| BOT-KEYBOARD-01 | Phase 1 | Pending |
| BOT-STATUS-01 | Phase 1 | Pending |
| BOT-UNLINK-01 | Phase 1 | Pending |
| CONFIG-PATH-01 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 7 total
- Mapped to phases: 7
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-18*
*Last updated: 2026-05-18 after initial definition*
