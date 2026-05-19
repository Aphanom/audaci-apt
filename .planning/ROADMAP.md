# Roadmap: Audaci

## Overview

Audaci's current milestone improves the desktop player UI layout and scalability while enriching the Telegram bot's functionality with automatic cover art fetching and status keyboards.

## Phases

- [x] **Phase 1: UI Scalability & Telegram Bot Enhancements** - Complete all UI scaling fixes, cover art fetching, bot reply keyboards, player connection status, and directory settings path compliance.

## Phase Details

### Phase 1: UI Scalability & Telegram Bot Enhancements

**Goal**: Deliver a robust, adaptive, and premium user experience for both the desktop player and the Telegram bot synchronization system.
**Depends on**: Nothing (first phase of the current milestone)
**Requirements**: UI-SCALE-01, UI-SCALE-02, BOT-COVER-01, BOT-KEYBOARD-01, BOT-STATUS-01, BOT-UNLINK-01, CONFIG-PATH-01
**Success Criteria**:

  1. The Flet player's right block is fully visible on startup without clipping the fullscreen button.
  2. In Focus Mode, all buttons and text scale down smoothly without overflow on smaller window heights.
  3. Audaci desktop client automatically downloads and embeds missing cover art via Last.fm API.
  4. The Telegram bot presents status information, unlinking triggers, and rich interactive button grids.
  5. Playlists and settings JSON files reside strictly inside the `~/.audaci/` folder.

**Plans**: 1 plan

Plans:

- [x] 01-01: Implement UI scalability fixes, Last.fm cover art downloader, bot keyboards, and settings path migration.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. UI Scalability & Telegram Bot Enhancements | 1/1 | Completed | 2026-05-18 |
| 2. UI Scalability & Telegram Bot Enhancements | 1/1 | Completed | 2026-05-18 |
| 3. Premium UI Enhancements and Playlists     | 1/1 | Completed | 2026-05-19 |

### Phase 2: UI Scalability & Telegram Bot Enhancements

**Goal:** Deliver, consolidate, and verify a robust, adaptive, and premium user experience for both the desktop player and the Telegram bot synchronization system.
**Requirements**: UI-SCALE-01, UI-SCALE-02, BOT-COVER-01, BOT-KEYBOARD-01, BOT-STATUS-01, BOT-UNLINK-01, CONFIG-PATH-01
**Depends on:** Phase 1
**Plans:** 1 plan

Plans:

- [x] 02-01: Implement UI scalability fixes, Last.fm cover art downloader, bot keyboards, and settings path migration.

### Phase 3: Premium UI Enhancements and Playlists

**Goal:** Implement premium UI themes (light/dark mode toggle), expose user playlists, enable playback remote control (Play/Pause, Next, Prev), and fetch currently playing track details via the Telegram bot over WebSocket.
**Requirements**: UI-PREMIUM-01, PLAYLIST-BOT-01, BOT-CONTROL-01, BOT-NOWPLAYING-01
**Depends on:** Phase 2
**Plans:** 1 plan

Plans:

- [x] 03-01: Implement theme toggling with instant updates, Telegram bot playlists query, remote control endpoints, and currently playing track info sync.
