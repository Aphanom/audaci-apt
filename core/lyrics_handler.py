import requests
import json

def fetch_synced_lyrics(artist, title, duration_s):
    """Получает синхронизированный текст с LRCLIB"""
    url = "https://lrclib.net/api/get"
    params = {
        "artist_name": artist,
        "track_name": title,
        "duration": int(duration_s)
    }
    try:
        # Увеличили таймаут до 10 секунд, сервер иногда отвечает не сразу
        response = requests.get(url, params=params, timeout=10)
        
        # ИСПРАВЛЕНО: status_code вместо status_status
        if response.status_code == 200:
            data = response.json()
            # Нас интересует поле syncedLyrics
            return data.get("syncedLyrics")
        elif response.status_code == 404:
            print(f"Текст для трека '{artist} - {title}' не найден в базе LRCLIB.")
        else:
            print(f"LRCLIB вернул код ошибки: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"Превышено время ожидания (таймаут) при поиске текста для '{title}'.")
    except Exception as e:
        print(f"Ошибка получения текста: {e}")
        
    return None

def parse_lrc(lrc_string):
    """Парсит LRC строку в список [ (time_ms, text), ... ]"""
    if not lrc_string: return []
    lines = []
    for line in lrc_string.split('\n'):
        if not line.startswith('['): continue
        try:
            # Формат: [mm:ss.xx] Text
            time_part, text = line.split(']', 1)
            time_str = time_part[1:] # убираем '['
            m, s = time_str.split(':')
            ms = int((float(m) * 60 + float(s)) * 1000)
            lines.append((ms, text.strip()))
        except: continue
    return sorted(lines, key=lambda x: x[0])