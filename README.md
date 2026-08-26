# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, spectrum visualizer, seek bar, panel pinning, draggable positioning, and compact/large display modes.

## Features

- **Liquid-Glass Style Overlay**: Translucent desktop overlay with modern Windows aesthetic.
- **Track Information & Cover Art**: Displays current track title, artist, app name, and album cover.
- **Playback Controls**: Play / Pause, Previous, Next, Pin, and Close buttons.
- **Draggable Panel**: Click and drag anywhere on the panel to reposition it freely on screen.
- **Audio Spectrum Visualizer**: Animated spectrum visualizer displaying playing audio frequency simulation.
- **Interactive Track Seek Bar**: Progress bar showing current track position and total duration with drag-to-seek support.
- **Panel Pinning**: Pin button to keep the panel visible regardless of cursor movement.
- **Large & Small Modes**: Double-click the panel card background to switch between Large mode (full details, cover, visualizer, slider) and Small compact mode.
- **System Tray / Silent Startup**: Can be launched as `.pyw` without showing a console window.

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
