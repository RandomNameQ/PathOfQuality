"""
About tab UI component.
"""
import tkinter as tk
from tkinter import ttk
import webbrowser
from src.i18n.locale import t
from src.ui.styles import BG_COLOR, FG_COLOR
from src.ui import theme
from src.ui.components.tooltip import ToolTip

class AboutTab:
    """About tab for project information and support."""

    def __init__(self, parent: tk.Frame) -> None:
        """Initialize about tab."""
        self.frame = parent
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create about tab widgets."""
        main_container = tk.Frame(self.frame, bg=BG_COLOR)
        main_container.pack(fill="both", expand=True, padx=12, pady=12)
        
        # We need a canvas with scrollbar because of the length
        canvas = tk.Canvas(main_container, bg=BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG_COLOR)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Intro text
        self.text1 = tk.Label(
            scrollable_frame,
            text=t("about.greeting", "Привет.\nЯ изгнанник, который добрался до решения некоторых проблем.\nБуду рад, если вам это помогает."),
            fg=FG_COLOR,
            bg=BG_COLOR,
            font=("Segoe UI", 10),
            justify="left"
        )
        self.text1.pack(anchor="w", pady=(0, 12))

        # Telegram
        tg_frame = tk.Frame(scrollable_frame, bg=BG_COLOR)
        tg_frame.pack(anchor="w", pady=(0, 12))
        
        self.tg_lbl = tk.Label(tg_frame, text=t("about.telegram", "Для связи используйте телеграм "), fg=FG_COLOR, bg=BG_COLOR, font=("Segoe UI", 10))
        self.tg_lbl.pack(side="left")
        
        url_tg = "https://t.me/Caridas"
        self.tg_link = tk.Label(tg_frame, text=url_tg, fg=theme.ACCENT_GOLD, bg=BG_COLOR, cursor="hand2", font=("Segoe UI", 10, "underline"))
        self.tg_link.pack(side="left")
        self.tg_link.bind("<Button-1>", lambda e: webbrowser.open(url_tg))
        self.tt_tg = ToolTip(self.tg_link, text=url_tg)

        # Support intro
        self.text2 = tk.Label(
            scrollable_frame,
            text=t("about.support", "Для поддержки текущих и будущих проектов можете донатить на:"),
            fg=FG_COLOR,
            bg=BG_COLOR,
            font=("Segoe UI", 10),
            justify="left"
        )
        self.text2.pack(anchor="w", pady=(0, 12))

        # Card
        self.card_lbl = tk.Label(scrollable_frame, text=t("about.card", "Карта"), fg=FG_COLOR, bg=BG_COLOR, font=("Segoe UI", 10, "bold"))
        self.card_lbl.pack(anchor="w", pady=(0, 4))
        
        url_card = "https://pay.cloudtips.ru/p/c837cb8f"
        self.card_link = tk.Label(scrollable_frame, text=url_card, fg=theme.ACCENT_GOLD, bg=BG_COLOR, cursor="hand2", font=("Segoe UI", 10, "underline"))
        self.card_link.pack(anchor="w", pady=(0, 12))
        self.card_link.bind("<Button-1>", lambda e: webbrowser.open(url_card))
        self.tt_card = ToolTip(self.card_link, text=url_card)

        # Crypto
        self.crypto_lbl = tk.Label(scrollable_frame, text=t("about.crypto", "Криптовалюта"), fg=FG_COLOR, bg=BG_COLOR, font=("Segoe UI", 10, "bold"))
        self.crypto_lbl.pack(anchor="w", pady=(0, 8))

        self._add_crypto(scrollable_frame, "TON", "UQBYbeE_Y27_11-MSFqO4Udr-YAihHuAEznyCQ5EHhevR71R")
        self._add_crypto(scrollable_frame, "BTC", "bc1qvtsc8p7stzpj88hyhd2z45ps5q62auxceztmxf")
        self._add_crypto(scrollable_frame, "ETH", "0x17e06f02FA09B5E1314e46B775d2825B480a57f5")
        
        # Add mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)

    def _add_crypto(self, parent, name, address):
        frame = tk.Frame(parent, bg=BG_COLOR)
        frame.pack(anchor="w", pady=(0, 4))
        
        name_lbl = tk.Label(frame, text=f"{name} ", fg=FG_COLOR, bg=BG_COLOR, font=("Segoe UI", 10, "bold"))
        name_lbl.pack(side="left")
        
        addr = tk.Entry(frame, font=("Consolas", 10), width=45, bg=BG_COLOR, fg=FG_COLOR, readonlybackground=BG_COLOR)
        addr.insert(0, address)
        addr.configure(state="readonly")
        addr.pack(side="left")

    def refresh_texts(self) -> None:
        """Refresh all translatable texts (if any)."""
        if hasattr(self, 'text1'):
            self.text1.config(text=t("about.greeting", "Привет.\nЯ изгнанник, который добрался до решения некоторых проблем.\nБуду рад, если вам это помогает."))
        if hasattr(self, 'tg_lbl'):
            self.tg_lbl.config(text=t("about.telegram", "Для связи используйте телеграм "))
        if hasattr(self, 'text2'):
            self.text2.config(text=t("about.support", "Для поддержки текущих и будущих проектов можете донатить на:"))
        if hasattr(self, 'card_lbl'):
            self.card_lbl.config(text=t("about.card", "Карта"))
        if hasattr(self, 'crypto_lbl'):
            self.crypto_lbl.config(text=t("about.crypto", "Криптовалюта"))

