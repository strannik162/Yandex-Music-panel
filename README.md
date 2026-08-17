# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, audio spectrum visualizer, track seek bar, draggable position, pinning feature, and compact display modes.

## Features

- **Liquid-glass style overlay**: Modern, translucent UI designed for Windows 10/11.
- **Track info & Album art**: Displays current track title, artist name, source application, and album artwork.
- **Playback controls**: Play/Pause, Previous, and Next track controls integrated with Windows Media Transport Controls (SMTC).
- **Audio Spectrum Visualizer**: Animated 32-band audio frequency visualization reflecting current music playback.
- **Interactive Seek Bar**: Timeline slider with elapsed/total time display allowing direct track scrubbing and seeking.
- **Draggable & Repositionable**: Click and drag the panel background to place it anywhere on screen.
- **Pinning Option**: Pin button (★) locks the panel on screen so it stays visible regardless of hover auto-hide.
- **Large & Small Display Modes**: Double-click the background to toggle between Large mode (with album cover, spectrum visualizer, and seek bar) and Small mode (compact track info and playback controls).
- **Silent execution**: Can be launched as `.pyw` without a console window.

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

Run the panel script:

```bash
pythonw yandex-liquid-panel.pyw
```

- **Move panel**: Click and hold on the panel card background to drag the window.
- **Toggle mode**: Double-click the panel card background to switch between Large and Small modes.
- **Seek track**: Click or drag along the seek slider to change current playback position.
- **Pin panel**: Click the star button to keep panel visible.
