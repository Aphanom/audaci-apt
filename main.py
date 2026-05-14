import sys
import traceback

def global_crash_handler(exctype, value, tb):
    with open("audaci_crash.log", "w", encoding="utf-8") as f:
        traceback.print_exception(exctype, value, tb, file=f)
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_crash_handler

import os
import sys
import platform
import threading
import asyncio
import time
import random
import json
import io

# Исправляем кодировку консоли для Windows, чтобы эмодзи не вызывали UnicodeEncodeError
if platform.system() == "Windows":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass

# --- 1. УМНОЕ ОПРЕДЕЛЕНИЕ ПУТЕЙ (Для работы и в venv, и в бинарнике) ---
if getattr(sys, 'frozen', False):
    # Если запущено как скомпилированный .exe/.bin
    base_dir = sys._MEIPASS
else:
    # Если запущен просто скрипт python main.py
    base_dir = os.path.dirname(os.path.abspath(__file__))

assets_dir = os.path.join(base_dir, "assets")
icon_path = os.path.join(assets_dir, "icon.png")

# --- 2. СИСТЕМНЫЕ НАСТРОЙКИ ---
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

if IS_LINUX:
    # Настройки исключительно для Astra Linux (Fly WM)
    os.environ["FLET_RENDER_VIA_GPU"] = "false"
    os.environ["GTK_THEME"] = "Adwaita:dark"              
    os.environ["GTK_OVERLAY_SCROLLING"] = "0"
    os.environ["PYSTRAY_BACKEND"] = "appindicator"

    # Настройки VLC
    os.environ["VLC_PLUGIN_PATH"] = "/usr/lib/x86_64-linux-gnu/vlc/plugins"
    os.environ["PYTHON_VLC_LIB_PATH"] = "/usr/lib/x86_64-linux-gnu/libvlc.so.5"

    # Глушим лишние логи GTK в консоли
    if not os.environ.get("DEBUG_GTK"):
        sys.stderr = open(os.devnull, 'w')
    
    try:
        from ctypes import cdll
        # Прямое обращение к системной библиотеке GTK
        lib_gtk = cdll.LoadLibrary('libgtk-3.so.0')
        # Принудительно устанавливаем иконку по умолчанию для всех создаваемых окон
        lib_gtk.gtk_window_set_default_icon_from_file(icon_path.encode('utf-8'), None)
    except Exception:
        pass 
else:
    # На macOS и Windows GPU работает отлично
    os.environ["FLET_RENDER_VIA_GPU"] = "true"

os.environ["FLET_VIEW_TYPE"] = "window"
os.environ["FLET_ICON"] = icon_path

import flet as ft
import flet.canvas as cv
from PIL import Image
import vlc
from colorthief import ColorThief

from core.voice_cmd import VoiceController, VoiceCommandHandler
from core.metadata_handler import get_track_info
from core.player import AudioPlayer
import core.db as db
from core.lyrics_handler import fetch_synced_lyrics, parse_lrc
from core.nlu import analyze_intent
from theme import AppColors
from core.telegram_handler import AudaciBot
from core.api_server import start_api

class AppState:
    def __init__(self, settings):
        self.settings = settings
        self.is_focus_mode = False
        self.is_small_screen = False
        self.is_queue_active = False
        self.karaoke_mode = False
        self.is_app_light_mode = (settings.get("theme_mode") == "light")
        self.view_mode = "grid"
        self.current_track_path = None
        self.playlist = []
        self.repeat_mode = 0
        self.shuffle_mode = False
        self.current_lyrics_index = -1
        self.is_typing = False

if getattr(sys, 'frozen', False):
    # Если запущено как бинарник, берем временную папку распаковки
    base_dir = sys._MEIPASS
else:
    # Если обычный скрипт, берем текущую папку
    base_dir = os.path.dirname(os.path.abspath(__file__))

assets_dir = os.path.join(base_dir, "assets")
icon_path = os.path.join(assets_dir, "icon.png")

global_page = None
tray_icon = None

# 2. БЕЗОПАСНЫЙ ТРЕЙ
def show_window(icon=None, item=None):
    if global_page:
        try:
            global_page.window.visible = True
            global_page.window.minimized = False
            global_page.update()

            async def force_focus():
                await asyncio.sleep(0.2)
                await global_page.window.to_front()
                global_page.update()

            global_page.run_task(force_focus)
        except Exception as e:
            print(f"[Audaci Tray] Ошибка развертывания: {e}")

def quit_app_full(icon=None, item=None):
    if tray_icon is not None:
        tray_icon.stop()
    if global_page:
        global_page.run_task(global_page.window.destroy)

# Оборачиваем в try-except, чтобы отсутствие зависимостей не роняло плеер
if not IS_MAC:
    try:
        import pystray
        if os.path.exists(icon_path):
            tray_img = Image.open(icon_path)
            tray_icon = pystray.Icon(
                "Audaci", 
                tray_img, 
                "Audaci Player", 
                menu=pystray.Menu(
                    pystray.MenuItem("Развернуть", show_window, default=True),
                    pystray.MenuItem("Выход", quit_app_full)
                )
            )
            # В некоторых ОС нужно запустить иконку, но pystray на Windows/Linux часто работает и так при создании объекта
            # Если нужно будет явно запускать - добавим tray_icon.run_detached()
    except Exception as e:
        print(f"[Audaci Tray] Ошибка инициализации трея: {e}")

def main(page: ft.Page):
    global global_page
    global_page = page

    page.title = "Audaci"
    if IS_WINDOWS:
        page.window.icon = "icon.ico"
    elif IS_MAC:
        page.window.icon = "icon.icns"
    else:
        page.window.icon = "icon.png"
    page.window.prevent_close = True 
    page.update()

    def handle_window_events(e):
        import os

        if e.type == ft.WindowEventType.FOCUS:
            try:
                page.run_task(play_button.focus)
            except:
                pass
            return
        
        # ПРОВЕРКА: Ловим событие по ТИПУ (как показал лог) или по данным
        if e.type == ft.WindowEventType.CLOSE or e.data == "close":
            # Сразу берем настройку из словаря
            is_tray_enabled = settings.get("close_to_tray", True)
            print(f"[Audaci] Поймано событие CLOSE. Трей: {is_tray_enabled}")

            if is_tray_enabled and tray_icon is not None:
                try:
                    page.window.visible = False
                    page.update()
                    tray_icon.visible = True
                    print("[Audaci] Окно скрыто, иконка в трее.")
                except Exception as err:
                    print(f"[Audaci Error] Ошибка скрытия в трей: {err}")
            else:
                print("[Audaci] Трей недоступен или отключен. Завершаем работу...")
                quit_app_full()


    # Привязываем только один, но правильный обработчик
    page.window.on_event = handle_window_events

    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#121212"
    page.theme = ft.Theme(color_scheme_seed="#1DB954")

    
    # ФИКС 1: Жесткие рамки (Адаптировано для Astra Linux)
    def apply_window_constraints():
        import time
        time.sleep(0.5) # Ждем, пока Fly WM отрисует окно
        page.window.min_width = 850
        page.window.min_height = 600
        page.window.width = 1050
        page.window.height = 700
        try:
            page.update()
        except: pass

    
    threading.Thread(target=apply_window_constraints, daemon=True).start()
    
    page.padding = 0 
    page.spacing = 0


    # Отслеживание размера окна для адаптивности
    is_small_screen = [False]
    is_app_light_mode = [False]
    is_typing = [False]


    # --- НАСТРОЙКИ ---
    SETTINGS_FILE = os.path.expanduser("~/.audaci_settings.json")
    PLAYLISTS_FILE = os.path.expanduser("~/.audaci_playlists.json")

    is_first_run = not os.path.exists(SETTINGS_FILE)
    
    def load_settings():
        """Загружает настройки из файла."""
        default_music_path = get_default_music_path()
        default_settings = {
            "music_folders": [default_music_path],
            "theme_mode": "dark",
            "accent_color": "#1DB954",
            "audio_device": "default",
            "equalizer_enabled": False,
            "equalizer_presets": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "crossfade_duration": 0,
            "normalize_volume": False,
            "voice_trigger": "астра",
            "voice_feedback": True,
            "close_to_tray": True,
        }
        
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
            except Exception as e:
                print(f"Ошибка загрузки настроек: {e}")
        
        return default_settings
    
    def save_settings():
        """Сохраняет настройки в файл."""
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
    
    def save_playlists():
        """Сохраняет плейлисты в JSON файл."""
        try:
            with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_playlists, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения плейлистов: {e}")
    
    def load_playlists():
        """Загружает плейлисты из JSON файла."""
        if os.path.exists(PLAYLISTS_FILE):
            try:
                with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки плейлистов: {e}")
        return {}
    
    # Кроссплатформенное определение папки с музыкой
    def get_default_music_path():
        import platform
        system = platform.system()
        
        if system == "Windows":
            possible_paths = [
                os.path.join(os.path.expanduser("~"), "Music"),
                os.path.join(os.path.expanduser("~"), "Музыка"),
                "C:\\Users\\Public\\Music",
            ]
        elif system == "Darwin":  # macOS
            possible_paths = [
                os.path.expanduser("~/Music"),
                os.path.expanduser("~/Музыка"),
            ]
        else:  # Linux
            possible_paths = [
                os.path.expanduser("~/Music"),
                os.path.expanduser("~/Музыка"),
                os.path.expanduser("~/music"),
            ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return os.path.expanduser("~")
    
    # Загружаем настройки и сразу устанавливаем theme_mode
    settings = load_settings()
    state = AppState(settings)
    if settings["theme_mode"] == "dark":
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#000000"
    elif settings["theme_mode"] == "light":
        page.theme_mode = ft.ThemeMode.LIGHT
        page.bgcolor = "#FFFFFF"
    else:
        page.theme_mode = ft.ThemeMode.SYSTEM
    
    current_playlist_for_cover = [None]

    # --- ИНИЦИАЛИЗАЦИЯ ---
    audio = AudioPlayer(normalize=settings.get("normalize_volume", False)) 
    audio.apply_eq_settings(settings["equalizer_presets"], settings["equalizer_enabled"])
    user_playlists = load_playlists()
    db.init_db()

    async def pick_files_async(dialog_title, allowed_extensions=None):
        """Открывает диалог выбора файла и возвращает список файлов."""
        return await ft.FilePicker().pick_files(
            dialog_title=dialog_title,
            allowed_extensions=allowed_extensions
        )

    async def get_directory_path_async(dialog_title):
        """Открывает диалог выбора папки и возвращает путь."""
        return await ft.FilePicker().get_directory_path(dialog_title=dialog_title)

    async def scan_library_async():
        from core.tag_fetcher import fetch_mood_from_web_async
        audio_exts = (".mp3", ".flac", ".wav", ".m4a")
        
        new_tracks_count = 0
        print("[Scan] Начинаю асинхронное сканирование медиатеки...")
        
        scan_tasks = []
        for folder in state.settings.get("music_folders", []):
            if not os.path.exists(folder): continue
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(audio_exts):
                        full_path = os.path.join(root, file)
                        if not db.get_track(full_path):
                            scan_tasks.append((full_path, folder, file))
        
        async def process_single_track(full_path, folder, file_name):
            nonlocal new_tracks_count
            try:
                info = get_track_info(full_path)
                print(f"🌍 Загружаю теги (async): {file_name}...")
                mood = await fetch_mood_from_web_async(info['artist'], info['title'])
                
                if not mood:
                    if "BULLY" in full_path or "bully" in info.get('album', '').upper():
                        mood = "experimental, dark, art pop"
                    elif "Yandhi" in full_path:
                        mood = "chill, futuristic, spiritual"
                
                info['mood_tags'] = mood
                db.add_track(full_path, folder, info)
                new_tracks_count += 1
            except Exception as e:
                print(f"❌ Ошибка {file_name}: {e}")

        # Обрабатываем пачками по 5 треков, чтобы не спамить API
        for i in range(0, len(scan_tasks), 5):
            batch = scan_tasks[i:i+5]
            await asyncio.gather(*(process_single_track(fp, fd, f) for fp, fd, f in batch))
            
        if IS_WINDOWS: print(f"[Success] Done! Added tracks: {new_tracks_count}")
        else: print(f"✅ Готово! Добавлено треков: {new_tracks_count}")

    # === МГНОВЕННЫЙ СКАНЕР ПАПОК (WATCHDOG) ===
    def start_watchdogs():
        if IS_WINDOWS: print("[Watchdog] Active: monitoring folders...")
        else: print("[Watchdog] Watchdog активен: следим за папками...")
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class MusicHandler(FileSystemEventHandler):
                async def process_async(self, file_path):
                    if not os.path.exists(file_path): return
                    audio_exts = (".mp3", ".flac", ".wav", ".m4a")
                    if file_path.lower().endswith(audio_exts):
                        if not db.get_track(file_path):
                            await asyncio.sleep(0.5) 
                            
                            try:
                                from core.tag_fetcher import fetch_mood_from_web_async
                                info = get_track_info(file_path)
                                mood = await fetch_mood_from_web_async(info.get('artist', ''), info.get('title', ''))
                                
                                if not mood:
                                    path_upper = file_path.upper()
                                    if "BULLY" in path_upper or "BULLY" in info.get('album', '').upper():
                                        mood = "experimental, dark, art pop"
                                    elif "YANDHI" in path_upper:
                                        mood = "chill, futuristic, spiritual"
                                    elif "JUICE" in path_upper or "PARTY NEVER ENDS" in path_upper:
                                        mood = "sad, energetic, pop rap, melodic"
                                    else:
                                        mood = "chill, energetic, pop"
                                
                                info['mood_tags'] = mood
                                folder = os.path.dirname(file_path)
                                db.add_track(file_path, folder, info)
                                
                                if current_folder_text.value in ["Главная", os.path.basename(folder)]:
                                    load_folder(music_path_ref[0], add_to_history=False)
                                show_snackbar(f"🎵 Добавлен новый трек: {os.path.basename(file_path)}")
                                
                            except Exception as e:
                                print(f"❌ Ошибка watchdog для {file_path}: {e}")

                def on_created(self, event):
                    if not event.is_directory:
                        page.run_task(self.process_async, event.src_path)

                def on_moved(self, event):
                    if not event.is_directory:
                        page.run_task(self.process_async, event.dest_path)

            observer = Observer()
            handler = MusicHandler()
            
            # Вешаем уши на все папки, которые юзер добавил в настройках
            for folder in settings.get("music_folders", []):
                if os.path.exists(folder):
                    observer.schedule(handler, folder, recursive=True)
            
            observer.start()
            print("[Watchdog] Watchdog запущен: слушаю папки на лету...")
            
        except ImportError:
            print("[Error] Ошибка: библиотека watchdog не установлена!")

    # Сначала прогоняем старый быстрый скан 
    page.run_task(scan_library_async)
    
    # А затем врубаем вечного наблюдателя за папками
    threading.Thread(target=start_watchdogs, daemon=True).start()

    # === НАТИВНЫЕ КРОССПЛАТФОРМЕННЫЕ УВЕДОМЛЕНИЯ ===
    def notify_system(title, artist, cover_path=None):
        import platform
        import subprocess
        import os
        from PIL import Image
        
        system = platform.system()
        safe_title = str(title).replace('"', '\\"')
        safe_artist = str(artist).replace('"', '\\"')
        
        try:
            if system == "Darwin":
                apple_script = f'display notification "{safe_artist}" with title "Audaci" subtitle "{safe_title}"'
                subprocess.Popen(["osascript", "-e", apple_script])
            elif system == "Linux":
                icon_arg = None
                
                if cover_path and isinstance(cover_path, str):
                    abs_path = os.path.abspath(os.path.expanduser(cover_path))
                    if os.path.exists(abs_path):
                        try:
                            img = Image.open(abs_path)
                            img.thumbnail((128, 128))
                            tmp_icon = "/tmp/audaci_notif.png"
                            img.save(tmp_icon, format="PNG")
                            os.chmod(tmp_icon, 0o777)
                            icon_arg = tmp_icon
                        except Exception as img_err:
                            print(f"Ошибка PIL: {img_err}")
                
                if not icon_arg:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    icon_arg = os.path.join(base_dir, "assets", "icon.png")
                
                cmd = ["notify-send", "-a", "Audaci", f"{safe_title}", safe_artist]
                if icon_arg and os.path.exists(icon_arg):
                    # ФИКС 2 ИЗ АНАЛИЗА: Используем Image Hints (протокол file://) вместо -i
                    cmd.append(f"--hint=string:image-path:{icon_arg}")
                
                subprocess.Popen(cmd)
        except Exception as e:
            print(f"Ошибка системного уведомления: {e}")

    music_path_ref = [settings["music_folders"][0] if settings["music_folders"] else get_default_music_path()]
    path_history = [music_path_ref[0]]
    
    def get_music_path():
        return music_path_ref[0]

    # --- PLAYLIST STATE ---
    current_view_tracks = []
    playlist      = []       
    original_playlist = []
    current_index = [-1]     
    active_track_path = [None] 
    repeat_mode   = [0]      
    shuffle_mode  = [False]
    _track_ended  = [False]  
    view_mode     = ["grid"] 
    previous_view_mode = ["grid"]

    # Элементы интерфейса
    current_track_img = ft.Image(src="https://via.placeholder.com/60", width=56, height=56, border_radius=4)
    current_track_title = ft.Text("", size=14, weight="bold", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    current_track_artist = ft.Text("", size=12, color="grey", overflow=ft.TextOverflow.ELLIPSIS)
    
    # === ИНТЕРФЕЙС КАРАОКЕ (FLET 0.84.0 АРХИТЕКТУРА) ===
    current_lyrics_data = [] 
    current_lyrics_index = [-1]
    karaoke_mode = [False]

    LYRICS_WIDTH = 480
    QUEUE_WIDTH = 350

    # ИСПРАВЛЕНИЕ: Жесткое ограничение ширины текста (STRETCH) + привязка к левому краю (START)
    lyrics_list_view = ft.Column(
        expand=True, spacing=15, scroll=ft.ScrollMode.HIDDEN
    )
    # Жёсткая ширина предотвращает схлопывание при анимации контейнера
    focus_lyrics_list_view = ft.Column(
        width=LYRICS_WIDTH, expand=True, spacing=15, scroll=ft.ScrollMode.HIDDEN
    )
    
    lyrics_container = ft.Container(
        content=lyrics_list_view, 
        visible=False, expand=True, border_radius=10, 
        padding=ft.Padding(40, 20, 40, 20), # Flet 0.84.0 Syntax
        alignment=ft.Alignment(-1.0, -1.0),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER, colors=["#1e1e1e", "#121212"],
        ),
        animate=ft.Animation(1000, ft.AnimationCurve.EASE_OUT)
    )
    
    def toggle_karaoke(_=None):
        if not audio.current_track_path:
            show_snackbar("Сначала включите трек")
            return
            
        karaoke_mode[0] = not karaoke_mode[0]
        
        if is_focus_mode[0]:
            async def animate_karaoke_focus():
                # --- ВЫТЕСНЯЕМ ОЧЕРЕДЬ ТОЛЬКО НА МАЛЕНЬКИХ ЭКРАНАХ ---
                if is_small_screen[0] and karaoke_mode[0] and is_queue_active[0]:
                    is_queue_active[0] = False
                    # Сначала плавно гасим прозрачность
                    focus_queue_container.opacity = 0
                    focus_row.update()
                    try: 
                        focus_queue_btn.icon_color = "white70"
                        focus_queue_btn.update()
                    except: pass
                    # Ждем, пока исчезнет, и только потом выключаем visible
                    await asyncio.sleep(0.4) 
                    focus_queue_container.visible = False
                    focus_row.update()
                # ----------------------------------------------------
                
                # --- АНИМАЦИЯ САМОЙ ПАНЕЛИ ТЕКСТА ---
                if karaoke_mode[0]:
                    # Включаем блок, но делаем прозрачным
                    focus_lyrics_container.visible = True
                    focus_lyrics_container.opacity = 0 
                    focus_row.update()
                    await asyncio.sleep(0.05) # Даем Flet мгновение на отрисовку
                    # Плавно проявляем
                    focus_lyrics_container.opacity = 1
                    focus_row.update()
                else:
                    # Сначала плавно гасим
                    focus_lyrics_container.opacity = 0
                    focus_row.update()
                    await asyncio.sleep(0.4) # Ждем окончания анимации
                    # Выключаем физически
                    focus_lyrics_container.visible = False
                    focus_row.update()
                
                try: on_resize(None) # принудительно пересчитываем обложку!
                except: pass
            
            # Запускаем нашу плавную анимацию
            page.run_task(animate_karaoke_focus)
        else:
            track_grid.visible = not karaoke_mode[0] and view_mode[0] == "grid"
            track_list.visible = not karaoke_mode[0] and view_mode[0] == "list"
            lyrics_container.visible = karaoke_mode[0]
            
            track_grid.expand = not karaoke_mode[0]
            track_list.expand = not karaoke_mode[0]
            
        is_light = is_app_light_mode[0]
        karaoke_btn.icon_color = "#1DB954" if karaoke_mode[0] else ("#000000" if is_light else "grey")
        try: 
            focus_karaoke_btn.icon_color = "#1DB954" if karaoke_mode[0] else "white70"
            focus_karaoke_btn.update()
        except NameError: pass
        page.update()

        if karaoke_mode[0] and current_lyrics_index[0] != -1:
            async def sync_karaoke_scroll():
                # УВЕЛИЧЕННАЯ ПАУЗА: Ждем 0.5с, чтобы панель успела выехать анимацией!
                await asyncio.sleep(0.5) 
                try:
                    target_key = f"foc_{current_lyrics_index[0]}" if is_focus_mode[0] else f"norm_{current_lyrics_index[0]}"
                    view = focus_lyrics_list_view if is_focus_mode[0] else lyrics_list_view
                    
                    # ПРОВЕРКА СОСТОЯНИЯ ПЕРЕД СКРОЛЛОМ
                    can_scroll = False
                    if is_focus_mode[0] and focus_view.visible and focus_lyrics_container.visible:
                        can_scroll = True
                    elif not is_focus_mode[0] and lyrics_container.visible:
                        can_scroll = True
                        
                    if can_scroll and view.page:
                        print(f"[Audaci Debug] Синхронизация текста при открытии панели: {target_key}")
                        await view.scroll_to(scroll_key=target_key, duration=300)
                except Exception as e:
                    if "Timeout waiting" not in str(e):
                        print(f"[Audaci Error] Ошибка синхронизации текста: {e}")
            page.run_task(sync_karaoke_scroll)

    def disable_karaoke():
        if karaoke_mode[0]:
            karaoke_mode[0] = False
            lyrics_container.visible = False
            focus_lyrics_container.visible = False
            track_grid.visible = (view_mode[0] == "grid")
            track_list.visible = (view_mode[0] == "list")
            
            # --- ВОТ ЭТИ ДВЕ СТРОЧКИ СПАСУТ ТВОЙ СКРОЛЛ ---
            track_grid.expand = True
            track_list.expand = True
            # ----------------------------------------------
            
            is_light = is_app_light_mode[0]
            karaoke_btn.icon_color = "#000000" if is_light else "grey"
            try:
                karaoke_btn.update()
            except: pass

    karaoke_btn = ft.IconButton(
        icon=ft.Icons.MIC_EXTERNAL_ON, icon_size=20, icon_color="grey", tooltip="Режим караоке", on_click=toggle_karaoke
    )
    # ==========================

    big_track_img = ft.Image(src="https://via.placeholder.com/300", width=250, height=250, border_radius=15, fit="cover")
    big_track_title = ft.Text("Выберите трек", size=20, weight="bold", text_align="center")
    big_track_artist = ft.Text("Артист", size=16, color="grey", text_align="center")

    big_track_album = ft.Text("", size=14, color="grey", text_align="center")
    big_track_dur = ft.Text("", size=12, color="grey", text_align="center")
    
    right_metadata_col = ft.Column([
        ft.Divider(height=10, color="transparent"),
        big_track_album,
        big_track_dur,
    ], horizontal_alignment="center", visible=True)

    is_queue_active = [False]
    
    
    right_queue_list = ft.Column(expand=True, spacing=5, scroll=ft.ScrollMode.ALWAYS)
    focus_queue_list = ft.Column(expand=True, spacing=5, scroll=ft.ScrollMode.ALWAYS)
    
    right_queue_col = ft.Column([
        ft.Divider(height=10, color="white10"),
        ft.Text("ОЧЕРЕДЬ", size=11, weight="bold", color="grey"),
        ft.Container(content=right_queue_list, expand=True) 
    ], visible=False, expand=True)

    user_is_dragging = threading.Event()

    def fmt_time(ms: int) -> str:
        if ms < 0: return "0:00"
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"

    def fmt_dur(ms: int) -> str:
        if ms <= 0: return "--:--"
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"

    # ========== ДИАЛОГИ ==========
    def show_track_info(file_path):
        info = get_track_info(file_path)
        dlg = ft.AlertDialog(
            title=ft.Text("Информация о треке"),
            content=ft.Column([
                ft.Text(f"Название: {info.get('title', 'Неизвестно')}", size=14),
                ft.Text(f"Исполнитель: {info.get('artist', 'Неизвестен')}", size=14),
                ft.Text(f"Альбом: {info.get('album', 'Неизвестен')}", size=14),
                ft.Text(f"Длительность: {fmt_dur(info.get('duration_ms', 0))}", size=14),
                ft.Text(f"Путь: {file_path}", size=12, color="grey", selectable=True),
            ], tight=True, spacing=8),
            actions=[ft.TextButton("Закрыть", on_click=lambda _: close_dialog(dlg))],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def close_dialog(dlg):
        dlg.open = False
        page.update()
        
        # Аккуратно удаляем закрытый диалог из памяти
        if dlg in page.overlay:
            page.overlay.remove(dlg)
            page.update()

    def add_to_playlist(file_path):
        playlist_items = []
        for pl_name in sorted(user_playlists.keys()):
            playlist_items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.PLAYLIST_PLAY),
                    title=ft.Text(pl_name),
                    on_click=lambda _, name=pl_name, fp=file_path: add_track_to_playlist(name, fp)
                )
            )
        
        playlist_items.append(ft.Divider())
        playlist_items.append(
            ft.ListTile(
                leading=ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=ft.Colors.GREEN),
                title=ft.Text("Создать новый плейлист", weight="bold"),
                on_click=lambda _: show_create_playlist_dialog(file_path)
            )
        )

        if not user_playlists:
            content = ft.Column([
                ft.Text("У вас пока нет плейлистов", color="grey"),
                ft.Divider(),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=ft.Colors.GREEN),
                    title=ft.Text("Создать новый плейлист", weight="bold"),
                    on_click=lambda _: show_create_playlist_dialog(file_path)
                )
            ], tight=True, spacing=4)
        else:
            content = ft.Column(playlist_items, tight=True, spacing=4)

        dlg = ft.AlertDialog(
            title=ft.Text("Добавить в плейлист"),
            content=content,
            actions=[ft.TextButton("Отмена", on_click=lambda _: close_dialog(dlg))],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def add_track_to_playlist(playlist_name, file_path):
        if playlist_name in user_playlists:
            if file_path not in user_playlists[playlist_name]["tracks"]:
                user_playlists[playlist_name]["tracks"].append(file_path)
                show_snackbar(f"Трек добавлен в '{playlist_name}'")
                save_playlists()  
            else:
                show_snackbar(f"Трек уже есть в '{playlist_name}'")
        for overlay in page.overlay[:]:
            if isinstance(overlay, ft.AlertDialog) and overlay.open:
                overlay.open = False
        update_playlist_sidebar()
        page.update()

    async def show_ai_dj_dialog():
        import flet.canvas as cv
        import math
        import asyncio
        import random

        VIBE_MAP = {
            # Основные настроения
            "chill": "Релаксация 🧘",
            "dark": "Мрачная атмосфера 🦇",
            "energetic": "Энергично 🔥",
            "soul": "Мелодично 🎷",
            "happy": "Позитив ☀️",
            "sad": "Меланхолия 🌧️",
            "focus": "Концентрация 🧠",
            "romantic": "Романтично ❤️",
            "party": "Танцевальное 🪩",
            "nostalgic": "Ретро 📼",
            
            # Хип-хоп и R&B
            "hip-hop": "Хип-хоп 🎤",
            "trap": "Трэп 🏎️",
            "alternative rnb": "Альтернативный R&B 🌃",
            "rap": "Рэп 🗣️",
            "pop rap": "Поп-рэп 🧢",
            "cloud rap": "Клауд-рэп ☁️",
            "drill": "Дрилл 🥷",
            "rnb": "R&B 🥂",
            
            # Исполнители (в контексте стилистики)
            "kanye west": "Стиль Канье Уэста 🐻",
            "the weeknd": "Стиль The Weeknd 🌟",
            
            # Поп и Электроника
            "pop": "Поп-музыка 🍭",
            "k-pop": "К-поп 🫰",
            "electronic": "Электронная музыка 🎛️",
            "techno": "Техно 🕶️",
            "house": "Хаус 🏠",
            "dubstep": "Дабстеп 🤖",
            "phonk": "Фонк 🏎️💨",
            "synthwave": "Синтвейв 🌃",
            
            # Рок и Инструментальная музыка
            "rock": "Рок 🎸",
            "metal": "Метал 🤘",
            "punk": "Панк 🛹",
            "indie": "Инди 🏕️",
            "alternative": "Альтернатива 🎸",
            "jazz": "Джаз 🎷",
            "blues": "Блюз 🎸",
            "funk": "Фанк 🕺",
            "classical": "Классическая музыка Violin",
            "acoustic": "Акустика 🏕️",
            
            # Специфические категории
            "experimental": "Экспериментальная музыка 🧬",
            "banger": "Хиты 💥",
            "workout": "Для тренировок 🏋️",
            "lo-fi": "Лоу-фай ☕"
        }

        # --- АДАПТИВНАЯ ПАЛИТРА ---
        is_light = is_app_light_mode[0]
        bg_color = "#FFFFFF" if is_light else "#1C1C1E"
        text_primary = "#000000" if is_light else "white"
        text_secondary = "#666666" if is_light else "grey"
        chip_bg = "#F0F0F0" if is_light else "white10"
        divider_color = "black12" if is_light else "white10"
        input_bg = "#F5F5F5" if is_light else "white10"

        # --- Логика закрытия с анимацией ---
        async def close_ai_dj_with_anim():
            is_animating[0] = False 
            dialog_box.scale = 0.9
            dialog_box.opacity = 0
            overlay_container.opacity = 0
            try:
                page.update()
                await asyncio.sleep(0.4) 
                if overlay_container in page.overlay:
                    page.overlay.remove(overlay_container)
                page.update()
            except: pass

        # --- Элементы интерфейса ---
        prompt_field = ft.TextField(
            label="Опишите настроение или артиста",
            hint_text="Например: 'грустное', 'веселое'...",
            autofocus=True, border_radius=15, 
            bgcolor=input_bg, color=text_primary, cursor_color=text_primary,
            label_style=ft.TextStyle(color=text_secondary),
            hint_style=ft.TextStyle(color=text_secondary),
            border_color="#8A2BE2", focused_border_color="#1DB954",
            text_size=16,
            on_focus=lambda _: (is_typing.__setitem__(0, True)),
            on_blur=lambda _: (is_typing.__setitem__(0, False)),
        )

        wave_canvas = cv.Canvas(width=400, height=80, shapes=[])
        is_animating = [True]

        async def animate_wave_async():
            t = 0
            while is_animating[0]:
                try:
                    new_elements = [cv.Path.MoveTo(0, 40)]
                    for x in range(0, 401, 10):
                        y = 40 + 20 * math.sin(x * 0.05 + t) * math.cos(t * 0.5)
                        new_elements.append(cv.Path.LineTo(x, y))
                    glow = ft.Paint(color="#408A2BE2", stroke_width=8, style=ft.PaintingStyle.STROKE, stroke_cap=ft.StrokeCap.ROUND)
                    core = ft.Paint(color="#8A2BE2", stroke_width=3, style=ft.PaintingStyle.STROKE, stroke_cap=ft.StrokeCap.ROUND)
                    
                    wave_canvas.shapes = [
                        cv.Path(elements=new_elements, paint=glow), 
                        cv.Path(elements=new_elements, paint=core)
                    ]
                    wave_canvas.update()
                    t += 0.15 
                    await asyncio.sleep(0.03) 
                except: break

        vibes_grid = ft.Row(wrap=True, spacing=12, run_spacing=12, alignment=ft.MainAxisAlignment.CENTER)
        
        vibes_section = ft.Container(
            content=ft.Column([
                ft.Divider(height=20, color=divider_color),
                ft.Text("Ваше персональное настроение:", size=14, color=text_secondary, weight="bold"),
                vibes_grid
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO), # <--- ВКЛЮЧИЛИ СКРОЛЛ ЗДЕСЬ
            height=0, opacity=0, clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate_size=ft.Animation(700, ft.AnimationCurve.EASE_OUT_QUINT),
            animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
        )

        async def toggle_vibes(_):
            if vibes_section.height == 0:
                vibes_grid.controls.clear()
                for key, label in VIBE_MAP.items():
                    tracks = db.get_tracks_by_vibe(key)
                    if tracks:
                        def make_click(k):
                            async def click_vibe(_):
                                await close_ai_dj_with_anim()
                                playlist.clear()
                                playlist.extend(db.get_tracks_by_vibe(k))
                                random.shuffle(playlist)
                                select_track(playlist[0])
                                show_snackbar(f"✨ Настроение '{VIBE_MAP[k]}' активировано!")
                            return click_vibe

                        # Динамический hover для кнопок (чтобы белый текст был на фиолетовом фоне)
                        def create_hover_handler(def_bg, def_text):
                            def on_hover(e):
                                is_hover = str(e.data).lower() == "true"
                                e.control.bgcolor = "#8A2BE2" if is_hover else def_bg
                                e.control.content.color = "white" if is_hover else def_text
                                e.control.update()
                            return on_hover

                        vibes_grid.controls.append(
                            ft.Container(
                                content=ft.Text(f"{label} ({len(tracks)})", size=14, weight="bold", color=text_primary),
                                padding=ft.Padding(18, 10, 18, 10),
                                bgcolor=chip_bg, border_radius=20,
                                on_click=make_click(key),
                                on_hover=create_hover_handler(chip_bg, text_primary)
                            )
                        )
                vibes_section.height = 320
                vibes_section.opacity = 1
            else:
                vibes_section.height = 0
                vibes_section.opacity = 0
            vibes_section.update()

        async def submit_click():
            query = prompt_field.value.strip().lower()
            if not query: 
                return
            
            await close_ai_dj_with_anim()

            # --- ОБНОВЛЕННЫЙ СЛОВАРЬ (Русский запрос -> Английские теги) ---
            TAG_TRANSLATOR = {
                # Состояния и настроения
                "релаксация": "chill", "спокойствие": "chill", "отдых": "relax", "чилл": "chill",
                "меланхолия": "sad", "грусть": "sad", "печаль": "melancholic", "тоска": "depressing",
                "энергично": "energetic", "драйв": "energetic", "динамика": "energetic", "кач": "energetic",
                "позитив": "upbeat", "оптимизм": "happy", "радость": "happy",
                "концентрация": "focus", "учеба": "study", "работа": "background", "фокус": "study",
                "романтика": "romantic", "любовь": "love", "свидание": "sexy",
                "танцевальное": "dance", "танцы": "dance", "вечеринка": "party", "клуб": "club",
                "мрачная атмосфера": "dark", "нуар": "dark", "мрак": "dark",
                "лирика": "soul", "мелодично": "soul", "душевно": "soul",
                "ретро": "nostalgic", "ностальгия": "nostalgic", "старое": "nostalgic",
                
                # Жанры и стили
                "хип-хоп": "hip hop", "рэп": "rap", "реп": "rap", "трэп": "trap", "дрилл": "drill",
                "рок": "rock", "метал": "metal", "панк": "punk", "инди": "indie", "альтернатива": "alternative",
                "поп": "pop", "к-поп": "k-pop", "kpop": "k-pop",
                "электронная музыка": "electronic", "электроника": "electronic", "техно": "techno", 
                "хаус": "house", "дабстеп": "dubstep", "фонк": "phonk", "синтвейв": "synthwave",
                "джаз": "jazz", "блюз": "blues", "фанк": "funk", "рнб": "rnb",
                "классическая музыка": "classical", "классика": "classical", "акустика": "acoustic",
                
                # Специфические категории
                "экспериментальная": "experimental", "экспериментал": "experimental",
                "хиты": "banger", "бэнгер": "banger",
                "тренировка": "workout", "спорт": "workout", "активность": "workout",
                "лоу-фай": "lo-fi", "lofi": "lo-fi"
            }

            found_tracks = []
            is_vibe_query = False
            search_tags = []

            # 1. Ищем совпадения в нашем словаре (русский -> английский тег)
            for ru_word, eng_tag in TAG_TRANSLATOR.items():
                if ru_word in query:
                    search_tags.append(eng_tag)
                    is_vibe_query = True
            
            # 2. Если в словаре нет, но запрос на английском (например, юзер ввел "synthwave")
            # Считаем, что юзер ввел тег напрямую
            if not is_vibe_query and any(c.isascii() and c.isalpha() for c in query) and len(query.split()) <= 2:
                search_tags.append(query)
                is_vibe_query = True

            # --- ЛОГИКА ВКЛЮЧЕНИЯ ---
            if is_vibe_query:
                # Собираем треки по всем найденным тегам
                for tag in search_tags:
                    tracks = db.get_tracks_by_vibe(tag)
                    if tracks:
                        found_tracks.extend(tracks)
                
                found_tracks = list(set(found_tracks))
                tags_str = ", ".join(search_tags) # Собираем теги в строку

                if found_tracks:
                    import random
                    random.shuffle(found_tracks)
                    playlist.clear()
                    playlist.extend(found_tracks)
                    current_index[0] = 0
                    select_track(playlist[0])
                    # Показываем, по каким тегам мы нашли музыку
                    show_snackbar(f"✨ AI Диджей: настроение подобрано ({tags_str})! Треков: {len(found_tracks)}")
                    return 
                else:
                    # Показываем, что перевод сработал, но треков в БД нет
                    show_snackbar(f"😔 Треки по запросу '{query}' (теги: {tags_str}) пока не найдены")
                    return

            # Если это не настроение и не жанр, значит пользователь ищет артиста/трек
            trigger = settings.get("voice_trigger", "астра")
            if not any(w in query for w in ["включи", "поставь", "сыграй"]):
                query = f"включи {query}"
            handle_voice_command(f"{trigger} {query}")

        instructions = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=22, color="orange"),
                    ft.Text("Что умеет AI Диджей:", weight="bold", color=text_primary, size=18)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ft.Text("• Опишите настроение: 'грустное', 'энергичный фон' или 'чилл'.", size=15, color=text_secondary, text_align=ft.TextAlign.CENTER),
                ft.Text("• Найдите артиста: просто введите имя, например, 'Kanye West'.", size=15, color=text_secondary, text_align=ft.TextAlign.CENTER),
            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(0, 20, 0, 10)
        )

        # --- Основной бокс окна ---
        dialog_box = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME, color="#8A2BE2", size=36),
                    ft.Text("Audaci AI", size=34, weight="bold", color=text_primary)
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(height=20, color="transparent"),
                wave_canvas,
                prompt_field,
                instructions,
                vibes_section,
                ft.Container(height=10),
                ft.Row([
                    ft.TextButton("Мои настроения", icon=ft.Icons.WAVES_ROUNDED, icon_color="#FF4500", on_click=toggle_vibes),
                    ft.TextButton("Отмена", on_click=lambda _: page.run_task(close_ai_dj_with_anim)),
                    ft.FilledButton("Запустить", on_click=lambda _: page.run_task(submit_click), style=ft.ButtonStyle(bgcolor="#8A2BE2", color="white", padding=20))
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=15)
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=550,
            padding=40,
            bgcolor=bg_color, 
            border_radius=30,
            scale=0.8, 
            opacity=0, 
            animate_scale=ft.Animation(600, ft.AnimationCurve.EASE_OUT_BACK),
            animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        )

        # --- Оверлей-затемнитель на весь экран ---
        overlay_container = ft.Container(
            # 👇 Оборачиваем диалог в перехватчик жестов 👇
            content=ft.GestureDetector(
                content=dialog_box,
                on_tap=lambda _: None,                # Глотаем клик, чтобы он не пробил до фона
                mouse_cursor=ft.MouseCursor.BASIC   # Принудительно возвращаем курсор-стрелочку
            ),
            alignment=ft.Alignment(0, 0),
            bgcolor="#90000000", 
            opacity=0,
            expand=True,
            animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _: page.run_task(close_ai_dj_with_anim) # А вот фон уже закрывает окно
        )

        page.overlay.append(overlay_container)
        page.update()

        await asyncio.sleep(0.05)
        overlay_container.opacity = 1
        dialog_box.opacity = 1
        dialog_box.scale = 1.0
        page.update()

        page.run_task(animate_wave_async)
        
    def show_create_playlist_dialog(file_path_to_add=None):
        for overlay in page.overlay[:]:
            if isinstance(overlay, ft.AlertDialog) and overlay.open:
                overlay.open = False
        
        playlist_name_field = ft.TextField(
            label="Название плейлиста",
            autofocus=True,
            on_submit=lambda _: create_playlist(playlist_name_field.value, file_path_to_add),
            on_focus=lambda _: (is_typing.__setitem__(0, True)), # ИСПРАВЛЕНИЕ
            on_blur=lambda _: (is_typing.__setitem__(0, False)),  
        )
        
        dlg = ft.AlertDialog(
            title=ft.Text("Новый плейлист"),
            content=playlist_name_field,
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: close_dialog(dlg)),
                ft.TextButton("Создать", on_click=lambda _: create_playlist(playlist_name_field.value, file_path_to_add)),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def create_playlist(name, file_path_to_add=None):
        if not name or not name.strip():
            show_snackbar("Введите название плейлиста")
            return
        
        name = name.strip()
        if name in user_playlists:
            show_snackbar("Плейлист с таким именем уже существует")
            return
        
        user_playlists[name] = {"tracks": [], "cover": None}
        if file_path_to_add:
            user_playlists[name]["tracks"].append(file_path_to_add)
        
        for overlay in page.overlay[:]:
            if isinstance(overlay, ft.AlertDialog) and overlay.open:
                overlay.open = False
        
        show_snackbar(f"Плейлист '{name}' создан")
        save_playlists()  
        update_playlist_sidebar()
        page.update()

    def show_snackbar(message):
        print(f"🔔 [Уведомление]: {message}") 
        
        # Создаем стильную плашку
        snack = ft.SnackBar(
            content=ft.Text(message, color="white", weight="bold"), 
            bgcolor="#1DB954", 
            duration=3000
        )
        
        # Аккуратно удаляем старые уведомления, не перезаписывая само свойство
        for c in page.overlay[:]:
            if isinstance(c, ft.SnackBar):
                page.overlay.remove(c)
        
        # Добавляем новое уведомление и показываем
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def load_playlist(playlist_name):
        if playlist_name not in user_playlists: return
        
        current_folder_text.value = f"Плейлист: {playlist_name}"
        back_button.visible = False
        
        is_light = is_app_light_mode[0]
        sidebar.content.bgcolor = "#FFFFFF" if is_light else "#121212"
        playlists_container.bgcolor = "#FFFFFF" if is_light else "#121212"
        sidebar.update()
        
        track_grid.controls.clear()
        track_list.controls.clear()
        
        # Flet 0.84.0 Syntax fix for padding/border
        track_list.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text("#", width=32, color="grey", size=12, text_align="right"),
                    ft.Container(width=10),
                    ft.Container(width=44),
                    ft.Container(width=10),
                    ft.Text("Название", size=12, color="grey", expand=True),
                    ft.Text("Альбом", size=12, color="grey", width=160),
                    ft.Icon(ft.Icons.ACCESS_TIME_OUTLINED, size=14, color="grey"),
                    ft.Container(width=40),
                ], vertical_alignment="center"),
                padding=ft.Padding(10, 0, 10, 8),
                border=ft.Border(bottom=ft.BorderSide(1, "white10")),
            )
        )
        
        is_light = is_app_light_mode[0]
        track_bgcolor = "#FFFFFF" if is_light else "#181818"
        track_hover_color = "#F0F0F0" if is_light else "#1e1e1e"
        
        pending: list[dict] = []
        track_paths = user_playlists[playlist_name]["tracks"]
        
        for idx, full_path in enumerate(track_paths, 1):
            if not os.path.exists(full_path): continue
            
            ph = "https://via.placeholder.com/150"
            
            # СЕТКА
            g_img    = ft.Image(src=ph, border_radius=8, fit="cover", aspect_ratio=1)
            g_title  = ft.Text(os.path.basename(full_path), weight="bold", size=14, max_lines=1, overflow="ellipsis")
            g_artist = ft.Text("...", size=12, color="grey", max_lines=1)
            g_more   = ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey",
                items=[
                    ft.PopupMenuItem(content="Информация о треке", on_click=lambda _, fp=full_path: show_track_info(fp)),
                    ft.PopupMenuItem(content="Удалить из плейлиста", on_click=lambda _, fp=full_path, pln=playlist_name: remove_from_playlist(pln, fp)),
                ]
            )
            track_grid.controls.append(
                ft.Container(
                    content=ft.Column([
                        g_img,
                        ft.Row([
                            ft.Column([g_title, g_artist], spacing=2, expand=True),
                            g_more,
                        ], vertical_alignment="center"),
                    ], spacing=5),
                    bgcolor=track_bgcolor, padding=12, border_radius=10,
                    on_click=lambda e, p=full_path: select_track(p),
                    on_hover=lambda e: setattr(e.control, "bgcolor", track_hover_color if e.data == "true" else track_bgcolor) or e.control.update()
                )
            )
            
            # СПИСОК
            l_img    = ft.Image(src=ph, width=44, height=44, border_radius=4, fit="cover")
            l_title  = ft.Text(os.path.basename(full_path), weight="bold", size=14, max_lines=1, overflow="ellipsis")
            l_artist = ft.Text("...", size=12, color="grey", max_lines=1)
            l_album  = ft.Text("...", size=12, color="grey", width=160, max_lines=1, overflow="ellipsis")
            l_dur    = ft.Text("--:--", size=12, color="grey", width=42, text_align="right")
            l_more   = ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey",
                items=[
                    ft.PopupMenuItem(content="Информация о треке", on_click=lambda _, fp=full_path: show_track_info(fp)),
                    ft.PopupMenuItem(content="Удалить из плейлиста", on_click=lambda _, fp=full_path, pln=playlist_name: remove_from_playlist(pln, fp)),
                ]
            )
            track_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(str(idx), width=32, color="grey", size=12, text_align="right"),
                        ft.Container(width=10), l_img, ft.Container(width=10),
                        ft.Column([l_title, l_artist], spacing=2, expand=True),
                        l_album, l_dur, l_more,
                    ], vertical_alignment="center"),
                    padding=ft.Padding(10, 6, 10, 6),
                    border_radius=6,
                    on_click=lambda e, p=full_path: select_track(p),
                    on_hover=lambda e: setattr(e.control, "bgcolor", track_hover_color if e.data == "true" else track_bgcolor) or e.control.update(),
                )
            )
            
            pending.append({
                "fp": full_path,
                "g_img": g_img, "g_title": g_title, "g_artist": g_artist,
                "l_img": l_img, "l_title": l_title, "l_artist": l_artist,
                "l_album": l_album, "l_dur": l_dur,
            })
        
        current_view_tracks.clear()
        current_view_tracks.extend(d["fp"] for d in pending)
        
        page.update()
        
        def _load_meta():
            BATCH = 4
            for i, d in enumerate(pending):
                try:
                    info = get_track_info(d["fp"])
                    cover  = info.get("cover_path") or ph
                    title  = info.get("title",  os.path.basename(d["fp"]))
                    artist = info.get("artist", "Неизвестен")
                    album  = info.get("album",  "")
                    dur    = fmt_dur(info.get("duration_ms", 0))
                    
                    d["g_img"].src      = cover;  d["g_title"].value  = title
                    d["g_artist"].value = artist
                    d["l_img"].src      = cover;  d["l_title"].value  = title
                    d["l_artist"].value = artist
                    d["l_album"].value  = album
                    d["l_dur"].value    = dur
                except Exception as ex: print(f"[meta] {d['fp']}: {ex}")
                if (i + 1) % BATCH == 0 or i == len(pending) - 1: page.update()
        
        threading.Thread(target=_load_meta, daemon=True).start()

    def remove_from_playlist(playlist_name, file_path):
        if playlist_name in user_playlists and file_path in user_playlists[playlist_name]["tracks"]:
            user_playlists[playlist_name]["tracks"].remove(file_path)
            show_snackbar(f"Трек удалён из '{playlist_name}'")
            save_playlists() 
            load_playlist(playlist_name) 
            update_playlist_sidebar()

    def change_playlist_cover(playlist_name):
        for overlay in page.overlay[:]:
            if isinstance(overlay, ft.AlertDialog) and overlay.open: overlay.open = False
        
        cover_path_field = ft.TextField(label="Путь к файлу изображения", hint_text="/путь/к/изображению.jpg", autofocus=True, multiline=False, width=400)
        
        cover_options = []
        if playlist_name in user_playlists:
            tracks = user_playlists[playlist_name]["tracks"]
            seen_covers = set()
            for track_path in tracks[:10]: 
                if os.path.exists(track_path):
                    try:
                        info = get_track_info(track_path)
                        cover = info.get("cover_path")
                        if cover and cover not in seen_covers and os.path.exists(cover):
                            seen_covers.add(cover)
                            cover_options.append(
                                ft.Container(
                                    content=ft.Image(src=cover, width=80, height=80, border_radius=8, fit="cover"),
                                    on_click=lambda _, c=cover: apply_cover(playlist_name, c),
                                    border_radius=8, padding=2,
                                )
                            )
                    except: pass
        
        def apply_cover_from_field(_):
            path = cover_path_field.value.strip()
            if path and os.path.exists(path):
                if path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                    apply_cover(playlist_name, path)
                else: show_snackbar("Файл должен быть изображением (jpg, png, gif, bmp, webp)")
            else: show_snackbar("Файл не найден. Проверьте путь.")
        
        async def open_file_dialog(_):
            files = await pick_files_async(
                dialog_title="Выберите изображение для обложки",
                allowed_extensions=["jpg", "jpeg", "png", "gif", "bmp", "webp"]
            )
            if files and files[0]:
                cover_path_field.value = files[0].path
                cover_path_field.update()
        
        content_items = []
        if cover_options:
            content_items.append(ft.Text("Выберите обложку из треков:", size=14, weight="bold"))
            content_items.append(ft.Row(cover_options[:5], spacing=10, scroll=ft.ScrollMode.AUTO))
            content_items.append(ft.Divider())
        
        content_items.append(ft.Text("Или укажите путь к файлу:", size=14))
        content_items.append(
            ft.Row([
                cover_path_field,
                ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=open_file_dialog, tooltip="Выбрать файл")
            ], vertical_alignment="center")
        )
        
        dlg = ft.AlertDialog(
            title=ft.Text(f"Обложка для '{playlist_name}'"),
            content=ft.Column(content_items, tight=True, spacing=10, width=450),
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: close_dialog(dlg)),
                ft.TextButton("Применить", on_click=apply_cover_from_field),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()
    
    def apply_cover(playlist_name, cover_path):
        if playlist_name in user_playlists:
            user_playlists[playlist_name]["cover"] = cover_path
            save_playlists()
            update_playlist_sidebar()
            show_snackbar(f"Обложка для '{playlist_name}' обновлена")
            for overlay in page.overlay[:]:
                if isinstance(overlay, ft.AlertDialog) and overlay.open: overlay.open = False
            page.update()
    
    def delete_playlist(playlist_name):
        def confirm_delete(_):
            if playlist_name in user_playlists:
                del user_playlists[playlist_name]
                save_playlists()
                update_playlist_sidebar()
                show_snackbar(f"Плейлист '{playlist_name}' удалён")
                if current_folder_text.value == f"Плейлист: {playlist_name}":
                    load_folder(music_path_ref[0])
            close_dialog(dlg)
        
        dlg = ft.AlertDialog(
            title=ft.Text("Удалить плейлист?"),
            content=ft.Text(f"Вы уверены, что хотите удалить плейлист '{playlist_name}'?"),
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: close_dialog(dlg)),
                ft.TextButton("Удалить", on_click=confirm_delete),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def rename_playlist(old_name):
        for overlay in page.overlay[:]:
            if isinstance(overlay, ft.AlertDialog) and overlay.open:
                overlay.open = False

        new_name_field = ft.TextField(
            label="Новое название плейлиста",
            value=old_name,
            autofocus=True,
            on_focus=lambda _: (is_typing.__setitem__(0, True)),
            on_blur=lambda _: (is_typing.__setitem__(0, False)),
        )

        def confirm_rename(_):
            new_name = new_name_field.value.strip()
            if not new_name:
                show_snackbar("Название не может быть пустым")
                return
            if new_name == old_name:
                close_dialog(dlg)
                return
            if new_name in user_playlists:
                show_snackbar("Плейлист с таким именем уже существует")
                return

            # Переносим треки и обложку под новое имя
            user_playlists[new_name] = user_playlists.pop(old_name)
            save_playlists()
            update_playlist_sidebar()
            show_snackbar(f"Плейлист переименован в '{new_name}'")

            # Если мы прямо сейчас сидим в этом плейлисте — обновляем заголовок
            if current_folder_text.value == f"Плейлист: {old_name}":
                current_folder_text.value = f"Плейлист: {new_name}"
                page.update()

            close_dialog(dlg)

        new_name_field.on_submit = confirm_rename

        dlg = ft.AlertDialog(
            title=ft.Text("Переименовать плейлист"),
            content=new_name_field,
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: close_dialog(dlg)),
                ft.TextButton("Сохранить", on_click=confirm_rename),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def load_smart_collection(collection_data):
        disable_karaoke()
        track_paths = collection_data["func"]()
        if not track_paths:
            show_snackbar("Пока недостаточно данных для этой коллекции")
            return
            
        current_folder_text.value = collection_data["name"]
        
        # --- Обновляем иконку/обложку в заголовке контента ---
        back_button.visible = False
        show_home_view()
        
        is_light = is_app_light_mode[0]
        sidebar.content.bgcolor = "#FFFFFF" if is_light else "#121212"
        playlists_container.bgcolor = "#FFFFFF" if is_light else "#121212"
        sidebar.update()
        
        track_grid.controls.clear()
        track_list.controls.clear()
        
        # --- ШАПКА ДЛЯ СПИСКА ---
        track_list.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text("#", width=32, color="grey", size=12, text_align="right"),
                    ft.Container(width=10),
                    ft.Container(width=44),
                    ft.Container(width=10),
                    ft.Text("Название", size=12, color="grey", expand=True),
                    ft.Text("Альбом", size=12, color="grey", width=160),
                    ft.Icon(ft.Icons.ACCESS_TIME_OUTLINED, size=14, color="grey"),
                    ft.Container(width=40),
                ], vertical_alignment="center"),
                padding=ft.Padding(10, 0, 10, 8),
                border=ft.Border(bottom=ft.BorderSide(1, "white10")),
            )
        )
        
        track_bgcolor = "#FFFFFF" if is_light else "#181818"
        track_hover_color = "#F0F0F0" if is_light else "#1e1e1e"
        
        for idx, full_path in enumerate(track_paths, 1):
            if not os.path.exists(full_path): continue
            
            # Берем данные мгновенно из БД, так как трек из истории!
            db_info = db.get_track(full_path)
            if not db_info: continue
            
            display_title = db_info.get("title") or os.path.basename(full_path)
            display_artist = db_info.get("artist") or "Неизвестен"
            display_album = db_info.get("album") or "..."
            display_dur = fmt_dur(db_info.get("duration_ms", 0))
            display_cover = db_info.get("cover_path") or "https://via.placeholder.com/150"
            
            # --- СЕТКА ---
            g_img = ft.Image(src=display_cover, border_radius=8, fit="cover", aspect_ratio=1)
            g_title = ft.Text(display_title, weight="bold", size=14, max_lines=1, overflow="ellipsis", no_wrap=True)
            g_artist = ft.Text(display_artist, size=12, color="grey", max_lines=1, overflow="ellipsis", no_wrap=True)
            g_more = ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey",
                items=[
                    ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=full_path: add_to_playlist(fp)),
                    ft.PopupMenuItem(content="Информация о треке", on_click=lambda _, fp=full_path: show_track_info(fp)),
                ]
            )
            
            def on_db_grid_hover(e):
                e.control.bgcolor = track_hover_color if str(e.data).lower() == "true" else track_bgcolor
                e.control.update()
                
            track_grid.controls.append(
                ft.Container(
                    content=ft.Column([
                        g_img,
                        ft.Row([
                            ft.Column([g_title, g_artist], spacing=2, expand=True),
                            g_more,
                        ], vertical_alignment="center"),
                    ], spacing=5),
                    bgcolor=track_bgcolor, padding=12, border_radius=10,
                    on_click=lambda e, p=full_path: select_track(p),
                    on_hover=on_db_grid_hover
                )
            )
            
            # --- СПИСОК ---
            l_img = ft.Image(src=display_cover, width=44, height=44, border_radius=4, fit="cover")
            l_title = ft.Text(display_title, weight="bold", size=14, max_lines=1, overflow="ellipsis", no_wrap=True)
            l_artist = ft.Text(display_artist, size=12, color="grey", max_lines=1, overflow="ellipsis", no_wrap=True)
            l_album = ft.Text(display_album, size=12, color="grey", width=160, max_lines=1, overflow="ellipsis", no_wrap=True)
            l_dur = ft.Text(display_dur, size=12, color="grey", width=42, text_align="right")
            l_more = ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey",
                items=[
                    ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=full_path: add_to_playlist(fp)),
                    ft.PopupMenuItem(content="Информация о треке", on_click=lambda _, fp=full_path: show_track_info(fp)),
                ]
            )
            
            track_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(str(idx), width=32, color="grey", size=12, text_align="right"),
                        ft.Container(width=10), l_img, ft.Container(width=10),
                        ft.Column([l_title, l_artist], spacing=2, expand=True),
                        l_album, l_dur, l_more,
                    ], vertical_alignment="center"),
                    padding=ft.Padding(10, 6, 10, 6),
                    border_radius=6, bgcolor="transparent",
                    on_click=lambda e, p=full_path: select_track(p),
                    on_hover=lambda e: setattr(e.control, "bgcolor", track_hover_color if str(e.data).lower() == "true" else "transparent") or e.control.update(),
                )
            )

        current_view_tracks.clear()
        current_view_tracks.extend(track_paths)
        page.update()


    def update_playlist_sidebar():
        playlists_container.controls.clear()
        
        # --- СЕКЦИЯ УМНЫХ ПЛЕЙЛИСТОВ С ОБЛОЖКАМИ ---
        smart_collections = [
            {
                "name": "Топ 50 месяца", 
                "icon": ft.Icons.LOCAL_FIRE_DEPARTMENT, 
                "cover": "top_month.jpg", # Файл в папке assets
                "func": lambda: db.get_top_tracks(30)
            },
            {
                "name": "На повторе", 
                "icon": ft.Icons.REPEAT, 
                "cover": "on_repeat.jpg",
                "func": lambda: db.get_top_tracks(14, 20)
            },
            {
                "name": "Забытое", 
                "icon": ft.Icons.DIAMOND_OUTLINED, 
                "cover": "forgotten.jpg",
                "func": db.get_forgotten_treasures
            }
        ]
        
        for sc in smart_collections:
            # Проверяем физическое наличие файла в папке assets для логики переключения
            has_cover = os.path.exists(os.path.join(assets_dir, sc["cover"]))
            
            playlists_container.controls.append(
                ft.Container(
                    content=ft.Row([
                        # Если картинка есть — выводим её, если нет — старую иконку
                        ft.Image(src=sc["cover"], width=28, height=28, border_radius=5) if has_cover 
                        else ft.Icon(sc["icon"], size=18, color="#1DB954"),
                        
                        ft.Text(sc["name"], size=13, weight="bold", expand=True)
                    ], spacing=8),
                    padding=10,
                    border_radius=8,
                    on_click=lambda _, s=sc: load_smart_collection(s),
                    on_hover=lambda e: setattr(e.control, "bgcolor", "white10" if e.data == "true" else None) or e.control.update()
                )
            )

        playlists_container.controls.append(ft.Divider(color="white10", height=1))

        # --- ОБЫЧНЫЕ ПЛЕЙЛИСТЫ ---
        if user_playlists:
            from ui.playlist_menu import PlaylistMenu
            for pl_name in sorted(user_playlists.keys()):
                track_count = len(user_playlists[pl_name]["tracks"])
                cover = user_playlists[pl_name].get("cover")
                
                playlists_container.controls.append(
                    PlaylistMenu(
                        pl_name=pl_name,
                        track_count=track_count,
                        cover_path=cover,
                        on_load=load_playlist,
                        on_rename=rename_playlist,
                        on_cover=change_playlist_cover,
                        on_delete=delete_playlist
                    )
                )
        else:
            playlists_container.controls.append(ft.Container(padding=10, content=ft.Text("Плейлисты...", size=11, color="grey")))
        
        playlists_container.update()

    timer_current = ft.Text("0:00", size=12, color="grey", width=38, text_align="right")
    timer_total   = ft.Text("0:00", size=12, color="grey", width=38, text_align="left")
    
    progress_slider = ft.Slider(
        min=0, max=100, value=0, height=20, expand=True,
        inactive_color="white10", active_color="white",
    )

    async def update_slider():
        last_val      = -1
        last_cur_text = ""
        last_tot_text = ""
        
        # --- ФИКС ИЗ СТАТЬИ: Изолированная корутина скролла ---
        async def smooth_scroll(target_idx):
            try:
                # 1. Жесткая защита: скроллим только если караоке включено
                if not karaoke_mode[0]: 
                    return
                    
                # 2. Даем интерфейсу время отрисовать новые стили
                await asyncio.sleep(0.1) 
                
                target_key_norm = f"norm_{target_idx}"
                target_key_foc = f"foc_{target_idx}"
                
                # 3. МНОГО ПРОВЕРОК ВИДИМОСТИ:
                # Flet намертво вешает приложение (TimeoutException 10s), 
                # если попытаться проскроллить невидимый элемент
                if not is_focus_mode[0]:
                    # Проверяем Обычный режим
                    if lyrics_container.visible and lyrics_container.page:
                        print(f"[Audaci Debug] Скролл (Обычный) к: {target_key_norm}")
                        await lyrics_list_view.scroll_to(scroll_key=target_key_norm, duration=600, curve=ft.AnimationCurve.DECELERATE)
                else:
                    # Проверяем Режим Фокуса по свойству visible
                    if focus_view.visible and focus_lyrics_container.visible and focus_lyrics_list_view.page:
                        print(f"[Audaci Debug] Скролл (Фокус) к: {target_key_foc}")
                        await focus_lyrics_list_view.scroll_to(scroll_key=target_key_foc, duration=600, curve=ft.AnimationCurve.DECELERATE)
                        
            except Exception as e:
                # Глушим ошибки таймаута, чтобы они НЕ вешали Event Loop
                if "Timeout waiting" in str(e):
                    print("[Audaci Warning] Скролл пропущен: элемент скрыт или не отрендерился на экране.")
                elif "Session closed" not in str(e):
                    print(f"[Audaci Error] Ошибка скролла: {e}")
        # ------------------------------------------------------

        while True:
            await asyncio.sleep(0.1) 
            try:
                if not user_is_dragging.is_set():
                    cur_ms = audio.get_time()
                    tot_ms = audio.get_length()
                    pos    = audio.get_position()

                    changed = False

                    if cur_ms >= 0:
                        new_cur = fmt_time(cur_ms)
                        if new_cur != last_cur_text:
                            timer_current.value = new_cur
                            last_cur_text = new_cur
                            changed = True

                    if tot_ms > 0:
                        new_tot = fmt_time(tot_ms)
                        if new_tot != last_tot_text:
                            timer_total.value = new_tot
                            last_tot_text = new_tot
                            changed = True

                    new_val = int(pos * 100)
                    if new_val != last_val:
                        progress_slider.value = new_val
                        last_val = new_val
                        changed = True

                    # === КАРАОКЕ: СИНХРОНИЗАЦИЯ СТРОК ===
                    if karaoke_mode[0] and current_lyrics_data and cur_ms > 0:
                        new_idx = -1
                        for i, (ts, txt) in enumerate(current_lyrics_data):
                            if ts <= cur_ms + 300: new_idx = i
                            else: break
                                
                        if new_idx != current_lyrics_index[0] and new_idx != -1:
                            old_idx = current_lyrics_index[0]
                            current_lyrics_index[0] = new_idx
                            changed = True 
                            
                            try:
                                for view in (lyrics_list_view, focus_lyrics_list_view):
                                    actual_old = old_idx + 1
                                    actual_new = new_idx + 1

                                    # Тушим старую строчку
                                    if 1 <= actual_old < len(view.controls) - 1:
                                        c_old = view.controls[actual_old]
                                        if isinstance(c_old, ft.Container) and c_old.page: 
                                            c_old.content.color = ft.Colors.WHITE38
                                            c_old.opacity = 0.3
                                            c_old.scale = ft.Scale(scale=1.0, alignment=ft.Alignment(-1.0, 0.0))
                                            try: c_old.update()
                                            except: pass

                                    # Зажигаем новую строчку
                                    if 1 <= actual_new < len(view.controls) - 1:
                                        c_new = view.controls[actual_new]
                                        if isinstance(c_new, ft.Container) and c_new.page:
                                            c_new.content.color = ft.Colors.GREEN_ACCENT_400
                                            c_new.opacity = 1.0
                                            c_new.scale = ft.Scale(scale=1.2, alignment=ft.Alignment(-1.0, 0.0))
                                            try: c_new.update()
                                            except: pass
                            except Exception:
                                pass 
                            
                            #  Целимся СТРОГО в текущую строчку (new_idx).
                            # Никаких +3! Из-за длинных переносимых строк они занимали весь экран 
                            # и наглухо выдавливали нужный текст наверх за пределы окна.
                            scroll_target_idx = max(0, new_idx - 2)
                            page.run_task(smooth_scroll, scroll_target_idx)
                    # ====================================

                    if changed:
                        try:
                            timer_current.update()
                            timer_total.update()
                            progress_slider.update()
                        except: pass

                    if (not _track_ended[0]
                            and audio.player.get_state() == vlc.State.Ended
                            and playlist):
                        _track_ended[0] = True
                        play_next()

            except Exception:
                pass

    page.run_task(update_slider)

    # --- ГОЛОСОВОЕ УПРАВЛЕНИЕ ---
    voice_handler = VoiceCommandHandler(
        voice_feedback=settings["voice_feedback"],
        wake_word=settings["voice_trigger"] 
    )
    
    voice_handler.register_callback('play', lambda: (audio.play(), setattr(play_button, 'icon', ft.Icons.PAUSE_CIRCLE_FILLED), page.update()))
    voice_handler.register_callback('pause', lambda: (audio.pause(), setattr(play_button, 'icon', ft.Icons.PLAY_CIRCLE_FILL), page.update()))
    voice_handler.register_callback('next', lambda: (play_next(), page.update()))
    voice_handler.register_callback('prev', lambda: (play_prev(), page.update()))
    voice_handler.register_callback('louder', lambda: (audio.set_volume(min(100, audio.get_volume() + 15)), page.update()))
    voice_handler.register_callback('quieter', lambda: (audio.set_volume(max(0, audio.get_volume() - 15)), page.update()))
    voice_handler.register_callback('shuffle', lambda: (toggle_shuffle(), page.update()))
    voice_handler.register_callback('repeat', lambda: (cycle_repeat(), page.update()))
    voice_handler.register_callback('grid', lambda: (set_view('grid'), page.update()))
    voice_handler.register_callback('list', lambda: (set_view('list'), page.update()))
    
    voice_controller_ref = [None]
    voice_thread = [None]
    
    def handle_voice_command(text):
        has_wake_word, command_text = voice_handler.check_wake_word(text)
        if not has_wake_word: return
            
        words = command_text.split()
        is_complex = any(w in command_text for w in ["артист", "альбом", "песню", "трек", "волну", "диджей", "новое", "не слушал"]) or \
                     (len(words) > 1 and words[0] in ["включи", "включить", "поставь", "включай", "врубай"])

        if not is_complex:
            result = voice_handler.handle_command(command_text)
            if result['success']:
                if voice_handler.voice_feedback: show_snackbar(result['message'])
                return 
        
        try:
            from core.nlu import analyze_intent
            import rapidfuzz 
        except ImportError:
            show_snackbar("Для работы ИИ установите библиотеку: pip install rapidfuzz")
            return

        analysis = analyze_intent(command_text)
        intent = analysis["intent"]
        entity = analysis["entity"]

        if intent == "play_unplayed":
            unplayed = db.get_unplayed_tracks()
            if unplayed:
                playlist.clear()
                playlist.extend(unplayed)
                current_index[0] = 0
                select_track(playlist[0])
                show_snackbar("🤖 Включаю треки, которые вы еще не слушали")
            else:
                show_snackbar("Вы уже послушали всю медиатеку!")

        elif intent == "play_wave":
            wave_tracks = db.generate_smart_wave()
            if wave_tracks:
                playlist.clear()
                playlist.extend(wave_tracks)
                current_index[0] = 0
                
                # Достаем инфу о первом треке, чтобы красиво написать в уведомлении
                seed_info = db.get_track(wave_tracks[0])
                vibe_name = seed_info.get("artist", "случайном треке") if seed_info else "случайном треке"
                if vibe_name == "Неизвестен": 
                    vibe_name = "неизвестном исполнителе"
                
                select_track(playlist[0])
                show_snackbar(f"🌊 Умная Волна: настроение основано на '{vibe_name}'")
            else:
                show_snackbar("Ваша медиатека пока пуста!")
                
        elif intent == "play_artist":
            artist_tracks = db.get_tracks_by_artist(entity)
            if artist_tracks:
                playlist.clear()
                playlist.extend(artist_tracks)
                current_index[0] = 0
                select_track(playlist[0])
                show_snackbar(f"🎤 Включаю артиста: {entity}")
                
        elif intent == "play_album":
            album_tracks = db.get_tracks_by_album(entity)
            if album_tracks:
                playlist.clear()
                playlist.extend(album_tracks)
                current_index[0] = 0
                select_track(playlist[0])
                show_snackbar(f"💿 Включаю альбом: {entity}")
            elif voice_handler.voice_feedback:
                show_snackbar(f"Альбом '{entity}' не найден")

        elif intent == "search" and entity:
            import os
            search_results = db.search_tracks(entity)
            valid_results = [res["file_path"] for res in search_results if os.path.exists(res["file_path"])]
            
            if valid_results:
                playlist.clear()
                playlist.extend(valid_results)
                current_index[0] = 0
                select_track(playlist[0])
                show_snackbar(f"🔍 Нашел и включаю: {entity}")
            elif voice_handler.voice_feedback:
                show_snackbar(f"По запросу '{entity}' ничего не найдено")

    def start_voice_assistant():
        try:
            voice_controller = VoiceController("model")
            voice_controller_ref[0] = voice_controller
            voice_controller.listen(handle_voice_command)
        except Exception as e:
            print(f"Ошибка голосового помощника: {e}")
    
    def stop_voice_assistant():
        if voice_controller_ref[0] is not None:
            voice_controller_ref[0].stop()
            voice_controller_ref[0] = None
        show_snackbar("Голосовой помощник отключен")
   
    if settings["voice_feedback"]:
        voice_thread[0] = threading.Thread(target=start_voice_assistant, daemon=True)
        voice_thread[0].start()

    # =========================================================
    # RESIZABLE PANELS
    # =========================================================
    sidebar_width   = [230]  # Немного сузили левую панель для баланса
    right_width     = [220]  
    _left_last_render  = [0.0]  
    _right_last_render = [0.0]
    _DRAG_FPS = 1 / 30        

    is_light_start = settings["theme_mode"] == "light"
    sidebar_bgcolor = "#FFFFFF" if is_light_start else "#121212"
    
    playlists_container = ft.Column([
        ft.ListTile(leading=ft.Icon(ft.Icons.LIBRARY_MUSIC), title=ft.Text("Моя медиатека")),
        ft.Divider(color="white10"),
        ft.Text("Плейлисты появятся тут...", size=12, color="grey")
    ], expand=True, scroll=ft.ScrollMode.ALWAYS) # <--- Убрали AUTO
    
    # ========== НАСТРОЙКИ ==========
    def show_settings():
        update_music_folders_list()
        load_audio_devices()
        main_row.visible = False
        player_control_bar.visible = False
        settings_page.visible = True
        page.update()
    
    def close_settings():
        new_music_path = settings["music_folders"][0] if settings["music_folders"] else get_default_music_path()
        if music_path_ref[0] != new_music_path:
            music_path_ref[0] = new_music_path
            path_history.clear()
            path_history.append(new_music_path)
            load_folder(new_music_path, add_to_history=False)
        
        settings_page.visible = False
        main_row.visible = True
        player_control_bar.visible = True
        page.update()
    
    music_folders_list_container = ft.Column([], tight=True, spacing=4)
    
    audio_device_dropdown = ft.Dropdown(
        label="Выходное устройство", value=settings["audio_device"],
        label_style=ft.TextStyle(color="#FFFFFF"), text_style=ft.TextStyle(color="#FFFFFF"),
        options=[ft.dropdown.Option(dev_id, dev_desc) for dev_id,dev_desc in audio.get_audio_devices().items()],
        width=260, on_select=lambda e: change_audio_device(e), border_color="white24", focused_border_color="#1DB954",
    )
    
    # UI ЭКВАЛАЙЗЕРА
    eq_bands_labels = ["32 Hz", "64 Hz", "125 Hz", "250 Hz", "500 Hz", "1 kHz", "2 kHz", "4 kHz", "8 kHz", "16 kHz"]
    EQ_PRESETS = {
        "flat": ("По умолчанию", [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        "acoustic": ("Акустика", [5.0, 5.0, 4.0, 1.0, 1.0, 1.0, 3.0, 4.0, 4.0, 3.0]),
        "bass": ("Усиление баса", [6.0, 5.0, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        "classical": ("Классика", [5.0, 4.0, 3.0, 2.0, -1.0, -1.0, 0.0, 2.0, 4.0, 5.0]),
        "electronic": ("Электроника", [4.0, 3.0, 1.0, 0.0, -2.0, 2.0, 1.0, 2.0, 4.0, 5.0]),
        "hiphop": ("Хип-хоп", [5.0, 4.0, 2.0, 3.0, -1.0, -1.0, 1.0, -1.0, 2.0, 3.0]),
        "pop": ("Поп", [-1.0, -1.0, 0.0, 2.0, 4.0, 4.0, 2.0, 0.0, -1.0, -1.0]),
        "rock": ("Рок", [5.0, 4.0, 3.0, 1.0, -1.0, -1.0, 2.0, 3.0, 4.0, 5.0]),
        "vocal": ("Вокал", [-2.0, -2.0, -2.0, 1.0, 4.0, 4.0, 3.0, 0.0, -2.0, -2.0])
    }

    eq_sliders = []
    eq_texts = []

    def on_eq_change(e, idx):
        val = round(float(e.control.value), 1)
        settings["equalizer_presets"][idx] = val
        audio.set_eq_band(idx, val)
        save_settings()
        eq_texts[idx].value = f"{val:+.1f} dB"
        eq_texts[idx].update()
        if eq_preset_dropdown.value is not None:
            eq_preset_dropdown.value = None
            eq_preset_dropdown.update()

    def apply_preset_values(values_list):
        settings["equalizer_presets"] = list(values_list)
        for i, val in enumerate(values_list):
            eq_sliders[i].value = val
            eq_texts[i].value = f"{val:+.1f} dB"
            audio.set_eq_band(i, val)
            eq_sliders[i].update()
            eq_texts[i].update()
        save_settings()

    def on_preset_change(e):
        preset_key = e.control.value
        if preset_key and preset_key in EQ_PRESETS:
            apply_preset_values(EQ_PRESETS[preset_key][1])
            show_snackbar(f"Применен пресет: {EQ_PRESETS[preset_key][0]}")

    def reset_eq(_):
        apply_preset_values(EQ_PRESETS["flat"][1])
        eq_preset_dropdown.value = "flat"
        eq_preset_dropdown.update()
        show_snackbar("Эквалайзер сброшен")

    eq_preset_dropdown = ft.Dropdown(
        label="Пресеты", options=[ft.dropdown.Option(key, data[0]) for key, data in EQ_PRESETS.items()],
        width=200, on_select=on_preset_change, disabled=not settings["equalizer_enabled"],
        label_style=ft.TextStyle(color="#FFFFFF"), text_style=ft.TextStyle(color="#FFFFFF"),
        border_color="white24", focused_border_color="#1DB954"
    )
    
    eq_reset_btn = ft.TextButton("Сбросить", icon=ft.Icons.REFRESH, icon_color="red400", on_click=reset_eq, disabled=not settings["equalizer_enabled"])

    async def add_music_folder(_=None):
        path = await get_directory_path_async(dialog_title="Выберите папку с музыкой")
        
        # 2. Если пользователь выбрал путь (не нажал "Отмена")
        if path:
            # Нормализуем путь (убираем лишние пробелы и приводим к стандарту системы)
            path = os.path.abspath(path)
            
            # 3. Проверяем, не была ли эта папка добавлена ранее
            if path in settings["music_folders"]:
                return show_snackbar("Эта папка уже добавлена")
            
            # 4. Добавляем в настройки и сохраняем
            settings["music_folders"].append(path)
            save_settings()
            
            # 5. Обновляем визуальный список папок в настройках
            update_music_folders_list()
            
            # 6. Уведомляем пользователя
            show_snackbar(f"Папка добавлена: {os.path.basename(path)}")
            
            # 7. Запускаем фоновое сканирование новых треков
            page.run_task(scan_library_async)
            # Обновляем страницу для применения изменений
            page.update()

    def toggle_eq(e):
        enabled = e.control.value
        settings["equalizer_enabled"] = enabled
        audio.enable_equalizer(enabled)
        save_settings()
        
        eq_preset_dropdown.disabled = not enabled
        eq_reset_btn.disabled = not enabled
        eq_preset_dropdown.update()
        eq_reset_btn.update()
        
        # Определяем цвета для текущей темы
        is_light = is_app_light_mode[0]
        active_text_color = "#000000" if is_light else "#FFFFFF"
        inactive_text_color = "black54" if is_light else "white54"
        
        for i in range(10):
            eq_sliders[i].disabled = not enabled
            eq_texts[i].color = active_text_color if enabled else inactive_text_color
            eq_sliders[i].update()
            eq_texts[i].update()
                
        show_snackbar(f"Эквалайзер {'включен' if enabled else 'выключен'}")
    eq_col_1 = ft.Column(expand=True)
    eq_col_2 = ft.Column(expand=True)
    
    for i, label in enumerate(eq_bands_labels):
        val = settings["equalizer_presets"][i]
        is_enabled = settings["equalizer_enabled"]
        slider = ft.Slider(min=-20, max=20, value=val, on_change=lambda e, idx=i: on_eq_change(e, idx), disabled=not is_enabled, expand=True, active_color="#1DB954", inactive_color="white10")
        
        text_val = ft.Text(f"{val:+.1f} dB", width=55, size=12) 
        
        eq_sliders.append(slider)
        eq_texts.append(text_val)
            
        # --- ВОТ ЭТОТ БЛОК БЫЛ УТЕРЯН ---
        row = ft.Row([ft.Text(label, width=50, size=12, color="grey", text_align="right"), slider, text_val])
        if i < 5: 
            eq_col_1.controls.append(row)
        else: 
            eq_col_2.controls.append(row)
        # --------------------------------
            
    eq_columns = ft.Row([eq_col_1, eq_col_2], spacing=20)

    settings_page_content = ft.Column([
        ft.Row([
            ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="#FFFFFF", on_click=lambda _: close_settings(), tooltip="Назад"),
            ft.Text("Настройки", size=28, weight="bold", color="#FFFFFF", expand=True),
        ]),
        ft.Divider(color="white24"),
        ft.Column([
            ft.Text("🎨 Оформление", size=20, weight="bold", color="#FFFFFF"),
            ft.Divider(height=10),
            ft.Text("Тема", size=16, weight="bold", color="#FFFFFF"),
            ft.RadioGroup(
                content=ft.Column([
                    ft.Radio(value="dark", label="Тёмная", fill_color="#1DB954", active_color="#1DB954"),
                    ft.Radio(value="light", label="Светлая", fill_color="#1DB954", active_color="#1DB954"),
                    ft.Radio(value="system", label="Системная", fill_color="#1DB954", active_color="#1DB954"),
                ]),
                value=settings["theme_mode"], on_change=lambda e: apply_theme(e.control.value, animate_transition=True)
            ),
            ft.Divider(height=10, color="transparent"),
            ft.Row([
                ft.Column([
                    ft.Text("Сворачивать в трей", size=16, weight="bold", color="#FFFFFF"),
                    ft.Text("Оставлять плеер работать в фоне при закрытии окна", size=12, color="white54"),
                ], expand=True),
                ft.Switch(
                    value=settings.get("close_to_tray", True),
                    active_color="#1DB954",
                    on_change=lambda e: toggle_close_to_tray(e.control.value)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

            ft.Divider(height=30),
            
            ft.Text("🎤 Голосовое управление", size=20, weight="bold", color="#FFFFFF"),
            ft.Divider(height=10),
            ft.TextField(
                label="Ключевое слово активации", value=settings["voice_trigger"], width=300,
                label_style=ft.TextStyle(color="#FFFFFF"), text_style=ft.TextStyle(color="#FFFFFF"),
                border_color="white24", focused_border_color="#1DB954",
                on_submit=lambda e: (update_voice_trigger(e.control.value), page.update()),
                on_blur=lambda e: (update_voice_trigger(e.control.value), page.update()),
                on_focus=lambda _: (is_typing.__setitem__(0, True)), # ИСПРАВЛЕНИЕ
            ),
            ft.Switch(
                label="Голосовой помощник (включить микрофон)", value=settings["voice_feedback"],
                label_text_style=ft.TextStyle(color="#FFFFFF"), active_color="#1DB954",
                on_change=lambda e: (update_voice_feedback(e.control.value), page.update())
            ),
            ft.Divider(height=30),
            
            ft.Text("🔊 Аудио", size=20, weight="bold", color="#FFFFFF"),
            ft.Divider(height=10),
            # --- НОВЫЙ БЛОК: НОРМАЛИЗАЦИЯ ---
            ft.Row([
                ft.Column([
                    ft.Text("Нормализация громкости", size=16, weight="bold", color="#FFFFFF"),
                    ft.Text("Выравнивает громкость тихих и громких треков (требует перезапуска плеера)", size=12, color="white54"),
                ], expand=True),
                ft.Switch(
                    value=settings.get("normalize_volume", False),
                    active_color="#1DB954",
                    on_change=lambda e: toggle_normalization(e.control.value)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=20, color="transparent"),
            audio_device_dropdown,
            ft.Divider(height=20, color="transparent"),
                ft.Row([
                    ft.Text("🎛️ Эквалайзер (10 полос)", size=16, weight="bold", color="#FFFFFF"),
                    ft.Switch(value=settings["equalizer_enabled"], on_change=toggle_eq, active_color="#1DB954")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Row([eq_preset_dropdown, eq_reset_btn], vertical_alignment="center"),
                ft.Divider(height=10, color="transparent"),
                eq_columns,
            ft.Divider(height=30),
            
            ft.Text("📁 Папки с музыкой", size=20, weight="bold", color="#FFFFFF"),
            ft.Divider(height=10),
            ft.Text("Управляйте папками, где хранится ваша музыка", size=12, color="white54"),
            ft.Divider(height=15),
            music_folders_list_container,
            ft.Divider(height=15),
            ft.Button("➕ Добавить папку", on_click=add_music_folder, icon=ft.Icons.FOLDER_OPEN, color="#FFFFFF", bgcolor="#1DB954"),
            ft.Divider(height=30),
        ], scroll=ft.ScrollMode.ALWAYS, expand=True),

    ])
    def toggle_normalization(enabled):
        settings["normalize_volume"] = enabled
        save_settings()
        show_snackbar("Настройка сохранена. Перезапустите приложение, чтобы применить.")

    def toggle_close_to_tray(enabled):
        settings["close_to_tray"] = enabled
        save_settings()
        print(f"[Audaci] Настройка закрытия в трей изменена на: {enabled}")
        
    settings_page = ft.Container(
        content=settings_page_content, bgcolor="#121212", 
        padding=30, expand=True, visible=False,
        animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT) # <---
    )

    def change_audio_device(e):
        new_device_id = e.control.value
        if new_device_id:
            settings["audio_device"] = new_device_id
            audio.set_output_device(new_device_id)
            if audio.player.is_playing():
                audio.pause()
                audio.play()
            show_snackbar("Устройство вывода изменено")
    
    def apply_theme(mode, show_toast=True, animate_transition=False):
        settings["theme_mode"] = mode
        save_settings() 
        is_light = mode == "light" or (mode == "system" and page.platform_brightness == ft.Brightness.LIGHT)
        try:
            page.theme = ft.Theme(color_scheme_seed="#1DB954")
            page.update()
        except: pass
        if mode == "dark":
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = "#121212"
            settings_page.bgcolor = "#121212"
            is_light = False
        elif mode == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
            page.bgcolor = "#FFFFFF"
            settings_page.bgcolor = "#F5F5F5"
            is_light = True
        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
            page.bgcolor = None 
            if page.platform_brightness == ft.Brightness.LIGHT:
                settings_page.bgcolor = "#F5F5F5"
                is_light = True
            else:
                settings_page.bgcolor = "#121212"
                is_light = False
        
        is_app_light_mode[0] = is_light
        
        text_color = "#000000" if is_light else "#FFFFFF"
        icon_color = "#000000" if is_light else "#FFFFFF"
        divider_color = "black12" if is_light else "white24"
        secondary_text_color = "black54" if is_light else "white54"
        
        def update_settings_colors(controls_list):
            for item in controls_list:
                if isinstance(item, ft.Text):
                    if item.value and any(s in item.value for s in ["в разработке", "Управляйте папками", "Hz", "kHz"]):
                        item.color = secondary_text_color
                    elif item.value and "dB" in item.value:
                        pass
                    else:
                        item.color = text_color
                elif isinstance(item, ft.IconButton):
                    if getattr(item, "icon_color", "") not in ["red", "red400"]:
                        item.icon_color = icon_color
                elif isinstance(item, ft.TextField):
                    item.label_style = ft.TextStyle(color=text_color)
                    item.text_style = ft.TextStyle(color=text_color)
                    item.border_color = divider_color
                elif isinstance(item, ft.Switch):
                    item.label_text_style = ft.TextStyle(color=text_color)
                elif isinstance(item, ft.Dropdown):
                    item.label_style = ft.TextStyle(color=text_color)
                    item.text_style = ft.TextStyle(color=text_color)
                    item.border_color = divider_color
                elif isinstance(item, ft.Divider):
                    item.color = divider_color
                
                if hasattr(item, 'controls') and item.controls:
                    update_settings_colors(item.controls)
                if hasattr(item, 'content') and item.content:
                    update_settings_colors([item.content])

        update_settings_colors(settings_page.content.controls)
        
        if is_light:
            main_content.bgcolor = "#FFFFFF"
            for container in sidebar.content.controls:
                # В белой теме делаем блоки светло-серыми, чтобы они выделялись!
                if isinstance(container, ft.Container): container.bgcolor = "#F5F5F5"
            sidebar.content.bgcolor = "transparent" # А промежуток между ними прозрачным
            right_panel.bgcolor = "#FFFFFF"
            player_control_bar.bgcolor = "#FFFFFF"
            playlists_container.bgcolor = "#FFFFFF"
            track_grid.bgcolor = "#FFFFFF"
            track_list.bgcolor = "#FFFFFF"
            search_input.bgcolor = "#E0E0E0"
            search_input.text_style = ft.TextStyle(color="#000000")
            search_input.hint_style = ft.TextStyle(color="#666666")
            
            left_divider_line.bgcolor = "#E0E0E0"
            right_divider_line.bgcolor = "#E0E0E0"
            
            left_divider.content.on_hover = lambda e: (
                setattr(left_divider_line, "bgcolor", "#B0B0B0" if e.data == "true" else "#E0E0E0"), left_divider_line.update()
            )
            right_divider.content.on_hover = lambda e: (
                setattr(right_divider_line, "bgcolor", "#B0B0B0" if e.data == "true" else "#E0E0E0"), right_divider_line.update()
            )
            
            current_folder_text.color = "#000000"
            current_track_title.color = "#000000"
            current_track_artist.color = "#666666"
            big_track_title.color = "#000000"
            big_track_artist.color = "#666666"
            timer_current.color = "#666666"
            timer_total.color = "#666666"
            greeting_text.color = "#000000"
            
            progress_slider.inactive_color = "#E0E0E0"
            progress_slider.active_color = "#1DB954"
            
            shuffle_btn.icon_color = "#1DB954" if shuffle_mode[0] else "#000000"
            repeat_btn.icon_color = "#1DB954" if repeat_mode[0] != 0 else "#000000"
            play_button.icon_color = "#000000"
            prev_btn.icon_color = "#000000"
            next_btn.icon_color = "#000000"
            volume_icon.color = "#666666"
            karaoke_btn.icon_color = "#1DB954" if karaoke_mode[0] else "#000000"
            queue_btn.icon_color = "#1DB954" if is_queue_active[0] else "#000000"
            focus_btn.icon_color = "#000000"
            
            view_grid_btn.icon_color = "#000000"
            view_list_btn.icon_color = "#666666"
            
            for container in track_grid.controls:
                if (isinstance(container.content, ft.Column) and len(container.content.controls) >= 2 and
                    isinstance(container.content.controls[0], ft.Icon) and container.content.controls[0].icon == ft.Icons.FOLDER_OPEN_ROUNDED):
                    container.bgcolor = "#F0F0F0" 
                    def on_hover_light(e, c=container):
                        if hasattr(c, 'original_bgcolor'): c.bgcolor = c.original_bgcolor
                        else: c.bgcolor = "#F0F0F0"
                        if e.data == "true": c.bgcolor = "#E0E0E0" 
                        c.update()
                    container.on_hover = on_hover_light
            
            for container in track_grid.controls:
                if (isinstance(container.content, ft.Column) and len(container.content.controls) >= 2 and isinstance(container.content.controls[1], ft.Row)):
                    container.bgcolor = "#FFFFFF" 
                    def on_hover_light(e, c=container):
                        if hasattr(c, 'original_bgcolor'): c.bgcolor = c.original_bgcolor
                        else: c.bgcolor = "#FFFFFF"
                        if e.data == "true": c.bgcolor = "#F0F0F0"
                        c.update()
                    container.on_hover = on_hover_light
            
        else:
            main_content.bgcolor = "#121212"
            for container in sidebar.content.controls:
                # В темной теме делаем блоки чуть светлее фона
                if isinstance(container, ft.Container): container.bgcolor = "#181818"
            sidebar.content.bgcolor = "transparent"
            right_panel.bgcolor = "#121212"
            player_control_bar.bgcolor = "#121212"
            playlists_container.bgcolor = "#121212"
            track_grid.bgcolor = "#121212"
            track_list.bgcolor = "#121212"
            search_input.bgcolor = "white10"
            search_input.text_style = ft.TextStyle(color="#FFFFFF")
            search_input.hint_style = ft.TextStyle(color="#AAAAAA")
            
            # ФИКС 1: Делаем разделители слегка видимыми (white10) вместо прозрачных
            left_divider_line.bgcolor = "white10"
            right_divider_line.bgcolor = "white10"
                
            left_divider.content.on_hover = lambda e: (
                setattr(left_divider_line, "bgcolor", "white24" if e.data == "true" else "white10"), left_divider_line.update()
            )
            right_divider.content.on_hover = lambda e: (
                    setattr(right_divider_line, "bgcolor", "white24" if e.data == "true" else "white10"), right_divider_line.update()
            )
            
            current_folder_text.color = "#FFFFFF"
            current_track_title.color = "#FFFFFF"
            current_track_artist.color = "#AAAAAA"
            big_track_title.color = "#FFFFFF"
            big_track_artist.color = "#AAAAAA"
            timer_current.color = "#AAAAAA"
            timer_total.color = "#AAAAAA"
            greeting_text.color = "#FFFFFF"
            
            progress_slider.inactive_color = "white10"
            progress_slider.active_color = "white"
            
            shuffle_btn.icon_color = "#1DB954" if shuffle_mode[0] else "grey"
            repeat_btn.icon_color = "#1DB954" if repeat_mode[0] != 0 else "grey"
            play_button.icon_color = "#FFFFFF"
            prev_btn.icon_color = "#FFFFFF"
            next_btn.icon_color = "#FFFFFF"
            volume_icon.color = "grey"
            karaoke_btn.icon_color = "#1DB954" if karaoke_mode[0] else "grey"
            queue_btn.icon_color = "#1DB954" if is_queue_active[0] else "grey"
            focus_btn.icon_color = "grey"
            
            view_grid_btn.icon_color = "white"
            view_list_btn.icon_color = "grey"
            
            for container in track_grid.controls:
                if (isinstance(container.content, ft.Column) and len(container.content.controls) >= 2 and
                    isinstance(container.content.controls[0], ft.Icon) and container.content.controls[0].icon == ft.Icons.FOLDER_OPEN_ROUNDED):
                    container.bgcolor = "#181818" 
            
            for container in track_list.controls:
                if isinstance(container.content, ft.Row):
                    if (len(container.content.controls) > 0 and not (isinstance(container.content.controls[0], ft.Text) and 
                             container.content.controls[0].value == "#" and len(container.content.controls) > 2 and
                             isinstance(container.content.controls[2], ft.Container))):
                        container.bgcolor = "#181818" 
            
            for container in track_grid.controls:
                if (isinstance(container.content, ft.Column) and len(container.content.controls) >= 2 and isinstance(container.content.controls[1], ft.Row)):
                    container.bgcolor = "#181818" 
        
        for i in range(10):
            slider = eq_sliders[i]
            if is_light:
                slider.active_color = ft.Colors.GREEN_700 
                slider.inactive_color = ft.Colors.BLACK12 
                slider.thumb_color = ft.Colors.GREEN_800
            else:
                slider.active_color = ft.Colors.GREEN_ACCENT_400 
                slider.inactive_color = ft.Colors.WHITE24 
                slider.thumb_color = ft.Colors.WHITE
            try:
                if slider.page: slider.update()
            except: pass
            
            if settings["equalizer_enabled"]: eq_texts[i].color = "#000000" if is_light else "#FFFFFF"
            else: eq_texts[i].color = "black54" if is_light else "white54"
                
            try:
                if eq_texts[i].page: eq_texts[i].update()
            except: pass
            
        try: update_right_queue()
        except: pass

        try:
            first_run_view.bgcolor = "#FFFFFF" if is_light else "#121212"
            first_run_view.content.controls[1].color = "#000000" if is_light else "white"
            first_run_view.content.controls[2].color = "#666666" if is_light else "white54"
            wizard_box = first_run_view.content.controls[4]
            wizard_box.bgcolor = "#F5F5F5" if is_light else "#1e1e1e"
            wizard_box.content.controls[0].color = "#000000" if is_light else "white"
            wizard_box.content.controls[3].color = "#000000" if is_light else "white"
            first_run_folder_val.color = "#000000" if is_light else "white"
            first_run_view.update()
        except: pass
            

        # --- ФИКС ИКОНОК САЙДБАРА ---
        sidebar_items = [
            sidebar_home_tile, sidebar_artists_tile, sidebar_albums_tile, 
            sidebar_search_tile, sidebar_history_tile, sidebar_settings_tile
        ]
        for tile in sidebar_items:
            try:
                # Перекрашиваем иконку (индекс 0) и текст (индекс 1)
                tile.content.controls[0].color = "#000000" if is_light else "#FFFFFF"
                tile.content.controls[1].color = "#000000" if is_light else "#FFFFFF"
                tile.update()
            except: pass
            
        # Заставляем кнопки Сетки/Списка обновиться под новую тему
        set_view(view_mode[0])
        
        page.update()

        try:
            if show_toast and page.page: 
                show_snackbar(f"Тема изменена на: {mode}")
        except: pass
    
    def update_voice_trigger(new_trigger):
        settings["voice_trigger"] = new_trigger.strip()
        voice_handler.set_wake_word(new_trigger)
        save_settings()
        show_snackbar(f"Ключевое слово изменено на: '{new_trigger}'")
    
    def update_voice_feedback(enabled):
        settings["voice_feedback"] = enabled
        voice_handler.set_feedback_enabled(enabled)
        save_settings()
        
        if enabled:
            if voice_controller_ref[0] is None:
                voice_thread[0] = threading.Thread(target=start_voice_assistant, daemon=True)
                voice_thread[0].start()
            show_snackbar("🎤 Голосовой помощник включен")
        else:
            stop_voice_assistant()
    
    
    def load_audio_devices():
        try:
            devices = audio.get_audio_devices()
            audio_device_dropdown.options.clear()
            for device_key, device_name in devices.items():
                audio_device_dropdown.options.append(ft.dropdown.Option(device_key, device_name))
            if settings["audio_device"] in devices:
                audio_device_dropdown.value = settings["audio_device"]
            elif devices:
                audio_device_dropdown.value = list(devices.keys())[0]
        except Exception as e:
            print(f"Ошибка при загрузке устройств: {e}")
    
    def update_music_folders_list():
        music_folders_list_container.controls.clear()
        if settings["music_folders"]:
            for idx, folder_path in enumerate(settings["music_folders"]):
                folder_name = os.path.basename(folder_path) or folder_path
                music_folders_list_container.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.FOLDER, size=20, color="#1DB954"),
                            ft.Column([
                                ft.Text(folder_name, size=13, weight="bold", max_lines=1, overflow="ellipsis"),
                                ft.Text(folder_path, size=10, color="grey", max_lines=1, overflow="ellipsis"),
                            ], spacing=2, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color="red", tooltip="Удалить папку",
                                on_click=lambda _, path=folder_path: remove_music_folder(path)
                            ) if len(settings["music_folders"]) > 1 else ft.Container(width=40),
                        ], spacing=10, vertical_alignment="center"),
                        padding=10, bgcolor="white10", border_radius=8,
                    )
                )
        else:
            music_folders_list_container.controls.append(ft.Text("Папки с музыкой не добавлены", size=12, color="grey"))
        music_folders_list_container.update()
    
    
    
    def remove_music_folder(folder_path):
        if folder_path in settings["music_folders"]:
            if len(settings["music_folders"]) > 1:
                settings["music_folders"].remove(folder_path)
                save_settings()
                update_music_folders_list()
                db.remove_folder_tracks(folder_path)
                show_snackbar(f"Папка удалена")
            else:
                show_snackbar("Должна быть хотя бы одна папка с музыкой")

    def make_sidebar_btn(icon, label, on_click=None):
        is_light = is_app_light_mode[0]
        hover_color = "#E0E0E0" if is_light else "white10"
        
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=20, color="#000000" if is_light else "#FFFFFF"), 
                ft.Text(label, size=14, weight=ft.FontWeight.W_500, expand=True)
            ], spacing=12, vertical_alignment="center"),
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=8,
            on_click=on_click,
            on_hover=lambda e: setattr(e.control, "bgcolor", hover_color if str(e.data).lower() == "true" else "transparent") or e.control.update()
        )
    
    sidebar_home_tile = make_sidebar_btn(ft.Icons.HOME_FILLED, "Главная", lambda _: (load_folder(music_path_ref[0]), show_home_view()))
    sidebar_artists_tile = make_sidebar_btn(ft.Icons.PEOPLE_ALT_ROUNDED, "Исполнители", lambda _: load_db_view("artists"))
    sidebar_albums_tile = make_sidebar_btn(ft.Icons.ALBUM_ROUNDED, "Альбомы", lambda _: load_db_view("albums"))
    sidebar_search_tile = make_sidebar_btn(ft.Icons.SEARCH, "Поиск", lambda _: show_search_view())
    sidebar_history_tile = make_sidebar_btn(ft.Icons.HISTORY, "История", lambda _: load_db_view("history"))
    sidebar_settings_tile = make_sidebar_btn(ft.Icons.SETTINGS, "Настройки", lambda _: show_settings())
    
    library_header = ft.Container(
        content=ft.Row([ft.Icon(ft.Icons.LIBRARY_MUSIC, size=16, color="grey"), ft.Text("МОЯ МЕДИАТЕКА", size=11, weight="bold", color="grey", overflow="ellipsis", expand=True)], spacing=10),
        padding=ft.Padding(10, 5, 0, 10),
    )
    
    #  Убрали ft.Divider и добавили padding=10 для верхнего блока
    sidebar_col = ft.Column([
        ft.Container(
            content=ft.Column([
                sidebar_home_tile, 
                sidebar_artists_tile, 
                sidebar_albums_tile, 
                sidebar_search_tile, 
                sidebar_history_tile, 
                sidebar_settings_tile,
            ], spacing=2),
            bgcolor=sidebar_bgcolor, border_radius=10, padding=10,
            animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
        ),
        ft.Container(
            content=ft.Column([library_header, playlists_container], spacing=0),
            bgcolor=sidebar_bgcolor, border_radius=10, padding=10, expand=True,
            animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
        ),
    ], spacing=10)

    sidebar = ft.Container(content=sidebar_col, width=sidebar_width[0])

    def on_left_drag(e: ft.DragUpdateEvent):
        dx = e.primary_delta or 0
        if abs(dx) < 1: return
        sidebar_width[0] = max(150, min(450, sidebar_width[0] + dx))
        sidebar.width = sidebar_width[0]
        now = time.monotonic()
        if now - _left_last_render[0] >= _DRAG_FPS:
            _left_last_render[0] = now
            main_row.update()

    left_divider_line = ft.Container(width=2, bgcolor="#E0E0E0" if is_light_start else "transparent", expand=True)
    left_divider = ft.GestureDetector(
        mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
        on_horizontal_drag_update=on_left_drag,
        content=ft.Container(
            width=8, content=left_divider_line,
            on_hover=lambda e: (
                setattr(left_divider_line, "bgcolor", ("#B0B0B0" if is_light_start else "#ffffff30") if e.data == "true" else ("#E0E0E0" if is_light_start else "transparent")),
                left_divider_line.update()
            )
        ),
    )

    right_col = ft.Column([
        ft.Text("СЕЙЧАС ИГРАЕТ", size=11, weight="bold", color="grey"),
        ft.Divider(height=20, color="transparent"),
        big_track_img, ft.Divider(height=20, color="transparent"),
        big_track_title, big_track_artist, right_metadata_col, right_queue_col
    ], horizontal_alignment="center", expand=True)

    right_panel = ft.Container(
        content=right_col, width=right_width[0], padding=20, 
        bgcolor="#121212", border_radius=10,
        animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT) # <---
    )

    def on_right_drag(e: ft.DragUpdateEvent):
        dx = e.primary_delta or 0
        if abs(dx) < 1: return
        right_width[0] = max(150, min(500, right_width[0] - dx))
        right_panel.width = right_width[0]
        img_size = min(right_width[0] - 40, 300)
        big_track_img.width  = img_size
        big_track_img.height = img_size
        now = time.monotonic()
        if now - _right_last_render[0] >= _DRAG_FPS:
            _right_last_render[0] = now
            main_row.update()

    right_divider_line = ft.Container(width=2, bgcolor="#E0E0E0" if is_light_start else "transparent", expand=True)
    right_divider = ft.GestureDetector(
        mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
        on_horizontal_drag_update=on_right_drag,
        content=ft.Container(
            width=8, content=right_divider_line,
            on_hover=lambda e: (
                setattr(right_divider_line, "bgcolor", ("#B0B0B0" if is_light_start else "#ffffff30") if e.data == "true" else ("#E0E0E0" if is_light_start else "transparent")),
                right_divider_line.update()
            )
        ),
    )

    def play_next():
        if not playlist: return
        if repeat_mode[0] == 2:
            if audio.current_track_path:
                audio.load(audio.current_track_path)
                audio.play()
                play_button.icon = ft.Icons.PAUSE_CIRCLE_FILLED
                progress_slider.value = 0
                page.update()
            _track_ended[0] = False
            return
            
        nxt = current_index[0] + 1
        if nxt >= len(playlist):
            if repeat_mode[0] == 1: nxt = 0
            else: return              
        current_index[0] = nxt
        select_track(playlist[nxt], playlist_idx=nxt) # <--- ПЕРЕДАЕМ ИНДЕКС ЗДЕСЬ
        

    def play_prev():
        if not playlist: return
        if audio.get_time() > 3000:
            audio.seek(0)
            return
        prv = max(0, current_index[0] - 1)
        current_index[0] = prv
        select_track(playlist[prv], playlist_idx=prv) # <--- И ЗДЕСЬ

    def toggle_shuffle(_=None):
        shuffle_mode[0] = not shuffle_mode[0]
        if shuffle_mode[0]:
            if not original_playlist: original_playlist.extend(playlist)
            current_track = playlist[current_index[0]] if current_index[0] >= 0 and current_index[0] < len(playlist) else None
            temp_playlist = playlist[:]
            if current_track in temp_playlist: temp_playlist.remove(current_track)
            random.shuffle(temp_playlist)
            playlist.clear()
            if current_track:
                playlist.append(current_track)
                current_index[0] = 0
            playlist.extend(temp_playlist)
        else:
            current_track = playlist[current_index[0]] if current_index[0] >= 0 and current_index[0] < len(playlist) else None
            if original_playlist:
                playlist.clear()
                playlist.extend(original_playlist)
            if current_track in playlist:
                current_index[0] = playlist.index(current_track)
                
        update_right_queue()
        is_light = is_app_light_mode[0]
        if shuffle_mode[0]:
            shuffle_btn.icon_color = "#1DB954"
            try: focus_shuffle_btn.icon_color = "#1DB954"; focus_shuffle_btn.update()
            except NameError: pass
        else:
            shuffle_btn.icon_color = "#666666" if is_light else "grey"
            try: focus_shuffle_btn.icon_color = "white70"; focus_shuffle_btn.update()
            except NameError: pass
        shuffle_btn.update()

    def cycle_repeat(_=None):
        repeat_mode[0] = (repeat_mode[0] + 1) % 3
        is_light = is_app_light_mode[0]
        inactive_color = "#666666" if is_light else "grey"
        
        icon_map = {0: ft.Icons.REPEAT, 1: ft.Icons.REPEAT, 2: ft.Icons.REPEAT_ONE}
        color_map = {0: inactive_color, 1: "#1DB954", 2: "#1DB954"}
        focus_color_map = {0: "white70", 1: "#1DB954", 2: "#1DB954"}

        repeat_btn.icon = icon_map[repeat_mode[0]]
        repeat_btn.icon_color = color_map[repeat_mode[0]]
        repeat_btn.update()
        try:
            focus_repeat_btn.icon = icon_map[repeat_mode[0]]
            focus_repeat_btn.icon_color = focus_color_map[repeat_mode[0]]
            focus_repeat_btn.update()
        except NameError: pass

    def toggle_play():
        if audio.player.is_playing():
            play_button.icon = ft.Icons.PLAY_CIRCLE_FILL
            focus_play_btn.icon = ft.Icons.PLAY_CIRCLE_FILL 
        else:
            play_button.icon = ft.Icons.PAUSE_CIRCLE_FILLED
            focus_play_btn.icon = ft.Icons.PAUSE_CIRCLE_FILLED 
            
        #  Точечное обновление кнопок
        try:
            play_button.update()
            focus_play_btn.update()
        except: pass
        
        audio.toggle_play_pause()

    play_button = ft.IconButton(icon=ft.Icons.PLAY_CIRCLE_FILL, icon_size=40, icon_color=ft.Colors.WHITE, on_click=lambda _: toggle_play())

    def on_slider_drag_start(e): user_is_dragging.set()
    def on_slider_change_end(e):
        audio.seek(e.control.value / 100)
        user_is_dragging.clear()
        page.update()
    
    progress_slider.on_change_start = on_slider_drag_start
    progress_slider.on_change_end = on_slider_change_end

    shuffle_btn = ft.IconButton(ft.Icons.SHUFFLE, icon_size=18, icon_color="grey", on_click=toggle_shuffle)
    repeat_btn = ft.IconButton(ft.Icons.REPEAT,  icon_size=18, icon_color="grey", on_click=cycle_repeat)
    queue_btn = ft.IconButton(ft.Icons.QUEUE_MUSIC, icon_size=20, icon_color="grey", tooltip="Очередь", on_click=lambda _: toggle_right_panel_view())

    view_grid_btn = ft.IconButton(ft.Icons.GRID_VIEW_ROUNDED, icon_size=18, icon_color=ft.Colors.WHITE, tooltip="Сетка", on_click=lambda _: set_view("grid"))
    view_list_btn = ft.IconButton(ft.Icons.FORMAT_LIST_BULLETED, icon_size=18, icon_color="grey", tooltip="Список", on_click=lambda _: set_view("list"))

    def set_view(mode: str):
        view_mode[0] = mode
        track_grid.visible = (mode == "grid")
        track_list.visible = (mode == "list")
        
        # Проверяем тему и назначаем правильные цвета
        is_light = is_app_light_mode[0]
        active_color = "#000000" if is_light else "white"
        inactive_color = "#666666" if is_light else "grey"
        
        view_grid_btn.icon_color = active_color if mode == "grid" else inactive_color
        view_list_btn.icon_color = active_color if mode == "list" else inactive_color
        
        try:
            view_grid_btn.update()
            view_list_btn.update()
        except: pass
        page.update()

    # --- РЕЖИМ ФОКУСА ---
    is_focus_mode = [False]

    focus_cover = ft.Image(src="https://via.placeholder.com/500", width=400, height=400, border_radius=20, fit="cover")
    focus_title = ft.Text("", size=36, weight="bold", color="white", text_align="center", max_lines=1, overflow="ellipsis")
    focus_artist = ft.Text("", size=20, color="white70", text_align="center", max_lines=1, overflow="ellipsis")

    focus_shuffle_btn = ft.IconButton(ft.Icons.SHUFFLE, icon_size=20, icon_color="white70", on_click=toggle_shuffle)
    focus_repeat_btn = ft.IconButton(ft.Icons.REPEAT, icon_size=20, icon_color="white70", on_click=cycle_repeat)
    focus_karaoke_btn = ft.IconButton(ft.Icons.MIC_EXTERNAL_ON, icon_size=20, icon_color="white70", tooltip="Текст", on_click=toggle_karaoke)
    focus_queue_btn = ft.IconButton(ft.Icons.QUEUE_MUSIC, icon_size=20, icon_color="white70", tooltip="Очередь", on_click=lambda _: toggle_right_panel_view())

    focus_play_btn = ft.IconButton(icon=ft.Icons.PLAY_CIRCLE_FILL, icon_size=60, icon_color="white", on_click=lambda _: toggle_play())
    
    focus_controls = ft.Row([
        focus_shuffle_btn,
        ft.IconButton(ft.Icons.SKIP_PREVIOUS_SHARP, icon_size=35, icon_color="white70", on_click=lambda _: play_prev()),
        focus_play_btn,
        ft.IconButton(ft.Icons.SKIP_NEXT_SHARP, icon_size=35, icon_color="white70", on_click=lambda _: play_next()),
        focus_repeat_btn,
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=15)

    focus_extra_controls = ft.Row([focus_karaoke_btn, focus_queue_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=20)

    # ФИКС 1: Добавили expand=True, чтобы колонка не сжималась
    focus_main_col = ft.Column([
        focus_cover, ft.Container(height=30), focus_title, focus_artist, ft.Container(height=20), 
        focus_controls, ft.Container(height=10), focus_extra_controls
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ФИКС 2: Убрали width=0 и animate_size. Теперь используем visible=False
    focus_lyrics_container = ft.Container(
        content=focus_lyrics_list_view, 
        width=LYRICS_WIDTH, visible=False, opacity=0, padding=ft.Padding(0, 50, 0, 80),
        animate_opacity=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        clip_behavior=ft.ClipBehavior.HARD_EDGE  
    )

    focus_queue_container = ft.Container(
        content=ft.Column([
            ft.Text("ОЧЕРЕДЬ", size=16, weight="bold", color="white54"),
            ft.Divider(color="white24"), focus_queue_list
        ], expand=True),
        width=QUEUE_WIDTH, visible=False, opacity=0, padding=ft.Padding(20, 50, 20, 80), 
        bgcolor="#08ffffff", border_radius=15,
        animate_opacity=ft.Animation(400, ft.AnimationCurve.DECELERATE),
    )

    # ФИКС 3: ДОБАВИЛИ vertical_alignment=STRETCH. Это спасает высоту от схлопывания в 0!
    focus_row = ft.Row([focus_main_col, focus_lyrics_container, focus_queue_container], expand=True, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.STRETCH, spacing=20)

    focus_bg_image = ft.Image(src="https://via.placeholder.com/500", fit="cover", expand=True)
    focus_blur_overlay = ft.Container(expand=True, bgcolor="#A0000000", blur=ft.Blur(sigma_x=60, sigma_y=60))

    def toggle_focus(_=None):
        if not audio.current_track_path: return

        is_focus_mode[0] = not is_focus_mode[0]
        sidebar.visible = not is_focus_mode[0]
        left_divider.visible = not is_focus_mode[0]

        if is_focus_mode[0]:
            right_panel.visible = False
            right_divider.visible = False
            home_view.visible = False
            search_view.visible = False
            focus_view.visible = True
            focus_btn.icon_color = "#1DB954"

            main_content.padding = 0
            main_content.border_radius = 0

            player_control_bar.height = 0
            player_control_bar.opacity = 0
            player_control_bar.update()
            
            # --- ЗАКРЫВАЕМ ОДНУ ПАНЕЛЬ ПРИ ВХОДЕ, ТОЛЬКО ЕСЛИ ЭКРАН МАЛЕНЬКИЙ ---
            if is_small_screen[0] and karaoke_mode[0] and is_queue_active[0]:
                is_queue_active[0] = False 
                queue_btn.icon_color = "grey"
                queue_btn.update()
                try: 
                    focus_queue_btn.icon_color = "white70"
                    focus_queue_btn.update()
                except: pass
            # --------------------------------------------------------------------
            
            focus_lyrics_container.visible = karaoke_mode[0]
            focus_lyrics_container.opacity = 1 if karaoke_mode[0] else 0
            focus_queue_container.visible = is_queue_active[0]
            focus_queue_container.opacity = 1 if is_queue_active[0] else 0
        else:
            # 1. Возвращаем видимость панелей
            right_panel.visible = not is_small_screen[0]
            right_divider.visible = not is_small_screen[0]
            focus_view.visible = False
            
            # Определяем, куда возвращаться: в поиск или на главную
            if search_input.value:
                search_view.visible = True
                home_view.visible = False
            else:
                home_view.visible = True
                search_view.visible = False

            # 2. ВОЗВРАЩАЕМ отступы и рамки
            main_content.padding = ft.Padding(left=30, top=30, right=30, bottom=0)
            main_content.border_radius = 10

            # 3. Восстанавливаем высоту плеера
            player_control_bar.height = 115 if is_small_screen[0] else 90            
            player_control_bar.opacity = 1
            
            # --- КРИТИЧЕСКИЙ ФИКС ВИДИМОСТИ ---
            # Если караоке выключено — показываем треки. Если включено — показываем только текст.
            track_grid.visible = not karaoke_mode[0] and view_mode[0] == "grid"
            track_list.visible = not karaoke_mode[0] and view_mode[0] == "list"
            lyrics_container.visible = karaoke_mode[0] # <--- Вот она, строчка, которая спасает от пустого экрана!
            
            # Сбрасываем цвета кнопок
            focus_btn.icon_color = "#000000" if is_app_light_mode[0] else "grey"
            
            # Если была очередь — возвращаем её
            if is_queue_active[0]:
                right_metadata_col.visible = False
                right_queue_col.visible = True
                
            # 4. ФИКС ДЛЯ ASTRA LINUX (Layout Pump)
            # Заставляем систему отрисовать всё разом
        main_content.update()
        page.update()
    
    # Прыгаем к текущей строке при развороте фокуса
        if karaoke_mode[0] and current_lyrics_index[0] != -1:
            async def sync_focus_scroll():
                # УВЕЛИЧЕННАЯ ПАУЗА: Даем Астре время на ресайз холста!
                await asyncio.sleep(0.5) 
                try:
                    view = focus_lyrics_list_view if is_focus_mode[0] else lyrics_list_view
                    target_key = f"foc_{current_lyrics_index[0]}" if is_focus_mode[0] else f"norm_{current_lyrics_index[0]}"
                    
                    # ПРОВЕРКА СОСТОЯНИЯ ПЕРЕД СКРОЛЛОМ
                    can_scroll = False
                    if is_focus_mode[0] and focus_view.visible and focus_lyrics_container.visible:
                        can_scroll = True
                    elif not is_focus_mode[0] and lyrics_container.visible:
                        can_scroll = True
                        
                    if can_scroll and view.page:
                        print(f"[Audaci Debug] Скролл после смены режима фокуса: {target_key}")
                        await view.scroll_to(scroll_key=target_key, duration=300)
                except Exception as e:
                    if "Timeout waiting" not in str(e):
                        print(f"[Audaci Error] Ошибка при смене фокуса: {e}")
            page.run_task(sync_focus_scroll)

    focus_top_hover_zone = ft.Container(
        content=ft.Container(
            content=ft.IconButton(icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, icon_size=35, icon_color="white", on_click=toggle_focus, tooltip="Свернуть"),
            bgcolor="#60000000", border_radius=50, width=50, height=50, alignment=ft.Alignment.CENTER
        ),
        alignment=ft.Alignment.TOP_LEFT, padding=ft.Padding(30, 30, 0, 0), 
        top=0, left=0, right=0, height=120, bgcolor=ft.Colors.TRANSPARENT,
        opacity=0, animate_opacity=300,
        on_hover=lambda e: setattr(e.control, 'opacity', 1 if (str(e.data).lower() == 'true' or e.data is True) else 0) or e.control.update()
    )

    focus_view = ft.Container(
        content=ft.Stack([focus_bg_image, focus_blur_overlay, focus_row, focus_top_hover_zone], expand=True),
        expand=True, visible=False, border_radius=10, clip_behavior=ft.ClipBehavior.HARD_EDGE,
        theme_mode=ft.ThemeMode.DARK, # <--- ИЗОЛЯЦИЯ ТЕМЫ: теперь внутри всегда ночь и белый текст
        animate=ft.Animation(800, ft.AnimationCurve.EASE_OUT)
    )

    focus_btn = ft.IconButton(icon=ft.Icons.FULLSCREEN_ROUNDED, icon_size=20, icon_color="grey", tooltip="Режим Фокуса", on_click=toggle_focus)
    # ==========================================
    # === БЛОКИ НИЖНЕЙ ПАНЕЛИ ПЛЕЕРА ===
    player_left_block = ft.Container(
        content=ft.Row([
            current_track_img,
            ft.Column([current_track_title, current_track_artist], spacing=0, alignment=ft.MainAxisAlignment.CENTER, expand=True) 
        ]),
        expand=1, 
    )

    # === НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ КНОПОК ===
    prev_btn = ft.IconButton(ft.Icons.SKIP_PREVIOUS_SHARP, icon_size=25, icon_color="white", on_click=lambda _: play_prev())
    next_btn = ft.IconButton(ft.Icons.SKIP_NEXT_SHARP, icon_size=25, icon_color="white", on_click=lambda _: play_next())
    volume_icon = ft.Icon(ft.Icons.VOLUME_UP, size=20, color="grey")

    player_center_block = ft.Container(
        content=ft.Column([
            ft.Row([
                shuffle_btn,
                prev_btn,      
                play_button,
                next_btn,      
                repeat_btn,
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=5),
            ft.Row([
                timer_current, progress_slider, timer_total,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER), 
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
        expand=2, 
    )

    player_right_block = ft.Container(
        content=ft.Row([
            volume_icon,       
            # Расширили ползунок громкости до 140px
            ft.Slider(width=140, min=0, max=1.0, value=0.7, on_change=lambda e: audio.set_volume(int(e.control.value * 100))),
            ft.Container(width=5),
            karaoke_btn, queue_btn, focus_btn
        ], alignment=ft.MainAxisAlignment.END, spacing=0),
        width=290, # <--- Вернули комфортную ширину блока
    )

    player_row_wide = ft.Row(
        controls=[player_left_block, player_center_block, player_right_block], 
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )
    player_top_small = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    player_col_small = ft.Column(alignment=ft.MainAxisAlignment.CENTER, spacing=5)

    player_control_bar = ft.Container(
        content=player_row_wide, 
        height=90, opacity=1.0, padding=ft.Padding(20, 5, 20, 5), 
        clip_behavior=ft.ClipBehavior.HARD_EDGE, 
        animate_size=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        animate_opacity=ft.Animation(400, ft.AnimationCurve.DECELERATE),
        animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT) # <--- Плавность фона плеера
    )

    
    # ==================================

    def get_dominant_color(image_path):
        if not image_path or not os.path.exists(image_path): return "#1e1e1e" 
        try:
            color_thief = ColorThief(image_path)
            dominant_color = color_thief.get_color(quality=5) 
            return f"#{dominant_color[0]:02x}{dominant_color[1]:02x}{dominant_color[2]:02x}"
        except Exception as e:
            print(f"Ошибка цвета: {e}")
            return "#1e1e1e"

   # --- ЛОГИКА ---
    def select_track(file_path, playlist_idx=None): # <--- ДОБАВИЛИ ПАРАМЕТР
        try:
            if active_track_path[0] == file_path and playlist_idx is None:
                toggle_play()
                return
            
            # --- НОВАЯ ЛОГИКА ОЧЕРЕДИ ---
            # Пересобираем плейлист ТОЛЬКО если клик был из главного окна (playlist_idx = None)
            if playlist_idx is None and file_path in current_view_tracks:
                playlist.clear()
                playlist.extend(current_view_tracks)
                original_playlist.clear()
                original_playlist.extend(current_view_tracks)
                
                # Сохраняем логику шаффла
                if shuffle_mode[0]:
                    temp = playlist[:]
                    temp.remove(file_path)
                    random.shuffle(temp)
                    playlist.clear()
                    playlist.append(file_path)
                    playlist.extend(temp)
            # ---------------------------

            # 1. ЗАПОМИНАЕМ ЦЕЛЬ: Какой трек мы сейчас пытаемся включить?
            active_track_path[0] = file_path
            current_target = file_path 

            # 🛑 ЖЕСТКАЯ УСТАНОВКА ИНДЕКСА (ЧТОБЫ ОЧЕРЕДЬ ДВИГАЛАСЬ)
            if playlist_idx is not None:
                current_index[0] = playlist_idx
            elif file_path in playlist:
                current_index[0] = playlist.index(file_path)

            # 🛑 ПРОВЕРКА НА ГОНКУ ПОТОКОВ (RACE CONDITION GUARD) 🛑
            if active_track_path[0] != current_target:
                return

            db_info = db.get_track(file_path)
            if db_info: info = db_info
            else: info = get_track_info(file_path)
            
            _track_ended[0] = False

            img_src = info.get("cover_path") or "https://via.placeholder.com/300"

            def _update_bg_color():
                if active_track_path[0] != current_target: return # Проверка внутри потока
                cover_path = info.get("cover_path")
                dom_color = get_dominant_color(cover_path)
                if active_track_path[0] != current_target: return # Вторая проверка после ColorThief
                lyrics_container.gradient.colors = [dom_color, "#121212"]
                try: lyrics_container.update()
                except: pass

            threading.Thread(target=_update_bg_color, daemon=True).start()

            current_track_img.src      = img_src
            current_track_title.value  = info.get("title", os.path.basename(file_path))
            current_track_artist.value = info.get("artist", "Неизвестен")

            cover_for_notif = info.get("cover_path")
            if isinstance(cover_for_notif, str) and cover_for_notif.startswith("http"):
                cover_for_notif = None 
                
            notify_system(current_track_title.value, current_track_artist.value, cover_for_notif)

            big_track_img.src      = img_src
            big_track_title.value  = current_track_title.value
            big_track_artist.value = current_track_artist.value
            
            focus_cover.src = img_src
            focus_bg_image.src = img_src
            focus_title.value = current_track_title.value
            focus_artist.value = current_track_artist.value

            big_track_album.value = info.get("album", "Неизвестный альбом")
            big_track_dur.value = fmt_dur(info.get("duration_ms", 0))

            audio.load(file_path)
            audio.play()
            play_button.icon      = ft.Icons.PAUSE_CIRCLE_FILLED
            focus_play_btn.icon   = ft.Icons.PAUSE_CIRCLE_FILLED 
            progress_slider.value = 0

            try:
                db.add_to_history(file_path)
            except Exception as ex:
                print(f"Ошибка записи в историю: {ex}")

            update_right_queue()
            
            # === ЗАГРУЗКА ТЕКСТА ===
            def _fetch_lyrics():
                if active_track_path[0] != current_target: return 
                
                nonlocal current_lyrics_data
                current_lyrics_data.clear()
                current_lyrics_index[0] = -1
                
                lyrics_list_view.controls.clear()
                focus_lyrics_list_view.controls.clear()
                
                # ФИКС 1: Выводим статус загрузки с ЛЕВЫМ выравниванием
                def get_load_msg():
                    return ft.Container(
                        content=ft.Text("Загрузка текста...", size=24, color="grey", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.LEFT), 
                        alignment=ft.Alignment(-1.0, -1.0),
                        margin=ft.Margin(left=0, top=80, right=0, bottom=0)
                    )
                lyrics_list_view.controls.append(get_load_msg())
                focus_lyrics_list_view.controls.append(get_load_msg())
                try: page.update()
                except: pass
                
                duration_s = (db_info["duration_ms"] if db_info else info.get("duration_ms", 0)) / 1000
                artist_name = db_info["artist"] if db_info else info.get("artist", "")
                track_name = db_info["title"] if db_info else info.get("title", "")
                
                cached = db.get_track(file_path)
                raw_lrc = None
                
                if cached and cached.get("lyrics"):
                    raw_lrc = cached["lyrics"]
                else:
                    raw_lrc = fetch_synced_lyrics(artist_name, track_name, duration_s)
                    if raw_lrc: db.update_track_lyrics(file_path, raw_lrc)
                
                if active_track_path[0] != current_target: return 
                
                lyrics_list_view.controls.clear()
                focus_lyrics_list_view.controls.clear()
                
                if raw_lrc:
                    current_lyrics_data = parse_lrc(raw_lrc)
                    
                    lyrics_list_view.controls.append(ft.Container(height=80)) 
                    focus_lyrics_list_view.controls.append(ft.Container(height=80))

                    for i, (ts, txt) in enumerate(current_lyrics_data):
                        display_text = txt.strip() if txt.strip() else "♪"
                        
                        #  Оборачиваем ключи в ft.ScrollKey(), чтобы движок Flet "увидел" их для скролла!
                        lyrics_list_view.controls.append(
                            ft.Container(
                                content=ft.Text(display_text, size=24, color="white", weight=ft.FontWeight.W_600, text_align=ft.TextAlign.LEFT),
                                key=ft.ScrollKey(f"norm_{i}"), opacity=0.3, scale=ft.Scale(scale=1.0, alignment=ft.Alignment(-1.0, 0.0)),
                                animate_scale=ft.Animation(300, ft.AnimationCurve.DECELERATE), animate_opacity=300
                            )
                        )
                        focus_lyrics_list_view.controls.append(
                            ft.Container(
                                content=ft.Text(display_text, size=24, color="white", weight=ft.FontWeight.W_600, text_align=ft.TextAlign.LEFT),
                                key=ft.ScrollKey(f"foc_{i}"), opacity=0.3, scale=ft.Scale(scale=1.0, alignment=ft.Alignment(-1.0, 0.0)),
                                animate_scale=ft.Animation(300, ft.AnimationCurve.DECELERATE), animate_opacity=300
                            )
                        )

                    lyrics_list_view.controls.append(ft.Container(height=300))
                    focus_lyrics_list_view.controls.append(ft.Container(height=300))
                else:
                    err_msg = ft.Container(
                        content=ft.Text("Текст не найден 😔", size=24, color="grey", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.LEFT), 
                        alignment=ft.Alignment(-1.0, -1.0),
                        margin=ft.Margin(left=0, top=80, right=0, bottom=0)
                    )
                    lyrics_list_view.controls.append(err_msg)
                    focus_lyrics_list_view.controls.append(err_msg)
                    
                #  Обновляем только тексты, не трогаем сетку!
                try: 
                    lyrics_list_view.update()
                    focus_lyrics_list_view.update()
                except: pass
                
            threading.Thread(target=_fetch_lyrics, daemon=True).start()
            # ==================================

            #  Убрали глобальный page.update() в конце! Обновляем только плеер.
            try:
                player_control_bar.update()
                right_panel.update()
                focus_main_col.update()
                focus_bg_image.update()
            except: pass
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")

    def update_right_queue():
        right_queue_list.controls.clear()
        focus_queue_list.controls.clear()
        
        if not playlist: return
            
        start_idx = current_index[0] + 1
        # Берем следующие 15 треков
        next_tracks = playlist[start_idx:start_idx+15]
        
        is_light = is_app_light_mode[0]
        hover_color = "#F0F0F0" if is_light else "#1e1e1e"
        text_color = "#000000" if is_light else "#FFFFFF"
        
        if not next_tracks:
            right_queue_list.controls.append(ft.Text("Очередь пуста", color="grey", size=12))
            focus_queue_list.controls.append(ft.Text("Очередь пуста", color="grey", size=12))
        else:
            for idx_offset, path in enumerate(next_tracks):
                absolute_idx = start_idx + idx_offset # Вычисляем точную позицию в плейлисте
                filename = os.path.basename(path)
                
                # Достаем инфу о треке из базы, чтобы показать обложку и нормальное название
                db_info = db.get_track(path)
                cover_src = "https://via.placeholder.com/150"
                display_title = filename
                display_artist = ""
                
                if db_info:
                    cover_src = db_info.get("cover_path") or "https://via.placeholder.com/150"
                    display_title = db_info.get("title", filename)
                    display_artist = db_info.get("artist", "")
                
                # ==========================================
                # 1. Элемент для правой панели (адаптивные цвета)
                # ==========================================
                right_img = ft.Image(src=cover_src, width=36, height=36, border_radius=4, fit="cover")
                right_text_col = ft.Column([
                    ft.Text(display_title, size=12, color=text_color, weight="bold", max_lines=1, overflow="ellipsis"),
                    ft.Text(display_artist, size=10, color="grey", max_lines=1, overflow="ellipsis", visible=bool(display_artist))
                ], spacing=0, expand=True)
                
                right_queue_list.controls.append(
                    ft.Container(
                        content=ft.Row([right_img, right_text_col], vertical_alignment="center", spacing=10), 
                        padding=8, border_radius=5,
                        # ИСПРАВЛЕННЫЙ КЛИК:
                        on_click=lambda e, pp=path, aidx=absolute_idx: select_track(pp, playlist_idx=aidx),
                        on_hover=lambda e: setattr(e.control, "bgcolor", hover_color if str(e.data).lower() == "true" or e.data is True else None) or e.control.update()
                    )
                )
                
                # ==========================================
                # 2. Элемент для режима Фокуса (всегда светлый текст)
                # ==========================================
                focus_img = ft.Image(src=cover_src, width=36, height=36, border_radius=4, fit="cover")
                focus_text_col = ft.Column([
                    ft.Text(display_title, size=12, color="white", weight="bold", max_lines=1, overflow="ellipsis"),
                    ft.Text(display_artist, size=10, color="white70", max_lines=1, overflow="ellipsis", visible=bool(display_artist))
                ], spacing=0, expand=True)
                
                focus_queue_list.controls.append(
                    ft.Container(
                        content=ft.Row([focus_img, focus_text_col], vertical_alignment="center", spacing=10), 
                        padding=8, border_radius=5,
                        # ИСПРАВЛЕННЫЙ КЛИК:
                        on_click=lambda e, pp=path, aidx=absolute_idx: select_track(pp, playlist_idx=aidx),
                        on_hover=lambda e: setattr(e.control, "bgcolor", "#20ffffff" if str(e.data).lower() == "true" or e.data is True else None) or e.control.update()
                    )
                )
                
        try:
            right_queue_list.update()
            focus_queue_list.update()
        except: pass

    def toggle_right_panel_view():
        is_queue_active[0] = not is_queue_active[0]
        
        if is_focus_mode[0]:
            async def animate_queue_focus():
                # --- ВЫТЕСНЯЕМ ТЕКСТ ТОЛЬКО НА МАЛЕНЬКИХ ЭКРАНАХ ---
                if is_small_screen[0] and is_queue_active[0] and karaoke_mode[0]:
                    karaoke_mode[0] = False
                    # Гасим прозрачность текста
                    focus_lyrics_container.opacity = 0
                    focus_row.update()
                    try: 
                        focus_karaoke_btn.icon_color = "white70"
                        focus_karaoke_btn.update()
                    except: pass
                    # Ждем анимацию и скрываем полностью
                    await asyncio.sleep(0.4)
                    focus_lyrics_container.visible = False
                    focus_row.update()
                # ---------------------------------------------------
                
                # --- АНИМАЦИЯ САМОЙ ПАНЕЛИ ОЧЕРЕДИ ---
                if is_queue_active[0]:
                    # Включаем прозрачным
                    focus_queue_container.visible = True
                    focus_queue_container.opacity = 0
                    focus_row.update()
                    await asyncio.sleep(0.05) # Пауза для рендера
                    # Проявляем
                    focus_queue_container.opacity = 1
                    focus_row.update()
                else:
                    # Плавно скрываем
                    focus_queue_container.opacity = 0
                    focus_row.update()
                    await asyncio.sleep(0.4) # Пауза для завершения анимации
                    # Выключаем
                    focus_queue_container.visible = False
                    focus_row.update()
                    
                try: on_resize(None) # спасаем обложку от "съедания"
                except: pass
                
            # Запускаем
            page.run_task(animate_queue_focus)
        else:
            right_metadata_col.visible = not is_queue_active[0]
            right_queue_col.visible = is_queue_active[0]
            
        queue_btn.icon_color = "#1DB954" if is_queue_active[0] else "grey"
        queue_btn.update()
        try:
            focus_queue_btn.icon_color = "#1DB954" if is_queue_active[0] else "white70"
            focus_queue_btn.update()
        except NameError: pass
        page.update()

    def load_db_view(view_type, param=None, add_to_history=True):
        disable_karaoke()
        history_path = f"db:{view_type}:{param}"
        if add_to_history and (not path_history or path_history[-1] != history_path):
            path_history.append(history_path)
            
        back_button.visible = len(path_history) > 1
        show_home_view() 
        
        track_grid.controls.clear()
        track_list.controls.clear()
        
        is_light = is_app_light_mode[0]
        folder_bgcolor = "#F0F0F0" if is_light else "#181818"
        track_bgcolor = "#FFFFFF" if is_light else "#181818"
        hover_color = "#E0E0E0" if is_light else "#252525"
        track_hover_color = "#F0F0F0" if is_light else "#1e1e1e"
        
        if view_type == "artists":
            current_folder_text.value = "Исполнители"
            
            def create_artist_card(artist_name):
                g_icon = ft.Container(
                    content=ft.Icon(ft.Icons.PERSON_ROUNDED, size=60, color="#1DB954"),
                    width=100, height=100, alignment=ft.Alignment.CENTER
                )
                play_ov = ft.Container(
                    content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color="white", size=30),
                    alignment=ft.Alignment.CENTER,
                    bgcolor="#80000000", opacity=0.0, animate_opacity=200, 
                    width=100, height=100, border_radius=50
                )
                g_cover = ft.Container(content=ft.Stack([g_icon, play_ov]), width=100, height=100, border_radius=50, clip_behavior=ft.ClipBehavior.HARD_EDGE)
                
                def hover(e):
                    is_hover = str(e.data).lower() == "true" or e.data is True
                    # ИСПРАВЛЕНИЕ: Динамический цвет
                    current_bg = "#F0F0F0" if is_app_light_mode[0] else "#181818"
                    current_hover = "#E0E0E0" if is_app_light_mode[0] else "#252525"
                    e.control.bgcolor = current_hover if is_hover else current_bg
                    play_ov.opacity = 1.0 if is_hover else 0.0
                    play_ov.update()
                    e.control.update()
                    
                return ft.Container(
                    content=ft.Column([g_cover, ft.Text(artist_name, weight="bold", size=14, max_lines=2, overflow="ellipsis", text_align="center")], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    # ИСПРАВЛЕНИЕ: Динамический цвет
                    bgcolor="#F0F0F0" if is_app_light_mode[0] else "#181818", 
                    padding=15, border_radius=10,
                    on_click=lambda e: load_db_view("artist_tracks", artist_name), on_hover=hover
                )

            for artist in db.get_all_artists():
                track_grid.controls.append(create_artist_card(artist))
                track_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text("", width=32), ft.Container(width=10),
                            ft.Icon(ft.Icons.PERSON_ROUNDED, size=44, color="#1DB954"), ft.Container(width=10),
                            ft.Text(artist, weight="bold", size=14, expand=True),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.Padding(10, 6, 10, 6), border_radius=6,
                        on_click=lambda e, a=artist: load_db_view("artist_tracks", a),
                        on_hover=lambda e: setattr(e.control, "bgcolor", track_hover_color if str(e.data).lower() == "true" or e.data is True else None) or e.control.update()
                    )
                )

        elif view_type == "albums":
            current_folder_text.value = "Альбомы"
            
            def create_album_card(album_name, cover_src):
                g_img = ft.Image(src=cover_src, fit="cover", width=400, height=400)
                play_icon = ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.TRANSPARENT, size=40)
                play_ov = ft.Container(
                    content=play_icon, alignment=ft.Alignment.CENTER, bgcolor=ft.Colors.TRANSPARENT, 
                    width=400, height=400, animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT) 
                )
                
                def hover(e):
                    is_hover = str(e.data).lower() == "true" or e.data is True
                    # ИСПРАВЛЕНИЕ: Динамический цвет
                    current_bg = "#F0F0F0" if is_app_light_mode[0] else "#181818"
                    current_hover = "#E0E0E0" if is_app_light_mode[0] else "#252525"
                    e.control.bgcolor = current_hover if is_hover else current_bg
                    play_ov.bgcolor = "#80000000" if is_hover else ft.Colors.TRANSPARENT
                    play_icon.color = "white" if is_hover else ft.Colors.TRANSPARENT
                    play_ov.update()
                    e.control.update()

                g_cover = ft.Container(content=ft.Stack([g_img, play_ov]), border_radius=8, aspect_ratio=1, clip_behavior=ft.ClipBehavior.HARD_EDGE)
                return ft.Container(
                    content=ft.Column([g_cover, ft.Text(album_name, weight="bold", size=14, max_lines=2, overflow="ellipsis", text_align="center")], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    # ИСПРАВЛЕНИЕ: Динамический цвет
                    bgcolor="#F0F0F0" if is_app_light_mode[0] else "#181818", 
                    padding=15, border_radius=10,
                    on_click=lambda e: load_db_view("album_tracks", album_name), on_hover=hover
                )

            for alb_data in db.get_all_albums():
                cover = alb_data["cover"] or "https://via.placeholder.com/150"
                track_grid.controls.append(create_album_card(alb_data["album"], cover))
                track_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text("", width=32), ft.Container(width=10),
                            ft.Image(src=cover, width=44, height=44, border_radius=4, fit="cover"), ft.Container(width=10),
                            ft.Text(alb_data["album"], weight="bold", size=14, expand=True),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.Padding(10, 6, 10, 6), border_radius=6,
                        on_click=lambda e, a=alb_data["album"]: load_db_view("album_tracks", a),
                        on_hover=lambda e: setattr(e.control, "bgcolor", track_hover_color if str(e.data).lower() == "true" or e.data is True else None) or e.control.update()
                    )
                )

        elif view_type in ["artist_tracks", "album_tracks"]:
            current_folder_text.value = param
            track_paths = db.get_tracks_by_artist(param) if view_type == "artist_tracks" else db.get_tracks_by_album(param)
            track_paths = sorted(track_paths)
            
            track_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text("#", width=32, color="grey", size=12, text_align="right"), ft.Container(width=10),
                        ft.Container(width=44), ft.Container(width=10),
                        ft.Text("Название", size=12, color="grey", expand=True),
                        ft.Text("Альбом", size=12, color="grey", width=160),
                        ft.Icon(ft.Icons.ACCESS_TIME_OUTLINED, size=14, color="grey"), ft.Container(width=40),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding(10, 0, 10, 8),
                    border=ft.Border(bottom=ft.BorderSide(1, "white10")),
                )
            )
            
            for idx, path in enumerate(track_paths, 1):
                if not os.path.exists(path): continue
                db_info = db.get_track(path)
                if not db_info: continue
                
                display_title = db_info.get("title") or "Неизвестно"
                display_artist = db_info.get("artist") or "Неизвестен"
                display_album = db_info.get("album") or "..."
                display_dur = fmt_dur(db_info.get("duration_ms", 0))
                display_cover = db_info.get("cover_path") or "https://via.placeholder.com/150"
                
                g_img = ft.Image(src=display_cover, fit="cover", width=400, height=400)
                play_icon = ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.TRANSPARENT, size=40)
                play_overlay = ft.Container(
                    content=play_icon, alignment=ft.Alignment.CENTER, bgcolor=ft.Colors.TRANSPARENT,
                    width=400, height=400, animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT)
                )
                
                def on_db_cover_hover(e, ov=play_overlay, icon=play_icon):
                    is_hover = str(e.data).lower() == "true"
                    ov.bgcolor = "#80000000" if is_hover else ft.Colors.TRANSPARENT
                    icon.color = "white" if is_hover else ft.Colors.TRANSPARENT
                    ov.update()
                    
                g_cover_container = ft.Container(content=ft.Stack([g_img, play_overlay]), border_radius=8, aspect_ratio=1, clip_behavior=ft.ClipBehavior.HARD_EDGE, on_hover=on_db_cover_hover)
                g_title = ft.Text(
                    display_title, 
                    weight="bold", 
                    size=14, 
                    max_lines=1,                 # Строго одна линия
                    overflow=ft.TextOverflow.ELLIPSIS, # Усекаем многоточием
                    no_wrap=True                 # Запрещаем перенос букв в столбец нахуй
                )
                
                g_artist = ft.Text(
                    display_artist, 
                    size=12, 
                    color="#B3B3B3",             # Приглушенный серый для метаданных
                    max_lines=1, 
                    overflow=ft.TextOverflow.ELLIPSIS, 
                    no_wrap=True
                )
                
                def on_db_grid_hover(e):
                    e.control.bgcolor = track_hover_color if e.data == "true" else track_bgcolor
                    e.control.update()
                    
                track_grid.controls.append(
                    ft.Container(
                        content=ft.Column([
                            g_cover_container,
                            ft.Row([
                                ft.Column([g_title, g_artist], spacing=2, expand=True),
                                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey", items=[
                                    ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=path: add_to_playlist(fp)),
                                    ft.PopupMenuItem(content="Информация", on_click=lambda _, fp=path: show_track_info(fp))
                                ])
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
                        ], spacing=5),
                        bgcolor=track_bgcolor, padding=12, border_radius=10,
                        on_click=lambda e, p=path: select_track(p), on_hover=on_db_grid_hover
                    )
                )
                
                l_img = ft.Image(src=display_cover, width=44, height=44, border_radius=4, fit="cover")
                l_title = ft.Text(display_title, weight="bold", size=14, max_lines=1, overflow="ellipsis")
                l_artist = ft.Text(display_artist, size=12, color="grey", max_lines=1, overflow="ellipsis")
                l_album_text = ft.Text(display_album, size=12, color="grey", width=160, max_lines=1, overflow="ellipsis")
                l_dur_text = ft.Text(display_dur, size=12, color="grey", width=42, text_align="right")
                track_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(str(idx), width=32, color="grey", size=12, text_align="right"), ft.Container(width=10), 
                            l_img, ft.Container(width=10), ft.Column([l_title, l_artist], spacing=2, expand=True),
                            l_album_text, l_dur_text,
                            ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey", items=[
                                ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=path: add_to_playlist(fp)),
                                ft.PopupMenuItem(content="Информация", on_click=lambda _, fp=path: show_track_info(fp))
                            ])
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.Padding(10, 6, 10, 6), border_radius=6,
                        on_click=lambda e, p=path: select_track(p),
                        on_hover=lambda e: setattr(e.control, "bgcolor", track_hover_color if e.data == "true" else None) or e.control.update()
                    )
                )
            
            current_view_tracks.clear()
            current_view_tracks.extend(track_paths)

        elif view_type == "history":
            current_folder_text.value = "История прослушивания"
            
            history_data = db.get_listening_history(150)
            track_paths = []
            
            import datetime
            now = datetime.datetime.now()
            today_date = now.date()
            yesterday_date = today_date - datetime.timedelta(days=1)
            
            MONTHS_RU = ["", "янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
            DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            current_group_date = None
            
            # Умные ховеры для истории
            def history_hover_grid(e):
                is_l = is_app_light_mode[0]
                bg = "#FFFFFF" if is_l else "#181818"
                hv = "#F0F0F0" if is_l else "#1e1e1e"
                e.control.bgcolor = hv if str(e.data).lower() == "true" else bg
                e.control.update()

            def history_hover_list(e):
                is_l = is_app_light_mode[0]
                hv = "#F0F0F0" if is_l else "#1e1e1e"
                e.control.bgcolor = hv if str(e.data).lower() == "true" else "transparent"
                e.control.update()
            
            for item in history_data:
                path = item["file_path"]
                if not path or not os.path.exists(path): continue
                
                track_paths.append(path)
                absolute_idx = len(track_paths) - 1
                
                title = item["title"] or os.path.basename(path)
                artist = item["artist"] or "Неизвестен"
                album = item["album"] or "Неизвестный альбом"
                dur = fmt_dur(item["duration_ms"] or 0)
                cover = item["cover_path"] or "https://via.placeholder.com/150"
                
                # --- ЖЕЛЕЗОБЕТОННЫЙ ПАРСЕР ДАТЫ ---
                raw_date = str(item.get("played_at", ""))
                time_part = ""
                item_date_obj = None
                
                try:
                    if " " in raw_date:
                        date_str, time_str = raw_date.split(" ")
                        item_date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                        time_part = time_str[:5]
                    elif "T" in raw_date:
                        date_str, time_str = raw_date.split("T")
                        item_date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                        time_part = time_str[:5]
                except Exception: pass
                
                group_title = "Ранее"
                if item_date_obj:
                    if item_date_obj == today_date:
                        group_title = "Сегодня"
                    elif item_date_obj == yesterday_date:
                        group_title = "Вчера"
                    else:
                        wd = DAYS_RU[item_date_obj.weekday()]
                        m = MONTHS_RU[item_date_obj.month]
                        group_title = f"{wd}, {item_date_obj.day} {m}"
                
                # Группировка дат добавляется ТОЛЬКО в список (в сетке они сломают дизайн)
                if group_title != current_group_date:
                    current_group_date = group_title
                    if absolute_idx > 0:
                        track_list.controls.append(ft.Container(height=15))
                        
                    track_list.controls.append(
                        ft.Container(
                            content=ft.Text(group_title, size=22, weight="bold", color="#1DB954"), # Выделил даты фирменным зеленым!
                            padding=ft.Padding(10, 15, 10, 5)
                        )
                    )

                # --- ЭЛЕМЕНТ СЕТКИ (С бейджем даты и кнопкой Play) ---
                g_img = ft.Image(src=cover, border_radius=8, fit="cover", aspect_ratio=1)
                
                # Кнопка Play при наведении
                play_icon = ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.TRANSPARENT, size=40)
                play_overlay = ft.Container(
                    content=play_icon, alignment=ft.Alignment.CENTER, bgcolor=ft.Colors.TRANSPARENT,
                    animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT)
                )
                
                # Стильный бейдж с датой и временем поверх обложки!
                badge_text = f"{group_title} • {time_part}" if time_part else group_title
                date_badge = ft.Container(
                    content=ft.Text(badge_text, size=10, color="white", weight="bold"),
                    bgcolor="#A0000000", padding=ft.Padding(6, 4, 6, 4), border_radius=8,
                    top=6, left=6 # Позиция в левом верхнем углу обложки
                )
                
                # Склеиваем: Обложка + Затенение с Play + Бейдж даты
                g_cover_container = ft.Container(
                    content=ft.Stack([g_img, play_overlay, date_badge]), 
                    border_radius=8, aspect_ratio=1, clip_behavior=ft.ClipBehavior.HARD_EDGE
                )
                
                g_title = ft.Text(title, weight="bold", size=14, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True)
                g_artist = ft.Text(artist, size=12, color="grey", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True)
                
                # Индивидуальный умный Hover для карточек истории
                def history_grid_hover_fixed(e, ov=play_overlay, icon=play_icon):
                    is_hover = str(e.data).lower() == "true" or e.data is True
                    # Перекраска фона карточки под тему
                    is_l = is_app_light_mode[0]
                    e.control.bgcolor = ("#F0F0F0" if is_l else "#1e1e1e") if is_hover else ("#FFFFFF" if is_l else "#181818")
                    
                    # Появление кнопки Play
                    ov.bgcolor = "#80000000" if is_hover else ft.Colors.TRANSPARENT
                    icon.color = "white" if is_hover else ft.Colors.TRANSPARENT
                    
                    ov.update()
                    e.control.update()

                track_grid.controls.append(
                    ft.Container(
                        content=ft.Column([
                            g_cover_container, 
                            ft.Row([
                                ft.Column([g_title, g_artist], spacing=2, expand=True),
                                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey", items=[
                                    ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=path: add_to_playlist(fp)),
                                    ft.PopupMenuItem(content="Информация", on_click=lambda _, fp=path: show_track_info(fp))
                                ])
                            ], vertical_alignment="center")
                        ], spacing=5),
                        bgcolor="#FFFFFF" if is_app_light_mode[0] else "#181818", padding=12, border_radius=10,
                        on_click=lambda e, p=path, aidx=absolute_idx: select_track(p, playlist_idx=aidx),
                        on_hover=history_grid_hover_fixed
                    )
                )
                # --- ЭЛЕМЕНТ СПИСКА ---
                l_img = ft.Image(src=cover, width=44, height=44, border_radius=4, fit="cover")
                l_title = ft.Text(title, weight="bold", size=14, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True)
                l_artist = ft.Text(artist, size=12, color="grey", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True)
                l_album_text = ft.Text(album, size=12, color="grey", width=160, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True)
                l_dur_text = ft.Text(dur, size=12, color="grey", width=42, text_align="right")
                l_time_text = ft.Text(time_part, width=40, color="grey", size=12, text_align="right")
                
                track_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            l_time_text, ft.Container(width=10), 
                            l_img, ft.Container(width=10), ft.Column([l_title, l_artist], spacing=2, expand=True),
                            l_album_text, l_dur_text,
                            ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey", items=[
                                ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=path: add_to_playlist(fp)),
                                ft.PopupMenuItem(content="Информация", on_click=lambda _, fp=path: show_track_info(fp))
                            ])
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.Padding(10, 6, 10, 6), border_radius=6, bgcolor="transparent",
                        on_click=lambda e, p=path, aidx=absolute_idx: select_track(p, playlist_idx=aidx),
                        on_hover=history_hover_list
                    )
                )
            
            current_view_tracks.clear()
            current_view_tracks.extend(track_paths)

        page.update()

    def load_folder(path, add_to_history=True):
        disable_karaoke()
        if add_to_history and (not path_history or path_history[-1] != path):
            path_history.append(path)

        back_button.visible = len(path_history) > 1
        current_folder_text.value = os.path.basename(path) if path != music_path_ref[0] else "Главная"

        is_light = is_app_light_mode[0]
        sidebar.content.bgcolor = "#FFFFFF" if is_light else "#121212"
        playlists_container.bgcolor = "#FFFFFF" if is_light else "#121212"
        sidebar.update()

        track_grid.controls.clear()
        track_list.controls.clear()

        track_list.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text("#",        width=32, color="grey", size=12, text_align="right"),
                    ft.Container(width=10), ft.Container(width=44), ft.Container(width=10),
                    ft.Text("Название", size=12, color="grey", expand=True),
                    ft.Text("Альбом",   size=12, color="grey", width=160),
                    ft.Icon(ft.Icons.ACCESS_TIME_OUTLINED, size=14, color="grey"),
                    ft.Container(width=40),
                ], vertical_alignment="center"),
                padding=ft.Padding(10, 0, 10, 8),
                border=ft.Border(bottom=ft.BorderSide(1, "white10")),
            )
        )

        pending: list[dict] = []
        audio_idx = 0   
        folder_audio_files = []
        try:
            items = sorted(os.listdir(path))

            # --- УМНЫЕ ФУНКЦИИ НАВЕДЕНИЯ (Больше никакого залипания цвета) ---
            def hover_folder(e):
                is_l = is_app_light_mode[0]
                bg = "#F0F0F0" if is_l else "#181818"
                hv = "#E0E0E0" if is_l else "#252525"
                e.control.bgcolor = hv if str(e.data).lower() == "true" else bg
                e.control.update()

            def hover_track_grid(e):
                is_l = is_app_light_mode[0]
                bg = "#FFFFFF" if is_l else "#181818"
                hv = "#F0F0F0" if is_l else "#1e1e1e"
                e.control.bgcolor = hv if str(e.data).lower() == "true" else bg
                e.control.update()

            def hover_track_list(e):
                is_l = is_app_light_mode[0]
                bg = "transparent" # В списке лучше прозрачный фон по умолчанию
                hv = "#F0F0F0" if is_l else "#1e1e1e"
                e.control.bgcolor = hv if str(e.data).lower() == "true" else bg
                e.control.update()
            # -----------------------------------------------------------------

            for item in items:
                if item.startswith("."): continue
                full_path = os.path.join(path, item)

                if os.path.isdir(full_path):
                    track_grid.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=60, color="#7BB3FF"),
                                ft.Text(item, weight="bold", size=14, max_lines=2, overflow="ellipsis", text_align="center")
                            ], alignment="center", horizontal_alignment="center"),
                            bgcolor="#F0F0F0" if is_app_light_mode[0] else "#181818", padding=15, border_radius=10,
                            on_click=lambda e, p=full_path: load_folder(p),
                            on_hover=hover_folder
                        )
                    )

                    track_list.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Text("", width=32), ft.Container(width=10),
                                    ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=44, color="#7BB3FF"), ft.Container(width=10),
                                    ft.Text(item, weight="bold", size=14, expand=True),
                                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                padding=ft.Padding(10, 6, 10, 6), border_radius=6,
                                on_click=lambda e, p=full_path: load_folder(p),
                                on_hover=hover_folder
                            )
                        )

                elif item.lower().endswith((".mp3", ".flac", ".wav", ".m4a")):
                    audio_idx += 1
                    folder_audio_files.append(full_path)
                    db_info = db.get_track(full_path)
                    if db_info:
                        display_title = db_info["title"]
                        display_artist = db_info["artist"]
                        display_album = db_info["album"]
                        display_dur = fmt_dur(db_info["duration_ms"])
                        display_cover = db_info["cover_path"] or "https://via.placeholder.com/150"
                    else:
                        display_title = item
                        display_artist = "..."
                        display_album = "..."
                        display_dur = "--:--"
                        display_cover = "https://via.placeholder.com/150"

                    g_img = ft.Image(src=display_cover, fit="cover", width=400, height=400)
                    play_icon = ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.TRANSPARENT, size=40)
                    play_overlay = ft.Container(
                        content=play_icon, alignment=ft.Alignment.CENTER, bgcolor=ft.Colors.TRANSPARENT,
                        width=400, height=400, animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT)
                    )
                    
                    def on_cover_hover(e, ov=play_overlay, icon=play_icon):
                        is_hover = str(e.data).lower() == "true"
                        ov.bgcolor = "#80000000" if is_hover else ft.Colors.TRANSPARENT
                        icon.color = "white" if is_hover else ft.Colors.TRANSPARENT
                        ov.update()
                        
                    g_cover_container = ft.Container(content=ft.Stack([g_img, play_overlay]), border_radius=8, aspect_ratio=1, clip_behavior=ft.ClipBehavior.HARD_EDGE, on_hover=on_cover_hover)
                    g_title  = ft.Text(display_title, weight="bold", size=14, max_lines=1, overflow="ellipsis", no_wrap=True)
                    g_artist = ft.Text(display_artist, size=12, color="#B3B3B3", max_lines=1, overflow="ellipsis", no_wrap=True)
                    
                    track_grid.controls.append(
                        ft.Container(
                            content=ft.Column([
                                g_cover_container,
                                ft.Row([ft.Column([g_title, g_artist], spacing=2, expand=True), 
                                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey", items=[
                                    ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=full_path: add_to_playlist(fp)),
                                    ft.PopupMenuItem(content="Информация о треке", on_click=lambda _, fp=full_path: show_track_info(fp)),
                                ])], vertical_alignment="center"),
                            ], spacing=5),
                            bgcolor="#FFFFFF" if is_app_light_mode[0] else "#181818", padding=12, border_radius=10,
                            on_click=lambda e, p=full_path: select_track(p), on_hover=hover_track_grid
                        )
                    )

                    l_img = ft.Image(src=display_cover, width=44, height=44, border_radius=4, fit="cover")
                    l_title  = ft.Text(display_title, weight="bold", size=14, max_lines=1, overflow="ellipsis")
                    l_artist = ft.Text(display_artist, size=12, color="grey", max_lines=1)
                    l_album  = ft.Text(display_album, size=12, color="grey", width=160, max_lines=1, overflow="ellipsis")
                    l_dur    = ft.Text(display_dur, size=12, color="grey", width=42, text_align="right")
                    
                    track_list.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Text(str(audio_idx), width=32, color="grey", size=12, text_align="right"), ft.Container(width=10),
                                l_img, ft.Container(width=10), ft.Column([l_title, l_artist], spacing=2, expand=True), l_album, l_dur, 
                                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey", items=[
                                    ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=full_path: add_to_playlist(fp)),
                                    ft.PopupMenuItem(content="Информация о треке", on_click=lambda _, fp=full_path: show_track_info(fp)),
                                ])
                            ], vertical_alignment="center"),
                            padding=ft.Padding(10, 6, 10, 6), border_radius=6, bgcolor="transparent",
                            on_click=lambda e, p=full_path: select_track(p),
                            on_hover=hover_track_list,
                        )
                    )

                    if not db_info:
                        pending.append({
                            "fp": full_path,
                            "g_img": g_img, "g_title": g_title, "g_artist": g_artist,
                            "l_img": l_img, "l_title": l_title, "l_artist": l_artist,
                            "l_album": l_album, "l_dur": l_dur,
                        })
        except Exception as e: print(f"Ошибка при чтении папки {path}: {e}")

        current_view_tracks.clear()
        current_view_tracks.extend(folder_audio_files)

        page.update()

        def _load_meta():
            BATCH = 4
            for i, d in enumerate(pending):
                try:
                    info = get_track_info(d["fp"])
                    cover  = info.get("cover_path") or "https://via.placeholder.com/150"
                    title  = info.get("title",  os.path.basename(d["fp"]))
                    artist = info.get("artist", "Неизвестен")
                    album  = info.get("album",  "")
                    dur    = fmt_dur(info.get("duration_ms", 0))

                    d["g_img"].src    = cover;  d["g_title"].value  = title
                    d["g_artist"].value = artist
                    d["l_img"].src    = cover;  d["l_title"].value  = title
                    d["l_artist"].value = artist
                    d["l_album"].value  = album
                    d["l_dur"].value    = dur
                except Exception as ex: print(f"[meta] {d['fp']}: {ex}")
                if (i + 1) % BATCH == 0 or i == len(pending) - 1: page.update()

        threading.Thread(target=_load_meta, daemon=True).start()

    def go_back(e):
        if len(path_history) > 1:
            # ФИКС 1: Восстанавливаем режим просмотра, если мы уходим из истории
            if path_history[-1] == "db:history:None":
                set_view(previous_view_mode[0])
                
            path_history.pop() 
            prev_path = path_history[-1]
            if prev_path.startswith("db:"):
                parts = prev_path.split(":", 2) 
                load_db_view(parts[1], parts[2] if len(parts) > 2 and parts[2] != "None" else None, add_to_history=False)
            else:
                load_folder(prev_path, add_to_history=False)

    back_button = ft.IconButton(icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED, on_click=go_back, icon_size=16, visible=False)
    
    def toggle_sidebar_labels(is_collapsed):
        """Прячет текст и ЦЕНТРИРУЕТ иконки в сайдбаре."""
        try:
            # Если свернуто - центрируем. Если развернуто - прижимаем влево.
            align_mode = ft.MainAxisAlignment.CENTER if is_collapsed else ft.MainAxisAlignment.START
            
            menu_btns = [sidebar_home_tile, sidebar_artists_tile, sidebar_albums_tile, sidebar_search_tile, sidebar_history_tile, sidebar_settings_tile]
            for btn in menu_btns:
                if len(btn.content.controls) > 1:
                    btn.content.controls[1].visible = not is_collapsed
                    btn.content.alignment = align_mode  # <--- ФИКС ВЫРАВНИВАНИЯ
                    btn.content.update()
            
            if len(library_header.content.controls) > 1:
                library_header.content.controls[1].visible = not is_collapsed
                library_header.content.alignment = align_mode
                library_header.content.update()
            
            for pl_btn in playlists_container.controls:
                if isinstance(pl_btn, ft.Container) and hasattr(pl_btn.content, 'controls'):
                    if len(pl_btn.content.controls) >= 2:
                        pl_btn.content.controls[1].visible = not is_collapsed
                    if len(pl_btn.content.controls) >= 3:
                        pl_btn.content.controls[2].visible = not is_collapsed
                    pl_btn.content.alignment = align_mode  # <--- ФИКС ВЫРАВНИВАНИЯ
                    pl_btn.content.update()
                elif isinstance(pl_btn, ft.Text):
                    pl_btn.visible = not is_collapsed
                    pl_btn.update()
        except: pass

    track_grid = ft.GridView(expand=True, max_extent=200, child_aspect_ratio=0.75, spacing=20, run_spacing=20, visible=True)
    track_list = ft.Column(
        expand=True, 
        spacing=2, 
        visible=False, 
        scroll=ft.ScrollMode.ALWAYS # Создает жесткий Viewport, который не "отваливается"
    )
    current_folder_text = ft.Text("Твоя музыка", size=20, weight="bold", color="grey")
    
    greeting_text = ft.Text("Добрый день", size=32, weight="bold", expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)

    def handle_search_submit(query):
        query = query.strip()
        if not query: return
        
        # Проверяем, похоже ли это на команду для ИИ
        command_keywords = ["включи", "поставь", "сыграй", "волну", "диджей", "артист", "альбом"]
        is_command = any(w in query.lower() for w in command_keywords)
        
        if is_command:
            # Обманываем систему: искусственно подставляем слово-триггер (например, "астра включи волну")
            # и отправляем в уже готовую функцию голосового помощника!
            trigger = settings.get("voice_trigger", "астра")
            handle_voice_command(f"{trigger} {query}")
            
            # Очищаем поле поиска и возвращаемся на главную
            search_input.value = ""
            search_input.update()
            show_home_view() 
        else:
            # Если это не команда (например, "Kanye West"), делаем обычный текстовый поиск
            perform_search(query)
    
    search_input = ft.TextField(
        hint_text="Найти трек (по имени файла)...", prefix_icon=ft.Icons.SEARCH, expand=True, border_color="transparent",
        bgcolor="white10", border_radius=30, 
        on_submit=lambda e: handle_search_submit(e.control.value), # <--- ИСПРАВЛЕНИЕ ЗДЕСЬ
        on_change=lambda e: perform_search(e.control.value) if len(e.control.value) > 2 else clear_search(),
        on_focus=lambda _: (is_typing.__setitem__(0, True)),
        on_blur=lambda _: (is_typing.__setitem__(0, False)) 
    )
    
    search_results_list = ft.Column(expand=True, spacing=2, scroll=ft.ScrollMode.ALWAYS) # <--- Был ListView
    search_status_text = ft.Text("Введите запрос для поиска", color="grey", italic=True)

    # --- НОВАЯ ПЛАШКА ПОДСКАЗОК В ПОИСКЕ ---
    search_hints = ft.Container(
        content=ft.Column([
            ft.Text("💡 Как использовать поиск:", weight="bold", color="grey"),
            ft.Text("• Поиск по файлам: просто введите название трека, альбома или артиста.", size=12, color="grey"),
            ft.Text("• Умные команды (введите и нажмите Enter): 'включи волну', 'поставь Канье Уэста', 'включи альбом Yandhi', 'включи то, что я не слушал'.", size=12, color="grey"),
        ], spacing=4),
        padding=15,
        bgcolor="white10",
        border_radius=8,
        visible=True
    )

    play_all_btn = ft.FilledButton(
        "Включить всё",
        icon=ft.Icons.PLAY_ARROW_ROUNDED,
        style=ft.ButtonStyle(color="white", bgcolor="#1DB954"), # <--- Современный синтаксис Flet 0.84+
        on_click=lambda _: play_all_tracks()
    )

    # --- НОВАЯ КНОПКА ---
    ai_dj_btn = ft.FilledButton(
        "AI Диджей",
        icon=ft.Icons.AUTO_AWESOME,
        style=ft.ButtonStyle(color="white", bgcolor="#8A2BE2"), # Фиолетовый цвет для ИИ
        on_click=lambda _: page.run_task(show_ai_dj_dialog)
    )

    # Функция включения вайба
    def play_vibe(vibe_key):
        tracks = db.get_tracks_by_vibe(vibe_key)
        if tracks:
            import random
            random.shuffle(tracks)
            playlist.clear()
            playlist.extend(tracks)
            current_index[0] = 0
            select_track(playlist[0])
            show_snackbar(f"🌊 Настроение включено ({len(tracks)} треков)")
        

    is_vibes_open = [False]
    
    # Контейнер для кнопок (изначально пустой)
    vibes_panel_content = ft.Row(wrap=True, spacing=10, run_spacing=10)
    
    # Сама выезжающая панель
    vibes_panel = ft.Container(
        content=vibes_panel_content,
        height=0,      
        opacity=0,     
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        # ИСПРАВЛЕНО: убрали лишнее подчеркивание в FAST_OUT_SLOWIN
        animate_size=ft.Animation(500, ft.AnimationCurve.FAST_OUT_SLOWIN), 
        animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        padding=ft.Padding(0, 0, 0, 0)
    )

    home_view = ft.Column([
        # Добавили vibes_btn в ряд
        ft.Row([back_button, greeting_text, play_all_btn, ai_dj_btn, view_grid_btn, view_list_btn], vertical_alignment="center"),

        # Встроили нашу панель с анимацией
        vibes_panel, 
        
        current_folder_text, ft.Divider(height=20, color="transparent"),
        track_grid, track_list, lyrics_container,
    ], expand=True, visible=True)

    search_view = ft.Column([
        ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: show_home_view(), tooltip="На главную"), search_input], vertical_alignment="center"),
        ft.Divider(height=10, color="transparent"), 
        search_hints,         # <--- Вставили подсказки
        search_status_text, 
        search_results_list,
    ], expand=True, visible=False)

    main_content = ft.Container(
        content=ft.Stack([home_view, search_view, focus_view], expand=True),
        bgcolor="#121212", 
        border_radius=10, 
        padding=ft.Padding(left=30, top=30, right=30, bottom=0), 
        expand=True,
    )

    def show_home_view():
        search_view.visible = False
        home_view.visible = True
        page.update()

    def show_search_view():
        disable_karaoke()
        home_view.visible = False
        search_view.visible = True
        page.update()

    def clear_search():
        search_results_list.controls.clear()
        search_status_text.value = ""
        search_status_text.visible = False
        search_hints.visible = True # Показываем подсказки
        page.update()

    def perform_search(query):
        query = query.lower().strip()
        search_results_list.controls.clear()
        
        if not query:
            clear_search()
            return
            
        search_hints.visible = False # Прячем подсказки во время поиска
        search_status_text.value = f"Ищем: '{query}'..."
        search_status_text.visible = True
        page.update()

        def _run_search():
            results_db = db.search_tracks(query)
            results = [res for res in results_db if os.path.exists(res["file_path"])]

            search_results_list.controls.clear()

            if not results:
                search_status_text.value = "Ничего не найдено"
                search_hints.visible = True # Показываем подсказки, если ничего не нашли
                page.update()
                return

            search_status_text.visible = False
            
            current_view_tracks.clear()
            current_view_tracks.extend([res["file_path"] for res in results])

            is_light = is_app_light_mode[0]
            track_bgcolor = "#FFFFFF" if is_light else "transparent"
            track_hover_color = "#F0F0F0" if is_light else "#1e1e1e"

            for idx, res in enumerate(results, 1):
                full_path = res["file_path"]
                title = res["title"]
                artist = res["artist"]
                cover_src = res["cover_path"] or "https://via.placeholder.com/150"
                
                l_img = ft.Image(src=cover_src, width=44, height=44, border_radius=4, fit="cover")
                l_title = ft.Text(title, weight="bold", size=14, max_lines=1, overflow="ellipsis")
                l_artist = ft.Text(artist, size=10, color="grey", max_lines=1, overflow="ellipsis")
                
                item_row = ft.Container(
                    content=ft.Row([
                        ft.Text(str(idx), width=32, color="grey", size=12, text_align="right"), ft.Container(width=10),
                        l_img, ft.Container(width=10), ft.Column([l_title, l_artist], spacing=2, expand=True),
                        ft.PopupMenuButton(
                            icon=ft.Icons.MORE_VERT, icon_size=16, icon_color="grey",
                            items=[
                                ft.PopupMenuItem(content="Добавить в плейлист", on_click=lambda _, fp=full_path: add_to_playlist(fp)),
                                ft.PopupMenuItem(content="Информация", on_click=lambda _, fp=full_path: show_track_info(fp)),
                            ]
                        )
                    ], vertical_alignment="center"),
                    padding=ft.Padding(10, 6, 10, 6), border_radius=6, bgcolor=track_bgcolor,
                    on_click=lambda e, p=full_path: select_track(p),
                    on_hover=lambda e: setattr(e.control, "bgcolor", track_hover_color if e.data == "true" else track_bgcolor) or e.control.update(),
                )
                search_results_list.controls.append(item_row)

            page.update()

        threading.Thread(target=_run_search, daemon=True).start()

    def play_all_tracks():
        all_files = []
        audio_exts = (".mp3", ".flac", ".wav", ".m4a")
        for folder in settings.get("music_folders", []):
            if not os.path.exists(folder): continue
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(audio_exts):
                        all_files.append(os.path.join(root, file))
        
        if not all_files:
            show_snackbar("Медиатека пуста!")
            return
            
        current_view_tracks.clear()
        current_view_tracks.extend(all_files)
        
        # Если включен шаффл - выбираем случайный стартовый трек, иначе первый
        start_track = random.choice(all_files) if shuffle_mode[0] else all_files[0]
        select_track(start_track)
        show_snackbar(f"Включаю всё ({len(all_files)} треков)")

    def on_keyboard(e: ft.KeyboardEvent):
        if is_typing[0]:
            return
        if e.key == " " and not e.shift and not e.ctrl: toggle_play()
        elif e.key == "Arrow Right" and e.ctrl: play_next()
        elif e.key == "Arrow Left" and e.ctrl: play_prev()
        elif e.key.lower() == "f" and not e.ctrl: toggle_focus()
        elif e.key.lower() == "l" and not e.ctrl: toggle_karaoke()
        elif e.key.lower() == "q" and not e.ctrl: toggle_right_panel_view()
        elif e.key == "Escape" and is_focus_mode[0]: toggle_focus()

    page.on_keyboard_event = on_keyboard

    # 1. Собираем рабочую область (горизонтальный ряд: сайдбар + контент + очередь)
    workspace = ft.Row([sidebar, left_divider, main_content, right_divider, right_panel], expand=True, spacing=0)
    
    # 2. Оживляем переменную main_row, чтобы горячие клавиши не выдавали ошибку
    main_row = workspace 

    # === МАСТЕР ПЕРВОЙ НАСТРОЙКИ (WIZARD) ===
    first_run_folder_val = ft.TextField(value=get_default_music_path(), expand=True, label="Папка с музыкой", border_color="#1DB954", color="white")
    first_run_theme_rg = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="dark", label="Тёмная", fill_color="#1DB954"),
            ft.Radio(value="light", label="Светлая", fill_color="#1DB954")
        ], alignment=ft.MainAxisAlignment.CENTER),
        value="dark",
        on_change=lambda e: apply_theme(e.control.value, show_toast=False, animate_transition=True)
    )

    async def open_first_run_folder(_):
        path = await get_directory_path_async(dialog_title="Выберите папку с вашей музыкой")
        
        # Если пользователь не нажал "Отмена" и выбрал путь
        if path:
            first_run_folder_val.value = path
            first_run_folder_val.update()
            print(f"[Audaci] Выбрана новая директория: {path}")

    def finish_first_run(_):
        async def _fade_out():
            settings["music_folders"] = [first_run_folder_val.value]
            settings["theme_mode"] = first_run_theme_rg.value
            save_settings()

            apply_theme(first_run_theme_rg.value, show_toast=False, animate_transition=False)
            
            music_path_ref[0] = first_run_folder_val.value
            path_history.clear()
            path_history.append(music_path_ref[0])
            load_folder(music_path_ref[0], add_to_history=False)
            page.run_task(scan_library_async)
            # Плавное растворение без фризов
            first_run_view.opacity = 0
            first_run_view.update()
            await asyncio.sleep(0.5) 
            first_run_view.visible = False
            first_run_view.update()
            page.update()
            
        # Передаем саму асинхронную функцию
        page.run_task(_fade_out)

   

    first_run_view = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.LIBRARY_MUSIC, size=80, color="#1DB954"),
            ft.Text("Добро пожаловать в Audaci", size=36, weight="bold", color="white"),
            ft.Text("Давай подготовим плеер к работе.", size=16, color="white54"),
            ft.Divider(height=30, color="transparent"),
            
            ft.Container(
                content=ft.Column([
                    ft.Text("1. Укажи основную папку с музыкой:", size=16, weight="bold", color="white"),
                    ft.Row([
                        first_run_folder_val,
                        ft.IconButton(ft.Icons.FOLDER_OPEN, icon_color="white", bgcolor="white10", tooltip="Выбрать", on_click=open_first_run_folder)
                    ]),
                    ft.Divider(height=20, color="transparent"),
                    ft.Text("2. Выбери тему оформления:", size=16, weight="bold", color="white"),
                    first_run_theme_rg,
                ]),
                width=500, padding=30, bgcolor="#1e1e1e", border_radius=15
            ),
            
            ft.Divider(height=30, color="transparent"),
            ft.FilledButton("Начать слушать", icon=ft.Icons.ROCKET_LAUNCH, style=ft.ButtonStyle(bgcolor="#1DB954", color="white", padding=20), on_click=finish_first_run)
            
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
        expand=True, bgcolor="#121212",
        visible=is_first_run, # Показываем только если нет файла настроек
        animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT)
    )

    # 3. Собираем финальный "пирог"
    page.add(
        ft.Stack([
            ft.Column([
                workspace,          # Верхний этаж (контент)
                player_control_bar  # Нижний этаж (плеер прибит к низу)
            ], expand=True, spacing=0),
            settings_page,
            first_run_view
        ], expand=True)
    )
    def on_resize(e):
        try:
            # 1. Берем внутренний размер холста (он точнее и быстрее, чем рамки окна Астры)
            w = page.width if page.width else (page.window.width or 1050)
            h = page.height if page.height else (page.window.height or 700)
            
            is_small = w < 950 
            is_small_screen[0] = is_small
            
            if not is_focus_mode[0]:
                right_panel.visible = not is_small
                right_divider.visible = not is_small
                left_divider.visible = not is_small
            
            # 2. ЖЕЛЕЗОБЕТОННАЯ ЗАЩИТА: Выключаем очередь, если открыт текст на малом экране
            if is_small and karaoke_mode[0] and is_queue_active[0]:
                is_queue_active[0] = False
                focus_queue_container.visible = False
                focus_queue_container.opacity = 0
                try:
                    focus_queue_btn.icon_color = "white70"
                    queue_btn.icon_color = "grey"
                except: pass

            # 3. УМНЫЙ РАЗМЕР ОБЛОЖКИ (Спасаем кнопки от исчезновения)
            panels_w = 0
            if is_focus_mode[0]:
                if karaoke_mode[0]: panels_w += LYRICS_WIDTH
                if is_queue_active[0]: panels_w += QUEUE_WIDTH

            # Считаем, сколько места осталось с учетом боковых панелей и нижних кнопок
            avail_w = max(100, w - panels_w - 60)
            avail_h = max(100, h - 300)

            # Обложка будет квадратом по минимальному доступному значению
            safe_size = min(400, avail_w, avail_h)
            focus_cover.width = safe_size
            focus_cover.height = safe_size
            
            # ФИКС 2: Жестко задаем ширину центральной колонки. 
            # Теперь она будет стоять ровно по центру рядом с текстом!
            focus_main_col.width = max(350, safe_size + 60)
            
            # 4. Адаптивность текста и плеера
            if is_small:
                greeting_text.size = 20
                sidebar.width = 70
                toggle_sidebar_labels(True)
                
                focus_title.size = 24
                focus_artist.size = 16
                
                if not is_focus_mode[0]:
                    player_control_bar.height = 145 
                    player_control_bar.padding = ft.Padding(left=15, top=5, right=15, bottom=5) 
                    
                    player_left_block.expand = True
                    player_center_block.expand = False
                    player_right_block.expand = False
                    player_right_block.width = None 
                    
                    player_row_wide.controls.clear()
                    player_top_small.controls = [player_left_block, player_right_block]
                    
                    player_col_small.alignment = ft.MainAxisAlignment.END
                    player_col_small.spacing = 0 
                    player_col_small.controls = [player_top_small, player_center_block]
                    
                    player_control_bar.content = player_col_small
            else:
                greeting_text.size = 32
                sidebar.width = 250
                toggle_sidebar_labels(False)

                focus_title.size = 36
                focus_artist.size = 20
                
                if not is_focus_mode[0]:
                    player_control_bar.height = 90
                    player_control_bar.padding = ft.Padding(left=20, top=5, right=20, bottom=5)
                    
                    player_left_block.expand = 1
                    player_center_block.expand = 2
                    player_right_block.expand = 1
                    player_right_block.width = None
                    
                    player_top_small.controls.clear()
                    player_col_small.controls.clear()
                    player_row_wide.controls = [player_left_block, player_center_block, player_right_block]
                    player_control_bar.content = player_row_wide
            
            page.update()
        except Exception as ex: 
            print(f"Ошибка ресайза: {ex}")
    
    page.on_resize = on_resize
    try: on_resize(None)
    except: pass 
    
    is_light = settings["theme_mode"] == "light"
    sidebar_bgcolor = "#FFFFFF" if is_light else "#121212"
    
    if settings["theme_mode"] == "dark":
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#121212"
    elif settings["theme_mode"] == "light":
        page.theme_mode = ft.ThemeMode.LIGHT
        page.bgcolor = "#FFFFFF"
    else:
        page.theme_mode = ft.ThemeMode.SYSTEM
    
    page.update() 
    
    sidebar.content.bgcolor = sidebar_bgcolor
    playlists_container.bgcolor = sidebar_bgcolor
    sidebar.update()
    
# Сначала применяем тему, а уже потом рисуем папки и боковое меню!
    apply_theme(settings["theme_mode"], show_toast=False)
    load_folder(music_path_ref[0])
    update_playlist_sidebar() 

    # --- ЗАПУСК ТЕЛЕГРАМ БОТА ---
    def run_bot_async(music_dir):
        try:
            bot_instance = AudaciBot(music_dir)
            asyncio.run(bot_instance.start())
        except Exception as e:
            print(f"[Audaci Bot] Ошибка запуска: {e}")

    # Запускаем в отдельном потоке, чтобы не блокировать GUI
    bot_thread = threading.Thread(
        target=run_bot_async, 
        args=(music_path_ref[0],), 
        daemon=True
    )
    bot_thread.start()
    print(f"[Audaci Bot] Бот запущен в фоновом режиме. Музыка: {music_path_ref[0]}")

    # --- ЗАПУСК API СЕРВЕРА ---
    def run_api():
        try:
            start_api(audio, state, port=8000)
        except Exception as e:
            print(f"[Audaci API] Ошибка запуска: {e}")

    threading.Thread(target=run_api, daemon=True).start()
    print(f"[Audaci API] Сервер запущен на http://0.0.0.0:8000")

if tray_icon is not None:
    threading.Thread(target=tray_icon.run, daemon=True).start()


if __name__ == "__main__":
    ft.run(main, assets_dir=assets_dir)