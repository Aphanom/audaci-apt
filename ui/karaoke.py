import flet as ft
import asyncio
from theme import AppColors

class KaraokePanel(ft.Container):
    def __init__(self, state, audio_player):
        super().__init__()
        self.state = state
        self.audio = audio_player
        
        # UI Элементы
        self.lyrics_list_view = ft.Column(
            expand=True, spacing=15, scroll=ft.ScrollMode.HIDDEN
        )
        
        # Настройки контейнера
        self.content = self.lyrics_list_view
        self.visible = False
        self.expand = True
        self.border_radius = 10
        self.padding = ft.Padding(40, 20, 40, 20)
        self.alignment = ft.Alignment(-1.0, -1.0)
        self.gradient = ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER, 
            end=ft.Alignment.BOTTOM_CENTER, 
            colors=[AppColors.KARAOKE_GRADIENT_START, AppColors.KARAOKE_GRADIENT_END],
        )
        self.animate = ft.Animation(1000, ft.AnimationCurve.EASE_OUT)

    def update_lyrics(self, lyrics_data):
        self.lyrics_list_view.controls.clear()
        for i, (timestamp, text) in enumerate(lyrics_data):
            self.lyrics_list_view.controls.append(
                ft.Text(
                    text,
                    size=24,
                    weight="bold",
                    color="white30",
                    key=f"norm_{i}",
                    animate_opacity=300,
                )
            )
        self.update()

    async def scroll_to_index(self, index):
        if not self.visible or index == -1:
            return
            
        try:
            for i, control in enumerate(self.lyrics_list_view.controls):
                if i == index:
                    control.color = AppColors.ACCENT
                    control.opacity = 1
                else:
                    control.color = "white30"
                    control.opacity = 0.5
            
            await self.lyrics_list_view.scroll_to(scroll_key=f"norm_{index}", duration=300)
            self.update()
        except Exception as e:
            print(f"[Karaoke] Scroll error: {e}")
