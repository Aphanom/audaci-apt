import requests
import aiohttp
import asyncio

API_KEY = "d0f09e818ba58229da96d69c73328e39"

def fetch_mood_from_web(artist, title):
    """Запрашивает теги трека у Last.fm (синхронно)."""
    if not artist or not title or artist == "Неизвестен":
        return ""
        
    try:
        artist = artist.strip()
        title = title.strip()
        url = f"http://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={artist}&track={title}&api_key={API_KEY}&format=json"
        response = requests.get(url, timeout=3).json()
        
        if 'toptags' in response and 'tag' in response['toptags']:
            tags = [t['name'].lower() for t in response['toptags']['tag'][:7]]
            return ", ".join(tags)
    except Exception as e:
        print(f"Ошибка получения тегов (sync) для {artist} - {title}: {e}")
    return ""

async def fetch_mood_from_web_async(artist, title):
    """Запрашивает теги трека у Last.fm (асинхронно)."""
    if not artist or not title or artist == "Неизвестен":
        return ""
        
    try:
        artist = artist.strip()
        title = title.strip()
        url = f"http://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={artist}&track={title}&api_key={API_KEY}&format=json"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'toptags' in data and 'tag' in data['toptags']:
                            tags = [t['name'].lower() for t in data['toptags']['tag'][:7]]
                            return ", ".join(tags)
                    else:
                        print(f"HTTP Error {response.status} for {artist} - {title}")
            except asyncio.TimeoutError:
                print(f"Timeout fetching tags for {artist} - {title}")
    except Exception as e:
        print(f"Ошибка получения тегов (async) для {artist} - {title}: {e}")
        
    return ""