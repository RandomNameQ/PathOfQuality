import os
import json
import ctypes

import cv2

from src.capture.mss_capture import MSSCapture
from src.capture.base_capture import Region
from src.detector.template_matcher import TemplateMatcher
from src.detector.library_matcher import LibraryMatcher
from src.ui.icon_mirrors import IconMirrorsOverlay
from src.ui.hud import BuffHUD
from src.ui.roi_selector import select_roi
from src.ui.overlay import OverlayHighlighter
from src.ui.tray import TrayIcon
from src.i18n.locale import set_lang


def get_screen_size():
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def load_settings(path: str) -> dict:
    defaults = {
        "capture": {"provider": "mss"},
        "roi": {"mode": "top_right", "width": 400, "height": 180, "top": 0, "left": 0},
        "threshold": 0.9,
        "scan_interval_ms": 50,
        "ui": {"keep_on_top": False, "alpha": 1.0, "grab_anywhere": True},
        "language": "en",
        "templates_dir": "assets/templates",
    }
    if not os.path.exists(path):
        return defaults
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # поверх дефолтов накладываем файл
        def merge(a, b):
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    merge(a[k], v)
                else:
                    a[k] = v
            return a
        return merge(defaults, data)
    except Exception:
        return defaults


def save_settings(path: str, settings: dict) -> None:
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def compute_roi(settings: dict, screen_w: int, screen_h: int) -> Region:
    roi_cfg = settings.get("roi", {})
    mode = roi_cfg.get("mode", "top_right")
    width = int(roi_cfg.get("width", 400))
    height = int(roi_cfg.get("height", 180))
    top = int(roi_cfg.get("top", 0))
    left = int(roi_cfg.get("left", 0))

    if mode == "top_right":
        left = max(0, screen_w - width)
        top = max(0, top)
    elif mode == "absolute":
        left = max(0, left)
        top = max(0, top)
    else:
        # fallback на top_right
        left = max(0, screen_w - width)
        top = max(0, top)

    width = min(width, screen_w)
    height = min(height, screen_h)
    return Region(left=left, top=top, width=width, height=height)


def main():
    settings = load_settings('settings.json')
    set_lang(settings.get('language', 'en'))

    screen_w, screen_h = get_screen_size()
    roi = compute_roi(settings, screen_w, screen_h)

    capture_provider = settings.get("capture", {}).get("provider", "mss")
    if capture_provider != "mss":
        print(f"Предупреждение: провайдер захвата '{capture_provider}' не реализован, используем 'mss'.")
    cap = MSSCapture()

    templates_dir = settings.get("templates_dir", "assets/templates")
    matcher = TemplateMatcher(templates_dir=templates_dir, threshold=float(settings.get("threshold", 0.9)))
    lib_matcher = LibraryMatcher(threshold=float(settings.get("threshold", 0.9)))

    print(f"Загружено шаблонов: {len(matcher.templates)} из '{templates_dir}'")
    if len(matcher.templates) > 0:
        print("Список шаблонов:", ", ".join([t[0] for t in matcher.get_template_infos()]))
    else:
        print(f"Шаблоны не найдены в каталоге '{templates_dir}'. Добавьте .png/.jpg, вырезанные ровно по иконке.")

    ui_cfg = settings.get("ui", {})
    hud = BuffHUD(
        templates=matcher.get_template_infos(),
        keep_on_top=bool(ui_cfg.get("keep_on_top", False)),
        alpha=float(ui_cfg.get("alpha", 1.0)),
        grab_anywhere=bool(ui_cfg.get("grab_anywhere", True)),
    )

    # Отобразим текущий ROI в настройках HUD
    hud.set_roi_info(roi.left, roi.top, roi.width, roi.height)

    # Оверлей-подсветка зоны анализа
    overlay = OverlayHighlighter(hud.get_root())
    mirrors = IconMirrorsOverlay(hud.get_root())
    overlay_enabled_last = False
    positioning_enabled_last = False

    # Системный трей
    tray = TrayIcon()
    tray.start()

    scan_interval_ms = int(settings.get("scan_interval_ms", 50))

    print(f"ROI: left={roi.left}, top={roi.top}, width={roi.width}, height={roi.height}")
    print(f"Порог совпадения: {matcher.threshold}")
    print(f"Интервал опроса: {scan_interval_ms} мс")

    try:
        # Снимок ROI для проверки (один раз)
        try:
            import cv2
            frame_bgr = MSSCapture().grab(roi)
            if frame_bgr is not None:
                os.makedirs('debug', exist_ok=True)
                snap_path = os.path.join('debug', 'roi_snapshot.png')
                cv2.imwrite(snap_path, frame_bgr)
                print(f"Снимок ROI сохранён: {snap_path}")
        except Exception:
            pass

        last_found = []
        while True:
            event = hud.read(timeout=scan_interval_ms)
            if event == 'EXIT' or tray.is_exit_requested():
                break
            if event == 'LIBRARY_UPDATED':
                # Перезагрузим список активных шаблонов
                try:
                    lib_matcher.refresh()
                except Exception:
                    pass

            # Переключение подсветки зоны анализа
            overlay_enabled_curr = hud.get_overlay_enabled()
            if overlay_enabled_curr != overlay_enabled_last:
                if overlay_enabled_curr:
                    overlay.show((roi.left, roi.top, roi.width, roi.height))
                else:
                    overlay.hide()
                overlay_enabled_last = overlay_enabled_curr

            # Переключение режима глобального позиционирования иконок
            positioning_enabled_curr = hud.get_positioning_enabled()
            if positioning_enabled_curr != positioning_enabled_last:
                try:
                    if positioning_enabled_curr:
                        print("[UI] Включён режим позиционирования активных иконок")
                        mirrors.enable_positioning_mode()
                    else:
                        print("[UI] Выключен режим позиционирования, сохраняю координаты")
                        mirrors.disable_positioning_mode(save_changes=True)
                except Exception as e:
                    print("[UI] Ошибка переключения позиционирования:", e)
                positioning_enabled_last = positioning_enabled_curr

            # Выбор зоны анализа по кнопке «Выделить зону»
            if event == 'SELECT_ROI':
                selected = select_roi(hud.get_root())
                if selected is not None:
                    left, top, width, height = selected
                    roi = Region(left=left, top=top, width=width, height=height)
                    # Сохраним в settings.json как абсолютную зону
                    settings.setdefault('roi', {})
                    settings['roi']['mode'] = 'absolute'
                    settings['roi']['left'] = left
                    settings['roi']['top'] = top
                    settings['roi']['width'] = width
                    settings['roi']['height'] = height
                    save_settings('settings.json', settings)
                    hud.set_roi_info(left, top, width, height)
                    if overlay_enabled_curr:
                        overlay.update((left, top, width, height))

            frame_bgr = cap.grab(roi)
            if frame_bgr is None:
                continue
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            found = matcher.match(gray)
            lib_results = lib_matcher.match(gray)
            hud.update(found)
            try:
                mirrors.update(lib_results, frame_bgr, (roi.left, roi.top, roi.width, roi.height))
            except Exception:
                pass
            if found != last_found:
                print("Найдены шаблоны:", ", ".join(found) if found else "—")
                last_found = found
    finally:
        hud.close()
        try:
            overlay.hide()
            overlay.close()
        except Exception:
            pass
        try:
            # Если уходили из приложения в режиме позиционирования — сохраним координаты
            mirrors.disable_positioning_mode(save_changes=True)
        except Exception:
            pass
        try:
            mirrors.close()
        except Exception:
            pass
        try:
            tray.stop()
        except Exception:
            pass
        cap.close()


if __name__ == '__main__':
    main()