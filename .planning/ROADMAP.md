# Roadmap: Audaci

## Milestones

- ✅ **v1.0 MVP** — UI Scalability & basic Telegram Sync (shipped 2026-05-18)
- ✅ **v1.1 Premium UI & Playlists** — Theme Switching, Remote Playback Controls, Playlists Querying (shipped 2026-05-19)
- 🚧 **v1.2 Release Infrastructure** — Cross-Platform Build & Packaging (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP & v1.1 Premium UI — SHIPPED</summary>

- [x] Phase 1: UI Scalability & Telegram Bot Enhancements — completed 2026-05-18
- [x] Phase 2: UI Scalability & Telegram Bot Enhancements — completed 2026-05-18
- [x] Phase 3: Premium UI Enhancements and Playlists — completed 2026-05-19

</details>

### 🚧 v1.2 Release Infrastructure

- [ ] Phase 4: Cross-Platform Build & Packaging System
  - **Goal**: Make the GitHub Actions build (`build.yml`) work out-of-the-box for macOS, Windows, and Linux, package all non-python dependencies (VLC, PortAudio, Vosk dylib/dll), and produce running executables.
  - **Depends on**: Phase 3
  - **Requirements**: BUILD-SYS-01, BUILD-SYS-02, BUILD-SYS-03
  - **Plans**: 1 plan

Plans:

- [ ] 04-01: Update and configure build.yml workflow for multi-platform dependency embedding (VLC, PortAudio, Vosk) and build automation.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. UI Scalability & Telegram Bot Enhancements | v1.0 | 1/1 | Complete | 2026-05-18 |
| 2. UI Scalability & Telegram Bot Enhancements | v1.1 | 1/1 | Complete | 2026-05-18 |
| 3. Premium UI Enhancements and Playlists     | v1.1 | 1/1 | Complete | 2026-05-19 |
| 4. Cross-Platform Build & Packaging System   | v1.2 | 0/1 | Not started | - |
