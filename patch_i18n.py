import json

def update_json(filepath, updates):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data.update(updates)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

ru_updates = {
    "tab.useful": "Полезное",
    "tab.about": "О проекте",
    "useful.chrome_ext": "Полезное расширение для торговли",
    "useful.yt_showcase": "Шоукейс расширения",
    "useful.party_site": "Удобный сайт для поиска пати для пое1 и пое2",
    "about.greeting": "Привет.\nЯ изгнанник, который добрался до решения некоторых проблем.\nБуду рад, если вам это помогает.",
    "about.telegram": "Для связи используйте телеграм ",
    "about.support": "Для поддержки текущих и будущих проектов можете донатить на:",
    "about.card": "Карта",
    "about.crypto": "Криптовалюта"
}

en_updates = {
    "tab.useful": "Useful",
    "tab.about": "About",
    "useful.chrome_ext": "Useful trading extension",
    "useful.yt_showcase": "Extension showcase",
    "useful.party_site": "Convenient party finder site for PoE 1 and PoE 2",
    "about.greeting": "Hello.\nI am an exile who got around to solving some problems.\nI will be glad if this helps you.",
    "about.telegram": "For contact use Telegram ",
    "about.support": "To support current and future projects you can donate to:",
    "about.card": "Card",
    "about.crypto": "Cryptocurrency"
}

try:
    update_json('assets/i18n/ru.json', ru_updates)
    update_json('assets/i18n/en.json', en_updates)
    print("i18n files updated")
except Exception as e:
    print(f"Error: {e}")
