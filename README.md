# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, audio spectrum visualizer, track seek bar, pin mode, movable window support, and compact/large display modes.

## Features

- **Liquid-Glass Style Overlay**: Translucent desktop overlay with subtle blur and shadow effects.
- **Track Info & Cover**: Shows real-time track title, artist, source application, and album art.
- **Playback Controls**: Play/pause, next track, and previous track buttons.
- **Movable Panel (Panel Dragging)**: Click and drag anywhere on the panel background to move it around the screen.
- **Pin Panel**: Toggle the pin button (★) to keep the panel visible at all times regardless of hover state.
- **Audio Spectrum Visualizer**: Animated multi-band audio spectrum bar graph reflecting active playback frequencies and dynamic volume.
- **Interactive Seek Bar**: Track position slider showing current position and total track duration, supporting direct seeking via clicking or dragging.
- **Small & Large Display Modes**: Double-click the panel background to switch between compact mode (controls & title only) and expanded mode (with cover, visualizer, and seek bar).
- **Windows Media Integration**: Seamless interaction with Yandex Music via Windows System Media Transport Controls (SMTC).
- **Silent Launch**: Can be launched directly as `.pyw` without displaying a console window.

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running

Launch the panel using Python:

```bash
pythonw yandex-liquid-panel.pyw
```
