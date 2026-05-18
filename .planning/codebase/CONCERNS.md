# Codebase Concerns

**Analysis Date:** 2026-05-18

## Tech Debt

**Dynamic Volume Normalization (VLC limitations):**
- **Issue:** In [player.py:L163-177](file:///Users/apfanom/audaci-apt/core/player.py#L163-L177), `set_normalization()` is defined as a stub:
  ```python
  def set_normalization(self, enabled: bool):
      # In VLC управление фильтрами через Python API ограничено, 
      # но мы можем передать аргументы при инициализации инстанса.
      pass
  ```
- **Why:** LibVLC does not support dynamic injection of audio output filters (such as `normvol`) on initialized instances.
- **Impact:** The volume normalization toggle cannot be updated "on the fly" and requires reinstantiating the underlying `vlc.Instance` / `AudioPlayer`, interrupting active playback.

**Lack of dependency lockfile:**
- **Issue:** The codebase uses a flat `requirements.txt` with loose version bounds.
- **Why:** Ad-hoc prototyping, standard with simple Python setups.
- **Impact:** Upgrading third-party core frameworks (e.g. Flet or Aiogram minor version revisions) could introduce breaking API changes, leading to random test breakages.

---

## Known Bugs & Hard Limitations

**Vosk offline model requirement:**
- **Symptoms:** App startup crash or voice recognition fail.
- **Trigger:** Starting the app without the preloaded `./model/` folder present.
- **Workaround:** Voice assistant is deactivated dynamically if folder is missing.

**Telegram 20MB upload ceiling:**
- **Symptoms:** Error message `"Файл слишком большой (> 20 МБ)"` when uploading music to Bot.
- **Trigger:** Sending high-fidelity FLAC tracks or audio podcasts exceeding 20MB.
- **Cause:** Standard Telegram Bot API polling imposes a strict 20MB download restriction on client downloads.
- **Fix:** Needs deployment of a self-hosted local Bot API server.

---

## Security Considerations

**API Streaming Path Traversal (LFI):**
- **Risk:** The local streaming route `/api/stream/{file_path:path}` in [api_server.py](file:///Users/apfanom/audaci-apt/core/api_server.py) streams local audio files. If path traversal occurs, it could expose sensitive files outside allowed directories.
- **Mitigation:** Safe resolved parent evaluations in [api_server.py:L31-58](file:///Users/apfanom/audaci-apt/core/api_server.py#L31-L58):
  ```python
  resolved_file = Path(file_path).resolve()
  # Verify resolved_file resides inside allowed directories or home music folders
  ```
- **Recommendations:** Ensure that allowed directories retrieved from `app_state.settings` are fully resolved beforehand.

---

## Fragile Areas

**Multi-Thread event loops lifecycle coordination:**
- **Files:** [main.py](file:///Users/apfanom/audaci-apt/main.py) and [central_bot_server.py](file:///Users/apfanom/audaci-apt/central_bot_server.py).
- **Why fragile:** Coordinated shutdown is highly sensitive. If the main Flet thread gets killed abruptly (SIGINT), the background Uvicorn API server thread and Aiogram polling task must terminate cleanly.
- **Failures:** Orphaned Python processes lock the API port, causing socket binding conflicts on subsequent launches.
- **Precautions:** Ensure `handle_signals=False` is passed to Aiogram, and register exit callbacks to shut down socket threads.

---

*Concerns audit: 2026-05-18*
*Update as issues are fixed or new ones discovered*
