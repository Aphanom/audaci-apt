from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uvicorn
from typing import List, Optional
import core.db as db

app = FastAPI(title="Audaci API")

# Глобальная ссылка на плеер и состояние (будет установлена из main.py)
app_state = None
audio_player = None

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
    """Стриминг аудиофайла"""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Track not found")
    return FileResponse(file_path)

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
    """Управление плеером"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Player not initialized")
    
    if cmd.command == "play":
        audio_player.play()
    elif cmd.command == "pause":
        audio_player.pause()
    elif cmd.command == "toggle":
        audio_player.toggle_play_pause()
    elif cmd.command == "next":
        # Логика переключения на следующий трек должна быть в main.py, 
        # но мы можем вызвать колбэк если он будет установлен.
        pass
    
    return {"status": "ok", "command": cmd.command}

def start_api(player_instance, state_instance, host="0.0.0.0", port=8000):
    global audio_player, app_state
    audio_player = player_instance
    app_state = state_instance
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    # Тестовый запуск
    uvicorn.run(app, host="0.0.0.0", port=8000)
