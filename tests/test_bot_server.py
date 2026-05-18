import pytest
from fastapi.testclient import TestClient
from central_bot_server import app, DB_PATH, db_add_to_queue, db_get_queue_count, db_set_sync_code
import uuid
from pathlib import Path
import os
import sqlite3

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM queue")
        conn.commit()
    
    # Create a test directory for files
    test_dir = Path("server_data")
    test_dir.mkdir(exist_ok=True)
    
    yield
    
    # Teardown
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT file_path FROM queue")
        for row in cursor.fetchall():
            path = Path(row[0])
            if path.exists():
                path.unlink()
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM queue")
        conn.commit()


def test_bot_info_endpoint():
    # Мы не можем реально достучаться до Telegram API без валидного токена,
    # поэтому тестируем только то, что эндпоинт отдает 200 и возвращает fallback
    response = client.get("/api/bot/info")
    assert response.status_code == 200
    data = response.json()
    assert "username" in data
    # По умолчанию возвращается AudaciBot при неудаче запроса в Telegram
    assert data["username"] == "AudaciBot"


def test_check_sync_no_tracks():
    response = client.get("/api/sync/NONEXISTENT_CODE")
    assert response.status_code == 200
    assert response.json()["tracks_available"] == 0


def test_check_sync_with_tracks():
    sync_code = "TEST-CODE"
    test_file_path = "server_data/test_file.mp3"
    db_add_to_queue(sync_code, test_file_path)
    
    response = client.get(f"/api/sync/{sync_code}")
    assert response.status_code == 200
    assert response.json()["tracks_available"] == 1


def test_download_track_not_found():
    response = client.get("/api/sync/EMPTY_CODE/download")
    assert response.status_code == 404
    assert response.json()["detail"] == "No tracks available"


def test_download_track_success():
    sync_code = "TEST-CODE"
    
    # Создаем фиктивный файл
    file_id = uuid.uuid4().hex
    original_name = "test_audio.mp3"
    test_filename = f"{file_id}_{original_name}"
    test_file_path = Path("server_data") / test_filename
    
    with open(test_file_path, "wb") as f:
        f.write(b"dummy audio content")
        
    db_add_to_queue(sync_code, str(test_file_path))
    
    # Скачиваем файл
    response = client.get(f"/api/sync/{sync_code}/download")
    assert response.status_code == 200
    assert response.content == b"dummy audio content"
    
    # Проверяем, что заголовок содержит оригинальное имя (или оно есть в response.headers)
    assert original_name in response.headers.get("content-disposition", "")
    
    # Проверяем, что очередь очистилась
    assert db_get_queue_count(sync_code) == 0
    
    # Поскольку BackgroundTasks работает в TestClient асинхронно, файл может удалиться не сразу,
    # но TestClient выполняет их после возврата ответа.
    assert not test_file_path.exists()


def test_websocket_connect_no_tracks():
    sync_code = "WS-TEST-CODE-NO-TRACKS"
    with client.websocket_connect(f"/api/ws/sync/{sync_code}") as websocket:
        # Соединение успешно открыто, проверяем, что оно зарегистрировано в active_connections
        from central_bot_server import active_connections
        assert sync_code in active_connections
        assert len(active_connections[sync_code]) == 1
        websocket.close()
    
    # После выхода из контекста соединение должно быть закрыто и удалено.
    # Так как отключение обрабатывается асинхронно, даем серверу несколько миллисекунд на очистку.
    import time
    for _ in range(50):
        if sync_code not in active_connections:
            break
        time.sleep(0.02)
        
    assert sync_code not in active_connections


def test_websocket_connect_with_existing_tracks():
    sync_code = "WS-TEST-CODE-WITH-TRACKS"
    test_file_path = "server_data/test_ws_file.mp3"
    db_add_to_queue(sync_code, test_file_path)
    
    with client.websocket_connect(f"/api/ws/sync/{sync_code}") as websocket:
        # Так как трек есть в очереди, сервер должен сразу прислать {"event": "new_track"}
        data = websocket.receive_json()
        assert data == {"event": "new_track"}


def test_websocket_instant_notification_on_new_track():
    sync_code = "WS-INSTANT-TEST-CODE"
    with client.websocket_connect(f"/api/ws/sync/{sync_code}") as websocket:
        from central_bot_server import active_connections, notify_clients
        assert sync_code in active_connections
        
        # Вызываем notify_clients асинхронно
        import asyncio
        asyncio.run(notify_clients(sync_code))
        
        # Проверяем, что сообщение мгновенно получено клиентом в реальном времени
        data = websocket.receive_json()
        assert data == {"event": "new_track"}


def test_db_delete_user():
    sync_code = "UNLINK-CODE"
    user_id = 99999
    db_set_sync_code(user_id, sync_code)
    
    # Verify set
    from central_bot_server import db_get_sync_code, db_delete_user
    assert db_get_sync_code(user_id) == sync_code
    
    # Delete and verify
    db_delete_user(user_id)
    assert db_get_sync_code(user_id) is None


def test_websocket_unlink_notification():
    sync_code = "WS-UNLINK-CODE"
    with client.websocket_connect(f"/api/ws/sync/{sync_code}") as websocket:
        from central_bot_server import active_connections, notify_unlink
        assert sync_code in active_connections
        
        # Trigger unlinking notification
        import asyncio
        asyncio.run(notify_unlink(sync_code))
        
        # Verify unlinked event received
        data = websocket.receive_json()
        assert data == {"event": "unlinked"}


