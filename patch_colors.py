import re

with open("src/ui/hud.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'self._tab_settings_frame,',
    'self._tab_settings_frame,\n                self._tab_useful_frame,\n                self._tab_about_frame,'
)

with open("src/ui/hud.py", "w", encoding="utf-8") as f:
    f.write(content)
