# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, and playback controls.

## Features

- **Liquid-glass style overlay**: Sleek translucent desktop widget for Windows.
- **Track information & cover art**: Displays current title, artist, app name, and high-resolution album cover.
- **Playback controls**: Play/pause, next track, previous track buttons with tooltips.
- **Interactive track seek bar**: Interactive slider showing current elapsed time, total duration, and allowing instant seeking by clicking or dragging.
- **Audio spectrum visualizer**: Frequency spectrum visualizer displaying real-time audio frequency animation during playback.
- **Small / Large display modes**: Toggle display modes by double-clicking the panel card. Compact mode hides visualizer, seek bar, and cover art while maintaining title, artist, and playback controls.
- **Draggable & manual positioning**: Drag and drop the panel anywhere on your screen.
- **Pin / Unpin panel**: Pin the panel to stay visible continuously without auto-hiding on mouse leave.
- **Native Windows integration**: Works with Yandex Music through Windows System Media Transport Controls (SMTC) and runs without a console window (`.pyw`).

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
