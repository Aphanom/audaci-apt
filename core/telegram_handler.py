import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТОКЕН БОТА (В идеале вынести в .env)
API_TOKEN = "8469253940:AAEWF4SZx0PnytzOnyCcAmSmRxFHRsNo6Go"

class AudaciBot:
    def __init__(self, music_dir: str):
        self.bot = Bot(token=API_TOKEN)
        self.dp = Dispatcher()
        # Создаем отдельную папку для музыки из Telegram
        self.telegram_dir = os.path.join(music_dir, "Telegram Music")
        os.makedirs(self.telegram_dir, exist_ok=True)
        self.music_dir = music_dir
        
        # Регистрируем обработчики
        self.dp.message.register(self.send_welcome, Command("start"))
        self.dp.message.register(self.handle_audio, lambda message: message.audio is not None)

    async def send_welcome(self, message: Message):
        """Обработчик команды /start"""
        # Ссылка на Web App (пока заглушка, позже заменим на ngrok URL)
        web_app_url = "https://google.com" # Временно
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Открыть плеер", web_app=WebAppInfo(url=web_app_url))]
        ])
        
        await message.answer(
            f"Привет, {message.from_user.full_name}! 👋\n\n"
            "Я — твой музыкальный ассистент Audaci.\n"
            "Отправь мне аудиофайл, и он появится в твоем плеере.\n"
            "Нажми кнопку ниже, чтобы открыть мобильную версию плеера.",
            reply_markup=kb
        )

    async def handle_audio(self, message: Message):
        """Обработчик входящих аудиофайлов"""
        audio = message.audio
        file_id = audio.file_id
        file_name = audio.file_name or f"audio_{file_id}.mp3"
        
        await message.answer(f"📥 Получаю файл: {file_name}...")
        
        # Сохраняем в специальную папку Telegram Music
        save_path = os.path.join(self.telegram_dir, file_name)
        
        try:
            file = await self.bot.get_file(file_id)
            await self.bot.download_file(file.file_path, save_path)
            
            await message.answer(f"✅ Файл сохранен! Он скоро появится в твоей медиатеке.\nПуть: `{save_path}`", parse_mode="Markdown")
            logger.info(f"Saved audio to {save_path}")
        except Exception as e:
            await message.answer(f"❌ Ошибка при загрузке: {e}")
            logger.error(f"Error downloading audio: {e}")

    async def start(self):
        """Запуск бота без перехвата сигналов (для работы в потоке)"""
        logger.info("Starting Telegram Bot...")
        # handle_signals=False критически важен для запуска в подпотоке!
        await self.dp.start_polling(self.bot, handle_signals=False)

if __name__ == "__main__":
    # Тестовый запуск
    music_folder = os.path.expanduser("~/Music")
    bot_instance = AudaciBot(music_folder)
    asyncio.run(bot_instance.start())
