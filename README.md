# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, audio spectrum visualizer, seek bar, and playback controls.

## Features

- **Liquid-glass Overlay Style:** Native-feeling floating window with smooth animations.
- **Track Info & Cover:** Shows current track title, artist, album, source app name, and cover art.
- **Spectrum Audio Visualizer:** Real-time visualizer bars indicating sound frequency levels during playback.
- **Track Seeking & Progress Bar:** Interactive slider displaying elapsed and total track time with clickable and draggable position seeking.
- **Large & Small Display Modes:** Double-click the panel background to switch between Large view (full detail with visualizer, seek slider, and cover art) and Small view (compact bar).
- **Movable / Draggable Panel:** Drag the panel anywhere on your screen.
- **Pin Panel Option:** Click the star (pin) button to keep the panel pinned on top without auto-hiding.
- **Media Controls:** Play/pause, next track, and previous track buttons integrated with Windows System Media Transport Controls (SMTC).
- **Background Execution:** Can be launched as `.pyw` without a console window.

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the panel:

```bash
pythonw yandex-liquid-panel.pyw
```
