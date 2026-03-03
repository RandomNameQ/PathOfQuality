# Focus Policy + works.json

Этот документ описывает, как теперь работает связка:

- `run only when the game is focused` (`require_game_focus` в `settings.json`)
- `works.json` (точечные исключения из этого правила)

## Основная логика

1. Если `require_game_focus = false`, ограничения по фокусу отключены полностью.
2. Если `require_game_focus = true`:
   - функционал работает, когда игра в фокусе;
   - при потере фокуса функционал блокируется;
   - но отдельные функции могут продолжать работать, если для них включен обход в `works.json`.

## Файл конфигурации

Путь: `works.json` в корне проекта.

Структура:

```json
{
  "version": 1,
  "bypass_when_focus_required": {
    "scan": false,
    "copy_overlay": false,
    "overlay_highlighter": false,
    "tab_overlay": false,
    "map_layout_overlay": false,
    "quickcraft_hotkey": false,
    "quickcraft_runtime_overlay": false,
    "quickcraft_click_action": false,
    "currency_positioning": false,
    "mega_qol_wheel": false,
    "wasd_controller": false,
    "triple_ctrl_click": false,
    "fast_destroy_hotkey": false,
    "fast_destroy_click_action": false,
    "fast_destroy_warning_overlay": false
  }
}
```

## Что контролирует каждый ключ

- `scan` - сканирование ROI и обновление найденных эффектов.
- `copy_overlay` - отображение copy overlay (Icon Mirrors).
- `overlay_highlighter` - основная рамка/оверлей области сканирования.
- `tab_overlay` - открытие/показ панели Tab Overlay.
- `map_layout_overlay` - открытие map-layout оверлея по `Ctrl+C`.
- `quickcraft_hotkey` - обработка hotkey QuickCraft.
- `quickcraft_runtime_overlay` - показ runtime QuickCraft оверлеев.
- `quickcraft_click_action` - клик-действия по QuickCraft оверлеям.
- `currency_positioning` - режим позиционирования валютных окон.
- `mega_qol_wheel` - Mega QoL (wheel down sequence).
- `wasd_controller` - WASD контроллер/движение.
- `triple_ctrl_click` - emulation по double Ctrl.
- `fast_destroy_hotkey` - включение/выключение Fast Destroy hotkey.
- `fast_destroy_click_action` - действие Fast Destroy на клик ЛКМ.
- `fast_destroy_warning_overlay` - предупреждающий Fast Destroy overlay.

## Пример

Требование: при потере фокуса игры оставить активным только Mega QoL wheel и Tab Overlay.

```json
{
  "version": 1,
  "bypass_when_focus_required": {
    "mega_qol_wheel": true,
    "tab_overlay": true
  }
}
```

Остальные ключи будут взяты из дефолта (`false`) при загрузке.
