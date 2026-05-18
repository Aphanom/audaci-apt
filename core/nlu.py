import re

RAPIDFUZZ_AVAILABLE = False
try:
    from rapidfuzz import process, fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    pass

import core.db as db

# Словарь жестких галлюцинаций для артистов
ARTIST_ALIASES = {
    "ткань мост": "Kanye West", 
    "канье": "Kanye West"
}

# Словарь жестких галлюцинаций для альбомов
ALBUM_ALIASES = {
    "яндекс": "Yandhi", 
    "були": "BULLY", 
    "булли": "BULLY"
}

def to_cyrillic_slug(text):
    if not text: return ""
    text = text.lower()
    complex_sounds = {'sh': 'ш', 'ch': 'ч', 'th': 'т', 'ph': 'ф', 'oo': 'у', 'ee': 'и', 'ck': 'к', 'ya': 'я', 'yu': 'ю'}
    for eng, rus in complex_sounds.items(): text = text.replace(eng, rus)
    replacements = {'a':'а', 'b':'б', 'c':'к', 'd':'д', 'e':'е', 'f':'ф', 'g':'г', 'h':'х', 'i':'и', 'j':'дж', 'k':'к', 'l':'л', 'm':'м', 'n':'н', 'o':'о', 'p':'п', 'q':'к', 'r':'р', 's':'с', 't':'т', 'u':'у', 'v':'в', 'w':'в', 'x':'кс', 'y':'й', 'z':'з'}
    for eng, rus in replacements.items(): text = text.replace(eng, rus)
    return text

def analyze_intent(text):
    text = text.lower().strip()
    
    # 1. ВОЛНА ИЛИ НОВОЕ
    unplayed_triggers = ["не слушал", "что-то новое", "новую музыку", "ни разу не"]
    if any(trigger in text for trigger in unplayed_triggers):
        return {"intent": "play_unplayed", "entity": None}

    wave_triggers = ["волну", "режим волны", "диджей", "ai dj", "умный плейлист", "поток"]
    if any(trigger in text for trigger in wave_triggers):
        return {"intent": "play_wave", "entity": None}

    # 2. АЛЬБОМ
    album_match = re.search(r'(?:включи|включить|поставь|включай)\s+альбом\s+(.*)', text)
    if album_match:
        target = album_match.group(1).strip()
        if RAPIDFUZZ_AVAILABLE:
            for alias, real_name in ALBUM_ALIASES.items():
                if fuzz.ratio(target, alias) > 80: 
                    return {"intent": "play_album", "entity": real_name}
            
            all_albums = db.get_all_albums()
            if all_albums:
                phonetic_albums = {to_cyrillic_slug(a["album"]): a["album"] for a in all_albums}
                best_match = process.extractOne(target, phonetic_albums.keys(), scorer=fuzz.WRatio)
                if best_match and best_match[1] > 70:
                    return {"intent": "play_album", "entity": phonetic_albums[best_match[0]]}
        else:
            # Простой фолбэк при отсутствии rapidfuzz
            for alias, real_name in ALBUM_ALIASES.items():
                if target in alias or alias in target:
                    return {"intent": "play_album", "entity": real_name}
        return {"intent": "play_album", "entity": target}

    # 3. АРТИСТ
    artist_match = re.search(r'(?:включи|включить|поставь|врубай|включай)\s+(?:артиста\s+|группу\s+)?(.*)', text)
    if artist_match:
        target = artist_match.group(1).strip()
        # Если в фразе есть "песню", значит это не артист, пропускаем дальше
        if "песню" not in target and "трек" not in target:
            if RAPIDFUZZ_AVAILABLE:
                for alias, real_name in ARTIST_ALIASES.items():
                    if fuzz.ratio(target, alias) > 80: 
                        return {"intent": "play_artist", "entity": real_name}
                
                all_artists = db.get_all_artists()
                if all_artists and target:
                    phonetic_artists = {to_cyrillic_slug(artist): artist for artist in all_artists}
                    best_match = process.extractOne(target, phonetic_artists.keys(), scorer=fuzz.WRatio)
                    if best_match and best_match[1] > 70:
                        return {"intent": "play_artist", "entity": phonetic_artists[best_match[0]]}
            else:
                for alias, real_name in ARTIST_ALIASES.items():
                    if target in alias or alias in target:
                        return {"intent": "play_artist", "entity": real_name}
                return {"intent": "play_artist", "entity": target}

    # 4. ПЕСНЯ / ТРЕК (С автокоррекцией твоих треков из логов!)
    search_match = re.search(r'(?:песню|трек)\s+(.*)', text)
    if search_match:
        target = search_match.group(1).strip()
        if "кинг" in target: target = "KING"
        if "сайт" in target or "слайда" in target: target = "SLIDE"
        if "фазер" in target: target = "FATHER"
        if "изабелла" in target: target = "ISABELLA"
        return {"intent": "search", "entity": target}

    # 5. ЕСЛИ НИЧЕГО НЕ ПОДОШЛО - ПРОСТО ИЩЕМ
    clean_text = text.replace("включай", "").replace("включи", "").replace("включить", "").replace("поставь", "").strip()
    return {"intent": "search", "entity": clean_text}