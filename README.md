# Yandex Music Panel

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, and playback controls.

## Features

- **Liquid-Glass Style Overlay**: Elegant semi-transparent desktop panel with modern design aesthetics.
- **Track Metadata & Cover Art**: Displays track title, artist name, and album artwork loaded dynamically from Yandex Music.
- **Playback Controls**: Play / Pause, Previous, and Next track buttons.
- **Spectrum Frequency Visualizer**: Audio frequency spectrum bar visualizer indicating live frequency response and volume intensity.
- **Seek Slider Bar**: Track progress bar displaying current position and duration, allowing precise scrubbing and seeking by clicking or dragging.
- **Draggable Panel Position**: Easily move the panel anywhere on your screen by dragging the panel background.
- **Pin Panel (Always Visible)**: Pin button (`★`) keeps the panel fixed on screen without auto-hiding when the mouse leaves.
- **Large & Small Display Modes**: Double-click the panel background to toggle between Large (full view with cover art, visualizer, slider) and Small mode (compact layout).
- **Auto-Hide Hover Trigger**: Smooth slide-and-fade animation when hovering near the top-center edge of the screen.
- **Works via Windows SMTC**: Native integration with Yandex Music desktop app via Windows System Media Transport Controls.
- **Console-less Execution**: Launched as `.pyw` without opening a command prompt window.

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
