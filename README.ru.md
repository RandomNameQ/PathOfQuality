# PathOfQuality

<p align="center">
  <b>Набор оверлеев для ускорения действий в Path of Exile</b><br/>
  <sub>Создано, чтобы улучшить игровой опыт на основе личной практики</sub>
  <br/>
  <a href="./README.md"><img alt="Read in English" src="https://img.shields.io/badge/Read%20in%20English-%F0%9F%87%BA%F0%9F%87%B8-blue?style=for-the-badge" /></a>
  <br/>
  <img src="https://img.shields.io/badge/Windows-10%2B-0078D6?logo=windows&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Build-PyInstaller-FFDF00" />
  <br/>
  <i>Сделано для повышения удобства, исходя из реального игрового опыта</i>
  <br/>
  <br/>
  <img src="https://img.shields.io/badge/Quick%20Craft-%D0%BE%D0%B4%D0%B8%D0%BD%20%D0%BA%D0%BB%D0%B8%D0%BA%20%F0%9F%91%8D-brightgreen" />
  <img src="https://img.shields.io/badge/Overlays-%D0%BD%D0%B5%20%D0%B0%D0%BA%D1%82%D0%B8%D0%B2%D0%B8%D1%80%D1%83%D1%8E%D1%82%20%D0%BE%D0%BA%D0%BD%D0%BE-blue" />
  <img src="https://img.shields.io/badge/Mega%20QoL-%D0%BA%D0%BE%D0%BB%D0%B5%D1%81%D0%BE%E2%86%92%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D1%88%D0%B8-orange" />
</p>

---

## 📽️ Демо‑видео

https://github.com/RandomNameQ/PathOfQuality/assets/125605136/show_scan_overlay.mp4

Рекомендуется показать в видео: оверлей сканирования (подсветку анализа ROI в работе).

---

## 🧩 Функции (кратко → подробнее)

1) Библиотека — Оверлей сканирования
- Находит сохранённые шаблоны иконок на экране и показывает неактивирующие оверлеи.
- Подходит для отслеживания нужных визуальных состояний без переключения фокуса игры.
- Подробнее: [docs/ru/scan-overlay.md](./docs/ru/scan-overlay.md)
- Видео-гайд (настройка Scan & Copy Area): [YouTube](https://www.youtube.com/watch?v=P4fPhLa3OZU)

![Демонстрация](https://raw.githubusercontent.com/RandomNameQ/PathOfQuality/main/video/show_scan_overlay.gif)

2) Библиотека — Оверлей копирования
- Дублирует выбранную область экрана отдельным слоем оверлея.
- Поддерживает условную видимость: всегда показывать или только если выбранного баффа/дебаффа нет.
- Подробнее: [docs/ru/copy-overlay.md](./docs/ru/copy-overlay.md)
- Видео-гайд (настройка Scan & Copy Area): [YouTube](https://www.youtube.com/watch?v=P4fPhLa3OZU)

3) Инструменты — Валюта — Quick Craft
- Показывает валютные оверлеи и выполняет настроенные быстрые действия по горячей клавише.
- Оптимизировано под сценарий «один клик» без активации окон.
- Подробнее: [docs/ru/quick-craft.md](./docs/ru/quick-craft.md)
- Видео-гайд (настройка Quick Craft): [YouTube](https://www.youtube.com/watch?v=EY1q780P3GI)

![Демонстрация](https://raw.githubusercontent.com/RandomNameQ/PathOfQuality/main/video/show_quick_craft.gif)

4) Инструменты — Mega QoL — Wheel Keys
- Прокрутка колеса вниз эмулирует настраиваемую последовательность клавиш (1-4) с подавлением «бурстов».
- Удобно для повторяемого ввода ротации со стабильным таймингом.
- Подробнее: [docs/ru/wheel-keys.md](./docs/ru/wheel-keys.md)

5) Инструменты — Mega QoL — Двойной Ctrl
- Двойное нажатие Ctrl запускает эмуляцию ЛКМ; отпускание Ctrl её останавливает.
- Упрощает взаимодействие со stash/inventory по наведению без частых физических кликов.
- Подробнее: [docs/ru/double-ctrl-click.md](./docs/ru/double-ctrl-click.md)

---

## 💡 Советы
- Наведение на оверлеи Скан/Копия временно скрывает их, чтобы взаимодействовать с интерфейсом под ними.
- В режиме позиционирования колесо мыши меняет размер квадратом (ширина = высота).
- Оверлеи не активируют окна и скрыты с панели задач/Alt+Tab.
