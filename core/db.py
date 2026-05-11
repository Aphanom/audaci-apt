import sqlite3
import os
import random
import datetime

# --- УМНЫЙ ПУТЬ К БАЗЕ ДАННЫХ ---
USER_HOME = os.path.expanduser("~")
APP_DIR = os.path.join(USER_HOME, ".audaci")
os.makedirs(APP_DIR, exist_ok=True) # Создаем скрытую папку, если ее нет

DB_PATH = os.path.join(APP_DIR, "audaci_library.db")

def get_connection():
    # Единая точка подключения для всего приложения
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                file_path TEXT PRIMARY KEY,
                folder_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration_ms INTEGER,
                cover_path TEXT,
                lyrics TEXT,
                mood_tags TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(file_path) REFERENCES tracks(file_path)
            )
        """)

def add_track(file_path, folder_path, info):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO tracks (
                file_path, folder_path, title, artist, album, 
                duration_ms, cover_path, mood_tags
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(file_path), str(folder_path), 
            info.get("title") or os.path.basename(file_path), 
            info.get("artist") or "Неизвестен", 
            info.get("album") or "", 
            info.get("duration_ms") or 0, 
            info.get("cover_path") or "",
            info.get("mood_tags", "")
        ))

def get_track(file_path):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM tracks WHERE file_path = ?", (str(file_path),))
        row = cursor.fetchone()
        return dict(row) if row else None

def search_tracks(query):
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        search_term = f"%{query}%"
        cursor.execute('''
            SELECT * FROM tracks 
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? OR file_path LIKE ? OR mood_tags LIKE ?
            LIMIT 50
        ''', (search_term, search_term, search_term, search_term, search_term))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return []

def get_tracks_by_vibe(vibe_category):
    conn = get_connection() # ИСПРАВЛЕНО
    cursor = conn.cursor()
    
    vibe_map = {
        "happy": ["happy", "upbeat", "uplifting", "feel good", "cheerful", "fun", "joy", "summer", "dance pop", "comedy"],
        "sad": ["sad", "melancholic", "melancholy", "depressing", "heartbreak", "crying", "emo", "tear", "sadcore", "grief"],
        "energetic": ["energetic", "workout", "hype", "gym", "pump", "rage", "aggressive", "hard", "metal", "edm", "rock", "banger"],
        "chill": ["chill", "chillout", "relax", "ambient", "downtempo", "lo-fi", "lofi", "acoustic", "smooth", "mellow", "calm"],
        "focus": ["focus", "study", "instrumental", "classical", "piano", "concentration", "reading", "coding", "neo-classical"],
        "romantic": ["romantic", "love", "sexy", "sensual", "romance", "smooth rnb", "love song", "passion"],
        "party": ["party", "dance", "club", "house", "techno", "disco", "groove", "electronic"],
        "dark": ["dark", "gothic", "gloomy", "industrial", "doom", "creepy", "darkwave", "dark ambient"],
        "soul": ["soul", "rnb", "rhythm and blues", "neo-soul", "jazz", "blues", "gospel", "vocal"],
        "nostalgic": ["nostalgic", "nostalgia", "retro", "80s", "90s", "synthwave", "retrowave", "classic"]
    }
    
    keywords = vibe_map.get(vibe_category, [vibe_category])
    conditions = [f"mood_tags LIKE '%{kw}%'" for kw in keywords]
    query = "SELECT file_path FROM tracks WHERE mood_tags IS NOT NULL AND (" + " OR ".join(conditions) + ")"
    
    try:
        cursor.execute(query)
        results = [row[0] for row in cursor.fetchall()]
        return results
    except Exception as e:
        print(f"Ошибка поиска вайба в БД: {e}")
        return []
    finally:
        conn.close()

def generate_smart_wave(limit=25):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT file_path, artist, folder_path FROM tracks ORDER BY RANDOM() LIMIT 1")
    seed = c.fetchone()
    if not seed:
        conn.close()
        return []

    seed_path, seed_artist, seed_folder = seed
    wave_tracks = {seed_path}

    if seed_artist and seed_artist != "Неизвестен":
        c.execute("SELECT file_path FROM tracks WHERE artist = ? AND file_path != ? LIMIT 10", (seed_artist, seed_path))
        wave_tracks.update([r[0] for r in c.fetchall()])

    c.execute("SELECT file_path FROM tracks WHERE folder_path = ? AND file_path != ? LIMIT 10", (seed_folder, seed_path))
    wave_tracks.update([r[0] for r in c.fetchall()])

    if len(wave_tracks) < limit:
        placeholders = ','.join('?' for _ in wave_tracks)
        c.execute(f"SELECT file_path FROM tracks WHERE file_path NOT IN ({placeholders}) ORDER BY RANDOM() LIMIT ?", 
                  list(wave_tracks) + [limit - len(wave_tracks)])
        wave_tracks.update([row[0] for row in c.fetchall()])

    conn.close()
    wave_list = list(wave_tracks)
    random.shuffle(wave_list)
    if seed_path in wave_list: wave_list.remove(seed_path)
    wave_list.insert(0, seed_path)
    return wave_list

def get_all_artists():
    with get_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT artist FROM tracks WHERE artist != 'Неизвестен' ORDER BY artist")
        return [row[0] for row in cursor.fetchall()]

def get_tracks_by_artist(artist):
    with get_connection() as conn:
        cursor = conn.execute("SELECT file_path FROM tracks WHERE artist = ? ORDER BY title", (artist,))
        return [row[0] for row in cursor.fetchall()]

def get_all_albums():
    with get_connection() as conn:
        cursor = conn.execute("SELECT album, cover_path FROM tracks WHERE album != '' GROUP BY album ORDER BY album")
        return [{"album": row[0], "cover": row[1]} for row in cursor.fetchall()]

def get_tracks_by_album(album):
    with get_connection() as conn:
        cursor = conn.execute("SELECT file_path FROM tracks WHERE album = ? ORDER BY title", (album,))
        return [row[0] for row in cursor.fetchall()]

def add_to_history(file_path):
    with get_connection() as conn:
        conn.execute("INSERT INTO history (file_path) VALUES (?)", (str(file_path),))

def get_unplayed_tracks(artist=None):
    query = "SELECT file_path FROM tracks WHERE file_path NOT IN (SELECT DISTINCT file_path FROM history)"
    params = []
    if artist:
        query += " AND artist = ?"
        params.append(artist)
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [row[0] for row in cursor.fetchall()]

def update_track_lyrics(file_path, lyrics_json):
    with get_connection() as conn:
        conn.execute("UPDATE tracks SET lyrics = ? WHERE file_path = ?", (lyrics_json, str(file_path)))

def remove_folder_tracks(folder_path):
    with get_connection() as conn:
        conn.execute("DELETE FROM tracks WHERE folder_path LIKE ?", (f"{folder_path}%",))

def get_listening_history(limit=150):
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT h.file_path, h.timestamp AS played_at, t.title, t.artist, t.album, t.duration_ms, t.cover_path
            FROM history h
            LEFT JOIN tracks t ON h.file_path = t.file_path
            ORDER BY h.timestamp DESC
            LIMIT ?
        """
        cursor.execute(query, (limit,))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        print(f"Ошибка получения истории: {e}")
        return []
    
def get_top_tracks(days=30, limit=50):
    date_limit = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection() # ИСПРАВЛЕНО
    cursor = conn.cursor()
    cursor.execute('''
        SELECT file_path, COUNT(*) as cnt 
        FROM history 
        WHERE timestamp > ? 
        GROUP BY file_path 
        ORDER BY cnt DESC 
        LIMIT ?
    ''', (date_limit, limit))
    paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    return paths

def get_forgotten_treasures(limit=50):
    conn = get_connection() # ИСПРАВЛЕНО
    cursor = conn.cursor()
    cursor.execute('''
        SELECT file_path FROM history 
        GROUP BY file_path 
        HAVING COUNT(*) > 5 AND MAX(timestamp) < datetime('now', '-30 days')
        ORDER BY COUNT(*) DESC 
        LIMIT ?
    ''', (limit,))
    paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    return paths