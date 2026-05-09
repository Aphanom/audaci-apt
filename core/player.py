import vlc
import time
from pathlib import Path
import subprocess

class AudioPlayer:
    def __init__(self, normalize=False):
        # 1. Формируем аргументы для движка VLC
        vlc_args = []
        if normalize:
            # Включаем аудио фильтр нормализации громкости (normvol)
            # norm-buff-size отвечает за окно анализа, norm-max-level за порог
            vlc_args.extend(["--audio-filter=normvol", "--norm-buff-size=2.0", "--norm-max-level=1.0"])

        # 2. Инициализируем инстанс и сам плеер
        # Используем распаковку *vlc_args, так VLC надежнее читает параметры
        if vlc_args:
            self.instance = vlc.Instance(*vlc_args)
        else:
            self.instance = vlc.Instance()
            
        self.player = self.instance.media_player_new()

        # 3. Базовые переменные состояния
        self.current_track_path = None
        self._current_volume = 50
        self.player.audio_set_volume(self._current_volume)

        # 4. Подготовка эквалайзера (VLC имеет встроенный 10-полосный эквалайзер)
        self.equalizer = vlc.AudioEqualizer()
        self.eq_enabled = False

    def load(self, file_path: str | Path):
        """Загружает аудиофайл в плеер"""
        # Используем pathlib для абсолютной совместимости macOS <-> Linux
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {path}")

        self.current_track_path = path
        media = self.instance.media_new(str(path))
        self.player.set_media(media)

    def play(self):
        """Запускает воспроизведение"""
        if self.player.get_media() is not None:
            self.player.play()

    def pause(self):
        """Ставит на паузу"""
        self.player.pause()

    def stop(self):
        """Останавливает воспроизведение"""
        self.player.stop()

    def toggle_play_pause(self):
        """Переключает состояние: Play / Pause"""
        if self.player.is_playing():
            self.pause()
        else:
            self.play()

    def set_volume(self, volume: int):
        """Устанавливает громкость (от 0 до 100)"""
        # VLC поддерживает громкость больше 100 (до 256), 
        # но для UI обычно удобнее лимит в 100%
        self.player.audio_set_volume(max(0, min(volume, 100)))

    def get_volume(self) -> int:
        """Возвращает текущую громкость"""
        return self.player.audio_get_volume()

    def get_time(self) -> int:
        """Текущее время воспроизведения в миллисекундах"""
        return self.player.get_time()

    def get_length(self) -> int:
        """
        Общая длина трека в миллисекундах. 
        Важно: VLC вычисляет длину асинхронно. Сразу после load() и play() 
        может вернуть -1 или 0. Нужно немного подождать.
        """
        return self.player.get_length()

    def set_time(self, time_ms: int):
        """Перемотка на указанное время (в миллисекундах)"""
        self.player.set_time(time_ms)

    def get_position(self) -> float:
        """Возвращает позицию трека от 0.0 до 1.0"""
        total = self.get_length()
        current = self.get_time()
        if total > 0 and current >= 0:
            return current / total
        return 0.0

    def seek(self, position: float):
        """Перемотка (position от 0.0 до 1.0)"""
        total = self.get_length()
        if total > 0:
            self.set_time(int(total * position))
    
    def get_audio_devices(self) -> dict:
        """Получает список аудиоустройств напрямую от VLC (чтобы получить правильные ID)"""
        devices = {}
        try:
            # Спрашиваем у плеера, какие выходы он видит
            dev_list = self.player.audio_output_device_enum()
            if dev_list:
                current = dev_list
                while current:
                    item = current.contents
                    # Получаем внутренний ID (для переключения) и Описание (для UI)
                    dev_id = item.device.decode('utf-8') if item.device else "default"
                    dev_desc = item.description.decode('utf-8') if item.description else "Неизвестно"
                    
                    devices[dev_id] = dev_desc
                    current = item.next
                
                # Обязательно освобождаем память, выделенную сишной библиотекой
                vlc.libvlc_audio_output_device_list_release(dev_list)
        except Exception as e:
            print(f"Ошибка при получении устройств от VLC: {e}")
            
        if not devices:
            devices["default"] = "По умолчанию (системное)"
            
        return devices
        
    def set_output_device(self, device_id: str):
        """Меняет устройство вывода 'на лету'."""
        try:
            self.player.audio_output_device_set(None, device_id.encode('utf-8'))
        except Exception as e:
            print(f"Ошибка смены аудиоустройства: {e}")


    # === НОВЫЕ МЕТОДЫ ДЛЯ ЭКВАЛАЙЗЕРА (добавь их в класс AudioPlayer) ===
    def enable_equalizer(self, enable: bool):
        """Включает или выключает эквалайзер"""
        self.eq_enabled = enable
        # Если включено - передаем объект эквалайзера, если выключено - None
        self.player.set_equalizer(self.equalizer if enable else None)

    def set_eq_band(self, index: int, amp: float):
        """
        Устанавливает значение полосы.
        index: 0-9 (соответствует частотам от 32Hz до 16kHz)
        amp: от -20.0 до 20.0 децибел
        """
        self.equalizer.set_amp_at_index(amp, index)
        # Применяем изменения "на лету", если эквалайзер включен
        if self.eq_enabled:
            self.player.set_equalizer(self.equalizer)
            
    def apply_eq_settings(self, bands: list, enabled: bool):
        """Загружает сохраненные настройки из JSON при запуске плеера"""
        for i, amp in enumerate(bands):
            self.equalizer.set_amp_at_index(amp, i)
        self.enable_equalizer(enabled)

    def set_normalization(self, enabled: bool):
        """Включает или выключает встроенный фильтр нормализации громкости VLC."""
        if not self.player:
            return

        # Получаем текущие аудио фильтры
        filters = self.player.audio_get_format()

        # В VLC управление фильтрами через Python API ограничено, 
        # но мы можем передать аргументы при инициализации инстанса.
        # Поэтому динамическое переключение фильтров сложно.
        # 
        # САМЫЙ НАДЕЖНЫЙ СПОСОБ ДЛЯ Python-VLC:
        # Управлять этим через параметры командной строки при создании vlc.Instance.
        pass

# ==========================================
# Блок для тестирования класса прямо в терминале
# ==========================================
if __name__ == "__main__":
    # Замени на путь к любому реальному mp3 файлу на твоем Маке
    TEST_FILE = "Ye - COUSINS.mp3" 
    
    try:
        print("Инициализация плеера...")
        player = AudioPlayer()
        
        print(f"Загрузка {TEST_FILE}...")
        player.load(TEST_FILE)
        
        print("Воспроизведение (громкость 70%)...")
        player.set_volume(70)
        player.play()
        
        # Ждем секунду, чтобы VLC успел подгрузить метаданные файла
        time.sleep(1) 
        
        length_ms = player.get_length()
        print(f"Длина трека: {length_ms / 1000} секунд")
        
        # Имитируем прослушивание (играем 5 секунд)
        for i in range(5):
            print(f"Текущая позиция: {player.get_time() / 1000} сек")
            time.sleep(1)
            
        print("Пауза на 2 секунды...")
        player.pause()
        time.sleep(2)
        
        print("Снова плей и перемотка на 30-ю секунду...")
        player.play()
        player.set_time(30000)
        time.sleep(3)
        
        print("Стоп.")
        player.stop()

    except FileNotFoundError as e:
        print(e)
        print("Создай или скачай mp3 файл с таким именем в папку со скриптом для теста.")