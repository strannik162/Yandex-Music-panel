# Yandex Music Panel / Панель Яндекс Музыки

A sleek, liquid-glass desktop overlay panel for Yandex Music on Windows 10 and 11.

Стильная плавающая панель в стиле liquid-glass для Яндекс Музыки на Windows 10/11.

---

## Features / Возможности

- **Liquid-Glass Style Overlay**: Translucent glass background with smooth slide and fade animations.
- **Movable Panel (Перемещение панели)**: Click and drag anywhere on the panel to position it anywhere on your desktop.
- **Audio Spectrum Visualizer (Визуализатор частот)**: Dynamic 32-bar audio spectrum visualizer displaying current playback frequency activity and volume levels.
- **Pin Panel (Закрепление панели)**: Click the star pin button (★) to lock the panel on top and prevent automatic hiding when the mouse leaves.
- **Large & Small Display Modes (Большой и маленький режим)**: Double-click the panel background to switch between Large (with album cover, visualizer, and seek bar) and Small/Compact modes.
- **Track Seeking (Перемотка трека)**: Interactive track position slider allowing direct seeking by clicking or dragging.
- **Track & Media Info**: Displays current track title, artist, app name, and high-resolution cover art.
- **Media Controls**: Previous track, Play/Pause toggle, Next track, Pin panel, and Close controls with bilingual tooltips.
- **Windows SMTC Integration**: Connects directly to Yandex Music (`YandexMusic.exe`) via System Media Transport Controls.
- **Console-Free Launch**: Launch directly via `yandex-liquid-panel.pyw` without a background command prompt window.

---

## Requirements / Требования

- Windows 10 or Windows 11
- Python 3.10+
- Yandex Music desktop application (`YandexMusic.exe`)

---

## Installation / Установка

1. Clone or download the repository:
   ```bash
   git clone https://github.com/user/yandex-music-panel.git
   cd yandex-music-panel
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the panel:
   ```bash
   pythonw yandex-liquid-panel.pyw
   ```
