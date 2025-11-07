"""
UI styling configuration for ttk widgets.
"""
from tkinter import ttk


# Modern color scheme
BG_COLOR = '#fafafa'  # Light background
FG_COLOR = '#2c3e50'  # Dark text
ACCENT_COLOR = '#6366f1'  # Indigo accent
ACCENT_HOVER = '#4f46e5'
BORDER_COLOR = '#e5e7eb'  # Light border
HOVER_COLOR = '#f3f4f6'  # Hover background


def configure_modern_styles(root) -> None:
    """
    Configure modern ttk styles for the application.
    
    Args:
        root: Tk root window
    """
    style = ttk.Style(root)
    
    try:
        # Notebook (tabs) style
        style.configure('TNotebook', background=BG_COLOR, borderwidth=0)
        style.configure('TNotebook.Tab', 
                      padding=[20, 10], 
                      background='#ffffff',
                      foreground=FG_COLOR,
                      borderwidth=0,
                      font=('Segoe UI', 10, 'normal'))
        style.map('TNotebook.Tab',
                 background=[('selected', BG_COLOR), ('active', HOVER_COLOR)],
                 expand=[('selected', [1, 1, 1, 0])])
        
        # Modern buttons - primary
        style.configure('Modern.TButton',
                      padding=[16, 8],
                      font=('Segoe UI', 9, 'normal'),
                      background=ACCENT_COLOR,
                      foreground='#000000',  # Black text for better contrast
                      borderwidth=0,
                      focuscolor='none')
        style.map('Modern.TButton',
                 background=[('active', ACCENT_HOVER), ('pressed', '#4338ca')],
                 foreground=[('active', '#000000'), ('pressed', '#000000')],
                 relief=[('pressed', 'sunken')])
        
        # Action buttons (secondary)
        style.configure('Action.TButton',
                      padding=[12, 6],
                      font=('Segoe UI', 9, 'normal'),
                      background='#f9fafb',  # Light grey background
                      foreground='#111827',  # Very dark text for contrast
                      borderwidth=1,
                      relief='flat',
                      bordercolor='#d1d5db')
        style.map('Action.TButton',
                 background=[('active', '#f3f4f6'), ('pressed', '#e5e7eb')],
                 foreground=[('active', '#000000'), ('pressed', '#000000')],
                 bordercolor=[('active', '#9ca3af'), ('pressed', '#6b7280')])
        
        # Entry fields
        style.configure('TEntry',
                      fieldbackground='#ffffff',
                      foreground=FG_COLOR,
                      borderwidth=1,
                      relief='flat',
                      padding=[8, 6],
                      font=('Segoe UI', 9))
        style.map('TEntry',
                 fieldbackground=[('focus', '#ffffff')],
                 bordercolor=[('focus', ACCENT_COLOR)])
        
        # Checkbutton
        style.configure('Toggle.TCheckbutton',
                      padding=6,
                      font=('Segoe UI', 9),
                      background=BG_COLOR,
                      foreground=FG_COLOR)
        
        # Frame
        style.configure('TFrame', background=BG_COLOR)
        
        # Treeview styles for buffs
        style.configure('BuffTree.Treeview', 
                      rowheight=64, 
                      background='#ffffff', 
                      fieldbackground='#ffffff', 
                      foreground=FG_COLOR,
                      borderwidth=1, 
                      relief='flat')
        style.configure('BuffTree.Treeview.Heading', 
                      font=('Segoe UI', 10, 'bold'),
                      background='#f8f9fa', 
                      foreground='#1f2937', 
                      relief='flat',
                      borderwidth=0, 
                      padding=[8, 8])
        style.map('BuffTree.Treeview', 
                 background=[('selected', '#e0e7ff')],
                 foreground=[('selected', '#1f2937')])
        
        # Treeview styles for debuffs
        style.configure('DebuffTree.Treeview', 
                      rowheight=64, 
                      background='#ffffff',
                      fieldbackground='#ffffff', 
                      foreground=FG_COLOR,
                      borderwidth=1, 
                      relief='flat')
        style.configure('DebuffTree.Treeview.Heading', 
                      font=('Segoe UI', 10, 'bold'),
                      background='#f8f9fa', 
                      foreground='#1f2937', 
                      relief='flat',
                      borderwidth=0, 
                      padding=[8, 8])
        style.map('DebuffTree.Treeview', 
                 background=[('selected', '#fef2f2')],
                 foreground=[('selected', '#1f2937')])
                 
    except Exception:
        pass

