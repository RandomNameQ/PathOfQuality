import re

with open("src/ui/hud.py", "r", encoding="utf-8") as f:
    content = f.read()

# Make sure imports are present and not duplicated
if "from src.ui.tabs.useful_tab import UsefulTab" not in content:
    content = content.replace("from src.ui.tabs.settings_tab import SettingsTab", "from src.ui.tabs.settings_tab import SettingsTab\nfrom src.ui.tabs.useful_tab import UsefulTab\nfrom src.ui.tabs.about_tab import AboutTab")

with open("src/ui/hud.py", "w", encoding="utf-8") as f:
    f.write(content)
