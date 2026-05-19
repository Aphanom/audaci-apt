import asyncio
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
import uuid
import sqlite3

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager, contextmanager
import uvicorn

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "123456789:AAGdummy_token_for_testing_purposes")
SERVER_PORT = int(os.getenv("PORT", "8080"))
DATA_DIR = Path("server_data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "audaci_server.db"

@contextmanager
def db_session():
    """Безопасный контекстный менеджер для SQLite3: транзакции + гарантированное закрытие."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Инициализация базы данных
def init_db():
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                sync_code TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_code TEXT NOT NULL,
                file_path TEXT NOT NULL
            )
        ''')

init_db()

# Вспомогательные функции для работы с БД
def db_set_sync_code(user_id: int, sync_code: str):
    with db_session() as conn:
        conn.execute("INSERT OR REPLACE INTO users (telegram_id, sync_code) VALUES (?, ?)", (user_id, sync_code))

def db_get_sync_code(user_id: int) -> Optional[str]:
    with db_session() as conn:
        cursor = conn.execute("SELECT sync_code FROM users WHERE telegram_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None

def db_delete_user(user_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM users WHERE telegram_id = ?", (user_id,))

def db_add_to_queue(sync_code: str, file_path: str):
    with db_session() as conn:
        conn.execute("INSERT INTO queue (sync_code, file_path) VALUES (?, ?)", (sync_code, file_path))

def db_get_queue_count(sync_code: str) -> int:
    with db_session() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM queue WHERE sync_code = ?", (sync_code,))
        return cursor.fetchone()[0]

def db_pop_from_queue(sync_code: str) -> Optional[str]:
    with db_session() as conn:
        cursor = conn.execute("SELECT id, file_path FROM queue WHERE sync_code = ? ORDER BY id ASC LIMIT 1", (sync_code,))
        row = cursor.fetchone()
        if row:
            conn.execute("DELETE FROM queue WHERE id = ?", (row[0],))
            return row[1]
        return None

# Активные WebSocket соединения: sync_code -> list[WebSocket]
active_connections: Dict[str, List[WebSocket]] = {}
# Ожидающие ответов WebSocket запросы: request_id -> Future
pending_requests: Dict[str, asyncio.Future] = {}

async def notify_clients(sync_code: str):
    if sync_code in active_connections:
        for ws in active_connections[sync_code]:
            try:
                await ws.send_json({"event": "new_track"})
            except Exception as e:
                logger.error(f"Error sending websocket message: {e}")

async def notify_unlink(sync_code: str):
    if sync_code in active_connections:
        for ws in list(active_connections[sync_code]):
            try:
                await ws.send_json({"event": "unlinked"})
            except Exception as e:
                logger.error(f"Error sending websocket unlink message: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск поллинга Aiogram в фоне
    dp.include_router(router)
    # handle_signals=False критично важно, чтобы Uvicorn мог нормально завершиться
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    yield
    # Остановка поллинга при завершении работы FastAPI
    polling_task.cancel()
    await dp.stop_polling()

app = FastAPI(title="Audaci Central Bot API", lifespan=lifespan)
router = Router()
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- AIOGRAM BOT ---

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [
            KeyboardButton(text="📊 Статус плеера"),
            KeyboardButton(text="🎵 Сейчас играет"),
            KeyboardButton(text="📋 Мои плейлисты")
        ],
        [
            KeyboardButton(text="⏮️ Предыдущий трек"),
            KeyboardButton(text="⏯️ Play/Pause"),
            KeyboardButton(text="⏭️ Следующий трек")
        ],
        [
            KeyboardButton(text="❌ Отключить плеер"),
            KeyboardButton(text="❓ Справка")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Если передан sync_code через диплинк (t.me/bot?start=CODE)
    args = message.text.split(" ", 1)
    if len(args) > 1:
        sync_code = args[1]
        logger.info(f"[Server Sync] Пользователь {message.from_user.id} привязал код: '{sync_code}'")
        await asyncio.to_thread(db_set_sync_code, message.from_user.id, sync_code)
        
        await message.answer(f"✅ Успешно синхронизировано с вашим приложением!\nВаш код синхронизации: `{sync_code}`.\n\nТеперь просто отправляйте мне музыкальные файлы, и они автоматически появятся в вашем десктопном плеере Audaci.", parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        logger.info(f"[Server Sync] Пользователь {message.from_user.id} прислал /start БЕЗ кода")
        await message.answer("Привет! Для синхронизации отсканируйте QR-код в вашем десктопном приложении Audaci.", reply_markup=get_main_keyboard())

@router.message(Command("status"))
@router.message(F.text == "📊 Статус плеера")
async def cmd_status(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if sync_code:
        # Проверяем WebSocket соединение
        is_online = sync_code in active_connections and len(active_connections[sync_code]) > 0
        if is_online:
            await message.answer(
                f"🟢 **Статус: Подключено (В сети)**\n\n"
                f"Ваше приложение Audaci запущено и готово принимать музыку.\n"
                f"Код синхронизации: `{sync_code}`.\n\n"
                f"Отправьте аудиофайл (mp3, flac, m4a, wav), и он сразу появится в плеере!",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                f"🔴 **Статус: Оффлайн (Не в сети)**\n\n"
                f"Десктопное приложение Audaci не запущено или нет интернет-соединения.\n"
                f"Код синхронизации: `{sync_code}`.\n\n"
                f"Ваши файлы сохранятся в очередь и автоматически загрузятся при запуске плеера.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
    else:
        await message.answer(
            "❌ **Статус: Не синхронизировано**\n\n"
            "Вы еще не связали свой Telegram-аккаунт с плеером Audaci. Отсканируйте QR-код в настройках приложения!",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

@router.message(Command("help"))
@router.message(F.text == "❓ Справка")
async def cmd_help(message: Message):
    await message.answer(
        "🎵 **Audaci Player Telegram Bot**\n\n"
        "Этот бот позволяет вам отправлять музыку прямо из Telegram в ваш плеер Audaci!\n\n"
        "**Как пользоваться:**\n"
        "1. Откройте Audaci на компьютере.\n"
        "2. Перейдите в настройки синхронизации и отсканируйте QR-код.\n"
        "3. Отправляйте боту любые файлы формата MP3, FLAC, M4A, WAV.\n\n"
        "**Команды:**\n"
        "/status — Проверить статус подключения\n"
        "/playlists — Список ваших плейлистов\n"
        "/nowplaying — Что сейчас играет\n"
        "/toggle — Воспроизведение / Пауза\n"
        "/next — Следующий трек\n"
        "/prev — Предыдущий трек\n"
        "/unlink — Отключить плеер от Telegram-бота\n"
        "/help — Справка",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "🔄 Как синхронизировать")
async def cmd_sync_info(message: Message):
    await message.answer(
        "🔄 **Как синхронизировать Audaci с Telegram:**\n\n"
        "1. Запустите Audaci на вашем компьютере.\n"
        "2. В правом нижнем углу нажмите кнопку шестеренки (настройки) или выберите раздел синхронизации.\n"
        "3. Нажмите кнопку генерации QR-кода.\n"
        "4. Отсканируйте QR-код камерой телефона или введите ссылку/код вручную через /start <код>.\n"
        "5. После этого вы сможете отправлять треки прямо сюда!",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@router.message(Command("playlists"))
@router.message(F.text == "📋 Мои плейлисты")
async def cmd_playlists(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if not sync_code:
        await message.answer("❌ Вы не синхронизированы с приложением. Пожалуйста, отсканируйте QR-код в Audaci.")
        return

    is_online = sync_code in active_connections and len(active_connections[sync_code]) > 0
    if not is_online:
        await message.answer("🔴 Плеер не в сети. Невозможно получить список плейлистов.")
        return

    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    pending_requests[req_id] = fut

    ws_client = active_connections[sync_code][0]
    try:
        await ws_client.send_json({
            "event": "get_playlists",
            "request_id": req_id
        })
        
        playlists = await asyncio.wait_for(fut, timeout=5.0)
        if not playlists:
            await message.answer("📋 **Ваши плейлисты в Audaci:**\n\nУ вас пока нет плейлистов.")
        else:
            text = "📋 **Ваши плейлисты в Audaci:**\n\n"
            for idx, pl in enumerate(playlists, 1):
                text += f"{idx}. {pl['name']} ({pl['track_count']} треков)\n"
            await message.answer(text)
    except asyncio.TimeoutError:
        await message.answer("⚠️ Не удалось получить ответ от плеера (таймаут).")
    except Exception as e:
        logger.error(f"Error requesting playlists: {e}")
        await message.answer("❌ Произошла ошибка при получении плейлистов.")
    finally:
        pending_requests.pop(req_id, None)

@router.message(Command("nowplaying"))
@router.message(F.text == "🎵 Сейчас играет")
async def cmd_nowplaying(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if not sync_code:
        await message.answer("❌ Вы не синхронизированы с приложением. Пожалуйста, отсканируйте QR-код в Audaci.")
        return

    is_online = sync_code in active_connections and len(active_connections[sync_code]) > 0
    if not is_online:
        await message.answer("🔴 Плеер не в сети. Невозможно получить информацию о треке.")
        return

    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    pending_requests[req_id] = fut

    ws_client = active_connections[sync_code][0]
    try:
        await ws_client.send_json({
            "event": "get_now_playing",
            "request_id": req_id
        })
        
        track = await asyncio.wait_for(fut, timeout=5.0)
        if not track or not track.get("title"):
            await message.answer("🎵 **Сейчас играет:**\n\nВоспроизведение остановлено.")
        else:
            artist = track.get("artist", "Неизвестный исполнитель")
            title = track.get("title", "Без названия")
            await message.answer(f"🎵 **Сейчас играет:**\n\n🎤 Исполнитель: {artist}\n💿 Трек: {title}")
    except asyncio.TimeoutError:
        await message.answer("⚠️ Не удалось получить ответ от плеера (таймаут).")
    except Exception as e:
        logger.error(f"Error requesting now playing: {e}")
        await message.answer("❌ Произошла ошибка при получении информации о треке.")
    finally:
        pending_requests.pop(req_id, None)

@router.message(Command("toggle"))
@router.message(F.text == "⏯️ Play/Pause")
async def cmd_control_toggle(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if not sync_code:
        await message.answer("❌ Вы не синхронизированы с приложением.")
        return

    is_online = sync_code in active_connections and len(active_connections[sync_code]) > 0
    if not is_online:
        await message.answer("🔴 Плеер не в сети. Невозможно отправить команду.")
        return

    ws_client = active_connections[sync_code][0]
    try:
        await ws_client.send_json({
            "event": "control",
            "action": "toggle"
        })
        await message.answer("⏯️ Команда отправлена: Воспроизведение / Пауза")
    except Exception as e:
        logger.error(f"Error sending control event: {e}")
        await message.answer("❌ Ошибка при отправке команды.")

@router.message(Command("next"))
@router.message(F.text == "⏭️ Следующий трек")
async def cmd_control_next(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if not sync_code:
        await message.answer("❌ Вы не синхронизированы с приложением.")
        return

    is_online = sync_code in active_connections and len(active_connections[sync_code]) > 0
    if not is_online:
        await message.answer("🔴 Плеер не в сети. Невозможно отправить команду.")
        return

    ws_client = active_connections[sync_code][0]
    try:
        await ws_client.send_json({
            "event": "control",
            "action": "next"
        })
        await message.answer("⏭️ Команда отправлена: Следующий трек")
    except Exception as e:
        logger.error(f"Error sending control event: {e}")
        await message.answer("❌ Ошибка при отправке команды.")

@router.message(Command("prev"))
@router.message(F.text == "⏮️ Предыдущий трек")
async def cmd_control_prev(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if not sync_code:
        await message.answer("❌ Вы не синхронизированы с приложением.")
        return

    is_online = sync_code in active_connections and len(active_connections[sync_code]) > 0
    if not is_online:
        await message.answer("🔴 Плеер не в сети. Невозможно отправить команду.")
        return

    ws_client = active_connections[sync_code][0]
    try:
        await ws_client.send_json({
            "event": "control",
            "action": "prev"
        })
        await message.answer("⏮️ Команда отправлена: Предыдущий трек")
    except Exception as e:
        logger.error(f"Error sending control event: {e}")
        await message.answer("❌ Ошибка при отправке команды.")

@router.message(Command("unlink"))
@router.message(F.text == "❌ Отключить плеер")
async def cmd_unlink(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if sync_code:
        # Уведомляем клиента через WebSocket перед разрывом
        await notify_unlink(sync_code)
        
        await asyncio.to_thread(db_delete_user, user_id)
        await message.answer(
            "❌ **Плеер успешно отключен**\n\n"
            "Ваш Telegram-аккаунт больше не связан с плеером Audaci. Чтобы восстановить связь, отсканируйте QR-код снова.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "❌ Вы не синхронизированы с плеером.",
            reply_markup=get_main_keyboard()
        )

def embed_cover_in_audio(file_path: Path, image_bytes: bytes):
    """Внедряет обложку (байты) в аудиофайл различных форматов с помощью mutagen."""
    from mutagen import File
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, error
    from mutagen.mp4 import MP4, MP4Cover
    
    suffix = file_path.suffix.lower()
    if suffix == ".mp3":
        try:
            audio = MP3(file_path, ID3=ID3)
            try:
                audio.add_tags()
            except error:
                pass
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc=u'Cover',
                    data=image_bytes
                )
            )
            audio.save()
        except Exception as e:
            logger.error(f"Error embedding MP3 cover: {e}")
    elif suffix in [".m4a", ".mp4"]:
        try:
            audio = MP4(file_path)
            if audio.tags is None:
                audio.add_tags()
            audio.tags["covr"] = [MP4Cover(image_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
        except Exception as e:
            logger.error(f"Error embedding M4A cover: {e}")
    else:
        # Try generic mutagen File approach if supported
        try:
            audio = File(file_path)
            if audio is not None and hasattr(audio, "pictures"):
                from mutagen.flac import Picture
                picture = Picture()
                picture.data = image_bytes
                picture.type = 3
                picture.mime = "image/jpeg"
                picture.desc = "Cover"
                audio.clear_pictures()
                audio.add_picture(picture)
                audio.save()
        except Exception as e:
            logger.error(f"Error embedding generic cover: {e}")

@router.message(F.audio)
async def handle_audio(message: Message):
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if not sync_code:
        await message.answer("❌ Вы не синхронизированы с приложением. Пожалуйста, отсканируйте QR-код в Audaci.")
        return

    audio = message.audio
    logger.info(f"[Server Sync] Получен аудиофайл от {user_id} для кода '{sync_code}': {audio.file_name or 'без имени'}")
    
    if audio.file_size > 20 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой (> 20 МБ).")
        return

    file_name = audio.file_name or f"audio_{audio.file_id}.mp3"
    await message.answer(f"📥 Сохраняю `{file_name}` на сервер...")

    save_path = DATA_DIR / f"{uuid.uuid4().hex}_{file_name}"
    try:
        file_info = await bot.get_file(audio.file_id)
        await bot.download_file(file_info.file_path, destination=str(save_path))
        
        # Попытка скачать и встроить обложку из Telegram (thumbnail)
        if audio.thumbnail:
            try:
                import tempfile
                thumb_file = await bot.get_file(audio.thumbnail.file_id)
                with tempfile.NamedTemporaryFile(delete=False) as tmp_thumb:
                    tmp_thumb_path = Path(tmp_thumb.name)
                
                await bot.download_file(thumb_file.file_path, destination=str(tmp_thumb_path))
                if tmp_thumb_path.exists():
                    with open(tmp_thumb_path, "rb") as f:
                        thumb_bytes = f.read()
                    
                    embed_cover_in_audio(save_path, thumb_bytes)
                    logger.info(f"[Server Sync] Successfully embedded Telegram thumbnail into {save_path}")
                    
                    try:
                        tmp_thumb_path.unlink()
                    except Exception:
                        pass
            except Exception as thumb_err:
                logger.error(f"[Server Sync] Error processing Telegram audio thumbnail: {thumb_err}")
        
        await asyncio.to_thread(db_add_to_queue, sync_code, str(save_path))
        queue_count = await asyncio.to_thread(db_get_queue_count, sync_code)
        
        logger.info(f"[Server Sync] Трек успешно сохранен на сервере: {save_path}. В очереди '{sync_code}' теперь {queue_count} треков.")
        await message.answer("✅ Трек загружен! Ваше десктопное приложение Audaci скачает его в течение нескольких секунд.")
        
        # Уведомляем клиента через WebSocket
        await notify_clients(sync_code)
    except Exception as e:
        logger.error(f"Error downloading: {e}")
        await message.answer("❌ Произошла ошибка при загрузке трека.")


@router.message()
async def handle_unauthorized(message: Message):
    """Глобальный обработчик для всех остальных сообщений от неавторизованных пользователей."""
    user_id = message.from_user.id
    sync_code = await asyncio.to_thread(db_get_sync_code, user_id)
    if not sync_code:
        await message.answer("❌ Сначала отсканируйте QR-код в десктопном приложении Audaci или отправьте мне код синхронизации через `/start <КОД>`, чтобы я мог работать с вашими файлами.")
    else:
        await message.answer("Я ожидаю музыкальные файлы (mp3, flac, wav, m4a). Пожалуйста, отправьте трек как аудиофайл.")


# --- FASTAPI SERVER ---

class SyncStatus(BaseModel):
    tracks_available: int

@app.websocket("/api/ws/sync/{sync_code}")
async def websocket_endpoint(websocket: WebSocket, sync_code: str):
    await websocket.accept()
    if sync_code not in active_connections:
        active_connections[sync_code] = []
    active_connections[sync_code].append(websocket)
    try:
        # При подключении сразу проверяем, есть ли треки
        count = await asyncio.to_thread(db_get_queue_count, sync_code)
        if count > 0:
            await websocket.send_json({"event": "new_track"})
            
        while True:
            # Ожидаем сообщений (пинг) от клиента, чтобы держать соединение открытым
            msg = await websocket.receive_text()
            import json
            try:
                data = json.loads(msg)
                event = data.get("event")
                if event == "playlists_data":
                    req_id = data.get("request_id")
                    if req_id in pending_requests:
                        pending_requests[req_id].set_result(data.get("playlists", []))
                elif event == "now_playing_data":
                    req_id = data.get("request_id")
                    if req_id in pending_requests:
                        pending_requests[req_id].set_result(data.get("track", {}))
            except Exception as e:
                logger.error(f"Error parsing incoming client websocket message: {e}")
    except Exception as e:
        logger.info(f"WebSocket disconnected or error for code '{sync_code}': {e}")
    finally:
        if sync_code in active_connections:
            if websocket in active_connections[sync_code]:
                active_connections[sync_code].remove(websocket)
            if not active_connections[sync_code]:
                del active_connections[sync_code]

@app.get("/api/sync/{sync_code}")
async def check_sync(sync_code: str):
    """Проверка наличия новых треков для клиента. Оставлено для обратной совместимости, лучше использовать WS."""
    count = await asyncio.to_thread(db_get_queue_count, sync_code)
    return {"tracks_available": count}

@app.get("/api/sync/{sync_code}/download")
async def download_track(sync_code: str, background_tasks: BackgroundTasks):
    """Скачивание одного трека (FIFO). После скачивания трек удаляется из очереди и с диска."""
    logger.info(f"[API] Запрос скачивания для sync_code='{sync_code}'")
    
    track_path_str = await asyncio.to_thread(db_pop_from_queue, sync_code)
    if not track_path_str:
        logger.warning(f"[API] Скачивание отклонено: нет треков в очереди для '{sync_code}'")
        raise HTTPException(status_code=404, detail="No tracks available")
    
    track_path = Path(track_path_str)
    
    # Функция для удаления файла с диска после его отправки
    def cleanup_file(path: Path):
        try:
            if path.exists():
                path.unlink()
                logger.info(f"File {path} deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
            
    background_tasks.add_task(cleanup_file, track_path)
    
    # Оригинальное имя файла можно вытащить (мы добавляли uuid в начало)
    original_name = track_path.name.split("_", 1)[-1]
    
    return FileResponse(path=track_path, filename=original_name)

@app.get("/api/bot/info")
async def get_bot_info():
    try:
        me = await bot.get_me()
        return {"username": me.username}
    except Exception as e:
        logger.error(f"Error fetching bot info: {e}")
        return {"username": "AudaciBot"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
