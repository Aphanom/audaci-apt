import os
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import json

class VoiceController:
    def __init__(self, model_path="model"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Папка модели '{model_path}' не найдена!")
        
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.queue = queue.Queue()
        self.is_running = True  # Флаг для остановки цикла прослушивания

    def callback(self, indata, frames, time, status):
        """Добавляет аудиоданные из микрофона в очередь"""
        self.queue.put(bytes(indata))

    def listen(self, callback_func):
        """
        Запускает бесконечный цикл прослушивания.
        callback_func — функция, которая будет вызываться при распознавании команды.
        """
        # Настройки микрофона (частота 16кГц — стандарт для Vosk)
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                               channels=1, callback=self.callback):
            print("Слушаю команды...")
            while self.is_running:
                try:
                    data = self.queue.get(timeout=0.5)  # Таймаут для проверки флага is_running
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "")
                        if text:
                            print(f"Распознано: {text}")
                            callback_func(text)
                except queue.Empty:
                    continue  # Таймаут истёк, проверяем флаг и продолжаем
    
    def stop(self):
        """Останавливает прослушивание"""
        self.is_running = False
        print("Голосовой помощник остановлен")


class VoiceCommandHandler:
    """Обработчик голосовых команд для плеера"""
    
    # Словари команд для быстрого поиска
    COMMANDS = {
        'play': ['играй', 'продолжи', 'play', 'start'],
        'pause': ['пауз', 'стоп', 'хватит', 'pause', 'stop'],
        'next': ['дальше', 'следующий', 'далее', 'вперед', 'вперёд', 'next', 'skip'],
        'prev': ['назад', 'предыдущий', 'вернись', 'back', 'previous', 'prev'],
        'louder': ['громче', 'увеличи', 'прибавь', 'погромче', 'louder', 'up'],
        'quieter': ['тише', 'убавь', 'уменьши', 'потише', 'quieter', 'down'],
        'shuffle': ['перемешай', 'перемешивание', 'shuffle', 'случайный', 'в случайном'],
        'repeat': ['повтор', 'повторяй', 'repeat', 'заново'],
        'grid': ['сетка', 'grid', 'карточки'],
        'list': ['список', 'list', 'лист'],
    }
    
    def __init__(self, voice_feedback=True, wake_word='астра'):
        """
        Инициализация обработчика команд
        
        Args:
            voice_feedback: включить ли голосовой отклик
            wake_word: ключевое слово для активации (по умолчанию 'астра')
        """
        self.voice_feedback = voice_feedback
        self.callbacks = {}
        self.wake_word = wake_word.lower()
        self.wake_word_enabled = True
    
    def register_callback(self, command, callback):
        """
        Регистрирует callback функцию для команды
        
        Args:
            command: строка команды (например 'play', 'pause', 'next')
            callback: функция, которую нужно вызвать при выполнении команды
        """
        self.callbacks[command] = callback
    
    def set_feedback_enabled(self, enabled):
        """Включить/отключить голосовой отклик"""
        self.voice_feedback = enabled
    
    def set_wake_word(self, wake_word):
        """Устанавливает новое ключевое слово активации"""
        self.wake_word = wake_word.lower().strip()
    
    def set_wake_word_enabled(self, enabled):
        """Включить/отключить проверку ключевого слова"""
        self.wake_word_enabled = enabled
    
    def check_wake_word(self, text):
        """
        Проверяет наличие ключевого слова в тексте
        
        Args:
            text: распознанный текст
        
        Returns:
            кортеж (has_wake_word, command_text)
            - has_wake_word: найдено ли ключевое слово
            - command_text: текст команды после ключевого слова
        """
        text_lower = text.lower().strip()
        
        # Если проверка ключевого слова отключена, обрабатываем весь текст
        if not self.wake_word_enabled:
            return True, text
        
        # Ищем ключевое слово в тексте
        if self.wake_word in text_lower:
            # Находим позицию ключевого слова
            wake_word_pos = text_lower.find(self.wake_word)
            # Извлекаем текст после ключевого слова
            command_text = text[wake_word_pos + len(self.wake_word):].strip()
            return True, command_text
        
        return False, ""
    
    def parse_command(self, text):
        """
        Парсит текст и определяет команду
        
        Args:
            text: распознанный текст от пользователя
        
        Returns:
            кортеж (command_name, confidence_level)
        """
        text_lower = text.lower().strip()
        
        # Ищем совпадение с командами
        for command_name, keywords in self.COMMANDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return command_name, True
        
        return None, False
    
    def execute_command(self, command_name, params=None):
        """
        Выполняет команду
        
        Args:
            command_name: имя команды
            params: дополнительные параметры для команды
        """
        if command_name in self.callbacks:
            try:
                if params:
                    self.callbacks[command_name](**params)
                else:
                    self.callbacks[command_name]()
                return True
            except Exception as e:
                print(f"Ошибка при выполнении команды '{command_name}': {e}")
                return False
        return False
    
    def handle_command(self, text):
        """
        Главный обработчик голосовой команды
        
        Args:
            text: распознанный текст от пользователя
        
        Returns:
            информация о выполненной команде
        """
        command_name, recognized = self.parse_command(text)
        
        if not recognized:
            return {
                'success': False,
                'command': None,
                'message': f'Команда не распознана: "{text}"'
            }
        
        # Выполняем команду
        success = self.execute_command(command_name)
        
        # Определяем сообщение обратной связи
        messages = {
            'play': '▶ Воспроизведение',
            'pause': '⏸ Пауза',
            'next': '⏭ Следующий трек',
            'prev': '⏮ Предыдущий трек',
            'louder': '🔊 Громче',
            'quieter': '🔉 Тише',
            'shuffle': '🔀 Перемешивание',
            'repeat': '🔁 Повтор',
            'grid': '📊 Режим сетки',
            'list': '📋 Режим списка',
        }
        
        return {
            'success': success,
            'command': command_name,
            'message': messages.get(command_name, f'Команда: {command_name}'),
            'text': text
        }
