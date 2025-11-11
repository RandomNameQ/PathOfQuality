# PathOfQuality

<p align="center">
  <b>Windows overlay toolkit to streamline Path of Exile gameplay</b><br/>
  <sub>Created to improve the gaming experience based on personal in‑game practice</sub>
</p>

<p align="center">
  <a href="#english">English</a> • <a href="#русский">Русский</a>
</p>

---

<details open>
<summary id="english"><b>English</b></summary>

## About
PathOfQuality is a Windows desktop helper that overlays small, non‑activating windows over your game to speed up routine actions. It was created to improve the gaming experience based on my own time with the game.

## Highlights
- Scan buffs/debuffs in a configurable ROI with a subtle analysis outline
- Copy Areas: place live cropped regions on screen; hide on hover; square resize with mouse wheel
- Quick Craft overlay: global/per‑item hotkeys, non‑activating, click‑through; single‑click execution
- Mega QoL: mouse wheel down → send a key sequence (1–4 keys) with burst suppression
- Double Ctrl press → continuous left click emulation (hold to stop)
- Focus policy: “Run only when the game is focused” or allow while the app is focused
- Floating control dock (bottom‑center by default): quick Scan/Copy toggles + settings button
- Modern UI with grouped tabs (Overview, Library, Tools, Settings)
- Portable build: PyInstaller one‑file EXE; settings are external next to the EXE

## Getting Started
### Run from source
```
python -m pip install -r requirements.txt
python app.py
```

### Build a one‑file EXE (recommended)
Option A — use the helper script:
```
build_exe.bat
```
This creates `dist/PathOfQuality.exe` and places `dist/settings.json` and `dist/assets/` for easy editing.

Option B — PyInstaller directly:
```
pyinstaller --noconfirm --clean --onefile --windowed \
  --name PathOfQuality \
  --add-data "assets;assets" \
  --add-data "settings.json;." \
  app.py
```

## Configuration & Persistence
- Settings live in `settings.json`. When running the EXE, a user‑editable copy is kept next to the EXE.
- Allowed processes are in `assets/allowed_processes.json` — add your game EXE name(s) to enforce focus gating.
- Templates go in `assets/templates/` (PNG/JPG cut tightly to the icon).

## Usage Tips
- Hovering over Scan/Copy overlays temporarily hides them to access the underlying UI.
- During positioning, use the mouse wheel to resize — width and height scale together (square).
- Quick Craft overlays are non‑activating; a single left click on an overlay runs the action.

## Notes
- Windows only. Uses low‑level hooks (keyboard/mouse) and layered, non‑activating windows. No network calls.
- Built for personal QoL; use responsibly and in compliance with the game’s ToS.

</details>

---

<details>
<summary id="русский"><b>Русский</b></summary>

## О проекте
PathOfQuality — это вспомогательная программа для Windows, накладывающая небольшие «неактивирующиеся» окна поверх игры, чтобы ускорить рутинные действия. Создана с целью улучшить игровой опыт на основе моего личного опыта в игре.

## Возможности
- Сканирование баффов/дебаффов в настраиваемой зоне (ROI) с аккуратной подсветкой анализа
- Области копирования (Copy Areas): живые вырезки экрана; скрываются при наведении; квадратное изменение размера колесом мыши
- Оверлей Quick Craft: глобальная/покомпонентная горячая клавиша, «не активирует» окно, клики сквозь; выполнение по одному клику
- Mega QoL: прокрутка колесика вниз → отправка последовательности клавиш (1–4) с подавлением «бурстов»
- Двойное нажатие Ctrl → непрерывная эмуляция ЛКМ (останавливается при отпускании)
- Политика фокуса: «Работать только при фокусе игры» или разрешить работу при фокусе приложения
- Плавающая панель управления (по умолчанию внизу по центру): быстрые переключатели Скан/Копия + кнопка настроек
- Современный интерфейс с группировкой вкладок (Обзор, Библиотека, Инструменты, Настройки)
- Портативная сборка: EXE через PyInstaller; настройки хранятся рядом с EXE

## Быстрый старт
### Запуск из исходников
```
python -m pip install -r requirements.txt
python app.py
```

### Сборка EXE (одним файлом)
Вариант A — скрипт:
```
build_exe.bat
```
В `dist/` появится `PathOfQuality.exe`, а также `settings.json` и `assets/` для удобного редактирования.

Вариант B — PyInstaller напрямую:
```
pyinstaller --noconfirm --clean --onefile --windowed \
  --name PathOfQuality \
  --add-data "assets;assets" \
  --add-data "settings.json;." \
  app.py
```

## Конфигурация и сохранение
- Настройки — в `settings.json`. При запуске EXE пользовательская копия хранится рядом с EXE.
- Разрешённые процессы — `assets/allowed_processes.json` (добавьте EXE игры для корректной работы режимов фокуса).
- Шаблоны — в `assets/templates/` (PNG/JPG, вырезанные точно по иконке).

## Подсказки
- Наведение на оверлеи Скан/Копия временно скрывает их, чтобы получить доступ к окнам игры.
- В режиме позиционирования крутим колесо — ширина и высота меняются синхронно (квадрат).
- Оверлеи Quick Craft не забирают фокус; одного ЛКМ по оверлею достаточно для выполнения действия.

## Примечания
- Только Windows. Используются низкоуровневые перехватчики (клавиатура/мышь) и «неактивирующиеся» окна. Никаких сетевых запросов.
- Инструмент создан как личный QoL; используйте ответственно и в соответствии с правилами игры.

</details>
