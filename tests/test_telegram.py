import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from core.telegram_handler import sanitize_filename, handle_audio

def test_sanitize_filename():
    """Тест функции очистки имен файлов."""
    test_cases = [
        ("🔥 Awesome Track! (Remix) @2024.mp3", "Awesome_Track_(Remix)_2024.mp3"),
        ("Track with emojis 🎸🎹.flac", "Track_with_emojis.flac"),
        ("   Spaces   and...Dots.wav", "Spaces_and_Dots.wav"),
        ("Already_Clean.mp3", "Already_Clean.mp3"),
        ("!@#$%^&*.mp3", "audio_"), # Fallback case
    ]
    
    for input_name, expected_substring in test_cases:
        sanitized = sanitize_filename(input_name)
        assert expected_substring in sanitized
        # Убеждаемся, что нет спецсимволов (кроме точки расширения)
        # Наш регэксп заменяет всё кроме \w\s\-\(\)\[\]
        assert not any(c in sanitized for c in '!@#$%^&*')

@pytest.mark.asyncio
async def test_handle_audio_logic():
    """Тест логики обработки аудио (через моки)."""
    # 1. Готовим моки
    bot = AsyncMock()
    message = MagicMock()
    message.answer = AsyncMock() # КРИТИЧНО: должен быть AsyncMock
    message.audio.file_id = "test_file_id"
    message.audio.file_name = "test track 🔥.mp3"
    message.audio.file_size = 1024
    message.audio.thumbnail = None
    
    telegram_dir = Path("/tmp/audaci_test")
    telegram_dir.mkdir(parents=True, exist_ok=True)
    
    callback = AsyncMock()
    
    # Мокаем bot.get_file
    mock_file = MagicMock()
    mock_file.file_path = "path/on/server/test.mp3"
    bot.get_file.return_value = mock_file
    
    # 2. Вызываем хендлер
    with patch("pathlib.Path.exists", return_value=True):
        await handle_audio(message, bot, telegram_dir, on_download_complete=callback)
    
    # 3. Проверки
    # Проверяем, что имя файла очищено (пробелы заменены на подчеркивания, эмодзи удалены)
    expected_save_path = str(telegram_dir / "test_track.mp3")
    bot.download_file.assert_called_once_with(mock_file.file_path, destination=expected_save_path)
    
    # Проверяем, что колбэк синхронизации был вызван
    callback.assert_called_once()
    
    # Очистка
    import shutil
    shutil.rmtree(telegram_dir)


@pytest.mark.asyncio
async def test_handle_audio_with_thumbnail_logic():
    """Тест логики обработки аудио с обложкой (thumbnail)."""
    bot = AsyncMock()
    message = MagicMock()
    message.answer = AsyncMock()
    message.audio.file_id = "test_file_id"
    message.audio.file_name = "test track 🔥.mp3"
    message.audio.file_size = 1024
    
    # Задаем mock-thumbnail
    mock_thumb = MagicMock()
    mock_thumb.file_id = "thumb_file_id"
    message.audio.thumbnail = mock_thumb
    
    telegram_dir = Path("/tmp/audaci_test_thumb")
    telegram_dir.mkdir(parents=True, exist_ok=True)
    
    callback = AsyncMock()
    
    mock_audio_file = MagicMock()
    mock_audio_file.file_path = "path/on/server/test.mp3"
    
    mock_thumb_file = MagicMock()
    mock_thumb_file.file_path = "path/on/server/thumb.jpg"
    
    # Настраиваем bot.get_file, чтобы возвращал разные файлы
    bot.get_file.side_effect = [mock_audio_file, mock_thumb_file]
    
    # Мокаем embed_cover_in_audio и pathlib.Path.exists
    with patch("pathlib.Path.exists", return_value=True), \
         patch("core.telegram_handler.embed_cover_in_audio") as mock_embed:
        
        # Переопределяем встроенный open, чтобы чтение байтов из временного файла не падало
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_file_handle = MagicMock()
            mock_file_handle.read.return_value = b"thumb_data_bytes"
            mock_open.return_value.__enter__.return_value = mock_file_handle
            
            await handle_audio(message, bot, telegram_dir, on_download_complete=callback)
            
            # Проверяем, что обложка была внедрена
            mock_embed.assert_called_once_with(telegram_dir / "test_track.mp3", b"thumb_data_bytes")
            
    # Очистка
    import shutil
    shutil.rmtree(telegram_dir)


def test_embed_cover_in_audio_mp3():
    """Тест встраивания обложки в MP3 (через мок)."""
    from core.telegram_handler import embed_cover_in_audio
    from unittest.mock import MagicMock, patch
    
    mock_mp3 = MagicMock()
    mock_mp3.tags = MagicMock()
    
    with patch("mutagen.mp3.MP3", return_value=mock_mp3) as mock_class:
        embed_cover_in_audio(Path("test.mp3"), b"fake_bytes")
        mock_class.assert_called_once()
        mock_mp3.tags.add.assert_called_once()
        mock_mp3.save.assert_called_once()


def test_embed_cover_in_audio_m4a():
    """Тест встраивания обложки в M4A (через мок)."""
    from core.telegram_handler import embed_cover_in_audio
    from unittest.mock import MagicMock, patch
    
    mock_mp4 = MagicMock()
    mock_mp4.tags = {}
    
    with patch("mutagen.mp4.MP4", return_value=mock_mp4) as mock_class:
        embed_cover_in_audio(Path("test.m4a"), b"fake_bytes")
        mock_class.assert_called_once()
        assert "covr" in mock_mp4.tags
        mock_mp4.save.assert_called_once()


def test_get_track_info_extracts_covr():
    """Тест извлечения обложки M4A covr из тегов (через мок)."""
    from core.metadata_handler import get_track_info
    from unittest.mock import MagicMock, patch
    
    mock_audio = MagicMock()
    # Имитируем covr тег
    mock_covr_item = MagicMock()
    mock_covr_item.data = b"extracted_m4a_cover_bytes"
    mock_audio.tags = {
        "covr": [mock_covr_item]
    }
    
    with patch("core.metadata_handler.File", return_value=mock_audio), \
         patch("core.metadata_handler.save_cover_optimized", return_value="/path/to/extracted.jpg") as mock_save:
        info = get_track_info("test.m4a")
        assert info["cover_path"] == "/path/to/extracted.jpg"
        mock_save.assert_called_once_with(b"extracted_m4a_cover_bytes")

