import re

with open("src/ui/hud.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'self._root_notebook.tab(\n                self._tab_settings_frame, text=t("tab.settings", "Settings")\n            )',
    'self._root_notebook.tab(\n                self._tab_useful_frame, text="Полезное"\n            )\n'
    '            self._root_notebook.tab(\n                self._tab_settings_frame, text=t("tab.settings", "Settings")\n            )\n'
    '            self._root_notebook.tab(\n                self._tab_about_frame, text="О проекте"\n            )'
)

with open("src/ui/hud.py", "w", encoding="utf-8") as f:
    f.write(content)
