# Yandex Music Liquid Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, media controls, audio spectrum visualizer, track seek bar, pin mode, window dragging, and compact mode.

## Features

- **Liquid-Glass Design**: Translucent animated overlay styled for desktop media playback.
- **Draggable Overlay**: Click and drag the panel anywhere on your screen.
- **Pin Panel (★)**: Pin the panel to keep it permanently visible without auto-hiding.
- **Display Modes (Large & Small)**: Double-click the panel background to toggle between Large (full details with cover, visualizer, seek bar) and Small (compact control bar) modes.
- **Audio Spectrum Visualizer**: Dynamic 32-band audio spectrum display with color-coded frequency bands (Bass, Mid, Treble) and volume-dependent brightness.
- **Interactive Track Seek Bar**: Interactive progress bar displaying current track position and total duration; click or drag to rewind/seek tracks.
- **Playback Controls**: Play/pause, next track, and previous track integrated directly with Windows System Media Transport Controls (SMTC).
- **Auto-Hide & Hover Trigger**: Move your mouse to the top-center edge of the screen to reveal the panel automatically.
- **Bilingual Tooltips**: Tooltips on all control buttons and visual elements in Russian and English.

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

To run the panel:

```bash
pythonw yandex-liquid-panel.pyw
```
