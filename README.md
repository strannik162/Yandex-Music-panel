# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, interactive seek bar, and spectrum visualizer.

## Features

- **Liquid-glass style overlay**: Modern translucent desktop overlay designed for Windows 10/11.
- **Track Metadata**: Displays current track title, artist, and application source.
- **Album Cover Art**: Displays album cover image (in Large mode).
- **Audio Spectrum Visualizer**: Displays real-time animated sound frequency bars indicating playback activity and volume levels.
- **Interactive Seek Bar**: Displays elapsed position and duration with click and drag seeking capabilities.
- **Movable Panel**: Drag and drop the panel anywhere on your desktop.
- **Pin Panel**: Lock the panel in place to keep it permanently visible on top.
- **Large & Small Display Modes**: Double-click the panel background to switch between Large mode (with cover, visualizer, and seek bar) and Small compact mode.
- **Playback Controls**: Play / Pause, Previous Track, Next Track, Pin, and Close buttons.
- **Windows Media Integration**: Integrates directly with Yandex Music via System Media Transport Controls (SMTC).
- **No Console Window**: Runs as `.pyw` for a seamless desktop experience without popping up terminal windows.

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
