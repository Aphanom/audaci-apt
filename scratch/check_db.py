import sqlite3
from pathlib import Path

db_path = Path.home() / ".audaci" / "audaci_library.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.execute("SELECT file_path, folder_path, title, artist FROM tracks")
rows = cursor.fetchall()
print(f"Total tracks in DB: {len(rows)}")
for idx, r in enumerate(rows, 1):
    print(f"{idx}. title='{r['title']}' artist='{r['artist']}' folder_path='{r['folder_path']}' file_path='{r['file_path']}'")
conn.close()
