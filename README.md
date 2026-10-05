# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, interactive seek bar, spectrum visualizer, and playback controls.

## Features

- **Liquid-glass style overlay**: Smooth floating window with dynamic opacity animations.
- **Track information & cover art**: Displays real-time track title, artist, and album cover art.
- **Playback controls**: Play / Pause, Next track, and Previous track buttons.
- **Draggable positioning**: Click and drag the panel background to move it anywhere on your screen.
- **Spectrum audio visualizer**: Real-time graphical visualization displaying frequency bands and sound intensity.
- **Interactive track seek bar**: Progress slider with current and total track time, supporting click and drag rewind/seeking.
- **Panel pinning**: Pin button (★) to keep the panel visible on screen without auto-hiding on mouse leave.
- **Large & Compact (Small) modes**: Double-click the panel background to toggle between Large (with cover, visualizer, seek bar) and Small (compact playback strip) modes.
- **Windows SMTC integration**: Connects directly with the Yandex Music desktop app via Windows Media Transport Controls.
- **Silent launcher**: Runs as `.pyw` without displaying a console window.

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

Run the panel:

```bash
pythonw yandex-liquid-panel.pyw
```
