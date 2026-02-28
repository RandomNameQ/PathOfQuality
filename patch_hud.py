import re

with open("src/ui/hud.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add imports
content = content.replace(
    "from src.ui.tabs.wasd_tab import WasdTab",
    "from src.ui.tabs.wasd_tab import WasdTab\nfrom src.ui.tabs.useful_tab import UsefulTab\nfrom src.ui.tabs.about_tab import AboutTab"
)

# 2. Add frames
content = content.replace(
    "self._tab_settings_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)",
    "self._tab_settings_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)\n        self._tab_useful_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)\n        self._tab_about_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)"
)

# 3. Add tabs instantiations
content = content.replace(
    "self._settings_tab = SettingsTab(\n            self._tab_settings_frame,",
    "self._useful_tab = UsefulTab(self._tab_useful_frame)\n        self._about_tab = AboutTab(self._tab_about_frame)\n        self._settings_tab = SettingsTab(\n            self._tab_settings_frame,"
)

# 4. Add to notebook
# Look for exactly:
#         self._root_notebook.add(
#             self._tab_settings_frame, text=t("tab.settings", "Settings")
#         )
content = content.replace(
    '        self._root_notebook.add(\n            self._tab_settings_frame, text=t("tab.settings", "Settings")\n        )',
    '        self._root_notebook.add(\n            self._tab_useful_frame, text="Полезное"\n        )\n        self._root_notebook.add(\n            self._tab_settings_frame, text=t("tab.settings", "Settings")\n        )\n        self._root_notebook.add(\n            self._tab_about_frame, text="О проекте"\n        )'
)

# 5. Add to refresh_texts
content = content.replace(
    '            self._root_notebook.tab(\n                self._tab_settings_frame, text=t("tab.settings", "Settings")\n            )',
    '            self._root_notebook.tab(\n                self._tab_useful_frame, text="Полезное"\n            )\n            self._root_notebook.tab(\n                self._tab_settings_frame, text=t("tab.settings", "Settings")\n            )\n            self._root_notebook.tab(\n                self._tab_about_frame, text="О проекте"\n            )'
)

# 6. Add to grab_anywhere widgets tuple
# Look for:
#                 self._tab_settings_frame,
#                 self._tab_library_group_frame,
content = content.replace(
    '                self._tab_settings_frame,\n                self._tab_library_group_frame,',
    '                self._tab_settings_frame,\n                self._tab_useful_frame,\n                self._tab_about_frame,\n                self._tab_library_group_frame,'
)

with open("src/ui/hud.py", "w", encoding="utf-8") as f:
    f.write(content)

