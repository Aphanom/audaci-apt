import sqlite3

def show_my_tags():
    # Подключаемся к твоей базе
    conn = sqlite3.connect('audaci_library.db')
    cursor = conn.cursor()

    try:
        # Достаем все уникальные комбинации тегов
        cursor.execute("SELECT DISTINCT mood_tags FROM tracks WHERE mood_tags IS NOT NULL AND mood_tags != ''")
        tags = cursor.fetchall()
        
        print("🎵 Уникальные теги в твоей медиатеке:")
        for tag in tags:
            print(f" - {tag[0]}")
    except Exception as e:
        print(f"Ошибка при чтении БД: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    show_my_tags()