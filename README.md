# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, and playback controls.

## Features

- Liquid-glass style overlay panel
- Shows track title, artist, and album cover art
- Spectrum visualizer displaying real-time frequency bar animations during playback
- Track seek slider with position/duration time indicators and drag seeking support
- Draggable panel allowing manual positioning on screen
- Panel pinning feature to keep the panel visible regardless of cursor movement
- Dual display modes: Large mode (with cover art, visualizer, and seek bar) and Small mode (compact layout without cover/visualizer/slider), toggled via double-click
- Play / pause, previous track, next track, pin, and close controls with bilingual tooltips
- Native integration with Yandex Music through Windows System Media Transport Controls (SMTC)
- Can be launched directly as `.pyw` without opening a console window

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
