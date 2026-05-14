import flet as ft
import requests
import os

# Базовый URL API (в разработке это localhost, в продакшене - публичный URL)
API_BASE_URL = "http://localhost:8000"

def main(page: ft.Page):
    page.title = "Audaci Mobile"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#000000"
    page.padding = 20
    page.window.width = 400
    page.window.height = 800

    # Состояние
    current_track = ft.Ref[ft.Text]()
    artist_text = ft.Ref[ft.Text]()
    cover_img = ft.Ref[ft.Image]()
    play_button = ft.Ref[ft.IconButton]()
    
    audio_player = ft.Audio(
        src="",
        autoplay=False,
    )
    page.overlay.append(audio_player)

    def update_status():
        try:
            # Получаем статус от основного плеера (опционально для синхронизации)
            response = requests.get(f"{API_BASE_URL}/api/status")
            if response.status_code == 200:
                data = response.json()
                if data.get("current_track"):
                    # Можно синхронизировать состояние, если нужно
                    pass
        except:
            pass

    def toggle_play(e):
        if audio_player.src:
            if play_button.current.icon == ft.Icons.PLAY_CIRCLE_FILL:
                audio_player.play()
                play_button.current.icon = ft.Icons.PAUSE_CIRCLE_FILLED
            else:
                audio_player.pause()
                play_button.current.icon = ft.Icons.PLAY_CIRCLE_FILL
            page.update()

    def play_track(track_path, title, artist):
        # Формируем URL для стриминга
        stream_url = f"{API_BASE_URL}/api/stream/{track_path}"
        audio_player.src = stream_url
        current_track.current.value = title
        artist_text.current.value = artist
        play_button.current.icon = ft.Icons.PAUSE_CIRCLE_FILLED
        audio_player.play()
        page.update()

    # Интерфейс
    page.add(
        ft.Column([
            ft.Container(height=40), # Отступ сверху
            ft.Row([
                ft.Text("Audaci", size=24, weight="bold", color="#1DB954"),
                ft.IconButton(ft.Icons.SYNC, on_click=lambda _: update_status())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Container(height=20),
            
            # Обложка
            ft.Container(
                content=ft.Image(
                    ref=cover_img,
                    src="https://via.placeholder.com/300",
                    width=300,
                    height=300,
                    border_radius=20,
                    fit=ft.ImageFit.COVER,
                ),
                alignment=ft.alignment.center,
                shadow=ft.BoxShadow(blur_radius=30, color="black"),
            ),
            
            ft.Container(height=30),
            
            # Инфо о треке
            ft.Column([
                ft.Text(ref=current_track, value="Выберите трек", size=22, weight="bold", no_wrap=True),
                ft.Text(ref=artist_text, value="Исполнитель", size=16, color="grey"),
            ], horizontal_alignment=ft.CrossAxisAlignment.START),
            
            ft.Container(height=20),
            
            # Слайдер прогресса (заглушка)
            ft.Slider(min=0, max=100, active_color="#1DB954", inactive_color="grey"),
            
            # Кнопки управления
            ft.Row([
                ft.IconButton(ft.Icons.SKIP_PREVIOUS_SHARP, icon_size=40),
                ft.IconButton(
                    ref=play_button,
                    icon=ft.Icons.PLAY_CIRCLE_FILL,
                    icon_size=80,
                    icon_color="#1DB954",
                    on_click=toggle_play
                ),
                ft.IconButton(ft.Icons.SKIP_NEXT_SHARP, icon_size=40),
            ], alignment=ft.MainAxisAlignment.CENTER),
            
            ft.Container(height=20),
            
            # Список треков (мини-очередь)
            ft.Text("Ваша музыка", size=18, weight="bold"),
            ft.ListView(
                expand=True,
                spacing=10,
                controls=[
                    # Сюда будем динамически добавлять треки из API
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.MUSIC_NOTE),
                        title=ft.Text("Пример трека 1"),
                        subtitle=ft.Text("Артист"),
                        on_click=lambda _: play_track("path/to/track.mp3", "Трек 1", "Артист")
                    )
                ]
            )
        ], expand=True)
    )

if __name__ == "__main__":
    ft.app(target=main)
