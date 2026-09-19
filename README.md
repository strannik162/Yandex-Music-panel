# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, seek slider, visualizer, and playback controls.

## Features

- **Liquid-glass style overlay**: Sleek translucent desktop widget.
- **Movable panel**: Drag and reposition the panel anywhere on your screen.
- **Spectrum Visualizer**: Frequency-band audio visualizer displaying real-time bass, mid, and treble amplitudes.
- **Track Seek Slider**: Interactive progress bar with track position, duration, and click/drag seeking.
- **Large and Small Display Modes**: Double-click the card to toggle between full (Large) mode and compact (Small) mode.
- **Pin Panel**: Pin option to keep the panel visible on top of other windows.
- **Playback Controls**: Play, pause, previous track, and next track controls.
- **Auto-hide / Hover Reveal**: Automatically reveals when hovering near top-center of the screen or over the panel.
- Works with Yandex Music through Windows media controls (SMTC).
- Can be launched as `.pyw` without a console window.

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

Launch the panel:

```bash
pythonw yandex-liquid-panel.pyw
```
