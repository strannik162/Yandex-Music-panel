# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, spectrum visualizer, seek slider, pinning, dragging, and small/large mode toggle.

## Features

- **Liquid-glass style overlay**: Modern floating aesthetic for desktop.
- **Track metadata & Cover**: Displays current track title, artist, and album art.
- **Playback Controls**: Play / Pause, Previous, and Next track buttons.
- **Interactive Seek Bar (Перемотка)**: Seek to any point in the current track by clicking or dragging the handle.
- **Audio Spectrum Visualizer (Частоты)**: Procedural spectrum visualizer rendering real-time sound frequency dynamics across Bass, Mid, and Treble ranges with dynamic color intensity.
- **Draggable Window (Перемещение)**: Move the panel anywhere on screen by dragging the card background.
- **Panel Pinning (Закрепление)**: Pin button (`★`) keeps the panel permanently visible without auto-hiding.
- **Small & Large Display Modes (Маленький/Большой режим)**: Double-click the panel background to toggle between Large mode (with cover, spectrum visualizer, and seek bar) and compact Small mode.
- **Windows Media Controls Integration**: Integrates directly with Yandex Music via SMTC.
- **No Console Window**: Executable `.pyw` script hides background console window.

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
