import flet as ft
import os
from theme import AppColors

class PlaylistMenu(ft.Container):
    def __init__(self, pl_name, track_count, cover_path, on_load, on_rename, on_cover, on_delete):
        super().__init__()
        self.padding = 10
        self.border_radius = 8
        self.on_click = lambda _: on_load(pl_name)
        self.on_hover = self.handle_hover
        
        if cover_path and os.path.exists(cover_path):
            leading_widget = ft.Image(src=cover_path, width=32, height=32, border_radius=4, fit="cover")
        else:
            leading_widget = ft.Icon(ft.Icons.PLAYLIST_PLAY, size=18)
        
        self.content = ft.Row([
            leading_widget,
            ft.Column([
                ft.Text(pl_name, size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(f"{track_count} треков", size=10, color=AppColors.TEXT_MUTED)
            ], spacing=0, expand=True),
            
            ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT, icon_size=14,
                items=[
                    ft.PopupMenuItem(content="Переименовать", on_click=lambda _: on_rename(pl_name)),
                    ft.PopupMenuItem(content="Обложка", on_click=lambda _: on_cover(pl_name)),
                    ft.PopupMenuItem(content="Удалить", on_click=lambda _: on_delete(pl_name)),
                ]
            )
        ], spacing=8, vertical_alignment="center")

    def handle_hover(self, e):
        self.bgcolor = AppColors.HOVER if str(e.data).lower() == "true" else None
        self.update()
