# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, audio spectrum visualizer, track seek bar, and playback controls.

## Features

- **Liquid-glass style overlay**: Sleek desktop widget with frosted glass appearance and drop shadow.
- **Track Metadata**: Displays track title, artist name, app source, and high-quality album cover art.
- **Spectrum Audio Visualizer**: Real-time frequency visualizer displaying audio dynamics while music is playing.
- **Track Seek Bar**: Interactive progress bar with elapsed/total time and click/drag seeking capability.
- **Draggable Panel**: Easily move the panel around the screen by clicking and dragging anywhere on the panel background.
- **Pin Overlay**: Pin button (★) to keep the overlay visible on top of other windows without auto-hiding.
- **Dual Display Modes**:
  - **Large Mode**: Full view with cover art, audio visualizer, seek bar, and controls.
  - **Small Mode**: Compact view displaying track information and controls only.
  - Toggle between modes by **double-clicking** the panel background.
- **Media Controls**: Play/pause, next track, previous track, pin, and close buttons.
- **Windows SMTC Integration**: Works seamlessly with the Yandex Music desktop app via Windows System Media Transport Controls.
- **No Console Window**: Can be launched silently as a `.pyw` script on Windows.

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

Launch the panel by double-clicking `yandex-liquid-panel.pyw` or running:

```bash
pythonw yandex-liquid-panel.pyw
```
