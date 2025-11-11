<h1 align="center">PathOfQuality</h1>

<p align="center">
  <b>Windows overlay toolkit to streamline Path of Exile gameplay</b><br/>
  <sub>Built to improve the gaming experience based on personal in‑game practice</sub>
  <br/>
  <a href="./README.ru.md">🇷🇺 Read in Russian</a>
  <br/>
  <img alt="OS" src="https://img.shields.io/badge/Windows-10%2B-0078D6?logo=windows&logoColor=white"/>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white"/>
  <img alt="Build" src="https://img.shields.io/badge/Build-PyInstaller-FFDF00"/>
  <br/>
  <i>Created to enhance QoL based on real gameplay experience</i>
  <br/>
  <br/>
  <img src="https://img.shields.io/badge/Quick%20Craft-single%20click%20%F0%9F%91%8D-brightgreen" />
  <img src="https://img.shields.io/badge/Overlays-non--activating-blue" />
  <img src="https://img.shields.io/badge/Mega%20QoL-wheel%E2%86%92keys-orange" />
</p>

---

## 🚀 Quick Start

```bash
python -m pip install -r requirements.txt
python app.py
```

Build EXE (one‑file):

```bash
build_exe.bat
# or
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name PathOfQuality ^
  --add-data "assets;assets" ^
  --add-data "settings.json;." ^
  app.py
```

Settings persist next to the EXE (`settings.json`). Add your game process names to `assets/allowed_processes.json`.

---

## 📽️ Demo video

Add a short MP4 (H.264/AAC) under `media/demo.mp4`, then embed:

```html
<video src="media/demo.mp4" controls playsinline width="800"></video>
```

GitHub also supports linking to YouTube/Vimeo. GIFs are fine for short loops.

---

## 🧩 Features (summary → details)

1) Library — Buff or Debuff Overlay
- Finds saved icons on screen and displays overlays.
- More: docs/en/library-buffs.md

2) Library — Copy Screen Area
- Duplicates a selected region of the screen; optional condition: “show only when a chosen buff/debuff is NOT present” or “always show”.
- More: docs/en/library-copy-area.md

3) Tools — Currency — Quick Craft
- Shows currency overlays and performs quick interactions via a hotkey (non‑activating, single‑click execution).
- More: docs/en/tools-quick-craft.md

4) Tools — Mega QoL — Wheel Keys
- Turning the mouse wheel (down) emulates a sequence of keys (1–4), with burst suppression.
- More: docs/en/tools-mega-qol-wheel.md

5) Tools — Mega QoL — Double Ctrl Click
- Quickly press Ctrl twice to start left‑click emulation; stops when Ctrl is released.
- More: docs/en/tools-mega-qol-double-ctrl.md

---

## 💡 Tips
- Hovering Scan/Copy overlays hides them to interact with the UI beneath.
- During positioning, mouse‑wheel resizing keeps perfect squares (width = height).
- Overlays are non‑activating and hidden from the taskbar/Alt‑Tab.

