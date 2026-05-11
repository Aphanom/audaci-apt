import sqlite3
import datetime

def inject_fake_history():
    # Подключаемся к нашей базе
    conn = sqlite3.connect('audaci_library.db')
    cursor = conn.cursor()

    # 1. Берем любой существующий трек из базы
    cursor.execute("SELECT file_path FROM tracks LIMIT 1")
    track = cursor.fetchone()

    if track:
        file_path = track[0]
        print(f"🧪 Делаем 'забытым' трек:\n{file_path}\n")

        # 2. Генерируем дату (например, 40 дней назад)
        past_date = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")

        # 3. Вставляем 6 прослушиваний этого трека в прошлое (чтобы было больше 5)
        for _ in range(6):
            cursor.execute("INSERT INTO history (file_path, timestamp) VALUES (?, ?)", (file_path, past_date))

        conn.commit()
        print("✅ Готово! Фейковая история из прошлого успешно добавлена.")
        print("Запускай main.py и проверяй плейлист '💎 Забытое'!")
    else:
        print("❌ Ошибка: В базе нет треков. Сначала просканируй папку с музыкой.")

    conn.close()

if __name__ == "__main__":
    inject_fake_history()