import os
import shutil
from pathlib import Path
import pytest

def test_telegram_symlink_migration(tmp_path):
    # Set up mock home directory paths
    music_tg_dir = tmp_path / "Music" / "Audaci Telegram"
    audaci_tg_dir = tmp_path / ".audaci" / "Audaci Telegram"

    # Create old tracks in real Music directory
    music_tg_dir.mkdir(parents=True)
    old_track = music_tg_dir / "old_track.mp3"
    old_track.write_text("audio-data")

    # Run migration logic
    audaci_tg_dir.mkdir(parents=True, exist_ok=True)

    if music_tg_dir.exists() and not music_tg_dir.is_symlink():
        try:
            for item in music_tg_dir.iterdir():
                if item.is_file():
                    dest = audaci_tg_dir / item.name
                    if not dest.exists():
                        shutil.move(str(item), str(dest))
            music_tg_dir.rmdir()
        except Exception as migration_err:
            pytest.fail(f"Migration failed: {migration_err}")

    if not music_tg_dir.exists() and not music_tg_dir.is_symlink():
        try:
            os.symlink(str(audaci_tg_dir), str(music_tg_dir))
        except Exception as symlink_err:
            pytest.fail(f"Symlink failed: {symlink_err}")

    # Verify migration results
    assert music_tg_dir.is_symlink()
    assert os.readlink(str(music_tg_dir)) == str(audaci_tg_dir)
    assert (audaci_tg_dir / "old_track.mp3").exists()
    assert (music_tg_dir / "old_track.mp3").exists()  # Visible through symlink!
