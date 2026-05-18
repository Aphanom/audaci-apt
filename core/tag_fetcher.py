import requests
import aiohttp
import asyncio

import os

API_KEY = os.getenv("LASTFM_API_KEY", "d0f09e818ba58229da96d69c73328e39")


def fetch_mood_from_web(artist, title):
    """Запрашивает теги трека у Last.fm (синхронно)."""
    if not artist or not title or artist == "Неизвестен":
        return ""
        
    try:
        artist = artist.strip()
        title = title.strip()
        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.gettoptags",
            "artist": artist,
            "track": title,
            "api_key": API_KEY,
            "format": "json"
        }
        headers = {'User-Agent': 'AudaciPlayer/1.0'}
        response = requests.get(url, params=params, headers=headers, timeout=3).json()
        
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
        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.gettoptags",
            "artist": artist,
            "track": title,
            "api_key": API_KEY,
            "format": "json"
        }
        headers = {'User-Agent': 'AudaciPlayer/1.0'}
        
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=3)) as response:
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


async def fetch_cover_from_web_async(artist, title):
    """Запрашивает обложку трека у Last.fm (асинхронно) и возвращает её байты."""
    if not artist or not title or artist == "Неизвестен" or artist == "Неизвестный исполнитель":
        return None
        
    try:
        artist = artist.strip()
        title = title.strip()
        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "artist": artist,
            "track": title,
            "api_key": API_KEY,
            "format": "json"
        }
        headers = {'User-Agent': 'AudaciPlayer/1.0'}
        
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=4)) as response:
                    if response.status == 200:
                        data = await response.json()
                        track_data = data.get("track", {})
                        album_data = track_data.get("album", {})
                        images = album_data.get("image", [])
                        img_url = None
                        for img in reversed(images):
                            if img.get("#text"):
                                img_url = img["#text"]
                                break
                        if img_url:
                            async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=5)) as img_resp:
                                if img_resp.status == 200:
                                    return await img_resp.read()
                    else:
                        print(f"HTTP Error {response.status} fetching cover for {artist} - {title}")
            except asyncio.TimeoutError:
                print(f"Timeout fetching cover for {artist} - {title}")
    except Exception as e:
        print(f"Ошибка получения обложки (async) для {artist} - {title}: {e}")
        
    return None