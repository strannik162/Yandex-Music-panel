# Yandex Music Panel / Панель Яндекс Музыки

A Windows liquid-glass overlay panel for Yandex Music with track cover, title, artist, playback controls, spectrum visualizer, seek bar, pinning, dragging, and dual display modes.

Интерактивная плавающая панель в стиле "Liquid Glass" для Яндекс Музыки с визуализатором спектра частот, перемоткой трека, перетаскиванием, закреплением и переключением режимов.

## Features / Возможности

- **Liquid-glass Overlay Style** — полупрозрачная стильная панель поверх окон.
- **Track Info & Cover** — отображение названия трека, исполнителя и обложки альбома.
- **Playback Controls** — кнопки Воспроизведение / Пауза, Предыдущий и Следующий трек.
- **Audio Spectrum Visualizer (Визуализатор частот)** — графическое отображение частот звука во время воспроизведения музыки.
- **Track Seeking / Seek Bar (Перемотка)** — интерактивная полоса прогресса для перемотки трека по клику или перетаскиванием ползунка.
- **Draggable Panel (Перемещение панели)** — возможность свободно перетаскивать панель по экрану за карточку.
- **Pin / Unpin (Закрепление)** — кнопка с иконкой звёздочки (★) для фиксации панели на экране (предотвращает авто-скрытие при уводе курсора).
- **Small & Large View Modes (Режимы)** — двухкликовый переключатель (двойной клик по панели):
  - **Large mode**: полнофункциональный режим с обложкой, визуализатором частот и полосой перемотки.
  - **Small mode**: компактный режим только с названием, исполнителем и кнопками управления.
- **Windows SMTC Integration** — интеграция с системным управлением медиа Windows (Yandex Music).

## Requirements / Требования

- Windows 10 / Windows 11
- Python 3.10+
- Yandex Music desktop app (`Яндекс Музыка.exe`)

## Installation & Running / Установка и запуск

Install dependencies:

```bash
pip install -r requirements.txt
```

Run panel:

```bash
pythonw yandex-liquid-panel.pyw
```
