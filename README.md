# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, and playback controls.

## Features

- Liquid-glass style overlay
- Shows track title, artist, and app status
- Shows track cover (in Large mode)
- Dynamic audio frequency spectrum visualizer (Bass, Mid, Treble frequency bands with amplitude-based colors)
- Interactive track seek bar with smooth position interpolation and drag-seeking
- Moveable / draggable window: drag anywhere on the card to reposition the panel
- Pin mode: pin the panel to stay on screen without hiding automatically
- Dual size modes: double-click the card background to switch between Large mode (with cover, spectrum visualizer, and seek slider) and compact Small mode
- Play / pause, previous, and next track playback controls
- Works with Yandex Music through Windows media controls
- Can be launched as `.pyw` without a console window

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
