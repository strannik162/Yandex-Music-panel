# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, spectrum visualizer, seek bar, and pin/compact modes.

## Features

- **Liquid-Glass Style Overlay**: Transparent animated floating card for desktop.
- **Moveable Panel**: Click and drag anywhere on the panel background to reposition it on screen.
- **Spectrum Visualizer**: Procedurally rendered audio spectrum bars reflecting dynamic music playback frequency bands.
- **Track Seek Bar & Rewind**: Interactive position slider with current/total time display allowing clicking or dragging to seek through the track.
- **Small & Large Display Modes**: Double-click the panel background to toggle between compact (Small) mode and full (Large) mode. Small mode hides the cover art, visualizer, and seek bar for a minimal footprint.
- **Pin Panel**: Toggle the pin button (★) to keep the panel visible regardless of cursor hover position.
- **Track Metadata & Controls**: Displays album art, track title, and artist name with play/pause, next, and previous buttons.
- **Windows Media Controls (SMTC)**: Direct integration with Yandex Music via `winsdk`.
- **Background Execution**: Can be launched as `.pyw` without a console window.

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app (`Yandex Music.exe`)

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

Hover over the top-center edge of your screen to reveal the floating panel when unpinned.
