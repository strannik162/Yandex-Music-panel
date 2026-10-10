# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, and playback controls.

## Features

- **Liquid-glass style overlay**: Modern semi-transparent glass aesthetic with rounded corners and drop shadow.
- **Track info & Cover**: Displays track title, artist name, app source, and album cover art.
- **Spectrum Visualizer**: Real-time 32-bar audio frequency visualizer displaying sound amplitudes while playing.
- **Seek Slider**: Track progress bar displaying elapsed / remaining track duration with click and drag seeking support.
- **Interactive Controls**: Play/pause, previous track, next track, pin panel, and close buttons.
- **Panel Pinning**: Toggle pinning (★) to keep the panel visible regardless of cursor position.
- **Mode Toggle (Large / Small)**: Double-click the panel background to toggle between Large mode (with cover art, visualizer, and seek slider) and Small mode (compact title & controls layout).
- **Draggable Window**: Click and drag the panel anywhere on screen; it remembers its custom position.
- **Top-Screen Trigger**: Automatically reveals when hovering near top-center of the screen.
- Works with Yandex Music through Windows System Media Transport Controls (SMTC).
- Can be launched as `.pyw` without a console window.

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
