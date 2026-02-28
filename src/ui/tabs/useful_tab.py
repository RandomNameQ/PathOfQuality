"""
Useful links tab UI component.
"""
import tkinter as tk
from tkinter import ttk
import webbrowser
from src.i18n.locale import t
from src.ui.styles import BG_COLOR, FG_COLOR
from src.ui import theme
from src.ui.components.tooltip import ToolTip

class UsefulTab:
    """Useful tab for helpful links."""

    def __init__(self, parent: tk.Frame) -> None:
        """Initialize useful tab."""
        self.frame = parent
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create useful tab widgets."""
        main_container = tk.Frame(self.frame, bg=BG_COLOR)
        main_container.pack(fill="both", expand=True, padx=12, pady=12)

        # Chrome extension
        url1 = "https://chromewebstore.google.com/detail/poe-trade-qol/ljdhhcfchhfikcdeamifmbbckojjkkmb"
        self.link1 = tk.Label(
            main_container,
            text=t("useful.chrome_ext", "Полезное расширение для торговли"),
            fg=theme.ACCENT_GOLD,
            bg=BG_COLOR,
            cursor="hand2",
            font=("Segoe UI", 10, "underline")
        )
        self.link1.pack(anchor="w", pady=(0, 4))
        self.link1.bind("<Button-1>", lambda e: webbrowser.open(url1))
        self.tt1 = ToolTip(self.link1, text=url1)
        
        url_yt = "https://www.youtube.com/watch?v=LkbhEHwQS0U"
        self.link1_yt = tk.Label(
            main_container,
            text=t("useful.yt_showcase", "Шоукейс расширения"),
            fg=theme.ACCENT_GOLD,
            bg=BG_COLOR,
            cursor="hand2",
            font=("Segoe UI", 10, "underline")
        )
        self.link1_yt.pack(anchor="w", pady=(0, 12))
        self.link1_yt.bind("<Button-1>", lambda e: webbrowser.open(url_yt))
        self.tt_yt = ToolTip(self.link1_yt, text=url_yt)

        # Party finder
        url2 = "https://find-party-for-games.online/ru/games/path-of-exile"
        self.link2 = tk.Label(
            main_container,
            text=t("useful.party_site", "Удобный сайт для поиска пати для пое1 и пое2"),
            fg=theme.ACCENT_GOLD,
            bg=BG_COLOR,
            cursor="hand2",
            font=("Segoe UI", 10, "underline")
        )
        self.link2.pack(anchor="w", pady=(0, 12))
        self.link2.bind("<Button-1>", lambda e: webbrowser.open(url2))
        self.tt2 = ToolTip(self.link2, text=url2)

    def refresh_texts(self) -> None:
        """Refresh all translatable texts (if any)."""
        if hasattr(self, 'link1'):
            self.link1.config(text=t("useful.chrome_ext", "Полезное расширение для торговли"))
            self.link1_yt.config(text=t("useful.yt_showcase", "Шоукейс расширения"))
            self.link2.config(text=t("useful.party_site", "Удобный сайт для поиска пати для пое1 и пое2"))

