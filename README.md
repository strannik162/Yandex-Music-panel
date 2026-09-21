# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, spectrum visualizer, seek slider, pinning, and mode toggling.

## Features

- **Liquid-glass style overlay**: Translucent design with smooth animated transitions.
- **Track information & Cover**: Displays current track title, artist, source application, and album art.
- **Playback controls**: Play / pause, previous, and next track buttons.
- **Spectrum visualizer**: Audio frequency bar widget displaying simulated track frequencies and volume intensity.
- **Track seek bar**: Interactive progress bar allowing seeking / scrubbing through tracks with time indicators.
- **Draggable panel**: Move the panel anywhere on screen by dragging it.
- **Pin / unpin mode**: Keep the panel fixed on screen using the pin button (★).
- **Large & Small display modes**: Double-click the panel background to toggle between Large mode (full controls, cover art, visualizer, slider) and Small mode (compact controls).
- **Windows Media Controls integration**: Seamlessly interacts with Yandex Music via Windows SMTC.
- **No console window**: Can be launched as `.pyw` directly without a command prompt window.

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
