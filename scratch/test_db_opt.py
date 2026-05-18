import pytest
import os
from pathlib import Path
import core.db as db

def test_add_track_optimized():
    """Тест оптимизированного добавления трека в БД."""
    db.init_db()
    
    test_info = {
        "file_path": "/tmp/test_track_opt.mp3",
        "title": "Optimized Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration_ms": 180000,
        "mood_tags": "test, mood"
    }
    
    db.add_track_optimized(test_info)
    
    # Проверяем, что трек добавился
    track = db.get_track("/tmp/test_track_opt.mp3")
    assert track is not None
    assert track["title"] == "Optimized Track"
    assert track["artist"] == "Test Artist"
    assert track["mood_tags"] == "test, mood"
    
    # Проверяем автоматическое определение папки
    assert track["folder_path"] == "/tmp"

if __name__ == "__main__":
    test_add_track_optimized()
    print("Test add_track_optimized passed!")
