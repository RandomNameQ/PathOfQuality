"""Tab overlay window shown above all windows."""

from __future__ import annotations

import json
import io
import os
import hashlib
import shutil
import queue
import threading
import tkinter as tk
from urllib.parse import urlparse
import urllib.request
import webbrowser
from tkinter import filedialog, simpledialog
from typing import Any, Callable, Optional

from PIL import Image, ImageTk

from src.ui import theme
from src.utils.settings import external_path, resource_path


class TabOverlayWindow:
    """Stylized top-level overlay window for tab tools."""

    _MAP_ROWS_CACHE: Optional[list[dict[str, str | int]]] = None
    _MENU_HOTKEY_SEQUENCE: tuple[str, ...] = (
        "1",
        "2",
        "3",
        "4",
        "5",
        "Q",
        "W",
        "E",
        "R",
        "A",
        "S",
        "D",
        "F",
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
    )

    def __init__(
        self,
        master: tk.Tk,
        settings: Optional[dict] = None,
        save_settings_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._master = master
        self._settings = settings if isinstance(settings, dict) else {}
        self._save_settings_callback = save_settings_callback
        self._layout_cache_dir = external_path(os.path.join("cache", "layout_images"))
        self._overlay_assets_dir = external_path(
            os.path.join("assets", "overlay_images")
        )
        self._ensure_layout_cache_dir()
        self._ensure_overlay_assets_dir()
        self._window = tk.Toplevel(master)
        self._window.withdraw()
        self._window.title("Tab Overlay")
        self._window.configure(bg=theme.BG_PRIMARY)
        self._window.protocol("WM_DELETE_WINDOW", self.hide)
        self._window.bind("<Escape>", lambda _event: self.hide())
        try:
            self._window.attributes("-topmost", True)
            self._window.attributes("-alpha", 1.0)
            self._window.overrideredirect(True)
        except Exception:
            pass

        self._menu_items = []
        self._menu_buttons = {}
        self._menu_hotkey_lookup = self._build_menu_hotkey_lookup()
        self._active_item_id = ""
        self._user_counter = 1
        self._menu_width = 220
        self._image_canvas_height = 480
        self._map_sort_key = "mapName"
        self._map_sort_desc = False
        self._map_search_query = ""
        self._map_rows = []
        self._map_col_name_width = 140
        self._map_col_img_layout_width = 100
        self._map_col_layout_width = 80
        self._map_col_density_width = 90
        self._map_col_tags_width = 290
        self._map_header_height = 36
        self._map_row_height = 36
        self._map_panel = None
        self._map_title_label = None
        self._map_rows_container = None
        self._map_search_var = None
        self._map_overlay_enabled_var = None
        self._map_header_buttons = {}
        self._layout_preview_window = None
        self._layout_preview_body = None
        self._layout_preview_photo = None
        self._layout_preview_close_binding = None
        self._layout_preview_request_id = 0
        self._clipboard_map_window = None
        self._clipboard_map_body = None
        self._clipboard_map_link_label = None
        self._clipboard_map_photo = None
        self._clipboard_map_request_id = 0
        self._drag_state = {
            "item_id": "",
            "start_y": 0,
            "dragging": False,
        }
        self._window_drag_state = {
            "active": False,
            "offset_x": 0,
            "offset_y": 0,
        }
        self._window_drag_region_height = 24
        self._image_states = []
        self._has_centered_geometry = False
        self._load_map_rows()

        self._build_layout()
        self._seed_menu()

    def _build_layout(self) -> None:
        root = tk.Frame(
            self._window,
            bg=theme.BG_SECONDARY,
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.BORDER_PRIMARY,
        )
        root.pack(fill="both", expand=True, padx=20, pady=20)

        self._window_drag_handle = tk.Frame(
            self._window,
            bg=theme.BG_SECONDARY,
            height=self._window_drag_region_height,
            bd=0,
            highlightthickness=0,
        )
        self._window_drag_handle.place(
            x=0,
            y=0,
            relwidth=1.0,
            height=self._window_drag_region_height,
        )

        self._btn_close_overlay = tk.Button(
            self._window,
            text="X",
            bg=theme.ACCENT_RED,
            fg="#ffffff",
            activebackground="#b30000",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            font=("Segoe UI", 11, "bold"),
            highlightthickness=1,
            highlightbackground="#ffffff",
            command=self.hide,
        )
        self._btn_close_overlay.place(relx=1.0, x=-8, y=8, anchor="ne")
        self._btn_close_overlay.lift()

        self._menu_frame = tk.Frame(
            root,
            bg=theme.BG_PRIMARY,
            width=self._menu_width,
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.BORDER_PRIMARY,
        )
        self._menu_frame.pack(side="left", fill="y")
        self._menu_frame.pack_propagate(False)

        separator = tk.Frame(root, bg=theme.BORDER_PRIMARY, width=1)
        separator.pack(side="left", fill="y")

        self._content_root = tk.Frame(root, bg=theme.BG_PRIMARY)
        self._content_root.pack(side="left", fill="both", expand=True)

        self._menu_list_container = tk.Frame(self._menu_frame, bg=theme.BG_PRIMARY)
        self._menu_list_container.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        self._menu_canvas = tk.Canvas(
            self._menu_list_container,
            bg=theme.BG_PRIMARY,
            highlightthickness=0,
            bd=0,
        )
        self._menu_scrollbar = tk.Scrollbar(
            self._menu_list_container,
            orient="vertical",
            command=self._menu_canvas.yview,
        )
        self._menu_canvas.configure(yscrollcommand=self._menu_scrollbar.set)
        self._menu_scrollbar.pack(side="right", fill="y")
        self._menu_canvas.pack(side="left", fill="both", expand=True)

        self._menu_list = tk.Frame(self._menu_canvas, bg=theme.BG_PRIMARY)
        self._menu_canvas_window = self._menu_canvas.create_window(
            (0, 0),
            window=self._menu_list,
            anchor="nw",
        )

        self._menu_list.bind("<Configure>", self._on_menu_list_configure)
        self._menu_canvas.bind("<Configure>", self._on_menu_canvas_configure)
        self._menu_canvas.bind("<MouseWheel>", self._on_menu_mouse_wheel, add="+")
        self._menu_list.bind("<MouseWheel>", self._on_menu_mouse_wheel, add="+")

        self._btn_add = tk.Button(
            self._menu_frame,
            text="ADD +",
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.HOVER_COLOR,
            activeforeground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            anchor="w",
            font=theme.FONT_HEADER,
            command=self._add_user_item,
        )
        self._btn_add.pack(side="bottom", fill="x", padx=8, pady=8)

        self._content_canvas = tk.Canvas(
            self._content_root,
            bg=theme.BG_PRIMARY,
            highlightthickness=0,
            bd=0,
        )
        self._content_scrollbar = tk.Scrollbar(
            self._content_root,
            orient="vertical",
            command=self._content_canvas.yview,
        )
        self._content_canvas.configure(yscrollcommand=self._content_scrollbar.set)
        self._content_scrollbar.pack(side="right", fill="y")
        self._content_canvas.pack(side="left", fill="both", expand=True)

        self._content_inner = tk.Frame(self._content_canvas, bg=theme.BG_PRIMARY)
        self._content_canvas_window = self._content_canvas.create_window(
            (0, 0),
            window=self._content_inner,
            anchor="nw",
        )

        self._content_inner.bind("<Configure>", self._on_content_inner_configure)
        self._content_canvas.bind("<Configure>", self._on_content_canvas_configure)
        self._window.bind("<KeyPress>", self._on_menu_hotkey_press, add="+")
        self._window.bind("<MouseWheel>", self._on_overlay_mouse_wheel, add="+")

        self._window_drag_handle.bind("<ButtonPress-1>", self._start_window_drag)
        self._window_drag_handle.bind("<B1-Motion>", self._on_window_drag)
        self._window_drag_handle.bind("<ButtonRelease-1>", self._finish_window_drag)

    def _seed_menu(self) -> None:
        self._menu_items = [
            {
                "id": "program:commands",
                "type": "program",
                "name": "Commands",
                "program_key": "commands",
            },
            {
                "id": "program:map",
                "type": "program",
                "name": "MAP",
                "program_key": "map",
            },
        ]

        stored_items, stored_active = self._load_overlay_menu_state()
        if stored_items:
            self._menu_items.extend(stored_items)

        self._user_counter = self._compute_next_user_counter()
        self._refresh_menu()
        active_id = (
            stored_active
            if self._get_item(stored_active) is not None
            else "program:map"
        )
        self._select_item(active_id)

    def _coerce_float(self, value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _normalize_image_entry(self, raw_image: Any) -> Optional[dict]:
        if not isinstance(raw_image, dict):
            return None

        path = str(raw_image.get("path", "")).strip()
        if not path:
            return None

        return {
            "path": path,
            "zoom": max(
                0.2, min(8.0, self._coerce_float(raw_image.get("zoom", 1.0), 1.0))
            ),
            "offset_x": self._coerce_float(raw_image.get("offset_x", 0.0), 0.0),
            "offset_y": self._coerce_float(raw_image.get("offset_y", 0.0), 0.0),
        }

    def _load_overlay_menu_state(self) -> tuple[list, str]:
        overlay_cfg = self._settings.get("overlay", {})
        if not isinstance(overlay_cfg, dict):
            return [], ""

        raw_items = overlay_cfg.get("menu_items", [])
        if not isinstance(raw_items, list):
            raw_items = []

        saved_items = []
        used_ids = {"program:map"}
        generated_id = 1

        for index, raw_item in enumerate(raw_items, start=1):
            if not isinstance(raw_item, dict):
                continue

            item_id = str(raw_item.get("id", "")).strip()
            if not item_id.startswith("user:") or item_id in used_ids:
                item_id = f"user:{generated_id}"
                while item_id in used_ids:
                    generated_id += 1
                    item_id = f"user:{generated_id}"

            used_ids.add(item_id)
            generated_id += 1

            name = str(raw_item.get("name", "")).strip() or f"Link {index}"
            images = []
            raw_images = raw_item.get("images", [])
            if not isinstance(raw_images, list):
                raw_images = []
            for raw_image in raw_images:
                image_entry = self._normalize_image_entry(raw_image)
                if image_entry is not None:
                    images.append(image_entry)

            saved_items.append(
                {
                    "id": item_id,
                    "type": "user",
                    "name": name,
                    "images": images,
                }
            )

        active_id = str(overlay_cfg.get("active_item_id", "")).strip()
        return saved_items, active_id

    def _is_map_layout_overlay_enabled(self) -> bool:
        overlay_cfg = self._settings.get("overlay", {})
        if not isinstance(overlay_cfg, dict):
            return True
        return bool(overlay_cfg.get("use_map_layout_overlay", True))

    def is_map_layout_overlay_enabled(self) -> bool:
        return self._is_map_layout_overlay_enabled()

    def _set_map_layout_overlay_enabled(self, enabled: bool) -> None:
        overlay_cfg = self._settings.setdefault("overlay", {})
        if not isinstance(overlay_cfg, dict):
            return

        overlay_cfg["use_map_layout_overlay"] = bool(enabled)
        if self._save_settings_callback is not None:
            try:
                self._save_settings_callback()
            except Exception:
                pass

    def _compute_next_user_counter(self) -> int:
        max_id = 0
        for item in self._menu_items:
            if item.get("type") != "user":
                continue

            item_id = str(item.get("id", ""))
            if not item_id.startswith("user:"):
                continue

            suffix = item_id.split(":", 1)[1].strip()
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))

        return max_id + 1

    def _coerce_int(self, value: Any, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _ensure_layout_cache_dir(self) -> None:
        try:
            os.makedirs(self._layout_cache_dir, exist_ok=True)
        except Exception:
            pass

    def _ensure_overlay_assets_dir(self) -> None:
        try:
            os.makedirs(self._overlay_assets_dir, exist_ok=True)
        except Exception:
            pass

    def _overlay_image_extension(self, source_path: str) -> str:
        extension = os.path.splitext(str(source_path))[1].lower()
        if extension not in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
            extension = ".img"
        return extension

    def _package_overlay_image(self, source_path: str) -> str:
        normalized_source = os.path.abspath(str(source_path))
        if not os.path.isfile(normalized_source):
            return str(source_path)

        self._ensure_overlay_assets_dir()
        packaged_dir = os.path.abspath(self._overlay_assets_dir)
        try:
            if os.path.commonpath([normalized_source, packaged_dir]) == packaged_dir:
                return normalized_source
        except Exception:
            pass

        try:
            source_stat = os.stat(normalized_source)
            source_fingerprint = f"{normalized_source}|{int(source_stat.st_mtime_ns)}|{int(source_stat.st_size)}"
        except Exception:
            source_fingerprint = normalized_source

        extension = self._overlay_image_extension(normalized_source)
        digest = hashlib.sha1(source_fingerprint.encode("utf-8")).hexdigest()
        packaged_path = os.path.join(packaged_dir, f"{digest}{extension}")

        if os.path.exists(packaged_path):
            return packaged_path

        try:
            shutil.copyfile(normalized_source, packaged_path)
            return packaged_path
        except Exception:
            return str(source_path)

    def _layout_cache_path(self, image_url: str) -> str:
        url_path = urlparse(image_url).path
        extension = os.path.splitext(url_path)[1].lower()
        if extension not in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
            extension = ".img"

        digest = hashlib.sha1(image_url.encode("utf-8")).hexdigest()
        return os.path.join(self._layout_cache_dir, f"{digest}{extension}")

    def _read_layout_cache_bytes(self, image_url: str) -> Optional[bytes]:
        cache_path = self._layout_cache_path(image_url)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, "rb") as file_obj:
                payload = file_obj.read()
        except Exception:
            return None

        return payload if payload else None

    def _write_layout_cache_bytes(self, image_url: str, payload: bytes) -> None:
        if not payload:
            return

        self._ensure_layout_cache_dir()
        cache_path = self._layout_cache_path(image_url)
        try:
            with open(cache_path, "wb") as file_obj:
                file_obj.write(payload)
        except Exception:
            pass

    def _load_map_rows(self) -> None:
        if TabOverlayWindow._MAP_ROWS_CACHE is not None:
            self._map_rows = TabOverlayWindow._MAP_ROWS_CACHE
            return

        map_data_path = external_path("map-data.json")
        if not os.path.exists(map_data_path):
            map_data_path = resource_path("map-data.json")

        try:
            with open(map_data_path, "r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
        except Exception:
            self._map_rows = []
            return

        if not isinstance(payload, list):
            self._map_rows = []
            return

        rows = []
        for row in payload:
            if not isinstance(row, dict):
                continue

            map_name = str(row.get("mapName", "")).strip()
            if not map_name:
                continue

            raw_tags = row.get("tags", [])
            if not isinstance(raw_tags, list):
                raw_tags = [raw_tags]

            rows.append(
                {
                    "mapName": map_name,
                    "mapUrl": str(row.get("mapUrl", "")).strip(),
                    "layout": self._coerce_int(row.get("layout", 0), 0),
                    "density": self._coerce_int(row.get("density", 0), 0),
                    "layoutUrl": str(row.get("layoutUrl", "")).strip(),
                    "tags": ", ".join(
                        str(tag).strip() for tag in raw_tags if str(tag).strip()
                    ),
                }
            )

        self._map_rows = rows
        TabOverlayWindow._MAP_ROWS_CACHE = rows

    def _get_sorted_filtered_map_rows(self) -> list:
        query = self._map_search_query.strip().lower()
        filtered_rows = []

        for row in self._map_rows:
            if query and query not in str(row.get("mapName", "")).lower():
                continue
            filtered_rows.append(row)

        if self._map_sort_key in ("mapName", "tags"):
            filtered_rows.sort(
                key=lambda row: str(row.get(self._map_sort_key, "")).lower(),
                reverse=self._map_sort_desc,
            )
            return filtered_rows

        filtered_rows.sort(
            key=lambda row: self._coerce_int(row.get(self._map_sort_key, 0), 0),
            reverse=self._map_sort_desc,
        )
        return filtered_rows

    def _sort_marker(self, sort_key: str) -> str:
        if self._map_sort_key != sort_key:
            return ""
        return " v" if self._map_sort_desc else " ^"

    def _refresh_map_sort_headers(self) -> None:
        header_titles = {
            "mapName": "Map name (link)",
            "layout": "Layout",
            "density": "Density",
            "tags": "Tags",
        }
        for sort_key, title in header_titles.items():
            button = self._map_header_buttons.get(sort_key)
            if button is None or not button.winfo_exists():
                continue
            button.configure(text=f"{title}{self._sort_marker(sort_key)}")

    def _toggle_map_sort(self, sort_key: str) -> None:
        if self._map_sort_key == sort_key:
            self._map_sort_desc = not self._map_sort_desc
        else:
            self._map_sort_key = sort_key
            self._map_sort_desc = False

        rows_container = self._map_rows_container
        if rows_container is None or not rows_container.winfo_exists():
            self._render_content()
            return

        self._refresh_map_sort_headers()
        self._refresh_map_table_rows(rows_container)

    def _open_external_map_link(self, map_url: str) -> None:
        if not map_url:
            return
        try:
            webbrowser.open_new_tab(map_url)
        except Exception:
            pass

    def _find_map_row_by_name(self, map_name: str) -> Optional[dict]:
        needle = str(map_name or "").strip().lower()
        if not needle:
            return None

        for row in self._map_rows:
            candidate = str(row.get("mapName", "")).strip().lower()
            if candidate == needle:
                return row
        return None

    def _clipboard_map_set_geometry(
        self, content_width: int, content_height: int
    ) -> None:
        if self._clipboard_map_window is None:
            return

        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        popup_width = max(360, int(screen_w * 0.5))
        popup_height = max(240, int(screen_h * 0.5))
        popup_x = max(0, (screen_w - popup_width) // 2)
        popup_y = max(0, (screen_h - popup_height) // 2)
        self._clipboard_map_window.geometry(
            f"{popup_width}x{popup_height}+{popup_x}+{popup_y}"
        )

    def _clipboard_map_show_message(self, message: str, width: int = 520) -> None:
        if self._clipboard_map_body is None:
            return

        for child in self._clipboard_map_body.winfo_children():
            child.destroy()

        label = tk.Label(
            self._clipboard_map_body,
            text=message,
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_BODY,
            justify="center",
            anchor="center",
            wraplength=max(260, width - 40),
        )
        label.pack(fill="both", expand=True, padx=12, pady=12)
        label.bind("<ButtonRelease-1>", self._on_clipboard_map_click_close, add="+")
        self._clipboard_map_set_geometry(width, 180)

    def _clipboard_map_show_image(self, request_id: int, image_bytes: bytes) -> bool:
        if request_id != self._clipboard_map_request_id:
            return False
        if self._clipboard_map_window is None or self._clipboard_map_body is None:
            return False
        if not self._clipboard_map_window.winfo_exists():
            return False

        try:
            source_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        except Exception as error:
            self._clipboard_map_show_message(f"Failed to render map image\n{error}")
            return False

        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        max_width = max(300, int(screen_w * 0.5) - 32)
        max_height = max(220, int(screen_h * 0.5) - 96)
        scale = min(
            max_width / source_image.width, max_height / source_image.height, 1.0
        )
        target_width = max(1, int(source_image.width * scale))
        target_height = max(1, int(source_image.height * scale))
        preview_image = source_image.resize(
            (target_width, target_height), Image.LANCZOS
        )
        self._clipboard_map_photo = ImageTk.PhotoImage(preview_image)

        for child in self._clipboard_map_body.winfo_children():
            child.destroy()

        image_label = tk.Label(
            self._clipboard_map_body,
            image=self._clipboard_map_photo,
            bg=theme.BG_PRIMARY,
        )
        image_label.pack(fill="both", expand=True, padx=8, pady=8)
        image_label.bind(
            "<ButtonRelease-1>", self._on_clipboard_map_click_close, add="+"
        )
        self._clipboard_map_set_geometry(target_width, target_height)
        return True

    def _clipboard_map_show_error(self, request_id: int, error_text: str) -> None:
        if request_id != self._clipboard_map_request_id:
            return
        self._clipboard_map_show_message(f"Failed to load map image\n{error_text}")

    def _on_clipboard_map_click_close(self, _event: Optional[tk.Event] = None) -> str:
        try:
            self._window.after(1, self._close_clipboard_map_overlay)
        except Exception:
            self._close_clipboard_map_overlay()
        return "break"

    def _on_clipboard_map_focus_out(self, _event: Optional[tk.Event] = None) -> None:
        def close_if_unfocused() -> None:
            popup = self._clipboard_map_window
            if popup is None or not popup.winfo_exists():
                return

            try:
                focused_widget = popup.focus_displayof()
            except Exception:
                focused_widget = None

            if focused_widget is None:
                self._close_clipboard_map_overlay()
                return

            try:
                if str(focused_widget).startswith(str(popup)):
                    return
            except Exception:
                pass

            self._close_clipboard_map_overlay()

        try:
            self._window.after(80, close_if_unfocused)
        except Exception:
            close_if_unfocused()

    def _on_clipboard_map_link_click(
        self, _event: Optional[tk.Event], map_url: str
    ) -> str:
        self._open_external_map_link(map_url)
        return self._on_clipboard_map_click_close(_event)

    def _close_clipboard_map_overlay(self, _event: Optional[tk.Event] = None) -> None:
        self._clipboard_map_request_id += 1
        if self._clipboard_map_window is not None:
            try:
                self._clipboard_map_window.grab_release()
            except Exception:
                pass
            try:
                self._clipboard_map_window.destroy()
            except Exception:
                pass
        self._clipboard_map_window = None
        self._clipboard_map_body = None
        self._clipboard_map_link_label = None
        self._clipboard_map_photo = None

    def show_map_overlay_for_map_name(self, map_name: str) -> bool:
        if not self._is_map_layout_overlay_enabled():
            return False

        row = self._find_map_row_by_name(map_name)
        if row is None:
            return False

        image_url = str(row.get("layoutUrl", "")).strip()
        map_url = str(row.get("mapUrl", "")).strip()
        visible_name = str(row.get("mapName", "")).strip() or map_name
        if not image_url:
            return False

        self._close_clipboard_map_overlay()

        popup = tk.Toplevel(self._master)
        popup.title(visible_name)
        popup.configure(bg=theme.BORDER_PRIMARY)
        popup.protocol("WM_DELETE_WINDOW", self._close_clipboard_map_overlay)
        popup.bind("<Escape>", self._close_clipboard_map_overlay)
        popup.bind("<FocusOut>", self._on_clipboard_map_focus_out, add="+")
        popup.bind("<Unmap>", self._close_clipboard_map_overlay, add="+")
        popup.bind("<ButtonRelease-1>", self._on_clipboard_map_click_close, add="+")
        try:
            popup.attributes("-topmost", True)
        except Exception:
            pass

        wrapper = tk.Frame(popup, bg=theme.BG_PRIMARY, padx=2, pady=2)
        wrapper.pack(fill="both", expand=True)
        wrapper.bind("<ButtonRelease-1>", self._on_clipboard_map_click_close, add="+")

        top_bar = tk.Frame(wrapper, bg=theme.BG_SECONDARY, padx=10, pady=8)
        top_bar.pack(fill="x")
        top_bar.bind("<ButtonRelease-1>", self._on_clipboard_map_click_close, add="+")

        title = tk.Label(
            top_bar,
            text=visible_name,
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_HEADER,
            anchor="w",
        )
        title.pack(side="left", anchor="w")
        title.bind("<ButtonRelease-1>", self._on_clipboard_map_click_close, add="+")

        if map_url:
            link_font = ("Segoe UI", 9, "underline")
            link_label = tk.Label(
                top_bar,
                text=map_url,
                bg=theme.BG_SECONDARY,
                fg=theme.RARITY_MAGIC,
                font=link_font,
                cursor="hand2",
                anchor="e",
                justify="right",
            )
            link_label.pack(side="right", anchor="e")
            link_label.bind(
                "<ButtonRelease-1>",
                lambda _event, current_url=map_url: self._on_clipboard_map_link_click(
                    _event, current_url
                ),
            )
            self._clipboard_map_link_label = link_label

        body = tk.Frame(wrapper, bg=theme.BG_PRIMARY)
        body.pack(fill="both", expand=True)
        body.bind("<ButtonRelease-1>", self._on_clipboard_map_click_close, add="+")

        self._clipboard_map_window = popup
        self._clipboard_map_body = body
        self._clipboard_map_photo = None
        request_id = self._clipboard_map_request_id

        self._clipboard_map_show_message("Loading map image...")
        popup.update_idletasks()
        self._clipboard_map_set_geometry(640, 420)
        try:
            popup.lift()
            popup.focus_force()
            popup.grab_set()
        except Exception:
            pass

        cached_payload = self._read_layout_cache_bytes(image_url)
        if cached_payload is not None:
            if self._clipboard_map_show_image(request_id, cached_payload):
                return True

        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

        def load_image_bytes() -> None:
            try:
                request = urllib.request.Request(
                    image_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0 Safari/537.36"
                        )
                    },
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    payload = response.read()
            except Exception as error:
                result_queue.put(("error", str(error)))
                return

            result_queue.put(("downloaded", payload))

        def poll_download_result() -> None:
            if request_id != self._clipboard_map_request_id:
                return
            if self._clipboard_map_window is None:
                return
            if not self._clipboard_map_window.winfo_exists():
                return

            try:
                result_kind, result_value = result_queue.get_nowait()
            except queue.Empty:
                try:
                    self._window.after(80, poll_download_result)
                except Exception:
                    pass
                return

            if result_kind == "downloaded":
                rendered = self._clipboard_map_show_image(request_id, result_value)
                if rendered:
                    self._write_layout_cache_bytes(image_url, result_value)
                return
            self._clipboard_map_show_error(request_id, str(result_value))

        threading.Thread(target=load_image_bytes, daemon=True).start()
        try:
            self._window.after(80, poll_download_result)
        except Exception:
            self._clipboard_map_show_error(
                request_id,
                "UI loop is not active for preview update",
            )
        return True

    def _truncate_text(self, value: Any, max_length: int) -> str:
        text = str(value or "").strip()
        if len(text) <= max_length:
            return text
        return f"{text[: max_length - 3].rstrip()}..."

    def _layout_preview_set_geometry(
        self, content_width: int, content_height: int
    ) -> None:
        if self._layout_preview_window is None:
            return

        self._window.update_idletasks()

        popup_width = max(120, content_width + 8)
        popup_height = max(80, content_height + 8)
        popup_x = (
            self._window.winfo_rootx() + (self._window.winfo_width() - popup_width) // 2
        )
        popup_y = (
            self._window.winfo_rooty()
            + (self._window.winfo_height() - popup_height) // 2
        )

        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        popup_x = max(0, min(popup_x, max(0, screen_w - popup_width)))
        popup_y = max(0, min(popup_y, max(0, screen_h - popup_height)))

        self._layout_preview_window.geometry(
            f"{popup_width}x{popup_height}+{popup_x}+{popup_y}"
        )

    def _layout_preview_show_message(self, message: str, width: int = 460) -> None:
        if self._layout_preview_body is None:
            return

        for child in self._layout_preview_body.winfo_children():
            child.destroy()

        label = tk.Label(
            self._layout_preview_body,
            text=message,
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_BODY,
            justify="center",
            anchor="center",
            wraplength=max(240, width - 40),
        )
        label.pack(fill="both", expand=True, padx=12, pady=12)
        label.bind("<Button-1>", self._close_layout_preview)
        self._layout_preview_set_geometry(width, 120)

    def _layout_preview_show_image(self, request_id: int, image_bytes: bytes) -> bool:
        if request_id != self._layout_preview_request_id:
            return False
        if self._layout_preview_window is None or self._layout_preview_body is None:
            return False
        if not self._layout_preview_window.winfo_exists():
            return False

        try:
            source_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        except Exception as error:
            self._layout_preview_show_message(f"Failed to render map image\n{error}")
            return False

        self._window.update_idletasks()
        max_width = max(240, int(self._window.winfo_width() * 0.9))
        max_height = max(240, int(self._window.winfo_height() * 0.9))
        scale = min(
            max_width / source_image.width,
            max_height / source_image.height,
            1.0,
        )
        target_width = max(1, int(source_image.width * scale))
        target_height = max(1, int(source_image.height * scale))

        preview_image = source_image.resize(
            (target_width, target_height), Image.LANCZOS
        )
        self._layout_preview_photo = ImageTk.PhotoImage(preview_image)

        for child in self._layout_preview_body.winfo_children():
            child.destroy()

        image_label = tk.Label(
            self._layout_preview_body,
            image=self._layout_preview_photo,
            bg=theme.BG_PRIMARY,
        )
        image_label.pack(fill="both", expand=True)
        image_label.bind("<Button-1>", self._close_layout_preview)
        self._layout_preview_set_geometry(target_width, target_height)
        return True

    def _layout_preview_show_error(self, request_id: int, error_text: str) -> None:
        if request_id != self._layout_preview_request_id:
            return
        self._layout_preview_show_message(f"Failed to load map image\n{error_text}")

    def _close_layout_preview(self, _event: Optional[tk.Event] = None) -> None:
        self._layout_preview_request_id += 1

        if self._layout_preview_close_binding is not None:
            try:
                self._window.unbind("<Button-1>", self._layout_preview_close_binding)
            except Exception:
                pass
            self._layout_preview_close_binding = None

        if self._layout_preview_window is not None:
            try:
                self._layout_preview_window.destroy()
            except Exception:
                pass
        self._layout_preview_window = None
        self._layout_preview_body = None
        self._layout_preview_photo = None

    def _show_layout_preview_overlay(self, image_url: str) -> None:
        if not image_url:
            return

        self._close_layout_preview()

        popup = tk.Toplevel(self._window)
        popup.transient(self._window)
        popup.overrideredirect(False)
        popup.title("Layout preview")
        popup.configure(bg=theme.BORDER_PRIMARY)
        popup.protocol("WM_DELETE_WINDOW", self._close_layout_preview)
        try:
            popup.attributes("-topmost", True)
        except Exception:
            pass

        frame = tk.Frame(popup, bg=theme.BG_PRIMARY, padx=2, pady=2)
        frame.pack(fill="both", expand=True)

        popup.bind("<Button-1>", self._close_layout_preview)
        frame.bind("<Button-1>", self._close_layout_preview)
        popup.bind("<Escape>", self._close_layout_preview)

        self._layout_preview_window = popup
        self._layout_preview_body = frame
        self._layout_preview_photo = None

        self._layout_preview_show_message("Loading map image...")
        popup.update_idletasks()
        try:
            popup.lift()
            popup.focus_force()
        except Exception:
            pass

        request_id = self._layout_preview_request_id

        cached_payload = self._read_layout_cache_bytes(image_url)
        if cached_payload is not None:
            if self._layout_preview_show_image(request_id, cached_payload):
                return

        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

        def load_image_bytes() -> None:
            try:
                request = urllib.request.Request(
                    image_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0 Safari/537.36"
                        )
                    },
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    payload = response.read()
            except Exception as error:
                result_queue.put(("error", str(error)))
                return

            result_queue.put(("downloaded", payload))

        def poll_download_result() -> None:
            if request_id != self._layout_preview_request_id:
                return
            if self._layout_preview_window is None:
                return
            if not self._layout_preview_window.winfo_exists():
                return

            try:
                result_kind, result_value = result_queue.get_nowait()
            except queue.Empty:
                try:
                    self._window.after(80, poll_download_result)
                except Exception:
                    pass
                return

            if result_kind == "downloaded":
                rendered = self._layout_preview_show_image(request_id, result_value)
                if rendered:
                    self._write_layout_cache_bytes(image_url, result_value)
                return
            self._layout_preview_show_error(request_id, str(result_value))

        threading.Thread(target=load_image_bytes, daemon=True).start()
        try:
            self._window.after(80, poll_download_result)
        except Exception:
            self._layout_preview_show_error(
                request_id,
                "UI loop is not active for preview update",
            )

    def _refresh_map_table_rows(self, rows_container: tk.Frame) -> None:
        for child in rows_container.winfo_children():
            child.destroy()

        rows = self._get_sorted_filtered_map_rows()
        if not rows:
            empty = tk.Label(
                rows_container,
                text="No maps found",
                bg=theme.BG_PRIMARY,
                fg=theme.FG_SECONDARY,
                font=theme.FONT_BODY,
                anchor="w",
            )
            empty.pack(fill="x", padx=10, pady=(8, 0))
            return

        link_font = ("Segoe UI", 9, "underline")

        for row_index, row in enumerate(rows):
            row_bg = theme.BG_SECONDARY if row_index % 2 == 0 else theme.HOVER_COLOR
            row_frame = tk.Frame(rows_container, bg=row_bg)
            row_frame.configure(height=self._map_row_height)
            row_frame.pack(fill="x")
            row_frame.grid_propagate(False)

            row_frame.grid_columnconfigure(
                0, weight=0, minsize=self._map_col_name_width
            )
            row_frame.grid_columnconfigure(
                1, weight=0, minsize=self._map_col_img_layout_width
            )
            row_frame.grid_columnconfigure(
                2, weight=0, minsize=self._map_col_layout_width
            )
            row_frame.grid_columnconfigure(
                3, weight=0, minsize=self._map_col_density_width
            )
            row_frame.grid_columnconfigure(
                4, weight=0, minsize=self._map_col_tags_width
            )

            map_name = str(row.get("mapName", ""))
            map_url = str(row.get("mapUrl", ""))
            layout_url = str(row.get("layoutUrl", ""))
            tags_value = str(row.get("tags", ""))

            name_label = tk.Label(
                row_frame,
                text=self._truncate_text(map_name, 34),
                bg=row_bg,
                fg=theme.RARITY_MAGIC if map_url else theme.FG_PRIMARY,
                font=link_font if map_url else theme.FONT_BODY,
                anchor="w",
                justify="left",
                cursor="hand2" if map_url else "",
            )
            name_label.grid(row=0, column=0, sticky="nsew", padx=(10, 8), pady=6)
            if map_url:
                name_label.bind(
                    "<Button-1>",
                    lambda _event, current_url=map_url: self._open_external_map_link(
                        current_url
                    ),
                )

            layout_button = tk.Button(
                row_frame,
                text="Show map" if layout_url else "-",
                bg=theme.BG_PRIMARY,
                fg=theme.FG_PRIMARY,
                activebackground=theme.HOVER_COLOR,
                activeforeground=theme.FG_PRIMARY,
                relief="flat",
                bd=0,
                font=theme.FONT_HEADER,
                anchor="center",
                state="normal" if layout_url else "disabled",
                command=lambda current_layout_url=layout_url: (
                    self._show_layout_preview_overlay(current_layout_url)
                ),
            )
            layout_button.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

            layout_value_label = tk.Label(
                row_frame,
                text=str(row.get("layout", 0)),
                bg=row_bg,
                fg=theme.FG_PRIMARY,
                font=theme.FONT_BODY,
                anchor="center",
            )
            layout_value_label.grid(row=0, column=2, sticky="nsew", padx=6, pady=6)

            density_label = tk.Label(
                row_frame,
                text=str(row.get("density", 0)),
                bg=row_bg,
                fg=theme.FG_PRIMARY,
                font=theme.FONT_BODY,
                anchor="center",
            )
            density_label.grid(row=0, column=3, sticky="nsew", padx=6, pady=6)

            tags_label = tk.Label(
                row_frame,
                text=self._truncate_text(tags_value, 72),
                bg=row_bg,
                fg=theme.FG_SECONDARY,
                font=theme.FONT_BODY,
                anchor="w",
                justify="left",
            )
            tags_label.grid(row=0, column=4, sticky="nsew", padx=(6, 10), pady=6)

    def _on_map_search_change(
        self,
        _event: tk.Event,
        search_var: tk.StringVar,
        rows_container: tk.Frame,
    ) -> None:
        self._map_search_query = search_var.get()
        self._refresh_map_table_rows(rows_container)

    def _save_overlay_menu_state(self) -> None:
        overlay_cfg = self._settings.setdefault("overlay", {})
        if not isinstance(overlay_cfg, dict):
            return

        serialized_items = []
        for item in self._menu_items:
            if item.get("type") != "user":
                continue

            images = []
            raw_images = item.get("images", [])
            if not isinstance(raw_images, list):
                raw_images = []
            for raw_image in raw_images:
                image_entry = self._normalize_image_entry(raw_image)
                if image_entry is not None:
                    images.append(image_entry)

            serialized_items.append(
                {
                    "id": str(item.get("id", "")).strip(),
                    "name": str(item.get("name", "")).strip(),
                    "images": images,
                }
            )

        overlay_cfg["menu_items"] = serialized_items
        overlay_cfg["active_item_id"] = self._active_item_id

        if self._save_settings_callback is not None:
            try:
                self._save_settings_callback()
            except Exception:
                pass

    def _on_content_inner_configure(self, _event: tk.Event) -> None:
        self._content_canvas.configure(scrollregion=self._content_canvas.bbox("all"))

    def _on_content_canvas_configure(self, event: tk.Event) -> None:
        self._content_canvas.itemconfigure(
            self._content_canvas_window,
            width=event.width,
        )

    def _on_menu_list_configure(self, _event: tk.Event) -> None:
        self._menu_canvas.configure(scrollregion=self._menu_canvas.bbox("all"))

    def _on_menu_canvas_configure(self, event: tk.Event) -> None:
        self._menu_canvas.itemconfigure(
            self._menu_canvas_window,
            width=event.width,
        )

    def _on_menu_mouse_wheel(self, event: tk.Event) -> str | None:
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return None

        steps = -1 if delta > 0 else 1
        self._menu_canvas.yview_scroll(steps, "units")
        return "break"

    def _build_menu_hotkey_lookup(self) -> dict[str, int]:
        lookup: dict[str, int] = {}
        for index, hotkey in enumerate(self._MENU_HOTKEY_SEQUENCE, start=1):
            normalized_hotkey = hotkey.strip().upper()
            if not normalized_hotkey:
                continue
            lookup[normalized_hotkey] = index
        return lookup

    def _menu_hotkey_label(self, index: int) -> str | None:
        if index <= 0:
            return None
        if index > len(self._MENU_HOTKEY_SEQUENCE):
            return None
        return self._MENU_HOTKEY_SEQUENCE[index - 1]

    def _is_image_canvas_widget(self, widget: Any) -> bool:
        current = widget
        while current is not None:
            for state in self._image_states:
                if current == state.get("canvas"):
                    return True
            current = getattr(current, "master", None)
        return False

    def _on_overlay_mouse_wheel(self, event: tk.Event) -> str | None:
        if self._is_image_canvas_widget(getattr(event, "widget", None)):
            return None

        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return None

        if delta > 0:
            steps = -1
        else:
            steps = 1

        self._content_canvas.yview_scroll(steps, "units")
        return "break"

    def _refresh_menu(self) -> None:
        for child in self._menu_list.winfo_children():
            child.destroy()
        self._menu_buttons.clear()

        for index, item in enumerate(self._menu_items, start=1):
            item_id = item["id"]
            hotkey_label = self._menu_hotkey_label(index)
            if hotkey_label is None:
                button_text = f"{item['name']}"
            else:
                button_text = f"[{hotkey_label}] {item['name']}"
            button = tk.Button(
                self._menu_list,
                text=button_text,
                bg=theme.BG_PRIMARY,
                fg=theme.FG_PRIMARY,
                activebackground=theme.HOVER_COLOR,
                activeforeground=theme.FG_PRIMARY,
                relief="flat",
                bd=0,
                padx=12,
                pady=10,
                anchor="w",
                font=theme.FONT_HEADER,
                command=lambda menu_item_id=item_id: self._select_item(menu_item_id),
            )
            button.pack(fill="x", pady=2)

            if item_id == self._active_item_id:
                button.configure(bg=theme.HOVER_COLOR)

            if item["type"] == "user":
                button.bind(
                    "<ButtonPress-1>",
                    lambda event, menu_item_id=item_id: self._start_drag(
                        event, menu_item_id
                    ),
                )
                button.bind("<B1-Motion>", self._on_drag_motion)
                button.bind("<ButtonRelease-1>", self._finish_drag)
                button.bind(
                    "<Button-3>",
                    lambda event, menu_item_id=item_id: self._show_item_context_menu(
                        event, menu_item_id
                    ),
                )

            self._menu_buttons[item_id] = button

    def _extract_menu_hotkey_index(self, event: tk.Event) -> int | None:
        keysym = str(getattr(event, "keysym", "") or "")
        if not keysym:
            return None

        if keysym.startswith("KP_"):
            suffix = keysym.split("_", 1)[1].strip().upper()
            if suffix in self._menu_hotkey_lookup:
                return self._menu_hotkey_lookup[suffix]
            return None

        normalized_keysym = keysym.strip().upper()
        return self._menu_hotkey_lookup.get(normalized_keysym)

    def _on_menu_hotkey_press(self, event: tk.Event) -> None:
        hotkey_index = self._extract_menu_hotkey_index(event)
        if hotkey_index is None:
            return

        focused_widget = self._window.focus_get()
        if isinstance(focused_widget, (tk.Entry, tk.Text)):
            return

        if hotkey_index > len(self._menu_items):
            return

        item = self._menu_items[hotkey_index - 1]
        item_id = str(item.get("id", "")).strip()
        if item_id:
            self._select_item(item_id)

    def _select_item(self, item_id: str) -> None:
        self._active_item_id = item_id
        for current_id, button in self._menu_buttons.items():
            button.configure(
                bg=theme.HOVER_COLOR if current_id == item_id else theme.BG_PRIMARY
            )
        self._render_content()
        self._save_overlay_menu_state()

    def _get_item(self, item_id: str):
        for item in self._menu_items:
            if item["id"] == item_id:
                return item
        return None

    def _clear_content(self) -> None:
        for state in self._image_states:
            self._cancel_pending_image_redraw(state)
        for child in self._content_inner.winfo_children():
            if child == self._map_panel and self._map_panel is not None:
                self._map_panel.pack_forget()
                continue
            child.destroy()
        self._image_states = []
        self._content_canvas.yview_moveto(0.0)

    def _render_content(self) -> None:
        self._clear_content()
        item = self._get_item(self._active_item_id)
        if item is None:
            return
        if item["type"] == "program":
            self._render_program_item(item)
            return
        self._render_user_item(item)

    def _render_program_item(self, item) -> None:
        if item.get("program_key") == "commands":
            self._render_commands_program_item(item)
            return
        if item.get("program_key") == "map":
            self._render_map_program_item(item)
            return

        panel = tk.Frame(self._content_inner, bg=theme.BG_PRIMARY)
        panel.pack(fill="both", expand=True, padx=40, pady=40)

        title = tk.Label(
            panel,
            text=f"{item['name']} - program action",
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_TITLE,
            anchor="w",
            justify="left",
        )
        title.pack(anchor="w", pady=(0, 12))

        description = tk.Label(
            panel,
            text="Placeholder: this section executes program logic instead of image content.",
            bg=theme.BG_PRIMARY,
            fg=theme.FG_SECONDARY,
            font=theme.FONT_BODY,
            anchor="w",
            justify="left",
        )
        description.pack(anchor="w", pady=(0, 14))

        feedback_var = tk.StringVar(value="")

        def run_stub() -> None:
            feedback_var.set("MAP placeholder executed.")

        action = tk.Button(
            panel,
            text="Run MAP placeholder",
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.HOVER_COLOR,
            activeforeground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            font=theme.FONT_BODY,
            command=run_stub,
        )
        action.pack(anchor="w")

        feedback = tk.Label(
            panel,
            textvariable=feedback_var,
            bg=theme.BG_PRIMARY,
            fg=theme.ACCENT_GREEN,
            font=theme.FONT_BODY,
            anchor="w",
            justify="left",
        )
        feedback.pack(anchor="w", pady=(10, 0))

    def _render_info_block(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str = "",
    ) -> tk.Frame:
        block = tk.Frame(
            parent,
            bg=theme.BG_SECONDARY,
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.BORDER_PRIMARY,
        )
        block.pack(fill="x", pady=(0, 10))

        title_label = tk.Label(
            block,
            text=title,
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_HEADER,
            anchor="w",
            justify="left",
            padx=12,
            pady=8,
        )
        title_label.pack(fill="x")

        if subtitle:
            subtitle_label = tk.Label(
                block,
                text=subtitle,
                bg=theme.BG_SECONDARY,
                fg=theme.FG_SECONDARY,
                font=theme.FONT_BODY,
                anchor="w",
                justify="left",
                wraplength=920,
                padx=12,
            )
            subtitle_label.pack(fill="x", pady=(0, 10))

        return block

    def _render_commands_program_item(self, item) -> None:
        panel = tk.Frame(self._content_inner, bg=theme.BG_PRIMARY)
        panel.pack(fill="both", expand=True, padx=24, pady=24)

        title = tk.Label(
            panel,
            text=item.get("name", "Commands"),
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_TITLE,
            anchor="w",
        )
        title.pack(anchor="w", pady=(0, 12))

        self._render_info_block(
            panel,
            "Commands",
            "Various functions can be executed by entering commands in the chat console. "
            "The syntax of a command is a forward slash (/) followed by a string. "
            "Commands that require additional parameters are appended after the command "
            "string followed by a space.",
        )

        for command, details in self._chat_commands_data():
            self._render_info_block(panel, command, details)

        popular_channels_block = self._render_info_block(
            panel,
            "Popular channels",
            "Commonly used chat channels from the PoE community.",
        )
        for channel_name, channel_desc in self._chat_popular_channels_data():
            channel_row = tk.Label(
                popular_channels_block,
                text=f"{channel_name} - {channel_desc}",
                bg=theme.BG_SECONDARY,
                fg=theme.FG_PRIMARY,
                font=theme.FONT_BODY,
                anchor="w",
                justify="left",
                wraplength=920,
                padx=12,
            )
            channel_row.pack(fill="x", pady=(0, 8))

        chatting_block = self._render_info_block(
            panel,
            "Chatting",
            "Domains, tags, and shortcuts used to choose message destination.",
        )
        for domain, tag, shortcut, purpose in self._chatting_domains_data():
            domain_row = tk.Label(
                chatting_block,
                text=f"{domain} | Tag: {tag} | Shortcut: {shortcut} | {purpose}",
                bg=theme.BG_SECONDARY,
                fg=theme.FG_PRIMARY,
                font=theme.FONT_BODY,
                anchor="w",
                justify="left",
                wraplength=920,
                padx=12,
            )
            domain_row.pack(fill="x", pady=(0, 8))

        variables_block = self._render_info_block(
            panel,
            "Variables",
            "Dynamic variables usable with chat commands.",
        )
        for variable_name, variable_desc in self._chat_variables_data():
            variable_row = tk.Label(
                variables_block,
                text=f"{variable_name} - {variable_desc}",
                bg=theme.BG_SECONDARY,
                fg=theme.FG_PRIMARY,
                font=theme.FONT_BODY,
                anchor="w",
                justify="left",
                wraplength=920,
                padx=12,
            )
            variable_row.pack(fill="x", pady=(0, 8))

    def _chat_commands_data(self) -> list[tuple[str, str]]:
        return [
            ("/help", "Displays a list of most console commands."),
            (
                "/bug <description> /debug <description>",
                "Reports a bug and gives a report reference number.",
            ),
            ("/ladder", "Displays top ten characters on the current ladder."),
            ("/played", "Displays how long the current character has been played."),
            ("/age", "Displays how long ago the current character was created."),
            (
                "/passives",
                "Shows passive point summary and Deal with the Bandits reward.",
            ),
            ("/deaths", "Displays death count for current character."),
            ("/remaining", "Displays how many monsters remain in current area."),
            ("/destroy", "Use with caution. Destroys item on cursor."),
            (
                "/recoveroldcraftingbenchitem",
                "Recovers an item placed in old inaccessible crafting benches.",
            ),
            ("/itemlevel", "Displays level of item on cursor."),
            ("/pvp", "Displays PvP win/loss/disconnect statistics."),
            ("/fixmyhelmet", "Updates existing non-unique helmet to new art."),
            ("/oos", "Forces resync."),
            ("/dance", "Performs dance if owned as microtransaction."),
            ("/status <text>", "Changes your status message for friends."),
            ("/invite <character>", "Sends party invite to character."),
            ("/kick <character>", "Kicks character from party."),
            (
                "/party_description <description>",
                "Changes the description of your party.",
            ),
            (
                "/tradewith <character>",
                "Initiates trade with character in same town hub instance.",
            ),
            ("/friend <character>", "Adds character to friends list."),
            ("/unfriend <character>", "Removes character from friends list."),
            ("/accept <character>", "Accepts friend request."),
            ("/leave", "Leaves the party."),
            (
                "/ignore <character> /squelch <character>",
                "Adds character account to ignore list.",
            ),
            (
                "/unignore <character> /unsquelch <character>",
                "Removes character account from ignore list.",
            ),
            ("/clear_ignore_list", "Clears all ignored accounts."),
            (
                "/whois <character>",
                "Displays level, class, league, and online status.",
            ),
            (
                "/afk <message>",
                "Turns AFK mode on and auto-replies to whispers.",
            ),
            ("/afkoff", "Turns off AFK mode."),
            (
                "/dnd <message> /donotdisturb <message>",
                "Toggles Do Not Disturb mode for chat.",
            ),
            ("/global <number>", "Joins global chat channel number."),
            ("/trade <number>", "Joins trade chat channel number."),
            ("/cls /clear", "Clears chat console text."),
            ("/hideout", "Sends you to your hideout from town."),
            (
                "/hideout <character>",
                "Sends you to character's hideout from town.",
            ),
            ("/guild", "Sends you to guild hideout from town."),
            ("/menagerie", "Sends you to Menagerie from town."),
            ("/delve", "Sends you to Azurite Mine from town."),
            ("/sanctum", "Sends you to The Forbidden Sanctum from town."),
            ("/kingsmarch", "Sends you to Kingsmarch from town."),
            ("/heist", "Sends you to The Rogue Harbour from town."),
            ("/exit", "Exits game to character selection screen."),
            ("/reset_xp", "Resets experience-per-hour estimation tool."),
            (
                "/recheck_achievements",
                "Forces recheck of certain achievements.",
            ),
            (
                "/autoreply <message>",
                "Replies with message when someone whispers you.",
            ),
            ("/nochat /togglenochat", "Toggles chat suppression."),
            (
                "/save_hideout",
                "Saves current hideout layout to a file.",
            ),
            (
                "/spectate <character>",
                "Spectates a mutual friend or guildmate in PvP area.",
            ),
            (
                "/itemfilter <filter name>",
                "Sets and refreshes specified item filter.",
            ),
            ("/kills", "Displays total kills for current character."),
            (
                "/atlaspassives",
                "Displays atlas passive point summary for the league.",
            ),
            (
                "/reloaditemfilter",
                "Refreshes currently loaded item filter.",
            ),
            (
                "/convertracereward",
                "Use with caution. Destroys alternate art unique on cursor and grants item skin.",
            ),
        ]

    def _chat_popular_channels_data(self) -> list[tuple[str, str]]:
        return [
            (
                "Global 820",
                "Sharing common or uncommon quests, challenges, and group opportunities.",
            ),
            (
                "Trade 820",
                "Paid services, rare challenges, and expensive map services.",
            ),
            ("Global 100", "Discord Global channel."),
            ("Global 101", "Guild Recruitment channel."),
            ("Global 150", "Mapping channel."),
            ("Global 773", "SSF channel."),
            ("Global 911", "Righteous Fire players channel."),
            ("Trade 800", "Currency-only trading channel."),
            ("Global 6666", "Spectre trading / minion build players."),
            (
                "Trade 5055",
                "Non-trade community channel often used by experienced players.",
            ),
            ("Global 5055", "Reddit Global channel."),
            ("Trade 1", "Ruthless league trading channel."),
        ]

    def _chatting_domains_data(self) -> list[tuple[str, str, str, str]]:
        return [
            (
                "Local",
                "-",
                "<chat key>",
                "Chat with nearby players in town hub or zone instance.",
            ),
            (
                "Global",
                "#",
                "Shift + <chat key>",
                "Chat with many players in the same league.",
            ),
            (
                "Party",
                "%",
                "Ctrl + Shift + <chat key>",
                "Chat with all party members.",
            ),
            (
                "Whisper",
                "@<character>",
                "Ctrl + <chat key>",
                "Chat with a specific character; shortcut replies to last whisper.",
            ),
            (
                "Trade",
                "$",
                "-",
                "Chat for item trading.",
            ),
            (
                "Guild",
                "&",
                "-",
                "Guild chat channel.",
            ),
            (
                "Twitch",
                "^",
                "-",
                "Twitch chat via client (feature removed).",
            ),
        ]

    def _chat_variables_data(self) -> list[tuple[str, str]]:
        return [
            (
                "@last",
                "Targets last player who contacted you. Examples: '@last Thanks!', '/invite @last', '/tradewith @last', '/hideout @last'.",
            ),
        ]

    def _ensure_map_program_panel(self) -> None:
        if self._map_panel is not None and self._map_panel.winfo_exists():
            return

        panel = tk.Frame(self._content_inner, bg=theme.BG_PRIMARY)

        title = tk.Label(
            panel,
            text="MAP",
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_TITLE,
            anchor="w",
        )
        title.pack(anchor="w", pady=(0, 12))

        toggle_row = tk.Frame(panel, bg=theme.BG_PRIMARY)
        toggle_row.pack(fill="x", pady=(0, 8))

        map_overlay_enabled_var = tk.BooleanVar(
            value=self._is_map_layout_overlay_enabled()
        )
        map_overlay_toggle = tk.Checkbutton(
            toggle_row,
            text="Use map layout overlay",
            variable=map_overlay_enabled_var,
            onvalue=True,
            offvalue=False,
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.BG_PRIMARY,
            activeforeground=theme.FG_PRIMARY,
            selectcolor=theme.BG_SECONDARY,
            highlightthickness=0,
            bd=0,
            font=theme.FONT_BODY,
            command=lambda current_var=map_overlay_enabled_var: (
                self._set_map_layout_overlay_enabled(bool(current_var.get()))
            ),
        )
        map_overlay_toggle.pack(side="left", anchor="w")

        search_row = tk.Frame(panel, bg=theme.BG_PRIMARY)
        search_row.pack(fill="x", pady=(0, 10))

        search_label = tk.Label(
            search_row,
            text="Search by name:",
            bg=theme.BG_PRIMARY,
            fg=theme.FG_SECONDARY,
            font=theme.FONT_BODY,
            anchor="w",
        )
        search_label.pack(side="left", padx=(0, 8))

        search_var = tk.StringVar(value=self._map_search_query)
        search_input = tk.Entry(
            search_row,
            textvariable=search_var,
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            insertbackground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            font=theme.FONT_BODY,
        )
        search_input.pack(side="left", fill="x", expand=True)

        header = tk.Frame(
            panel,
            bg=theme.BG_SECONDARY,
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.BORDER_PRIMARY,
        )
        header.configure(height=self._map_header_height)
        header.pack(fill="x")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=0, minsize=self._map_col_name_width)
        header.grid_columnconfigure(1, weight=0, minsize=self._map_col_img_layout_width)
        header.grid_columnconfigure(2, weight=0, minsize=self._map_col_layout_width)
        header.grid_columnconfigure(3, weight=0, minsize=self._map_col_density_width)
        header.grid_columnconfigure(4, weight=0, minsize=self._map_col_tags_width)

        name_header = tk.Button(
            header,
            text="Map name (link)",
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.HOVER_COLOR,
            activeforeground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            font=theme.FONT_HEADER,
            anchor="w",
            command=lambda: self._toggle_map_sort("mapName"),
        )
        name_header.grid(row=0, column=0, sticky="ew")

        img_layout_header = tk.Label(
            header,
            text="Img layout",
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            padx=8,
            pady=8,
            font=theme.FONT_HEADER,
            anchor="center",
        )
        img_layout_header.grid(row=0, column=1, sticky="ew")

        layout_header = tk.Button(
            header,
            text="Layout",
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.HOVER_COLOR,
            activeforeground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            font=theme.FONT_HEADER,
            anchor="center",
            command=lambda: self._toggle_map_sort("layout"),
        )
        layout_header.grid(row=0, column=2, sticky="ew")

        density_header = tk.Button(
            header,
            text="Density",
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.HOVER_COLOR,
            activeforeground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            font=theme.FONT_HEADER,
            anchor="center",
            command=lambda: self._toggle_map_sort("density"),
        )
        density_header.grid(row=0, column=3, sticky="ew")

        tags_header = tk.Button(
            header,
            text="Tags",
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.HOVER_COLOR,
            activeforeground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            font=theme.FONT_HEADER,
            anchor="w",
            command=lambda: self._toggle_map_sort("tags"),
        )
        tags_header.grid(row=0, column=4, sticky="ew")

        rows_container = tk.Frame(
            panel,
            bg=theme.BG_PRIMARY,
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.BORDER_PRIMARY,
        )
        rows_container.pack(fill="both", expand=True)

        search_input.bind(
            "<KeyRelease>",
            lambda event, current_var=search_var, current_rows=rows_container: (
                self._on_map_search_change(
                    event,
                    current_var,
                    current_rows,
                )
            ),
        )

        self._map_panel = panel
        self._map_title_label = title
        self._map_rows_container = rows_container
        self._map_search_var = search_var
        self._map_overlay_enabled_var = map_overlay_enabled_var
        self._map_header_buttons = {
            "mapName": name_header,
            "layout": layout_header,
            "density": density_header,
            "tags": tags_header,
        }

    def _render_map_program_item(self, item) -> None:
        self._ensure_map_program_panel()
        if self._map_panel is None:
            return

        if self._map_title_label is not None and self._map_title_label.winfo_exists():
            self._map_title_label.configure(text=item.get("name", "MAP"))

        overlay_enabled = self._is_map_layout_overlay_enabled()
        if (
            self._map_overlay_enabled_var is not None
            and self._map_overlay_enabled_var.get() != overlay_enabled
        ):
            self._map_overlay_enabled_var.set(overlay_enabled)

        if (
            self._map_search_var is not None
            and self._map_search_var.get() != self._map_search_query
        ):
            self._map_search_var.set(self._map_search_query)

        self._map_panel.pack(fill="both", expand=True, padx=24, pady=24)
        self._refresh_map_sort_headers()

        if (
            self._map_rows_container is not None
            and self._map_rows_container.winfo_exists()
        ):
            self._refresh_map_table_rows(self._map_rows_container)

    def _render_user_item(self, item) -> None:
        panel = tk.Frame(self._content_inner, bg=theme.BG_PRIMARY)
        panel.pack(fill="both", expand=True, padx=24, pady=24)

        title = tk.Label(
            panel,
            text=item["name"],
            bg=theme.BG_PRIMARY,
            fg=theme.FG_PRIMARY,
            font=theme.FONT_TITLE,
            anchor="w",
        )
        title.pack(anchor="w", pady=(0, 12))

        images = item.get("images", [])
        if not images:
            empty = tk.Frame(panel, bg=theme.BG_PRIMARY)
            empty.pack(fill="both", expand=True)
            load_button = self._build_load_images_button(empty, item)
            load_button.pack(anchor="w", pady=(0, 0))
            return

        for index, image_entry in enumerate(images):
            card = tk.Frame(
                panel,
                bg=theme.BG_SECONDARY,
                bd=1,
                highlightthickness=1,
                highlightbackground=theme.BORDER_PRIMARY,
            )
            card.pack(fill="x", pady=(0, 12))

            path_label = tk.Label(
                card,
                text=os.path.basename(image_entry["path"]),
                bg=theme.BG_SECONDARY,
                fg=theme.FG_SECONDARY,
                font=theme.FONT_BODY,
                anchor="w",
                padx=10,
                pady=8,
            )
            path_label.pack(fill="x")

            canvas = tk.Canvas(
                card,
                bg=theme.BG_PRIMARY,
                height=self._image_canvas_height,
                highlightthickness=0,
                bd=0,
            )
            canvas.pack(fill="x", padx=10, pady=(0, 10))
            self._attach_image_interactions(canvas, item, index)

        load_more = self._build_load_images_button(panel, item)
        load_more.pack(anchor="w", pady=(4, 4))

    def _build_load_images_button(self, parent: tk.Widget, item):
        return tk.Button(
            parent,
            text="LOAD IMAGES",
            bg=theme.BG_SECONDARY,
            fg=theme.FG_PRIMARY,
            activebackground=theme.HOVER_COLOR,
            activeforeground=theme.FG_PRIMARY,
            relief="flat",
            bd=0,
            padx=14,
            pady=10,
            font=theme.FONT_HEADER,
            command=lambda current_item=item: self._load_images_for_item(current_item),
        )

    def _load_images_for_item(self, item) -> None:
        try:
            self._window.lift()
            self._window.focus_force()
        except Exception:
            pass

        selected_paths = filedialog.askopenfilenames(
            parent=self._window,
            title="Load images",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not selected_paths:
            return

        images = item.setdefault("images", [])
        for path in selected_paths:
            packaged_path = self._package_overlay_image(str(path))
            images.append(
                {
                    "path": packaged_path,
                    "zoom": 1.0,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                }
            )
        self._save_overlay_menu_state()
        self._render_content()

    def _attach_image_interactions(
        self, canvas: tk.Canvas, item, image_index: int
    ) -> None:
        image_entry = item["images"][image_index]
        try:
            pil_image = Image.open(image_entry["path"]).convert("RGBA")
        except Exception:
            canvas.create_text(
                10,
                10,
                text="Failed to load image",
                anchor="nw",
                fill=theme.ACCENT_RED,
                font=theme.FONT_BODY,
            )
            return

        state = {
            "canvas": canvas,
            "entry": image_entry,
            "image": pil_image,
            "photo": None,
            "render_cache": {},
            "render_key": None,
            "canvas_image_id": None,
            "preview_job": None,
            "high_quality_job": None,
            "preview_image": None,
            "preview_ratio": 1.0,
            "is_panning": False,
            "preview_interval_ms": self._get_preview_interval_ms(pil_image),
            "pan_x": 0,
            "pan_y": 0,
            "base_zoom": 1.0,
            "menu_item_id": item["id"],
            "image_index": image_index,
        }
        self._image_states.append(state)

        canvas.bind(
            "<Configure>",
            lambda event, image_state=state: self._draw_image(
                image_state, event.width, event.height
            ),
        )
        canvas.bind(
            "<MouseWheel>",
            lambda event, image_state=state: self._on_image_wheel(event, image_state),
        )
        canvas.bind(
            "<ButtonPress-1>",
            lambda event, image_state=state: self._start_pan(event, image_state),
        )
        canvas.bind(
            "<B1-Motion>",
            lambda event, image_state=state: self._on_pan(event, image_state),
        )
        canvas.bind(
            "<ButtonRelease-1>",
            lambda event, image_state=state: self._end_pan(event, image_state),
        )
        canvas.bind(
            "<Button-3>",
            lambda event, image_state=state: self._show_image_context_menu(
                event, image_state
            ),
        )

        canvas.after(0, lambda image_state=state: self._draw_image(image_state))

    def _cancel_pending_image_redraw(self, state) -> None:
        for job_key in ("preview_job", "high_quality_job"):
            redraw_job = state.get(job_key)
            if redraw_job is None:
                continue
            try:
                state["canvas"].after_cancel(redraw_job)
            except Exception:
                pass
            state[job_key] = None

    def _get_preview_interval_ms(self, image) -> int:
        pixel_count = int(image.width * image.height)
        if pixel_count >= 20000000:
            return 30
        if pixel_count >= 12000000:
            return 24
        if pixel_count >= 8000000:
            return 20
        return 14

    def _get_interaction_preview_source(self, state):
        preview_image = state.get("preview_image")
        preview_ratio = float(state.get("preview_ratio", 1.0))
        if preview_image is not None and preview_ratio > 0.0:
            return preview_image, preview_ratio

        image = state["image"]
        max_preview_dim = 1920
        longest_side = max(int(image.width), int(image.height))
        if longest_side <= max_preview_dim:
            state["preview_image"] = image
            state["preview_ratio"] = 1.0
            return image, 1.0

        preview_ratio = max_preview_dim / float(longest_side)
        preview_width = max(1, int(image.width * preview_ratio))
        preview_height = max(1, int(image.height * preview_ratio))
        try:
            preview_image = image.resize(
                (preview_width, preview_height), Image.BILINEAR
            )
        except Exception:
            preview_image = image
            preview_ratio = 1.0
        state["preview_image"] = preview_image
        state["preview_ratio"] = preview_ratio
        return preview_image, preview_ratio

    def _request_preview_redraw(self, state) -> None:
        if state.get("preview_job") is not None:
            return
        canvas = state["canvas"]
        if not canvas.winfo_exists():
            return
        delay_ms = max(12, int(state.get("preview_interval_ms", 14)))
        state["preview_job"] = canvas.after(
            delay_ms,
            lambda image_state=state: self._run_preview_redraw(image_state),
        )

    def _run_preview_redraw(self, state) -> None:
        state["preview_job"] = None
        self._draw_image(state, resample=Image.BILINEAR, interaction_mode=True)

    def _schedule_high_quality_redraw(self, state, delay_ms: int = 120) -> None:
        redraw_job = state.get("high_quality_job")
        if redraw_job is not None:
            try:
                state["canvas"].after_cancel(redraw_job)
            except Exception:
                pass
        canvas = state["canvas"]
        if not canvas.winfo_exists():
            state["high_quality_job"] = None
            return
        state["high_quality_job"] = canvas.after(
            delay_ms,
            lambda image_state=state: self._run_high_quality_redraw(image_state),
        )

    def _run_high_quality_redraw(self, state) -> None:
        state["high_quality_job"] = None
        self._draw_image(state, resample=Image.LANCZOS)

    def _draw_image(
        self,
        state,
        width: int | None = None,
        height: int | None = None,
        resample: int = Image.LANCZOS,
        interaction_mode: bool = False,
    ) -> None:
        canvas = state["canvas"]
        if not canvas.winfo_exists():
            return
        canvas_width = int(width or canvas.winfo_width() or 1)
        canvas_height = int(height or canvas.winfo_height() or 1)
        image = state["image"]
        if canvas_width <= 1 or canvas_height <= 1:
            return

        base_zoom = min(canvas_width / image.width, canvas_height / image.height)
        state["base_zoom"] = max(base_zoom, 0.01)
        zoom = max(0.2, min(8.0, float(state["entry"].get("zoom", 1.0))))
        state["entry"]["zoom"] = zoom

        scale = state["base_zoom"] * zoom
        offset_x = float(state["entry"].get("offset_x", 0.0))
        offset_y = float(state["entry"].get("offset_y", 0.0))
        center_x = canvas_width / 2 + offset_x
        center_y = canvas_height / 2 + offset_y

        scaled_width = image.width * scale
        scaled_height = image.height * scale
        image_left = center_x - scaled_width / 2
        image_top = center_y - scaled_height / 2
        image_right = image_left + scaled_width
        image_bottom = image_top + scaled_height

        visible_left = max(0.0, image_left)
        visible_top = max(0.0, image_top)
        visible_right = min(float(canvas_width), image_right)
        visible_bottom = min(float(canvas_height), image_bottom)

        canvas_image_id = state.get("canvas_image_id")
        if visible_right <= visible_left or visible_bottom <= visible_top:
            if canvas_image_id is not None:
                try:
                    canvas.itemconfigure(canvas_image_id, state="hidden")
                except Exception:
                    pass
            return

        source_left = max(0.0, (visible_left - image_left) / scale)
        source_top = max(0.0, (visible_top - image_top) / scale)
        source_right = min(float(image.width), (visible_right - image_left) / scale)
        source_bottom = min(float(image.height), (visible_bottom - image_top) / scale)

        crop_left = max(0, min(image.width - 1, int(source_left)))
        crop_top = max(0, min(image.height - 1, int(source_top)))
        crop_right = max(crop_left + 1, min(image.width, int(source_right + 1)))
        crop_bottom = max(crop_top + 1, min(image.height, int(source_bottom + 1)))

        source_image = image
        source_ratio = 1.0
        source_mode = "full"
        if interaction_mode:
            source_image, source_ratio = self._get_interaction_preview_source(state)
            source_mode = "preview"

        source_crop_left = crop_left
        source_crop_top = crop_top
        source_crop_right = crop_right
        source_crop_bottom = crop_bottom
        if source_ratio != 1.0:
            source_crop_left = max(
                0,
                min(source_image.width - 1, int(crop_left * source_ratio)),
            )
            source_crop_top = max(
                0,
                min(source_image.height - 1, int(crop_top * source_ratio)),
            )
            source_crop_right = max(
                source_crop_left + 1,
                min(source_image.width, int(crop_right * source_ratio + 1)),
            )
            source_crop_bottom = max(
                source_crop_top + 1,
                min(source_image.height, int(crop_bottom * source_ratio + 1)),
            )

        draw_x = image_left + crop_left * scale
        draw_y = image_top + crop_top * scale
        draw_width = max(1, int((crop_right - crop_left) * scale))
        draw_height = max(1, int((crop_bottom - crop_top) * scale))

        cache_key = (
            source_mode,
            source_crop_left,
            source_crop_top,
            source_crop_right,
            source_crop_bottom,
            draw_width,
            draw_height,
            int(resample),
        )
        render_cache = state.get("render_cache", {})
        photo = render_cache.get(cache_key)
        if photo is None:
            cropped = source_image.crop(
                (
                    source_crop_left,
                    source_crop_top,
                    source_crop_right,
                    source_crop_bottom,
                )
            )
            resized = cropped.resize((draw_width, draw_height), resample)
            photo = ImageTk.PhotoImage(resized)
            render_cache[cache_key] = photo
            while len(render_cache) > 8:
                oldest_key = next(iter(render_cache))
                render_cache.pop(oldest_key, None)
            state["render_cache"] = render_cache
        state["photo"] = photo

        if canvas_image_id is None:
            canvas_image_id = canvas.create_image(
                draw_x,
                draw_y,
                image=photo,
                anchor="nw",
            )
            state["canvas_image_id"] = canvas_image_id
            state["render_key"] = cache_key
            return

        try:
            canvas.itemconfigure(canvas_image_id, state="normal")
            canvas.coords(canvas_image_id, draw_x, draw_y)
            if state.get("render_key") != cache_key:
                canvas.itemconfigure(canvas_image_id, image=photo)
                state["render_key"] = cache_key
        except Exception:
            canvas.delete("all")
            state["canvas_image_id"] = canvas.create_image(
                draw_x,
                draw_y,
                image=photo,
                anchor="nw",
            )
            state["render_key"] = cache_key

    def _on_image_wheel(self, event: tk.Event, state) -> str:
        delta = 1.1 if event.delta > 0 else 0.9
        current = float(state["entry"].get("zoom", 1.0))
        state["entry"]["zoom"] = max(0.2, min(8.0, current * delta))

        self._request_preview_redraw(state)
        self._schedule_high_quality_redraw(state, delay_ms=180)
        return "break"

    def _start_pan(self, event: tk.Event, state) -> None:
        state["is_panning"] = True
        state["pan_x"] = event.x
        state["pan_y"] = event.y
        self._cancel_pending_image_redraw(state)

    def _on_pan(self, event: tk.Event, state) -> None:
        dx = event.x - int(state.get("pan_x", event.x))
        dy = event.y - int(state.get("pan_y", event.y))
        state["pan_x"] = event.x
        state["pan_y"] = event.y

        state["entry"]["offset_x"] = float(state["entry"].get("offset_x", 0.0)) + dx
        state["entry"]["offset_y"] = float(state["entry"].get("offset_y", 0.0)) + dy
        self._request_preview_redraw(state)

    def _end_pan(self, event: tk.Event, state) -> None:
        state["is_panning"] = False
        state["pan_x"] = event.x
        state["pan_y"] = event.y
        self._request_preview_redraw(state)
        self._schedule_high_quality_redraw(state, delay_ms=160)

    def _show_image_context_menu(self, event: tk.Event, state) -> None:
        menu = tk.Menu(self._window, tearoff=0)
        menu.add_command(
            label="Up",
            command=lambda: self._move_image(
                state["menu_item_id"], state["image_index"], -1
            ),
        )
        menu.add_command(
            label="Down",
            command=lambda: self._move_image(
                state["menu_item_id"], state["image_index"], 1
            ),
        )
        menu.add_separator()
        menu.add_command(
            label="Delete",
            command=lambda: self._delete_image(
                state["menu_item_id"], state["image_index"]
            ),
        )
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def _move_image(self, item_id: str, image_index: int, direction: int) -> None:
        item = self._get_item(item_id)
        if item is None:
            return
        images = item.get("images", [])
        target = image_index + direction
        if target < 0 or target >= len(images):
            return
        images[image_index], images[target] = images[target], images[image_index]
        self._save_overlay_menu_state()
        self._render_content()

    def _delete_image(self, item_id: str, image_index: int) -> None:
        item = self._get_item(item_id)
        if item is None:
            return
        images = item.get("images", [])
        if image_index < 0 or image_index >= len(images):
            return
        images.pop(image_index)
        self._save_overlay_menu_state()
        self._render_content()

    def _add_user_item(self) -> None:
        next_name = f"Link {self._user_counter}"
        item_id = f"user:{self._user_counter}"
        self._user_counter += 1
        self._menu_items.append(
            {
                "id": item_id,
                "type": "user",
                "name": next_name,
                "images": [],
            }
        )
        self._refresh_menu()
        self._select_item(item_id)

    def _show_item_context_menu(self, event: tk.Event, item_id: str) -> None:
        menu = tk.Menu(self._window, tearoff=0)
        menu.add_command(label="Rename", command=lambda: self._rename_item(item_id))
        menu.add_command(
            label="Duplicate", command=lambda: self._duplicate_item(item_id)
        )
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._delete_item(item_id))
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def _rename_item(self, item_id: str) -> None:
        item = self._get_item(item_id)
        if item is None or item["type"] != "user":
            return
        new_name = simpledialog.askstring(
            "Rename",
            "Enter new name",
            initialvalue=item["name"],
            parent=self._window,
        )
        if not new_name:
            return
        item["name"] = new_name.strip() or item["name"]
        self._refresh_menu()
        self._select_item(item_id)

    def _duplicate_item(self, item_id: str) -> None:
        item = self._get_item(item_id)
        if item is None or item["type"] != "user":
            return

        duplicated_images = []
        for entry in item.get("images", []):
            duplicated_images.append(
                {
                    "path": entry.get("path", ""),
                    "zoom": float(entry.get("zoom", 1.0)),
                    "offset_x": float(entry.get("offset_x", 0.0)),
                    "offset_y": float(entry.get("offset_y", 0.0)),
                }
            )

        new_id = f"user:{self._user_counter}"
        self._user_counter += 1
        duplicated = {
            "id": new_id,
            "type": "user",
            "name": f"{item['name']} Copy",
            "images": duplicated_images,
        }

        insert_index = self._menu_items.index(item) + 1
        self._menu_items.insert(insert_index, duplicated)
        self._refresh_menu()
        self._select_item(new_id)

    def _delete_item(self, item_id: str) -> None:
        item = self._get_item(item_id)
        if item is None or item["type"] != "user":
            return
        self._menu_items = [
            entry for entry in self._menu_items if entry["id"] != item_id
        ]
        self._refresh_menu()
        fallback_id = "program:map"
        if self._get_item(fallback_id) is None and self._menu_items:
            fallback_id = self._menu_items[0]["id"]
        self._select_item(fallback_id)

    def _start_drag(self, event: tk.Event, item_id: str) -> None:
        self._drag_state["item_id"] = item_id
        self._drag_state["start_y"] = event.y_root
        self._drag_state["dragging"] = False

    def _on_drag_motion(self, event: tk.Event) -> None:
        item_id = self._drag_state.get("item_id", "")
        if not item_id:
            return
        distance = abs(
            event.y_root - int(self._drag_state.get("start_y", event.y_root))
        )
        if distance > 6:
            self._drag_state["dragging"] = True

        if not self._drag_state.get("dragging", False):
            return

        user_ids = [item["id"] for item in self._menu_items if item["type"] == "user"]
        if item_id not in user_ids:
            return

        source_index = user_ids.index(item_id)
        target_index = len(user_ids)
        for index, user_id in enumerate(user_ids):
            button = self._menu_buttons.get(user_id)
            if button is None or user_id == item_id:
                continue
            midpoint = button.winfo_rooty() + (button.winfo_height() // 2)
            if event.y_root < midpoint:
                target_index = index
                break

        if source_index < target_index:
            target_index -= 1
        if source_index == target_index:
            return

        user_ids.pop(source_index)
        user_ids.insert(target_index, item_id)
        self._apply_user_order(user_ids)

    def _finish_drag(self, _event: tk.Event) -> None:
        self._drag_state["item_id"] = ""
        self._drag_state["start_y"] = 0
        self._drag_state["dragging"] = False

    def _apply_user_order(self, ordered_user_ids) -> None:
        program_items = [item for item in self._menu_items if item["type"] == "program"]
        users_by_id = {
            item["id"]: item for item in self._menu_items if item["type"] == "user"
        }
        ordered_users = [
            users_by_id[user_id]
            for user_id in ordered_user_ids
            if user_id in users_by_id
        ]
        self._menu_items = program_items + ordered_users
        self._refresh_menu()
        if self._active_item_id:
            self._select_item(self._active_item_id)

    def _start_window_drag(self, event: tk.Event) -> None:
        self._window_drag_state["active"] = True
        self._window_drag_state["offset_x"] = event.x_root - self._window.winfo_x()
        self._window_drag_state["offset_y"] = event.y_root - self._window.winfo_y()

    def _on_window_drag(self, event: tk.Event) -> None:
        if not self._window_drag_state.get("active", False):
            return

        new_x = event.x_root - int(self._window_drag_state.get("offset_x", 0))
        new_y = event.y_root - int(self._window_drag_state.get("offset_y", 0))
        self._window.geometry(f"+{new_x}+{new_y}")

    def _finish_window_drag(self, _event: tk.Event) -> None:
        self._window_drag_state["active"] = False

    def _apply_centered_geometry(self) -> None:
        self._window.update_idletasks()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        width = max(400, int(screen_w * 0.7))
        height = max(300, int(screen_h * 0.7))
        left = max(0, (screen_w - width) // 2)
        top = max(0, (screen_h - height) // 2)
        self._window.geometry(f"{width}x{height}+{left}+{top}")

    def show(self) -> None:
        if not self._has_centered_geometry:
            self._apply_centered_geometry()
            self._has_centered_geometry = True
        self._window.deiconify()
        try:
            self._window.lift()
            self._window.focus_force()
        except Exception:
            pass

    def hide(self) -> None:
        self._close_layout_preview()
        self._close_clipboard_map_overlay()
        self._window.withdraw()

    def toggle(self) -> None:
        if self._window.state() == "withdrawn":
            self.show()
            return
        self.hide()

    def close(self) -> None:
        self._close_layout_preview()
        self._close_clipboard_map_overlay()
        try:
            self._window.destroy()
        except Exception:
            pass
