import threading
from typing import Optional, Any

from src.utils.settings import resource_path

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


class TrayIcon:
    """
    Системный трей-иконка с пунктом меню «Закрыть».
    Работает в отдельном потоке. Если зависимости недоступны, становится no-op.
    """

    def __init__(self) -> None:
        self._icon: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._exit_requested: bool = False

    def _create_image(self) -> Optional[Any]:
        if Image is None:
            return None
        try:
            icon_path = resource_path("poq_icon.png")
            file_icon = Image.open(icon_path).convert("RGBA")
            return file_icon.resize((64, 64))
        except Exception:
            pass
        img = Image.new("RGBA", (64, 64), (30, 30, 30, 255))
        if ImageDraw is None:
            return img
        d = ImageDraw.Draw(img)
        d.ellipse((14, 14, 50, 50), fill=(0, 180, 0, 255))
        return img

    def _run(self):
        if pystray is None:
            return

        def on_exit(icon, item):
            self._exit_requested = True
            try:
                icon.stop()
            except Exception:
                pass

        image = self._create_image()
        menu = pystray.Menu(pystray.MenuItem("Закрыть", on_exit))
        self._icon = pystray.Icon("BuffHUD", image, "BuffHUD", menu)
        try:
            self._icon.run()
        except Exception:
            # Если не удалось запустить, откажемся молча
            self._icon = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            if self._icon is not None:
                self._icon.stop()
        except Exception:
            pass

    def is_exit_requested(self) -> bool:
        return self._exit_requested
