"""
UI styling configuration for ttk widgets.
"""
from tkinter import ttk


from src.ui import theme

# Modern color scheme (PoE Themed)
BG_COLOR = theme.BG_PRIMARY
FG_COLOR = theme.FG_PRIMARY
ACCENT_COLOR = theme.ACCENT_GOLD
ACCENT_HOVER = theme.FG_SECONDARY
BORDER_COLOR = theme.BORDER_PRIMARY
HOVER_COLOR = theme.HOVER_COLOR

def configure_modern_styles(root) -> None:
    """
    Configure modern ttk styles for the application.
    
    Args:
        root: Tk root window
    """
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    try:
        root.configure(background=BG_COLOR)
    except Exception:
        pass
    
    try:
        # Notebook (tabs) style
        style.configure('TNotebook', background=BG_COLOR, borderwidth=0)
        style.configure(
            'TNotebook.Tab',
            padding=[18, 8],
            background=theme.BG_SECONDARY,
            foreground=theme.FG_SECONDARY,
            borderwidth=0,
            font=theme.FONT_BODY,
        )
        style.map(
            'TNotebook.Tab',
            background=[('selected', BG_COLOR), ('active', HOVER_COLOR)],
            foreground=[('selected', FG_COLOR)],
        )
        
        # Modern buttons - primary (more expressive)
        style.configure('Modern.TButton',
                        padding=[16, 10],
                        font=theme.FONT_HEADER,
                        background=theme.ACCENT_GOLD,
                        foreground='#000000',
                        borderwidth=1,
                        relief='solid')
        style.map('Modern.TButton',
                  background=[('active', theme.FG_PRIMARY), ('pressed', theme.FG_SECONDARY)],
                  foreground=[('active', '#000000'), ('pressed', '#000000')],
                  relief=[('pressed', 'sunken')])
        
        # Action buttons (secondary) - outlined
        style.configure('Action.TButton',
                        padding=[12, 8],
                        font=theme.FONT_BODY,
                        background=theme.BG_TERTIARY,
                        foreground=FG_COLOR,
                        borderwidth=1,
                        bordercolor=theme.BORDER_PRIMARY,
                        relief='solid')
        style.map('Action.TButton',
                  background=[('active', HOVER_COLOR), ('pressed', theme.BG_SECONDARY)],
                  foreground=[('active', FG_COLOR), ('pressed', FG_COLOR)],
                  bordercolor=[('active', theme.ACCENT_GOLD)])
        
        # Entry fields
        style.configure('TEntry',
                      fieldbackground=theme.BG_TERTIARY,
                      foreground=FG_COLOR,
                      borderwidth=1,
                      relief='flat',
                      insertcolor=FG_COLOR,
                      padding=[8, 6],
                      font=theme.FONT_BODY)
        style.map('TEntry',
                 fieldbackground=[('focus', theme.BG_TERTIARY)],
                 bordercolor=[('focus', theme.ACCENT_GOLD)])
        
        # Checkbutton
        style.configure('Toggle.TCheckbutton',
                        padding=6,
                        font=theme.FONT_BODY,
                        background=BG_COLOR,
                        foreground=FG_COLOR,
                        indicatorcolor=theme.BG_TERTIARY,
                        indicatorrelief='flat',
                        indicatorborderwidth=1)
        style.map('Toggle.TCheckbutton',
                  indicatorcolor=[('selected', theme.ACCENT_GOLD), ('active', theme.FG_SECONDARY)])

        # Gray variant for better contrast on plain backgrounds
        style.configure('ToggleGray.TCheckbutton',
                        padding=8,
                        font=theme.FONT_BODY,
                        background=theme.BG_SECONDARY,
                        foreground=FG_COLOR)
        style.map('ToggleGray.TCheckbutton',
                  background=[('active', HOVER_COLOR), ('selected', HOVER_COLOR)])
        
        # Frames
        style.configure('TFrame', background=BG_COLOR)
        style.configure('Card.TFrame', background=theme.BG_SECONDARY, relief='flat', borderwidth=1, bordercolor=theme.BORDER_PRIMARY)
        
        # Common Treeview Styles
        for tree_style in ['BuffTree.Treeview', 'DebuffTree.Treeview', 'CopyArea.Treeview', 'Currency.Treeview']:
            style.configure(tree_style,
                          rowheight=64,
                          background=theme.BG_TERTIARY,
                          fieldbackground=theme.BG_TERTIARY,
                          foreground=FG_COLOR,
                          borderwidth=1,
                          relief='flat')
            style.configure(f'{tree_style}.Heading',
                          font=theme.FONT_HEADER,
                          background=theme.BG_SECONDARY,
                          foreground=theme.FG_PRIMARY,
                          relief='flat',
                          borderwidth=0,
                          padding=[8, 8])
            style.map(tree_style,
                     background=[('selected', theme.BG_SECONDARY)],
                     foreground=[('selected', theme.ACCENT_GOLD)])

        # Labels
        style.configure('Title.TLabel', background=BG_COLOR, foreground=theme.FG_PRIMARY, font=theme.FONT_TITLE)
        style.configure('Subtitle.TLabel', background=BG_COLOR, foreground=theme.FG_SECONDARY, font=theme.FONT_BODY)
        style.configure('Prompt.TFrame', background=BG_COLOR)
        style.configure('Prompt.TLabel', background=BG_COLOR, foreground=FG_COLOR, font=theme.FONT_BODY)
                 
    except Exception:
        pass
