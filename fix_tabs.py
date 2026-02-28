with open("src/ui/tabs/useful_tab.py", "r", encoding="utf-8") as f:
    u_content = f.read()

u_content = u_content.replace(
    'self.link1.config(text=t("useful.chrome_ext", "Полезное расширение для торговли"))',
    'self.link1.config(text=t("useful.chrome_ext", "Полезное расширение для торговли"))\n            self.link1_yt.config(text=t("useful.yt_showcase", "Шоукейс расширения"))\n            self.link2.config(text=t("useful.party_site", "Удобный сайт для поиска пати для пое1 и пое2"))'
)

# Fix duplicate refresh calls inside useful tab
u_content = u_content.replace(
    """        if hasattr(self, 'link1_yt'):
            self.link1_yt.config(text=t("useful.yt_showcase", "Шоукейс расширения"))
        if hasattr(self, 'link2'):
            self.link2.config(text=t("useful.party_site", "Удобный сайт для поиска пати для пое1 и пое2"))""",
    ""
)

with open("src/ui/tabs/useful_tab.py", "w", encoding="utf-8") as f:
    f.write(u_content)

print("Cleaned up useful_tab.py texts")
