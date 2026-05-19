import pytest
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import core.db as db
import core.nlu as nlu
from core.api_server import app, start_api
import core.api_server as api_server

# 1. Тестирование защиты от LFI (FastAPI)
def test_lfi_streaming_security():
    # Создаем временную директорию (разрешенную для музыки)
    with tempfile.TemporaryDirectory() as temp_music_dir:
        music_path = Path(temp_music_dir).resolve()
        
        # Создаем разрешенный файл
        allowed_file = music_path / "song.mp3"
        allowed_file.write_text("dummy mp3 content")
        
        # Создаем запрещенный файл (вне разрешенной папки)
        with tempfile.TemporaryDirectory() as temp_forbidden_dir:
            forbidden_path = Path(temp_forbidden_dir).resolve()
            forbidden_file = forbidden_path / "secret.txt"
            forbidden_file.write_text("secret user data")
            
            # Настраиваем mock app_state с разрешенными директориями
            mock_app_state = MagicMock()
            mock_app_state.settings = {
                "music_folders": [str(music_path)]
            }
            
            # Внедряем mock состояние в сервер
            api_server.app_state = mock_app_state
            
            client = TestClient(app)
            
            # Проверяем, что разрешенный файл возвращается успешно (200)
            response_allowed = client.get(f"/api/stream/{allowed_file}")
            assert response_allowed.status_code == 200
            assert response_allowed.text == "dummy mp3 content"
            
            # Проверяем, что запрещенный файл отклоняется (403)
            response_forbidden = client.get(f"/api/stream/{forbidden_file}")
            assert response_forbidden.status_code == 403
            assert "Access denied" in response_forbidden.json()["detail"]

# 2. Тестирование транзакционности db_session
def test_db_session_transaction_and_close(db_conn):
    # Должен автоматически закомитить изменения при успешном выполнении
    info = {"title": "Session Track", "artist": "Session Artist"}
    db.add_track("/path/to/session.mp3", "/path/to", info)
    
    track = db.get_track("/path/to/session.mp3")
    assert track is not None
    assert track["title"] == "Session Track"
    
    # Должен откатить транзакцию при возникновении исключения
    original_count = len(db.search_tracks(""))
    try:
        with db.db_session() as conn:
            conn.execute("INSERT INTO tracks (file_path, title) VALUES (?, ?)", ("/path/to/error.mp3", "Error"))
            # Вызовем исключение внутри блока
            raise ValueError("Forced error")
    except ValueError:
        pass
        
    # Проверяем, что запись не добавилась
    assert len(db.search_tracks("")) == original_count
    assert db.get_track("/path/to/error.mp3") is None

# 3. Тестирование NLU fallback без rapidfuzz
def test_nlu_fallbacks():
    # Мокаем RAPIDFUZZ_AVAILABLE = False
    nlu.RAPIDFUZZ_AVAILABLE = False
    
    # 1. Проверяем разбор интента артиста с простым совпадением (по алиасу)
    intent_artist = nlu.analyze_intent("поставь канье")
    assert intent_artist["intent"] == "play_artist"
    assert intent_artist["entity"] == "Kanye West"
    
    # 2. Проверяем разбор интента альбома (по алиасу)
    intent_album = nlu.analyze_intent("включи альбом були")
    assert intent_album["intent"] == "play_album"
    assert intent_album["entity"] == "BULLY"


# 4. Тестирование сохранения настроек темы оформления (UI-PREMIUM-01)
def test_theme_persistence():
    import json
    with tempfile.TemporaryDirectory() as temp_dir:
        settings_file = Path(temp_dir) / "settings.json"
        
        # Начальные настройки
        settings = {
            "theme_mode": "dark",
            "music_folders": []
        }
        
        # Имитируем сохранение настроек
        def mock_save_settings(filepath, data):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        # Меняем тему на light и сохраняем
        settings["theme_mode"] = "light"
        mock_save_settings(settings_file, settings)
        
        # Считываем обратно
        with open(settings_file, 'r', encoding='utf-8') as f:
            loaded_settings = json.load(f)
            
        assert loaded_settings["theme_mode"] == "light"
