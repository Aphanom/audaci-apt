import os
import hashlib
import platform
import subprocess
from mutagen import File
from pathlib import Path

# Создаем скрытую папку для постоянного хранения обложек (чтобы не пропадали!)
# Rule 5: Оперируй путями исключительно через модуль pathlib
COVERS_DIR = Path(os.getenv("AUDACI_DB_DIR", str(Path.home() / ".audaci"))) / "covers"

def ensure_covers_dir():
    global COVERS_DIR
    try:
        COVERS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Ошибка при создании директории {COVERS_DIR}: {e}")
        # Грациозный фолбэк в рабочую область проекта при ограничениях прав macOS (TCC)
        fallback_dir = Path(__file__).resolve().parent.parent / "covers"
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
            COVERS_DIR = fallback_dir
            print(f"[meta] Использование фолбэк-директории для обложек: {COVERS_DIR}")
        except Exception as fe:
            print(f"Критическая ошибка фолбэка обложек: {fe}")

ensure_covers_dir()

# Оставляем кэш в памяти для скорости, чтобы плеер не читал файлы дважды за сессию
_cover_cache: dict[str, str | None] = {}

def save_cover_optimized(image_bytes):
    """
    Берет байты картинки, делает хэш и сохраняет только уникальные обложки.
    """
    if not image_bytes:
        return None

    # Генерируем уникальный MD5 хэш из самих байтов картинки
    image_hash = hashlib.md5(image_bytes).hexdigest()
    cover_path = COVERS_DIR / f"{image_hash}.jpg"

    # Магия оптимизации: если файл с таким хэшем УЖЕ ЕСТЬ, мы его НЕ перезаписываем!
    if not cover_path.exists():
        try:
            with open(cover_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            print(f"Ошибка сохранения обложки: {e}")
            return None

    return str(cover_path)


def get_track_info(file_path: str | Path) -> dict:
    file_path = Path(file_path).resolve()
    audio = File(file_path)

    info: dict = {
        "title":       file_path.stem,
        "artist":      "Неизвестный исполнитель",
        "album":       "",
        "cover_path":  None,
        "duration_ms": 0,
    }

    if audio is None:
        return info

    # ── 1. Длительность ─────────────────────────────────────────────────────
    try:
        if hasattr(audio, "info") and hasattr(audio.info, "length"):
            info["duration_ms"] = int(audio.info.length * 1000)
    except Exception:
        pass

    # ── 2. Текстовые теги ────────────────────────────────────────────────────
    try:
        if file_path.suffix.lower() == ".mp3":
            if "TIT2" in audio: info["title"]  = str(audio["TIT2"])
            if "TPE1" in audio: info["artist"] = str(audio["TPE1"])
            if "TALB" in audio: info["album"]  = str(audio["TALB"])
        else:
            tags = {k.lower(): v for k, v in audio.items()}
            if "title"  in tags: info["title"]  = tags["title"][0]
            if "artist" in tags: info["artist"] = tags["artist"][0]
            if "album"  in tags: info["album"]  = tags["album"][0]
    except Exception as e:
        print(f"[meta] tag error: {e}")

    # ── 3. Обложка ──────────────────────────────────────────────────────────
    str_path = str(file_path)
    
    # Если мы уже доставали обложку для этого трека в текущей сессии — отдаем сразу
    if str_path in _cover_cache:
        info["cover_path"] = _cover_cache[str_path]
        return info

    cover_data: bytes | None = None
    try:
        # 1. Попытка прочитать обложку как MP3 (ID3 APIC)
        if audio.tags and hasattr(audio.tags, "items"):
            apic = [v for k, v in audio.tags.items() if k.startswith("APIC")]
            if apic:
                cover_data = apic[0].data
        
        # 2. Попытка прочитать обложку как MP4/M4A (covr)
        if not cover_data and audio.tags and "covr" in audio.tags:
            covr = audio.tags["covr"]
            if covr:
                item = covr[0] if isinstance(covr, list) else covr
                if isinstance(item, bytes):
                    cover_data = item
                elif hasattr(item, "data"):
                    cover_data = item.data
                else:
                    cover_data = bytes(item)
                    
        # 3. Попытка прочитать обложку для FLAC и др. (pictures)
        if not cover_data and hasattr(audio, "pictures") and audio.pictures:
            cover_data = audio.pictures[0].data
    except Exception as e:
        print(f"[meta] cover error: {e}")

    # === ВОТ ЗДЕСЬ МЫ ВСТАВИЛИ ОПТИМИЗАТОР ===
    cover_path = save_cover_optimized(cover_data)

    # Сохраняем в оперативную память и отдаем плееру
    _cover_cache[str_path] = cover_path
    info["cover_path"] = cover_path
    
    return info

def show_track_notification(title, artist, cover_path):
    """Кроссплатформенное системное уведомление"""
    current_os = platform.system()
    
    # Фолбэк, если обложки нет
    if not cover_path or not Path(cover_path).exists():
        cover_path = str(Path("assets/icon.png").resolve()) # Убедись, что путь верный
    else:
        cover_path = str(Path(cover_path).resolve())

    try:
        if current_os == "Linux":
            # Нативная команда для Astra Linux / Ubuntu
            subprocess.run([
                "notify-send",
                "-a", "Audaci",          # Имя приложения
                "-i", cover_path,        # Путь к картинке
                f"Сейчас играет: {title}",
                artist,
                "-t", "3000"             # Время показа (мс)
            ], check=False)
            
        elif current_os == "Windows":
            # Для Windows потребуется: pip install plyer
            from plyer import notification
            # Windows часто требует .ico вместо .jpg/.png для иконок уведомлений
            # Поэтому здесь иконка может не отображаться, если формат не поддерживается
            notification.notify(
                title=f"Audaci: {title}",
                message=artist,
                app_name="Audaci",
                timeout=3
            )
    except Exception as e:
        print(f"Ошибка вывода системного уведомления: {e}")