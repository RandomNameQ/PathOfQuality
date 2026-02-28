with open("src/ui/hud.py", "r", encoding="utf-8") as f:
    content = f.read()

# Make sure we actually have the patched refresh texts
content = content.replace(
    'self._root_notebook.tab(\n                self._tab_useful_frame, text="Полезное"\n            )',
    'self._root_notebook.tab(\n                self._tab_useful_frame, text=t("tab.useful", "Useful")\n            )'
)

content = content.replace(
    'self._root_notebook.tab(\n                self._tab_about_frame, text="О проекте"\n            )',
    'self._root_notebook.tab(\n                self._tab_about_frame, text=t("tab.about", "About")\n            )'
)

with open("src/ui/hud.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Patched tab names in hud.py")
