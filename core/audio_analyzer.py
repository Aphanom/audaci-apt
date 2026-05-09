import librosa
import numpy as np
import warnings

def analyze_vibe(file_path):
    # Игнорируем предупреждения о старых методах librosa
    warnings.filterwarnings('ignore', category=FutureWarning)
    
    try:
        # Сначала просто узнаем длительность
        duration = librosa.get_duration(path=file_path)
        
        # Если трек короче 30 секунд, анализируем его с самого начала
        # Если длиннее — берем кусок из середины
        offset = 0 if duration < 35 else (duration / 2) - 15
        
        y, sr = librosa.load(file_path, duration=20, offset=offset)
        
        # Если файл оказался пустым или не прочитался
        if len(y) == 0:
            return 120.0, 0.05

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        energy = np.mean(librosa.feature.rms(y=y))
        
        return float(tempo), float(energy)
    except Exception as e:
        print(f"Ошибка анализа звука {file_path}: {e}")
        return 120.0, 0.05