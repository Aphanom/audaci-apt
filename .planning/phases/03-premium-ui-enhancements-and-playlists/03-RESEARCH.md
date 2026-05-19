# Phase 3 Research: Premium UI Enhancements and Playlists

## Technical Approach

### 1. Theme Switching Architecture (UI-PREMIUM-01)
*   **Flet Theme Mechanism:** Flet uses `page.theme_mode` (either `ft.ThemeMode.DARK` or `ft.ThemeMode.LIGHT`) to determine the system appearance.
*   **Color Persistence:** Toggle switches will mutate `settings["theme_mode"]` inside `settings.json` (stored in `~/.audaci/settings.json`) and call `page.update()` to apply changes dynamically across all active controls.
*   **Dynamic Container Adapters:** Ensure the sidebar (`playlists_container`) dynamically alternates colors:
    *   Dark mode: `#121212` background, white/grey text.
    *   Light mode: `#FFFFFF` background, black/dark-grey text.

### 2. Telegram Bot Playlists API (PLAYLIST-BOT-01)
*   **WebSocket Protocol Extension:** Introduce a new request-response message pair over the established WebSocket client-server channel:
    *   Action: `get_playlists` (sent by central server to desktop client).
    *   Response: `playlists_data` (sent by desktop client containing playlist names and track counts).
*   **Aiogram Handlers:** Add a button `📋 Мои плейлисты` and a command `/playlists` in `central_bot_server.py`.
*   **Timeout & Fallback:** If the client is offline (`🔴 Оффлайн`), the bot returns an offline status message without trying to poll the WebSocket.

### 3. Playback Remote Control (BOT-CONTROL-01)
*   **WebSocket Controls:** Add buttons and commands for playback control to `ReplyKeyboardMarkup` inside the Telegram bot:
    *   `⏯️ Воспроизведение / Пауза` (or command `/toggle`) -> Sends WebSocket event `{"event": "control", "action": "toggle"}`
    *   `⏭️ Следующий трек` (or command `/next`) -> Sends WebSocket event `{"event": "control", "action": "next"}`
    *   `⏮️ Предыдущий трек` (or command `/prev`) -> Sends WebSocket event `{"event": "control", "action": "prev"}`
*   **Flet Integration:** Inside `poll_central_server`'s WebSocket client in `main.py`, parse `"control"` events and call `play_pause_click()`, `next_click()`, or `prev_click()` respectively on the main thread safely.

### 4. Now Playing Status (BOT-NOWPLAYING-01)
*   **WebSocket Query:** Add a command `/nowplaying` and a button `🎵 Сейчас играет` inside the Telegram bot.
*   **Flet Query Handling:** Client receives event `{"event": "get_now_playing", "request_id": request_id}`. It reads current track info (`currently_playing` state, artist, title) and replies with event `{"event": "now_playing_data", "request_id": request_id, "track": {"title": ..., "artist": ...}}` or `None` if stopped.

## Validation Architecture

### Automated Tests
*   Add a test case in `tests/test_telegram.py` simulating a `get_playlists`, `control`, and `get_now_playing` message exchange over WebSocket.
*   Add a test in `tests/test_architectural_fixes.py` verifying that theme setting toggle preserves state in settings JSON file.

## RESEARCH COMPLETE
