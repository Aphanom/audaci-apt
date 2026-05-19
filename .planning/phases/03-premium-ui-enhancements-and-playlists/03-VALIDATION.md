---
phase: 3
slug: premium-ui-enhancements-and-playlists
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-19
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=. venv/bin/pytest tests/test_telegram.py` |
| **Full suite command** | `PYTHONPATH=. venv/bin/pytest tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=. venv/bin/pytest tests/test_telegram.py`
- **After every plan wave:** Run `PYTHONPATH=. venv/bin/pytest tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | UI-PREMIUM-01 | — | N/A | unit | `PYTHONPATH=. venv/bin/pytest tests/test_architectural_fixes.py` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | PLAYLIST-BOT-01 | — | N/A | integration | `PYTHONPATH=. venv/bin/pytest tests/test_telegram.py` | ✅ | ⬜ pending |
| 03-01-03 | 01 | 1 | BOT-CONTROL-01 | — | N/A | integration | `PYTHONPATH=. venv/bin/pytest tests/test_telegram.py` | ✅ | ⬜ pending |
| 03-01-04 | 01 | 1 | BOT-NOWPLAYING-01 | — | N/A | integration | `PYTHONPATH=. venv/bin/pytest tests/test_telegram.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Theme switches instantly on clicking light/dark toggle | UI-PREMIUM-01 | Requires GUI rendering validation | Launch desktop player, click the Theme icon in settings/nav, confirm the entire application swaps background colors. |
| Remote control pauses/plays and skips tracks from Telegram | BOT-CONTROL-01 | Requires VLC player state check | Click the playback controls in Telegram bot, ensure the local music player plays/pauses or skips songs accordingly. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-19
