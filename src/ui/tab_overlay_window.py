"""Tab overlay window shown above all windows."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, simpledialog
from typing import Any, Callable, Optional

from PIL import Image, ImageTk

from src.ui import theme


class TabOverlayWindow:
    """Stylized top-level overlay window for tab tools."""

    def __init__(
        self,
        master: tk.Tk,
        settings: Optional[dict] = None,
        save_settings_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._master = master
        self._settings = settings if isinstance(settings, dict) else {}
        self._save_settings_callback = save_settings_callback
        self._window = tk.Toplevel(master)
        self._window.withdraw()
        self._window.title("Tab Overlay")
        self._window.configure(bg=theme.BG_PRIMARY)
        self._window.protocol("WM_DELETE_WINDOW", self.hide)
        self._window.bind("<Escape>", lambda _event: self.hide())
        try:
            self._window.attributes("-topmost", True)
            self._window.attributes("-alpha", 0.95)
            self._window.overrideredirect(True)
        except Exception:
            pass

        self._menu_items = []
        self._menu_buttons = {}
        self._active_item_id = ""
        self._user_counter = 1
        self._menu_width = 220
        self._image_canvas_height = 480
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

        self._menu_list = tk.Frame(self._menu_frame, bg=theme.BG_PRIMARY)
        self._menu_list.pack(fill="both", expand=True, padx=8, pady=(8, 0))

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

        self._window.bind("<ButtonPress-1>", self._start_window_drag, add="+")
        self._window.bind("<B1-Motion>", self._on_window_drag, add="+")
        self._window.bind("<ButtonRelease-1>", self._finish_window_drag, add="+")

    def _seed_menu(self) -> None:
        self._menu_items = [
            {
                "id": "program:map",
                "type": "program",
                "name": "MAP",
                "program_key": "map",
            }
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

    def _refresh_menu(self) -> None:
        for child in self._menu_list.winfo_children():
            child.destroy()
        self._menu_buttons.clear()

        for item in self._menu_items:
            item_id = item["id"]
            button = tk.Button(
                self._menu_list,
                text=item["name"],
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
        for child in self._content_inner.winfo_children():
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
            images.append(
                {
                    "path": path,
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
            "<Button-3>",
            lambda event, image_state=state: self._show_image_context_menu(
                event, image_state
            ),
        )

        canvas.after(0, lambda image_state=state: self._draw_image(image_state))

    def _draw_image(
        self, state, width: int | None = None, height: int | None = None
    ) -> None:
        canvas = state["canvas"]
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
        target_width = max(1, int(image.width * scale))
        target_height = max(1, int(image.height * scale))

        resized = image.resize((target_width, target_height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        state["photo"] = photo

        offset_x = float(state["entry"].get("offset_x", 0.0))
        offset_y = float(state["entry"].get("offset_y", 0.0))
        center_x = canvas_width / 2 + offset_x
        center_y = canvas_height / 2 + offset_y

        canvas.delete("all")
        canvas.create_image(center_x, center_y, image=photo, anchor="center")

    def _on_image_wheel(self, event: tk.Event, state) -> None:
        delta = 1.1 if event.delta > 0 else 0.9
        current = float(state["entry"].get("zoom", 1.0))
        state["entry"]["zoom"] = max(0.2, min(8.0, current * delta))
        self._draw_image(state)

    def _start_pan(self, event: tk.Event, state) -> None:
        state["pan_x"] = event.x
        state["pan_y"] = event.y

    def _on_pan(self, event: tk.Event, state) -> None:
        dx = event.x - int(state.get("pan_x", event.x))
        dy = event.y - int(state.get("pan_y", event.y))
        state["pan_x"] = event.x
        state["pan_y"] = event.y

        state["entry"]["offset_x"] = float(state["entry"].get("offset_x", 0.0)) + dx
        state["entry"]["offset_y"] = float(state["entry"].get("offset_y", 0.0)) + dy
        self._draw_image(state)

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
        window_top = self._window.winfo_rooty()
        local_y = event.y_root - window_top
        if local_y > self._window_drag_region_height:
            self._window_drag_state["active"] = False
            return

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
        self._apply_centered_geometry()
        self._window.deiconify()
        try:
            self._window.lift()
            self._window.focus_force()
        except Exception:
            pass

    def hide(self) -> None:
        self._window.withdraw()

    def toggle(self) -> None:
        if self._window.state() == "withdrawn":
            self.show()
            return
        self.hide()

    def close(self) -> None:
        try:
            self._window.destroy()
        except Exception:
            pass
