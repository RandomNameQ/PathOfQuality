with open("src/ui/hud.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace tab additions
content = content.replace(
    '        self._root_notebook.add(\n            self._tab_useful_frame, text="Полезное"\n        )\n        self._root_notebook.add(\n            self._tab_settings_frame, text=t("tab.settings", "Settings")\n        )\n        self._root_notebook.add(\n            self._tab_about_frame, text="О проекте"\n        )',
    '        self._root_notebook.add(\n            self._tab_settings_frame, text=t("tab.settings", "Settings")\n        )\n        self._root_notebook.add(\n            self._tab_useful_frame, text=t("tab.useful", "Useful")\n        )\n        self._root_notebook.add(\n            self._tab_about_frame, text=t("tab.about", "About")\n        )'
)

content = content.replace(
    '            self._root_notebook.tab(\n                self._tab_useful_frame, text="Полезное"\n            )\n            self._root_notebook.tab(\n                self._tab_settings_frame, text=t("tab.settings", "Settings")\n            )\n            self._root_notebook.tab(\n                self._tab_about_frame, text="О проекте"\n            )',
    '            self._root_notebook.tab(\n                self._tab_settings_frame, text=t("tab.settings", "Settings")\n            )\n            self._root_notebook.tab(\n                self._tab_useful_frame, text=t("tab.useful", "Useful")\n            )\n            self._root_notebook.tab(\n                self._tab_about_frame, text=t("tab.about", "About")\n            )'
)

with open("src/ui/hud.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated HUD order")
