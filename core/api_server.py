from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uvicorn
from typing import List, Optional
from pathlib import Path
import core.db as db

app = FastAPI(title="Audaci API")

# Глобальная ссылка на плеер, состояние и колбэк управления (будет установлена из main.py)
app_state = None
audio_player = None
control_callback = None

class ControlCommand(BaseModel):
    command: str  # play, pause, toggle, next, prev
    value: Optional[float] = None

@app.get("/api/tracks")
async def get_tracks():
    """Возвращает список всех треков из БД"""
    tracks = db.search_tracks("") # Пустой запрос вернет все (с лимитом 50)
    return tracks

@app.get("/api/stream/{file_path:path}")
async def stream_track(file_path: str):
    """Стриминг аудиофайла с предотвращением Path Traversal / Local File Inclusion (LFI)"""
    try:
        resolved_file = Path(file_path).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path format")

    if not resolved_file.exists() or not resolved_file.is_file():
        raise HTTPException(status_code=404, detail="Track not found")

    # Сверяем со списком разрешенных директорий из настроек плеера
    allowed_folders = []
    if app_state and hasattr(app_state, "settings"):
        allowed_folders.extend(app_state.settings.get("music_folders", []))
    
    # Также разрешаем стандартную директорию для Telegram-загрузок
    allowed_folders.append(str(Path.home() / "Music" / "Audaci Telegram"))
    allowed_folders.append(str(Path.home() / ".audaci" / "Audaci Telegram"))

    is_allowed = False
    for folder in allowed_folders:
        try:
            resolved_folder = Path(folder).resolve()
            # Проверяем, что запрашиваемый файл находится внутри разрешенной папки
            if resolved_folder in resolved_file.parents or resolved_folder == resolved_file:
                is_allowed = True
                break
        except Exception:
            continue

    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied: file is outside allowed music folders")

    return FileResponse(str(resolved_file))

@app.get("/api/status")
async def get_status():
    """Текущее состояние плеера"""
    if not audio_player:
        return {"status": "offline"}
    
    return {
        "is_playing": audio_player.player.is_playing(),
        "current_track": audio_player.current_track_path,
        "volume": audio_player.get_volume(),
        "position": audio_player.get_position()
    }

@app.post("/api/control")
async def control_player(cmd: ControlCommand):
    """Управление плеером через внешние вызовы"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Player not initialized")
    
    if control_callback:
        # Вызываем потокобезопасный UI-колбэк
        control_callback(cmd.command)
    else:
        # Фолбэк, если колбэк не зарегистрирован
        if cmd.command == "play":
            audio_player.play()
        elif cmd.command == "pause":
            audio_player.pause()
        elif cmd.command == "toggle":
            audio_player.toggle_play_pause()
    
    return {"status": "ok", "command": cmd.command}

def start_api(player_instance, state_instance, on_control_cmd=None, host="0.0.0.0", port=8000):
    global audio_player, app_state, control_callback
    audio_player = player_instance
    app_state = state_instance
    control_callback = on_control_cmd
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    # Тестовый запуск
    uvicorn.run(app, host="0.0.0.0", port=8000)
