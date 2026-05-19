# Requirements: Milestone v1.2 (Release Infrastructure)

This milestone focuses on providing robust, out-of-the-box running application builds for macOS, Windows, and Linux via GitHub Actions (`build.yml`).

## Requirements

### Active

- [ ] **BUILD-SYS-01**: Windows standalone assembly. The executable `Audaci.exe` produced by the build pipeline must contain all Python dependencies, Vosk model directory, PortAudio dynamic link libraries (`libportaudio` / `portaudio.dll` for `sounddevice`), and handle VLC engine initialization cleanly without requiring a pre-installed VLC player.
- [ ] **BUILD-SYS-02**: macOS bundle portability. The generated `Audaci.app` bundle must resolve all system dynamic libraries (including `PIL` dylibs, Vosk dynamic libraries, `portaudio` / `sounddevice` dylibs, and `libvlc` references). It must run cleanly on a vanilla macOS machine without missing library linkage errors (fix rpaths using `delocate` or environment configurations).
- [ ] **BUILD-SYS-03**: Linux package compliance. The `.deb` package should package internal Python requirements and resource files (Vosk model, app icons), list proper system dependencies (`libgtk-3-0`, `libvlc5`, `vlc`, `portaudio19`), and run out-of-the-box on Debian/Ubuntu environments.

## Traceability Matrix

| Requirement | Phase | Plan | Test Case | Status |
|-------------|-------|------|-----------|--------|
| BUILD-SYS-01 | Phase 4 | 04-01 | Manual Verification / Win Run | Planned |
| BUILD-SYS-02 | Phase 4 | 04-01 | Manual Verification / macOS Run | Planned |
| BUILD-SYS-03 | Phase 4 | 04-01 | Manual Verification / Linux Run | Planned |
