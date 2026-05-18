import re
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import (
    Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultAudio, ReplyKeyboardMarkup, KeyboardButton
)

import core.db as db # Импортируем БД для поиска

# Настройка логирования
logger = logging.getLogger(__name__)

# Используем Router для модульности
router = Router()

def sanitize_filename(filename: str) -> str:
    """Очищает имя файла от запрещенных символов и эмодзи."""
    # Удаляем расширение, чтобы очистить только имя
    path = Path(filename)
    name = path.stem
    ext = path.suffix

    # Оставляем только буквы, цифры, пробелы и базовые знаки
    # Заменяем все остальное на подчеркивание
    name = re.sub(r'[^\w\s\-\(\)\[\]]', '_', name)
    # Удаляем лишние пробелы и подчеркивания
    name = re.sub(r'[\s_]+', '_', name).strip('_')
    
    return f"{name}{ext}" if name else f"audio_{hash(filename)}{ext}"

class AudaciBot:
    def __init__(self, token: str, app_dir: Path, on_download_complete: Optional[Callable[[Path], Awaitable[None]]] = None):
        """
        Инициализация бота Audaci.
        :param token: Токен Telegram Bot API
        :param app_dir: Путь к папке приложения
        :param on_download_complete: Асинхронный колбэк, вызываемый после успешной загрузки
        """
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.dp.include_router(router)
        self.on_download_complete = on_download_complete
        
        # Rule 5: Сохраняем музыку в переданную папку
        self.telegram_dir = app_dir
        self.telegram_dir.mkdir(parents=True, exist_ok=True)

    async def start(self):
        """Запуск поллинга бота"""
        logger.info("Starting Telegram Bot polling...")
        # Передаем telegram_dir и колбэк в контекст хендлеров
        await self.dp.start_polling(
            self.bot, 
            telegram_dir=self.telegram_dir, 
            on_download_complete=self.on_download_complete,
            handle_signals=False
        )

@router.message(Command("start"))
async def send_welcome(message: Message):
    """Обработчик команды /start"""
    # Rule 3: Используем Web App для управления
    web_app_url = "https://google.com" # В будущем можно заменить на реальный URL
    
    # Главная клавиатура (Reply)
    kb_reply = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎵 Моя библиотека"), KeyboardButton(text="🔍 Поиск треков")]
    ], resize_keyboard=True)
    
    # Инлайн-кнопка для Web App
    kb_inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть пульт управления", web_app=WebAppInfo(url=web_app_url))]
    ])
    
    await message.answer(
        f"Привет, {message.from_user.full_name}! 👋\n\n"
        "Я — твой музыкальный ассистент Audaci.\n"
        "• Отправь мне аудиофайл, и он появится в плеере.\n"
        "• Нажми 'Моя библиотека', чтобы увидеть свои треки.\n"
        "• Введи @имя_бота в любом чате для поиска.",
        reply_markup=kb_reply
    )
    await message.answer("Также ты можешь открыть пульт управления:", reply_markup=kb_inline)

@router.message(F.text == "🎵 Моя библиотека")
@router.message(Command("tracks"))
async def list_tracks(message: Message):
    """Список последних 10 треков"""
    tracks = db.search_tracks("")[:10]
    if not tracks:
        await message.answer("Библиотека пока пуста. Отправь мне первый трек!")
        return
        
    text = "🎵 **Ваши последние треки:**\n\n"
    for i, t in enumerate(tracks, 1):
        text += f"{i}. {t['artist']} — {t['title']}\n"
    
    text += "\n_Чтобы найти конкретный трек, используй поиск._"
    await message.answer(text, parse_mode="Markdown")

@router.inline_query()
async def inline_search(inline_query: InlineQuery):
    """Поиск треков через инлайн-режим"""
    query = inline_query.query
    results = db.search_tracks(query)[:20] # Берем топ-20
    
    import urllib.parse
    items = []
    for t in results:
        encoded_path = urllib.parse.quote(t['file_path'])
        items.append(InlineQueryResultAudio(
            id=str(hash(t['file_path'])),
            audio_url=f"http://your_server_ip:8000/api/stream/{encoded_path}", # Это будет работать только если есть проброс
            title=t['title'],
            performer=t['artist']
        ))
    
    # Если проброса нет, можно просто выводить текстом (но тогда это не AudioResult)
    # Для простоты пока оставим так, или можно использовать ArticleResult
    
    await inline_query.answer(items, cache_time=300)

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
async def handle_audio(message: Message, bot: Bot, telegram_dir: Path, on_download_complete: Optional[Callable[[Path], Awaitable[None]]] = None):
    """Обработчик входящих аудиофайлов"""
    audio = message.audio
    if not audio:
        return

    # Проверка лимитов Bot API (20 МБ)
    if audio.file_size > 20 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой (> 20 МБ).")
        return

    # Санитизация имени файла
    raw_name = audio.file_name or f"audio_{audio.file_id}.mp3"
    file_name = sanitize_filename(raw_name)
    
    await message.answer(f"📥 Загружаю: `{file_name}`...", parse_mode="Markdown")
    
    save_path = telegram_dir / file_name
    
    try:
        file = await bot.get_file(audio.file_id)
        # Гарантируем, что путь — это строка для Bot API
        await bot.download_file(file.file_path, destination=str(save_path))
        
        if not save_path.exists():
            raise FileNotFoundError(f"Файл не найден после загрузки: {save_path}")

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
                    logger.info(f"Successfully embedded Telegram thumbnail into {save_path}")
                    
                    try:
                        tmp_thumb_path.unlink()
                    except Exception:
                        pass
            except Exception as thumb_err:
                logger.error(f"Error processing Telegram audio thumbnail: {thumb_err}")

        # Вызываем колбэк для синхронизации с плеером
        if on_download_complete:
            await on_download_complete(save_path)
            
        await message.answer(
            f"✅ Готово! Трек добавлен в библиотеку.\n"
            f"Путь: `{save_path}`", 
            parse_mode="Markdown"
        )
        logger.info(f"Saved and synced audio: {save_path}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при загрузке: {e}")
        logger.error(f"Error downloading audio: {e}")

if __name__ == "__main__":
    # Тестовый запуск (требует токен в переменной окружения)
    import os
    import asyncio
    token = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
    app_path = Path.home() / ".audaci"
    
    bot_instance = AudaciBot(token, app_path)
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(bot_instance.start())

