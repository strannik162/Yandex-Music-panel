import sys
import time
import asyncio
import hashlib
import threading
import ctypes
import datetime

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
PANEL_H = 160

PANEL_H_LARGE = 160
PANEL_H_SMALL = 88

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


class MediaWorker(QObject):
    media_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.running = False
        self.loop = None
        self.manager = None
        self.session = None
        self.thread = None
        self.last_signature = None

    def start(self):
        if not WINSDK_OK:
            self.media_changed.emit({
                "title": "winsdk не установлен",
                "artist": "Введи: pip install winsdk",
                "app": "",
                "playing": False,
                "cover": None,
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

    def command(self, action_tuple: tuple):
        if not self.loop:
            return

        action, value = action_tuple
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
            })
            return

        while self.running:
            data = await self._read_current_media()

            cover = data.get("cover")
            cover_hash = hashlib.sha1(cover).hexdigest() if cover else ""

            signature = (
                data.get("title", ""),
                data.get("artist", ""),
                data.get("album", ""),
                data.get("app", ""),
                data.get("playing", False),
                cover_hash,
            )

            # Metadata properties change only when structure differs, but we always emit position/duration updates.
            # To ensure the slider position and duration stay updated in the UI, we can emit on every poll,
            # but we can set a flag inside the data so components like cover/text aren't reload-snapped.
            if signature != self.last_signature:
                self.last_signature = signature
                data["metadata_changed"] = True
            else:
                data["metadata_changed"] = False

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

            position = 0.0
            duration = 0.0
            try:
                timeline = session.get_timeline_properties()
                if timeline:
                    # winsdk timeline position returns TimeSpan in 100-nanosecond ticks
                    # Or standard datetime.timedelta
                    pos_val = timeline.position
                    dur_val = timeline.end_time - timeline.start_time

                    if hasattr(pos_val, "duration"): # winsdk TimeSpan structure
                        position = float(pos_val.duration) / 10000000.0
                    elif hasattr(pos_val, "total_seconds"):
                        position = pos_val.total_seconds()
                    else:
                        position = float(pos_val) / 10000000.0

                    if hasattr(dur_val, "duration"):
                        duration = float(dur_val.duration) / 10000000.0
                    elif hasattr(dur_val, "total_seconds"):
                        duration = dur_val.total_seconds()
                    else:
                        duration = float(dur_val) / 10000000.0
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
                "position": position,
                "duration": duration,
            }

        except Exception as e:
            return {
                "title": "Ошибка чтения Яндекс Музыки",
                "artist": str(e),
                "album": "",
                "app": "",
                "playing": False,
                "cover": None,
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

    async def _control(self, action: str, value: object = None):
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

            elif action == "seek":
                if value is not None:
                    try:
                        # try_change_playback_position_async takes 100ns ticks, or sometimes timedelta
                        requested_pos_seconds = float(value)
                        ticks = int(requested_pos_seconds * 10000000)
                        # We try to pass a datetime.timedelta first, as it is standard in the pywin32 / winsdk wrapper
                        delta = datetime.timedelta(seconds=requested_pos_seconds)
                        try:
                            await session.try_change_playback_position_async(delta)
                        except Exception:
                            # Fallback if timedelta is not supported/recognized by specific winsdk versions
                            await session.try_change_playback_position_async(ticks)
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


import random

class SpectrumVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 32)
        self.bars_count = 32
        self.heights = [2.0] * self.bars_count
        self.playing = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.start(50)

    def set_playing(self, playing: bool):
        self.playing = playing

    def _update_animation(self):
        if not self.playing:
            changed = False
            for i in range(self.bars_count):
                if self.heights[i] > 2.0:
                    self.heights[i] = max(2.0, self.heights[i] - 1.0)
                    changed = True
            if changed:
                self.update()
            return

        # Procedural simulation
        # Left side: low frequencies (thumping), middle: mids, right: highs (flickering)
        for i in range(self.bars_count):
            t = time.time()
            if i < 8: # Lows
                base = 12.0 + 8.0 * random.random()
                amp = 8.0 * (1.0 + 0.5 * (1.0 if random.random() > 0.8 else -0.5))
            elif i < 22: # Mids
                base = 6.0 + 4.0 * random.random()
                amp = 10.0
            else: # Highs
                base = 4.0 + 10.0 * random.random()
                amp = 14.0

            target = base + amp * (0.5 + 0.5 * (1.0 if random.random() > 0.5 else -0.5))
            target = min(30.0, max(2.0, target))

            # Smooth transition to target height
            self.heights[i] = self.heights[i] * 0.5 + target * 0.5

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        gap = 2.0
        bar_w = (w - (self.bars_count - 1) * gap) / self.bars_count

        painter.setPen(Qt.NoPen)

        # Draw each bar with gradient matching aesthetic
        for i in range(self.bars_count):
            bar_h = self.heights[i]
            x = i * (bar_w + gap)
            y = h - bar_h

            # Create a nice vertical gradient
            grad = QColor(255, 255, 255, 220)
            if i < 8: # purple-ish/pink accents for bass
                grad = QColor(230, 100, 250, 220)
            elif i > 24: # blue-ish accents for high
                grad = QColor(100, 200, 255, 220)

            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.0, 1.0)


class CustomSlider(QWidget):
    slider_moved = Signal(float) # Emits position in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 16)
        self.position = 0.0      # Current position in seconds
        self.duration = 0.0      # Track duration in seconds
        self.dragging = False
        self.hovered = False

        self.setCursor(Qt.PointingHandCursor)

        # Timer for local position interpolation (100ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._interpolate_position)
        self.timer.start(100)
        self.playing = False
        self.last_update_time = time.time()

    def set_playing(self, playing: bool):
        self.playing = playing
        self.last_update_time = time.time()

    def set_timeline(self, position: float, duration: float):
        if not self.dragging:
            self.position = position
            self.duration = duration
            self.last_update_time = time.time()
            self.update()

    def _interpolate_position(self):
        if self.playing and not self.dragging and self.duration > 0:
            now = time.time()
            dt = now - self.last_update_time
            self.last_update_time = now
            self.position = min(self.duration, self.position + dt)
            self.update()
        else:
            self.last_update_time = time.time()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self._update_position_from_mouse(event.position().x())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._update_position_from_mouse(event.position().x())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.slider_moved.emit(self.position)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _update_position_from_mouse(self, mouse_x):
        if self.duration <= 0:
            return
        ratio = max(0.0, min(1.0, mouse_x / self.width()))
        self.position = ratio * self.duration
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        h = self.height()
        w = self.width()

        track_h = 4.0
        track_y = (h - track_h) / 2.0

        # Draw background track
        track_path = QPainterPath()
        track_path.addRoundedRect(QRectF(0, track_y, w, track_h), 2.0, 2.0)
        painter.fillPath(track_path, QColor(255, 255, 255, 45))

        # Progress bar width
        progress_ratio = 0.0
        if self.duration > 0:
            progress_ratio = max(0.0, min(1.0, self.position / self.duration))

        progress_w = progress_ratio * w

        if progress_w > 0:
            progress_path = QPainterPath()
            progress_path.addRoundedRect(QRectF(0, track_y, progress_w, track_h), 2.0, 2.0)
            painter.fillPath(progress_path, QColor(255, 255, 255, 200))

        # Handle drawing
        if self.hovered or self.dragging:
            handle_r = 5.0
            cx = progress_ratio * w
            cy = h / 2.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
            painter.drawEllipse(QPointF(cx, cy), handle_r, handle_r)


class LiquidCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_start_pos = None
        self.window_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPosition()
            self.window_start_pos = self.window().pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and self.window_start_pos is not None:
            delta = event.globalPosition() - self.drag_start_pos
            new_pos = self.window_start_pos + QPoint(int(delta.x()), int(delta.y()))
            self.window().move(new_pos)
            self.window().manual_pos = True
            self.window().saved_manual_x = new_pos.x()
            self.window().saved_manual_y = new_pos.y()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None
            self.window_start_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            panel = self.window()
            if hasattr(panel, "toggle_mode"):
                panel.toggle_mode()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        path = QPainterPath()
        path.addRoundedRect(rect, 28, 28)

        # Subtle white border for improved contrast
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(CARD_BG_QCOLOR)
        painter.drawPath(path)


class LiquidMusicPanel(QWidget):
    action_requested = Signal(tuple)

    def __init__(self):
        super().__init__()

        self.visible_panel = False
        self.pinned = False
        self.last_hot_time = 0
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

    def _build_ui(self):
        self.is_large_mode = True
        self.geo_anim = None

        self.card = LiquidCard(self)
        self.card.setGeometry(0, 0, PANEL_W, PANEL_H)

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

        self.visualizer = SpectrumVisualizer()
        self.slider = CustomSlider()
        self.slider.slider_moved.connect(lambda pos: self.action_requested.emit(("seek", pos)))

        self.prev_btn = CircleIconButton("prev")
        self.play_btn = CircleIconButton("play", accent=True)
        self.next_btn = CircleIconButton("next")
        self.pin_btn = CircleIconButton("pin")
        self.close_btn = CircleIconButton("close", danger=True)

        self.prev_btn.clicked.connect(lambda: self.action_requested.emit(("prev", None)))
        self.play_btn.clicked.connect(lambda: self.action_requested.emit(("play_pause", None)))
        self.next_btn.clicked.connect(lambda: self.action_requested.emit(("next", None)))
        self.pin_btn.clicked.connect(self._toggle_pin)
        self.close_btn.clicked.connect(QApplication.quit)

        # Left column layout
        left_vbox = QVBoxLayout()
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(2)
        left_vbox.addWidget(self.title)
        left_vbox.addWidget(self.artist)
        left_vbox.addWidget(self.app_label)
        left_vbox.addStretch(1) # Stretch at the bottom to center content in small mode

        self.left_column_container = QWidget()
        self.left_column_container.setLayout(left_vbox)

        # Right column visualizer + slider block
        right_vbox = QVBoxLayout()
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(10)
        right_vbox.addWidget(self.visualizer)
        right_vbox.addWidget(self.slider)

        self.right_column_container = QWidget()
        self.right_column_container.setLayout(right_vbox)

        # Info row (album cover + left column label block + right column visualizer/slider block)
        self.info_row_layout = QHBoxLayout()
        self.info_row_layout.setContentsMargins(0, 0, 0, 0)
        self.info_row_layout.setSpacing(14)
        self.info_row_layout.addWidget(self.cover)
        self.info_row_layout.addWidget(self.left_column_container, 1)
        self.info_row_layout.addWidget(self.right_column_container, 0, Qt.AlignVCenter)

        self.info_row_widget = QWidget()
        self.info_row_widget.setLayout(self.info_row_layout)

        # Controls layout
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(14)
        self.controls_layout.addWidget(self.prev_btn)
        self.controls_layout.addWidget(self.play_btn)
        self.controls_layout.addWidget(self.next_btn)
        self.controls_layout.addWidget(self.pin_btn)
        self.controls_layout.addWidget(self.close_btn)

        self.controls_widget = QWidget()
        self.controls_widget.setLayout(self.controls_layout)

        # Main content layout
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(14)
        self.content_layout.addWidget(self.info_row_widget)
        self.content_layout.addWidget(self.controls_widget, 0, Qt.AlignCenter)

        self.card.setLayout(self.content_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.card.setGeometry(0, 0, self.width(), self.height())

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

    def toggle_mode(self):
        self.is_large_mode = not self.is_large_mode

        # Stop existing transition animation if active
        if self.geo_anim:
            self.geo_anim.stop()

        target_h = PANEL_H_LARGE if self.is_large_mode else PANEL_H_SMALL

        # Pre-configure visibility changes to prevent visual layout snap/pop
        if self.is_large_mode:
            # Re-enable/expand spacing/margins
            self.content_layout.setContentsMargins(16, 16, 16, 16)
            self.content_layout.setSpacing(14)
            self.right_column_container.setVisible(True)
            self.cover.setVisible(True)

            self.setMinimumHeight(PANEL_H_SMALL)
            self.setMaximumHeight(PANEL_H_LARGE)
        else:
            # Reduce layout footprint to avoid text clipping before transition finishes
            self.content_layout.setContentsMargins(16, 10, 16, 10)
            self.content_layout.setSpacing(0)

            self.setMinimumHeight(PANEL_H_SMALL)
            self.setMaximumHeight(PANEL_H_LARGE)

        curr_rect = self.geometry()
        target_rect = QRectF(curr_rect.x(), curr_rect.y(), PANEL_W, target_h).toRect()

        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(250)
        self.geo_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.geo_anim.setStartValue(curr_rect)
        self.geo_anim.setEndValue(target_rect)

        def on_finished():
            # Clean up properties to avoid constraint warnings
            self.setMinimumHeight(target_h)
            self.setMaximumHeight(target_h)
            self.setFixedSize(PANEL_W, target_h)

            if not self.is_large_mode:
                # Fully hide background-aligned larger visual widgets
                self.right_column_container.setVisible(False)
                self.cover.setVisible(False)

        # Disconnect any previously connected finished signal safely
        try:
            self.geo_anim.finished.disconnect()
        except Exception:
            pass

        self.geo_anim.finished.connect(on_finished)
        self.geo_anim.start()

    def update_media(self, data: dict):
        title = data.get("title") or "Яндекс Музыка не найдена"
        artist = data.get("artist") or "Открой Яндекс Музыка.exe"
        app = data.get("app") or ""
        playing = data.get("playing", False)

        self.title.setText(self._elide(title, self.title, 270))
        self.artist.setText(self._elide(artist, self.artist, 270))

        if app:
            clean_app = app.replace("Microsoft.", "").replace("_", " ")
            self.app_label.setText(self._elide(clean_app, self.app_label, 270))
        else:
            self.app_label.setText("Только Яндекс Музыка.exe")

        self.play_btn.set_icon("pause" if playing else "play")
        self.cover.set_cover_bytes(data.get("cover"))

        # Update sub-widgets states
        self.visualizer.set_playing(playing)
        self.slider.set_playing(playing)

        # Timeline duration/position updates
        pos = data.get("position", 0.0)
        dur = data.get("duration", 0.0)
        self.slider.set_timeline(pos, dur)

    def _elide(self, text, label, width):
        metrics = label.fontMetrics()
        return metrics.elidedText(text, Qt.ElideRight, width)

    def reposition(self, hidden=False):
        if self.manual_pos:
            if hidden:
                # hide off-screen when manually positioned to avoid block, keep opacity target
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
            target_x = self.saved_manual_x
            target_y = self.saved_manual_y
            self.move(target_x, target_y)
        else:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            target_x = geo.x() + geo.width() // 2 - self.width() // 2
            target_y = geo.y() + SHOW_Y_OFFSET

        self._animate_to(target_x, target_y, 1.0)
        self._refresh_topmost()

    def hide_panel(self):
        self.visible_panel = False

        if self.manual_pos:
            target_x = self.saved_manual_x
            target_y = -5000
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