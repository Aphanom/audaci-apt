import pytest
import core.db as db
import os

def test_init_db(db_conn):
    # init_db is called in fixture
    cursor = db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "tracks" in tables
    assert "history" in tables

def test_add_and_get_track(db_conn):
    info = {
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration_ms": 120000,
        "cover_path": "/path/to/cover.jpg",
        "mood_tags": "chill, happy"
    }
    db.add_track("/path/to/file.mp3", "/path/to", info)
    
    track = db.get_track("/path/to/file.mp3")
    assert track is not None
    assert track["title"] == "Test Track"
    assert track["artist"] == "Test Artist"
    assert track["mood_tags"] == "chill, happy"

def test_search_tracks(db_conn):
    info = {"title": "UniqueSong", "artist": "UniqueArtist"}
    db.add_track("/path/to/unique.mp3", "/path/to", info)
    
    results = db.search_tracks("Unique")
    assert len(results) >= 1
    assert results[0]["title"] == "UniqueSong"

def test_get_tracks_by_vibe(db_conn):
    info = {"title": "Chill Song", "mood_tags": "lo-fi, chill"}
    db.add_track("/path/to/chill.mp3", "/path/to", info)
    
    # "chill" vibe category includes "chill" keyword
    results = db.get_tracks_by_vibe("chill")
    assert "/path/to/chill.mp3" in results
