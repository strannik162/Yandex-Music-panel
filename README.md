# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, spectrum visualizer, track seek bar, pin mode, and panel dragging support.

## Features

- **Liquid-glass Overlay Style:** Modern translucent desktop overlay with custom glass styling.
- **Panel Dragging:** Click and drag anywhere on the card background to move the panel anywhere on your screen.
- **Audio Spectrum Visualizer:** Real-time frequency spectrum display bar showing playing sound frequencies and intensity.
- **Track Seeking:** Interactive track position bar showing current playback position, total duration, and allowing seeking by clicking or dragging the handle.
- **Pin Panel (Always Visible):** Pin button to keep the panel open on screen without auto-hiding when the mouse leaves.
- **Small / Large Display Modes:** Double-click the card background to toggle between Large mode (with cover, visualizer, and slider) and Small compact mode.
- **Playback Controls:** Previous, Next, Play/Pause buttons with SMTC media integration.
- **No Console Window:** Launches as `.pyw` without a terminal window.

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app (`Yandex Music.exe`)

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running

Run the script:

```bash
pythonw yandex-liquid-panel.pyw
```
