import requests

API_KEY = "d0f09e818ba58229da96d69c73328e39"

def fetch_mood_from_web(artist, title):
    """Запрашивает теги трека у Last.fm, чтобы понять его настроение."""
    if not artist or not title or artist == "Неизвестен":
        return ""
        
    try:
        # Убираем лишние пробелы и символы
        artist = artist.strip()
        title = title.strip()
        
        url = f"http://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={artist}&track={title}&api_key={API_KEY}&format=json"
        
        # Ставим таймаут 3 секунды, чтобы плеер не завис, если интернет пропадет
        response = requests.get(url, timeout=3).json()
        
        if 'toptags' in response and 'tag' in response['toptags']:
            # Берем первые 7 самых популярных тегов (они обычно описывают жанр и настроение)
            tags = [t['name'].lower() for t in response['toptags']['tag'][:7]]
            return ", ".join(tags)
    except Exception as e:
        print(f"Ошибка получения тегов для {artist} - {title}: {e}")
        
    return ""