# Phase 2: UI Scalability & Telegram Bot Enhancements - Context

**Gathered:** 2026-05-18
**Status:** Completed

<domain>
## Phase Boundary
This phase formally consolidates and verifies the Flet UI scalable dynamic sizing, the Last.fm integration for downloading and embedding missing track cover art via Mutagen, custom bot keyboards, player online status, and client settings path migrations.
</domain>

<decisions>
## Implementation Decisions

### 1. Concurrency & Event Loops
*   All heavy synchronous operations (Mutagen metadata parsing, Last.fm HTTP downloads) are offloaded to background threads (`asyncio.to_thread` or thread pools) so Flet's UI loop never blocks.
*   FastAPI runs via Uvicorn inside a daemon thread.
*   Aiogram bot runs background polling with `handle_signals=False` inside a daemon thread to prevent intercepting termination signals.

### 2. Path Compliance
*   Database (`audaci_library.db`), configurations, and covers are localized strictly to standard user directory `~/.audaci/`.

### 3. Security Checks
*   SQL query in `get_tracks_by_vibe` is parameterized safely to protect against injection vectors.
*   FastAPI stream-track file pathways are validated using `parents` checks to secure against path traversal (LFI).
</decisions>

<canonical_refs>
## Canonical References
*   [audaci-core.md](file:///Users/apfanom/audaci-apt/.gemini/antigravity/knowledge/audaci-core.md) — Main user architectural guidelines.
</canonical_refs>

<specifics>
## Specific Ideas
*   All tests must pass successfully to confirm 100% execution health.
</specifics>
