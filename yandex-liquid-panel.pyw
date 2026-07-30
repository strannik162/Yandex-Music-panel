import sys
import time
import asyncio
import hashlib
import threading
import ctypes
import random
from datetime import timedelta

from PySide6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QEasingCurve,
    Signal,
    QObject,
    QRectF,
    QPointF,
    QPoint,
    QRect,
)
from PySide6.QtGui import (
    QCursor,
    QPixmap,
    QFont,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QPolygonF,
    QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QGraphicsDropShadowEffect,
    QSizePolicy,
)

try:
    import winsdk
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
    from winsdk.windows.storage.streams import Buffer, DataReader, InputStreamOptions
    WINSDK_OK = True
except Exception:
    WINSDK_OK = False


PANEL_W = 570
PANEL_H_LARGE = 160
PANEL_H_SMALL = 88
PANEL_H = PANEL_H_LARGE

TRIGGER_WIDTH = 360
TRIGGER_Y = 6

SHOW_Y_OFFSET = 10
HIDE_DELAY = 0.10
POLL_INTERVAL = 0.55

THUMBNAIL_MAX_BYTES = 5 * 1024 * 1024

CARD_BG_QCOLOR = QColor(22, 22, 30, 190)

TARGET_APP_KEYWORDS = [
    "яндекс",
    "yandex",
    "yandexmusic",
    "yandex.music",
    "яндекс музыка",
    "яндекс музыка.exe",
    "yandex music",
    "yandex music.exe",
    "music.yandex",
]


def is_media_playing(info):
    try:
        status = info.playback_status
    except Exception:
        return False

    try:
        value = getattr(status, "value", None)
        if value is not None:
            return int(value) == 4
    except Exception:
        pass

    try:
        return int(status) == 4
    except Exception:
        pass

    try:
        text = str(status).lower()
        return "playing" in text or text.endswith(".playing")
    except Exception:
        return False


def _timespan_to_seconds(ts) -> float:
    if ts is None:
        return 0.0
    if hasattr(ts, "total_seconds"):
        try:
            return ts.total_seconds()
        except Exception:
            pass
    if hasattr(ts, "duration"):
        try:
            # TimeSpan ticks are in 100-nanoseconds. 1 tick = 1e-7 seconds.
            return ts.duration / 10000000.0
        except Exception:
            pass
    return 0.0


class MediaWorker(QObject):
    media_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.running = False
        self.loop = None
        self.manager = None
        self.session = None
        self.thread = None
        self.last_metadata_signature = None

    def start(self):
        if not WINSDK_OK:
            self.media_changed.emit({
                "title": "winsdk не установлен",
                "artist": "Введи: pip install winsdk",
                "app": "",
                "playing": False,
                "cover": None,
                "position": 0.0,
                "duration": 0.0,
                "metadata_changed": True,
            })
            return

        self.running = True
        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.loop:
            try:
                self.loop.call_soon_threadsafe(lambda: None)
            except Exception:
                pass

    def command(self, action: str, value=None):
        if not self.loop:
            return

        try:
            asyncio.run_coroutine_threadsafe(self._control(action, value), self.loop)
        except Exception:
            pass

    def _thread_main(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self._poll_loop())
        except Exception as e:
            self.media_changed.emit({
                "title": "Ошибка медиа-сессии",
                "artist": str(e),
                "app": "",
                "playing": False,
                "cover": None,
                "position": 0.0,
                "duration": 0.0,
                "metadata_changed": True,
            })

    async def _poll_loop(self):
        try:
            self.manager = await MediaManager.request_async()
        except Exception as e:
            self.media_changed.emit({
                "title": "Windows Media Controls недоступны",
                "artist": str(e),
                "app": "",
                "playing": False,
                "cover": None,
                "position": 0.0,
                "duration": 0.0,
                "metadata_changed": True,
            })
            return

        while self.running:
            data = await self._read_current_media()

            cover = data.get("cover")
            cover_hash = hashlib.sha1(cover).hexdigest() if cover else ""

            # Only title, artist, album, app, and cover hash constitute metadata.
            metadata_sig = (
                data.get("title", ""),
                data.get("artist", ""),
                data.get("album", ""),
                data.get("app", ""),
                cover_hash,
            )

            metadata_changed = False
            if metadata_sig != self.last_metadata_signature:
                self.last_metadata_signature = metadata_sig
                metadata_changed = True

            data["metadata_changed"] = metadata_changed
            data["cover_hash"] = cover_hash

            # Continuously emit to keep track position & duration updated smoothly in the UI
            self.media_changed.emit(data)

            await asyncio.sleep(POLL_INTERVAL)

    def _is_target_yandex_music(self, session):
        try:
            app = getattr(session, "source_app_user_model_id", "") or ""
            app_lower = app.lower()

            for keyword in TARGET_APP_KEYWORDS:
                if keyword.lower() in app_lower:
                    return True

            return False
        except Exception:
            return False

    def _get_yandex_music_session(self):
        if not self.manager:
            return None

        try:
            sessions = self.manager.get_sessions()
        except Exception:
            sessions = []

        for session in sessions:
            if self._is_target_yandex_music(session):
                return session

        return None

    async def _read_current_media(self):
        try:
            session = self._get_yandex_music_session()
            self.session = session

            if not session:
                return {
                    "title": "Яндекс Музыка не найдена",
                    "artist": "Открой именно приложение Яндекс Музыка.exe",
                    "album": "",
                    "app": "",
                    "playing": False,
                    "cover": None,
                    "position": 0.0,
                    "duration": 0.0,
                }

            try:
                props = await asyncio.wait_for(
                    session.try_get_media_properties_async(),
                    timeout=1.2
                )
            except Exception:
                props = None

            title = ""
            artist = ""
            album = ""
            cover = None

            if props:
                title = getattr(props, "title", "") or ""
                artist = getattr(props, "artist", "") or ""
                album = getattr(props, "album_title", "") or ""

                thumb = getattr(props, "thumbnail", None)
                cover = await self._read_thumbnail(thumb)

            app = getattr(session, "source_app_user_model_id", "") or ""

            playing = False
            try:
                info = session.get_playback_info()
                playing = is_media_playing(info)
            except Exception:
                pass

            # Try to retrieve timeline properties safely
            pos_sec = 0.0
            dur_sec = 0.0
            try:
                timeline = session.get_timeline_properties()
                if timeline:
                    pos_sec = _timespan_to_seconds(timeline.position)
                    dur_sec = _timespan_to_seconds(timeline.end_time) - _timespan_to_seconds(timeline.start_time)
                    if dur_sec <= 0.0:
                        dur_sec = _timespan_to_seconds(timeline.end_time)
            except Exception:
                pass

            if not title:
                title = "Музыка не найдена"
            if not artist:
                artist = "Включи трек в приложении Яндекс Музыка"

            return {
                "title": title,
                "artist": artist,
                "album": album,
                "app": app,
                "playing": playing,
                "cover": cover,
                "position": pos_sec,
                "duration": dur_sec,
            }

        except Exception as e:
            return {
                "title": "Ошибка чтения Яндекс Музыки",
                "artist": str(e),
                "album": "",
                "app": "",
                "playing": False,
                "cover": None,
                "position": 0.0,
                "duration": 0.0,
            }

    async def _read_thumbnail(self, thumbnail):
        if not thumbnail:
            return None

        try:
            stream = await asyncio.wait_for(
                thumbnail.open_read_async(),
                timeout=0.8
            )

            size = int(getattr(stream, "size", 0) or 0)
            if size <= 0 or size > THUMBNAIL_MAX_BYTES:
                size = THUMBNAIL_MAX_BYTES

            buffer = Buffer(size)

            await asyncio.wait_for(
                stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD),
                timeout=0.8
            )

            length = int(getattr(buffer, "length", 0) or 0)
            if length <= 0:
                return None

            reader = DataReader.from_buffer(buffer)
            data = bytearray(length)

            try:
                reader.read_bytes(data)
                return bytes(data)
            except Exception:
                arr = winsdk.system.Array("B", length)
                reader.read_bytes(arr)
                return bytes(bytearray(arr))

        except Exception:
            return None

    async def _control(self, action: str, value=None):
        try:
            session = self._get_yandex_music_session()
            self.session = session

            if not session:
                return

            if action == "play_pause":
                try:
                    await session.try_toggle_play_pause_async()
                except Exception:
                    try:
                        info = session.get_playback_info()
                        if is_media_playing(info):
                            await session.try_pause_async()
                        else:
                            await session.try_play_async()
                    except Exception:
                        pass

            elif action == "next":
                await session.try_skip_next_async()

            elif action == "prev":
                await session.try_skip_previous_async()

            elif action == "seek" and value is not None:
                try:
                    await session.try_change_playback_position_async(timedelta(seconds=float(value)))
                except Exception:
                    pass

        except Exception:
            pass


class CircleIconButton(QPushButton):
    def __init__(self, icon="play", accent=False, danger=False):
        super().__init__("")

        self.icon = icon
        self.accent = accent
        self.danger = danger
        self.hovered = False

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(34, 34)
        self.setFlat(True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

    def set_icon(self, icon):
        self.icon = icon
        self.update()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)

        if self.danger:
            base = QColor(140, 42, 42, 150)
            border = QColor(255, 170, 170, 70)
            hover = QColor(175, 58, 58, 175)
        elif self.accent:
            base = QColor(42, 112, 255, 170)
            border = QColor(200, 225, 255, 85)
            hover = QColor(75, 138, 255, 195)
        else:
            base = QColor(255, 255, 255, 34)
            border = QColor(255, 255, 255, 60)
            hover = QColor(255, 255, 255, 56)

        bg = hover if self.hovered else base

        if self.isDown():
            bg = QColor(
                min(bg.red() + 20, 255),
                min(bg.green() + 20, 255),
                min(bg.blue() + 20, 255),
                min(bg.alpha() + 20, 255)
            )

        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(bg))
        painter.drawEllipse(rect)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 238)))

        cx = self.width() / 2
        cy = self.height() / 2

        if self.icon == "play":
            points = QPolygonF([
                QPointF(cx - 3.5, cy - 7),
                QPointF(cx - 3.5, cy + 7),
                QPointF(cx + 7.5, cy),
            ])
            painter.drawPolygon(points)

        elif self.icon == "pause":
            bar_w = 4.2
            bar_h = 14.0
            gap = 4.0

            left_x = cx - gap / 2 - bar_w
            right_x = cx + gap / 2

            painter.drawRoundedRect(
                QRectF(left_x, cy - bar_h / 2, bar_w, bar_h),
                1.2,
                1.2
            )
            painter.drawRoundedRect(
                QRectF(right_x, cy - bar_h / 2, bar_w, bar_h),
                1.2,
                1.2
            )

        elif self.icon == "next":
            p1 = QPolygonF([
                QPointF(cx - 8.0, cy - 7.0),
                QPointF(cx - 8.0, cy + 7.0),
                QPointF(cx - 0.5, cy),
            ])
            p2 = QPolygonF([
                QPointF(cx - 1.0, cy - 7.0),
                QPointF(cx - 1.0, cy + 7.0),
                QPointF(cx + 6.5, cy),
            ])

            painter.drawPolygon(p1)
            painter.drawPolygon(p2)
            painter.drawRoundedRect(
                QRectF(cx + 7.7, cy - 7.0, 2.4, 14.0),
                1.0,
                1.0
            )

        elif self.icon == "prev":
            p1 = QPolygonF([
                QPointF(cx + 8.0, cy - 7.0),
                QPointF(cx + 8.0, cy + 7.0),
                QPointF(cx + 0.5, cy),
            ])
            p2 = QPolygonF([
                QPointF(cx + 1.0, cy - 7.0),
                QPointF(cx + 1.0, cy + 7.0),
                QPointF(cx - 6.5, cy),
            ])

            painter.drawPolygon(p1)
            painter.drawPolygon(p2)
            painter.drawRoundedRect(
                QRectF(cx - 10.1, cy - 7.0, 2.4, 14.0),
                1.0,
                1.0
            )

        elif self.icon == "close":
            pen = QPen(QColor(255, 255, 255, 238), 2.0)
            pen.setCapStyle(Qt.RoundCap)

            painter.setPen(pen)
            painter.drawLine(QPointF(cx - 6.0, cy - 6.0), QPointF(cx + 6.0, cy + 6.0))
            painter.drawLine(QPointF(cx + 6.0, cy - 6.0), QPointF(cx - 6.0, cy + 6.0))

        elif self.icon == "pin":
            painter.setPen(QColor(255, 255, 255, 238))
            painter.setFont(QFont("Segoe UI Symbol", 13))
            painter.drawText(self.rect(), Qt.AlignCenter, "★")


class SpectrumVisualizer(QWidget):
    """
    A 270x32 widget that procedurally simulates audio frequencies (32 bars total).
    Thumping effect on low frequencies (left), flickering effect on high frequencies (right).
    Updates smoothly every 50ms using target heights and current heights.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 32)
        self.num_bars = 32
        self.bars = [1.0] * self.num_bars
        self.targets = [1.0] * self.num_bars
        self.is_playing = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_spectrum)
        self.timer.start(50)

    def set_playing(self, playing: bool):
        self.is_playing = playing

    def _update_spectrum(self):
        # Decay current bars towards targets or minimums
        for i in range(self.num_bars):
            # Calculate new target if playing
            if self.is_playing:
                if i < 8:  # Bass / Thumping
                    # High chance of keeping previous or jumping
                    if random.random() < 0.25:
                        self.targets[i] = random.uniform(8.0, 28.0)
                    else:
                        self.targets[i] = max(1.0, self.targets[i] - random.uniform(2.0, 5.0))
                else:  # High / Flickering
                    if random.random() < 0.4:
                        self.targets[i] = random.uniform(2.0, 18.0)
                    else:
                        self.targets[i] = max(1.0, self.targets[i] - random.uniform(1.0, 3.0))
            else:
                self.targets[i] = 1.0

            # Interpolate current values towards targets
            diff = self.targets[i] - self.bars[i]
            if abs(diff) > 0.1:
                self.bars[i] += diff * 0.35
            else:
                self.bars[i] = self.targets[i]

            # Enforce bounds
            self.bars[i] = max(1.0, min(self.bars[i], 32.0))

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        bar_w = 6.0
        gap = 2.0
        # 32 bars * 6px + 31 gaps * 2px = 192 + 62 = 254px total width.
        # We start with a left offset to center them: (270 - 254) / 2 = 8px.
        start_x = (w - (self.num_bars * bar_w + (self.num_bars - 1) * gap)) / 2.0

        for i in range(self.num_bars):
            bar_h = self.bars[i]
            x = start_x + i * (bar_w + gap)
            y = h - bar_h

            rect = QRectF(x, y, bar_w, bar_h)

            gradient = QLinearGradient(x, y, x, h)
            # Subtle accent gradient from cyan-blue to white/light-cyan
            gradient.setColorAt(0.0, QColor(0, 240, 255, 230))
            gradient.setColorAt(0.6, QColor(42, 112, 255, 190))
            gradient.setColorAt(1.0, QColor(42, 112, 255, 100))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(rect, 1.5, 1.5)


class CustomSlider(QWidget):
    """
    A custom slider widget supporting continuous dragging and absolute clicks.
    Calculates current track position smoothly via internal interpolation (100ms timer)
    between SMTC polls. Includes text labels for elapsed/duration on left and right.
    """
    seek_requested = Signal(float)  # Emits target position in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 20)
        self.setCursor(Qt.PointingHandCursor)

        self.position = 0.0      # Current position in seconds
        self.duration = 0.0      # Track duration in seconds
        self.is_playing = False
        self.dragging = False    # True while dragging the handle

        # Visual states
        self.hovered = False
        self.handle_hovered = False
        self.drag_start_x = 0

        # High-res interpolation timer (smooth position updates)
        self.interpolate_timer = QTimer(self)
        self.interpolate_timer.timeout.connect(self._interpolate_position)
        self.interpolate_timer.start(100)

        # Start/End Time Labels are drawn directly inside paintEvent
        # to maximize custom layout space and ensure flawless liquid aesthetic.

    def update_timeline(self, position: float, duration: float, is_playing: bool):
        if not self.dragging:
            self.position = max(0.0, min(position, duration if duration > 0.0 else position))
        self.duration = max(0.0, duration)
        self.is_playing = is_playing
        self.update()

    def _interpolate_position(self):
        # Only interpolate if track is playing and not currently user-dragging
        if self.is_playing and not self.dragging and self.duration > 0:
            self.position = min(self.position + 0.1, self.duration)
            self.update()

    def _get_slider_rect(self) -> QRectF:
        # Central track bar rect inside the 270px width (leaving margins for text labels)
        # Left margin: 40px, Right margin: 40px, Track width: 190px
        # Track height: 4px centered vertically
        margin_left = 38.0
        track_w = 194.0
        track_h = 4.0
        y = (self.height() - track_h) / 2.0
        return QRectF(margin_left, y, track_w, track_h)

    def _val_to_pos(self, val: float) -> float:
        rect = self._get_slider_rect()
        if self.duration <= 0.0:
            return rect.left()
        ratio = val / self.duration
        return rect.left() + ratio * rect.width()

    def _pos_to_val(self, x: float) -> float:
        rect = self._get_slider_rect()
        if rect.width() <= 0.0:
            return 0.0
        ratio = (x - rect.left()) / rect.width()
        ratio = max(0.0, min(ratio, 1.0))
        return ratio * self.duration

    def _is_on_handle(self, pos: QPointF) -> bool:
        hx = self._val_to_pos(self.position)
        hy = self.height() / 2.0
        radius = 7.0 if (self.hovered or self.dragging) else 5.0
        dist = ((pos.x() - hx) ** 2 + (pos.y() - hy) ** 2) ** 0.5
        return dist <= radius

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.handle_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            if self._is_on_handle(pos):
                self.dragging = True
            else:
                # Direct absolute click seeking
                rect = self._get_slider_rect()
                # Expand click target slightly for comfort
                click_margin = 10.0
                if rect.left() - click_margin <= pos.x() <= rect.right() + click_margin:
                    new_val = self._pos_to_val(pos.x())
                    self.position = new_val
                    self.dragging = True
                    self.seek_requested.emit(self.position)
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        self.handle_hovered = self._is_on_handle(pos)

        if self.dragging and (event.buttons() & Qt.LeftButton):
            new_val = self._pos_to_val(pos.x())
            self.position = new_val
            self.seek_requested.emit(self.position)
            self.update()
        else:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.dragging:
                self.dragging = False
                self.seek_requested.emit(self.position)
                self.update()

    def _format_time(self, seconds: float) -> str:
        s = int(seconds)
        mins = s // 60
        secs = s % 60
        return f"{mins}:{secs:02d}"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Get slider track dimensions
        track_rect = self._get_slider_rect()

        # 1. Paint Background Track
        bg_color = QColor(255, 255, 255, 45) if self.hovered else QColor(255, 255, 255, 25)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(track_rect, 2.0, 2.0)

        # 2. Paint Active Progress Track
        if self.duration > 0.0:
            ratio = self.position / self.duration
            active_w = track_rect.width() * ratio
            if active_w > 0:
                active_rect = QRectF(track_rect.left(), track_rect.top(), active_w, track_rect.height())
                # Neon gradient reflecting liquid active progress
                active_grad = QLinearGradient(active_rect.left(), 0, active_rect.right(), 0)
                active_grad.setColorAt(0.0, QColor(42, 112, 255, 220))
                active_grad.setColorAt(1.0, QColor(0, 240, 255, 240))
                painter.setBrush(QBrush(active_grad))
                painter.drawRoundedRect(active_rect, 2.0, 2.0)

        # 3. Paint Slide Handle
        if self.duration > 0.0:
            hx = self._val_to_pos(self.position)
            hy = self.height() / 2.0

            # Interactive sizes: bigger on hover/drag
            if self.dragging:
                radius = 6.0
                border_color = QColor(255, 255, 255, 240)
            elif self.hovered or self.handle_hovered:
                radius = 5.0
                border_color = QColor(255, 255, 255, 210)
            else:
                radius = 4.0
                border_color = QColor(255, 255, 255, 170)

            painter.setPen(QPen(border_color, 1.2))
            painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
            painter.drawEllipse(QPointF(hx, hy), radius, radius)

        # 4. Paint Time Labels (Elapsed on Left, Total Duration on Right)
        painter.setPen(QColor(255, 255, 255, 140))
        painter.setFont(QFont("Segoe UI", 7))

        elapsed_str = self._format_time(self.position)
        duration_str = self._format_time(self.duration)

        # Centered vertically in the widget height
        metrics = painter.fontMetrics()
        text_h = metrics.height()
        y_text = (self.height() + text_h) / 2.0 - 2.0

        # Draw left text aligned right at track_rect.left() - 6px
        left_text_w = metrics.horizontalAdvance(elapsed_str)
        painter.drawText(QPointF(track_rect.left() - left_text_w - 6.0, y_text), elapsed_str)

        # Draw right text aligned left at track_rect.right() + 6px
        painter.drawText(QPointF(track_rect.right() + 6.0, y_text), duration_str)


class RoundedCoverLabel(QWidget):
    def __init__(self):
        super().__init__()

        self.setFixedSize(64, 64)
        self._pixmap = None
        self._radius = 16

    def set_cover_bytes(self, cover_bytes):
        if cover_bytes:
            pix = QPixmap()

            if pix.loadFromData(cover_bytes):
                self._pixmap = pix
                self.update()
                return

        self._pixmap = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        painter.setClipPath(path)

        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2

            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillPath(path, QColor(255, 255, 255, 28))
            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(QFont("Segoe UI Symbol", 26))
            painter.drawText(self.rect(), Qt.AlignCenter, "♪")


class LiquidCard(QFrame):
    dragged = Signal(QPoint)
    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and (event.buttons() & Qt.LeftButton):
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self.drag_start_pos
            self.drag_start_pos = current_pos
            self.dragged.emit(delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        path = QPainterPath()
        path.addRoundedRect(rect, 28, 28)

        # Subtle white border with 1px width and 30 alpha
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        painter.setBrush(CARD_BG_QCOLOR)
        painter.drawPath(path)


class LiquidMusicPanel(QWidget):
    action_requested = Signal(str, object)

    def __init__(self):
        super().__init__()

        self.visible_panel = False
        self.pinned = False
        self.last_hot_time = 0

        # Manual position state
        self.manual_pos = False
        self.saved_manual_x = 0
        self.saved_manual_y = 0

        self.setFixedSize(PANEL_W, PANEL_H)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(0.0)

        self._build_ui()
        self._build_animation()

        self.reposition(hidden=True)
        self.show()

        self._apply_native_window_flags()

        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self._check_hover)
        self.hover_timer.start(15)

    def resizeEvent(self, event):
        self.card.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def _build_ui(self):
        self.card = LiquidCard(self)
        self.card.setGeometry(0, 0, PANEL_W, PANEL_H)

        # Connect drag and double-click signals from LiquidCard
        self.card.dragged.connect(self._on_card_dragged)
        self.card.double_clicked.connect(self.toggle_mode)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 110))
        self.card.setGraphicsEffect(shadow)

        self.cover = RoundedCoverLabel()

        self.title = QLabel("Яндекс Музыка не найдена")
        self.title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.title.setStyleSheet("color: rgba(245,245,245,245); background: transparent;")

        self.artist = QLabel("Открой Яндекс Музыка.exe")
        self.artist.setFont(QFont("Segoe UI", 9))
        self.artist.setStyleSheet("color: rgba(255,255,255,175); background: transparent;")

        self.app_label = QLabel("")
        self.app_label.setFont(QFont("Segoe UI", 8))
        self.app_label.setStyleSheet("color: rgba(255,255,255,110); background: transparent;")

        self.prev_btn = CircleIconButton("prev")
        self.play_btn = CircleIconButton("play", accent=True)
        self.next_btn = CircleIconButton("next")
        self.pin_btn = CircleIconButton("pin")
        self.close_btn = CircleIconButton("close", danger=True)

        self.prev_btn.clicked.connect(lambda: self.action_requested.emit("prev", None))
        self.play_btn.clicked.connect(lambda: self.action_requested.emit("play_pause", None))
        self.next_btn.clicked.connect(lambda: self.action_requested.emit("next", None))
        self.pin_btn.clicked.connect(self._toggle_pin)
        self.close_btn.clicked.connect(QApplication.quit)

        text_block = QVBoxLayout()
        text_block.setContentsMargins(0, 0, 0, 0)
        text_block.setSpacing(2)
        text_block.addWidget(self.title)
        text_block.addWidget(self.artist)
        text_block.addWidget(self.app_label)
        text_block.addStretch(1)

        text_container = QWidget()
        text_container.setLayout(text_block)
        text_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self.prev_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.next_btn)
        controls_layout.addWidget(self.pin_btn)
        controls_layout.addWidget(self.close_btn)

        controls_widget = QWidget()
        controls_widget.setLayout(controls_layout)
        controls_widget.setFixedWidth(34 * 5 + 8 * 4 + 2)

        # Main Vertical Layout for LiquidCard
        self.card_v_layout = QVBoxLayout(self.card)
        self.card_v_layout.setContentsMargins(0, 0, 0, 16)
        self.card_v_layout.setSpacing(10)

        # Row 1 layout
        self.main_row_layout = QHBoxLayout()
        self.main_row_layout.setContentsMargins(16, 16, 16, 12)
        self.main_row_layout.setSpacing(14)
        self.main_row_layout.addWidget(self.cover)
        self.main_row_layout.addWidget(text_container, 1)
        self.main_row_layout.addWidget(controls_widget, 0, Qt.AlignVCenter)

        self.main_row_widget = QWidget()
        self.main_row_widget.setLayout(self.main_row_layout)

        # Row 2 layout (Visualizer and Seek slider)
        self.bottom_row_layout = QHBoxLayout()
        self.bottom_row_layout.setContentsMargins(16, 0, 16, 0)
        self.bottom_row_layout.setSpacing(14)

        self.visualizer = SpectrumVisualizer()
        self.slider = CustomSlider()
        # Connect slider seek to action requested
        self.slider.seek_requested.connect(lambda secs: self.action_requested.emit("seek", secs))

        self.bottom_row_layout.addWidget(self.visualizer)
        self.bottom_row_layout.addWidget(self.slider)

        self.bottom_row_widget = QWidget()
        self.bottom_row_widget.setLayout(self.bottom_row_layout)

        # Add rows to card layout
        self.card_v_layout.addWidget(self.main_row_widget)
        self.card_v_layout.addWidget(self.bottom_row_widget)

    def _build_animation(self):
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(165)
        self.pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(150)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(self.pos_anim)
        self.anim_group.addAnimation(self.opacity_anim)
        self.anim_group.finished.connect(self._on_animation_finished)

    def _on_animation_finished(self):
        # Move offscreen when completely hidden so it doesn't block clicks
        if not self.visible_panel:
            self.move(self.x(), -5000)

    def _apply_native_window_flags(self):
        if sys.platform != "win32":
            return

        try:
            hwnd = int(self.winId())

            user32 = ctypes.windll.user32

            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_APPWINDOW = 0x00040000

            exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            exstyle |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            exstyle &= ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)

            HWND_TOPMOST = -1

            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040

            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
            )
        except Exception:
            pass

    def _toggle_pin(self):
        self.pinned = not self.pinned
        self.pin_btn.accent = self.pinned
        self.pin_btn.update()

        if self.pinned:
            self.show_panel()

    def _on_card_dragged(self, delta: QPoint):
        self.manual_pos = True
        new_pos = self.pos() + delta
        self.move(new_pos)
        self.saved_manual_x = new_pos.x()
        self.saved_manual_y = new_pos.y()

    def toggle_mode(self):
        if hasattr(self, "geo_anim") and self.geo_anim.state() == QPropertyAnimation.Running:
            self.geo_anim.stop()

        current_rect = self.geometry()
        target_h = PANEL_H_LARGE if current_rect.height() == PANEL_H_SMALL else PANEL_H_SMALL

        if hasattr(self, "geo_anim"):
            try:
                self.geo_anim.finished.disconnect()
            except Exception:
                pass

        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(250)
        self.geo_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.geo_anim.setStartValue(current_rect)

        target_y = current_rect.y()
        if not self.manual_pos:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            target_y = geo.y() + SHOW_Y_OFFSET

        target_rect = QRect(current_rect.x(), target_y, PANEL_W, target_h)
        self.geo_anim.setEndValue(target_rect)

        if target_h == PANEL_H_LARGE:
            self.cover.setVisible(True)
            self.visualizer.setVisible(True)
            self.slider.setVisible(True)
            self.main_row_layout.setContentsMargins(16, 16, 16, 12)
            self.card_v_layout.setContentsMargins(0, 0, 0, 16)
            self.card_v_layout.setSpacing(10)
            self.setMinimumHeight(PANEL_H_SMALL)
            self.setMaximumHeight(PANEL_H_LARGE)
        else:
            self.main_row_layout.setContentsMargins(16, 0, 16, 0)
            self.card_v_layout.setContentsMargins(0, 0, 0, 0)
            self.card_v_layout.setSpacing(0)
            self.setMinimumHeight(PANEL_H_SMALL)
            self.setMaximumHeight(PANEL_H_LARGE)

            def on_shrink_finished():
                self.cover.setVisible(False)
                self.visualizer.setVisible(False)
                self.slider.setVisible(False)
                self.setFixedSize(PANEL_W, PANEL_H_SMALL)

            self.geo_anim.finished.connect(on_shrink_finished)

        def finalize_expand():
            if target_h == PANEL_H_LARGE:
                self.setFixedSize(PANEL_W, PANEL_H_LARGE)

        if target_h == PANEL_H_LARGE:
            self.geo_anim.finished.connect(finalize_expand)

        self.geo_anim.start()

    def update_media(self, data: dict):
        # We check metadata_changed to avoid reload flicker of cover and labels
        if data.get("metadata_changed", True):
            title = data.get("title") or "Яндекс Музыка не найдена"
            artist = data.get("artist") or "Открой Яндекс Музыка.exe"
            app = data.get("app") or ""

            self.title.setText(self._elide(title, self.title, 270))
            self.artist.setText(self._elide(artist, self.artist, 270))

            if app:
                clean_app = app.replace("Microsoft.", "").replace("_", " ")
                self.app_label.setText(self._elide(clean_app, self.app_label, 270))
            else:
                self.app_label.setText("Только Яндекс Музыка.exe")

            self.cover.set_cover_bytes(data.get("cover"))

        # Always update play/pause state independently
        playing = data.get("playing", False)
        self.play_btn.set_icon("pause" if playing else "play")

        # Update sub-widgets
        self.visualizer.set_playing(playing)
        self.slider.update_timeline(data.get("position", 0.0), data.get("duration", 0.0), playing)

    def _elide(self, text, label, width):
        metrics = label.fontMetrics()
        return metrics.elidedText(text, Qt.ElideRight, width)

    def reposition(self, hidden=False):
        if self.manual_pos:
            if hidden:
                self.move(self.saved_manual_x, -5000)
            else:
                self.move(self.saved_manual_x, self.saved_manual_y)
            return

        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geo = screen.availableGeometry()

        x = geo.x() + geo.width() // 2 - self.width() // 2

        if hidden:
            y = geo.y() - self.height() - 6
        else:
            y = geo.y() + SHOW_Y_OFFSET

        self.move(x, y)

    def _check_hover(self):
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        geo = screen.availableGeometry()

        center_x = geo.x() + geo.width() // 2

        # Hover detection at screen top edge remains active even in manual positioning
        near_top_center = (
            geo.y() <= cursor.y() <= geo.y() + TRIGGER_Y
            and abs(cursor.x() - center_x) <= TRIGGER_WIDTH // 2
        )

        inside_panel = self.frameGeometry().contains(cursor)
        now = time.time()

        if near_top_center or inside_panel:
            self.last_hot_time = now

            if not self.visible_panel:
                self.show_panel()

            return

        if self.pinned:
            return

        if self.visible_panel and (now - self.last_hot_time) >= HIDE_DELAY:
            self.hide_panel()

    def show_panel(self):
        self.visible_panel = True

        if self.manual_pos:
            # Instantly move to saved manual position to prevent long slide from off-screen
            self.move(self.saved_manual_x, self.saved_manual_y)
            self._animate_to(self.saved_manual_x, self.saved_manual_y, 1.0)
        else:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            geo = screen.availableGeometry()

            target_x = geo.x() + geo.width() // 2 - self.width() // 2
            target_y = geo.y() + SHOW_Y_OFFSET

            # Jump instantly to just above top edge before sliding in
            self.move(target_x, geo.y() - self.height() - 6)
            self._animate_to(target_x, target_y, 1.0)

        self._refresh_topmost()

    def hide_panel(self):
        self.visible_panel = False

        if self.manual_pos:
            self._animate_to(self.saved_manual_x, self.saved_manual_y, 0.0)
        else:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            geo = screen.availableGeometry()

            target_x = geo.x() + geo.width() // 2 - self.width() // 2
            target_y = geo.y() - self.height() - 6

            self._animate_to(target_x, target_y, 0.0)

    def _refresh_topmost(self):
        if sys.platform != "win32":
            return

        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32

            HWND_TOPMOST = -1

            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040

            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
            )
        except Exception:
            pass

    def _animate_to(self, x, y, opacity):
        self.anim_group.stop()

        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(QPoint(x, y))

        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(opacity)

        self.anim_group.start()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    panel = LiquidMusicPanel()

    worker = MediaWorker()
    worker.media_changed.connect(panel.update_media)
    panel.action_requested.connect(worker.command)
    worker.start()

    app.aboutToQuit.connect(worker.stop)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()