import sys
import time
import asyncio
import hashlib
import threading
import ctypes
import random
import math
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
PANEL_H = 160  # Initial matches the default Large Mode panel height
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
    # Tuple representing: action name, optional action value (e.g. seek position)
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

    def command(self, action: str, value: object = None):
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
                "metadata_changed": True,
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
                cover_hash,
            )

            # Separate tracking of metadata and polling progress updates
            metadata_changed = (signature != self.last_signature)
            if metadata_changed:
                self.last_signature = signature

            # Always emit so UI updates the seek position & duration on every poll
            data["metadata_changed"] = metadata_changed
            data["cover_hash"] = cover_hash
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
            duration = 1.0
            try:
                # Retrieve timeline position and duration from SMTC
                timeline = session.get_timeline_properties()
                if timeline:
                    # Windows returns position/duration in 100-nanosecond units (ticks) or TimeSpan
                    # Let's support both .total_seconds() (standard timedelta/TimeSpan mapping)
                    # and falling back to manual ticks if needed.
                    try:
                        position = timeline.position.total_seconds()
                    except Exception:
                        position = getattr(timeline.position, "duration", 0) / 10000000.0

                    try:
                        duration = timeline.end_position.total_seconds()
                    except Exception:
                        duration = getattr(timeline.end_position, "duration", 1) / 10000000.0
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
                "position": 0.0,
                "duration": 1.0,
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
                    # value is a float between 0.0 and 1.0 representing percentage
                    timeline = session.get_timeline_properties()
                    if timeline:
                        # Fetch the absolute duration
                        try:
                            tot_sec = timeline.end_position.total_seconds()
                        except Exception:
                            tot_sec = getattr(timeline.end_position, "duration", 0) / 10000000.0

                        target_sec = value * tot_sec
                        # convert target_sec to a timedelta
                        requested_pos = datetime.timedelta(seconds=target_sec)
                        try:
                            await session.try_change_playback_position_async(requested_pos)
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
    def __init__(self):
        super().__init__()
        self.setFixedSize(270, 32)
        self.bars = 32
        self.heights = [2.0] * self.bars
        self.targets = [2.0] * self.bars
        self.playing = False

        # procedural animation timer (50ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(50)

    def set_playing(self, playing):
        self.playing = playing

    def _animate(self):
        if self.playing:
            # Generate target heights based on frequency profile (low/mid/high)
            # Thumping bass on the left (bars 0 to 8), mid-range in middle, flickering highs on right (bars 24 to 31)
            t = time.time()
            for i in range(self.bars):
                if i < 8:
                    # Low frequencies / Bass (large thumps, slower changes)
                    base = math.sin(t * 8 + i * 0.5) * 12 + 15
                    noise = random.uniform(-4, 4)
                    val = max(3.0, min(30.0, base + noise))
                elif i < 24:
                    # Mids (medium activity)
                    base = math.cos(t * 12 + i * 0.8) * 8 + 12
                    noise = random.uniform(-3, 3)
                    val = max(2.0, min(24.0, base + noise))
                else:
                    # High frequencies (high-frequency flicker)
                    base = math.sin(t * 22 + i * 1.5) * 6 + 8
                    noise = random.uniform(-6, 6)
                    val = max(1.5, min(20.0, base + noise))
                self.targets[i] = val
        else:
            # Decay to baseline if paused/stopped
            for i in range(self.bars):
                self.targets[i] = 2.0

        # Smoothly interpolate towards targets
        for i in range(self.bars):
            self.heights[i] += (self.targets[i] - self.heights[i]) * 0.3

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        bar_gap = 2
        total_gaps_w = bar_gap * (self.bars - 1)
        bar_w = (w - total_gaps_w) / self.bars

        # Draw bars
        for i in range(self.bars):
            bar_h = self.heights[i]
            x = i * (bar_w + bar_gap)
            y = h - bar_h

            # Gentle gradient/color mapping: softer white/cyan-ish gradient
            # Low bars on left have slightly warmer tone, high on right cooler
            color = QColor(255, 255, 255, 200)
            if i < 8:
                color = QColor(255, 120 + i * 10, 150 + i * 10, 200)
            elif i < 24:
                color = QColor(140 + i * 3, 200 + i * 2, 255, 200)
            else:
                color = QColor(180, 240, 255, 200)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            # Draw rounded top bar
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), bar_w / 2, bar_w / 2)


class CustomSlider(QWidget):
    # Signal emitted when user seeks: passes the requested percentage (0.0 to 1.0)
    seek_requested = Signal(float)

    def __init__(self):
        super().__init__()
        self.setFixedSize(270, 18)
        self.setCursor(Qt.PointingHandCursor)

        self.position = 0.0  # current track position in seconds
        self.duration = 1.0  # track duration in seconds
        self.playing = False
        self.dragging = False

        # Timer to interpolate track progress between SMTC poll intervals (smooth progress bar)
        self.interpolation_timer = QTimer(self)
        self.interpolation_timer.timeout.connect(self._interpolate_position)
        self.interpolation_timer.start(100)

    def set_range(self, position: float, duration: float):
        if not self.dragging:
            self.position = max(0.0, position)
            self.duration = max(1.0, duration)
            self.update()

    def set_playing(self, playing: bool):
        self.playing = playing

    def _interpolate_position(self):
        if self.playing and not self.dragging:
            # Add 100ms (0.1 seconds) to current position
            if self.position < self.duration:
                self.position = min(self.duration, self.position + 0.1)
                self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self._handle_click_or_drag(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._handle_click_or_drag(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            pct = max(0.0, min(1.0, event.position().x() / self.width()))
            self.seek_requested.emit(pct)

    def _handle_click_or_drag(self, event):
        pct = max(0.0, min(1.0, event.position().x() / self.width()))
        self.position = pct * self.duration
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Draw slider track
        track_h = 4
        track_y = (self.height() - track_h) / 2
        track_rect = QRectF(0, track_y, self.width(), track_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 34)))
        painter.drawRoundedRect(track_rect, track_h / 2, track_h / 2)

        # Calculate progress width
        progress_ratio = self.position / self.duration if self.duration > 0 else 0.0
        progress_w = progress_ratio * self.width()

        # Draw active/filled track
        if progress_w > 0:
            active_rect = QRectF(0, track_y, progress_w, track_h)
            # Nice bright highlight color
            painter.setBrush(QBrush(QColor(42, 112, 255, 220)))
            painter.drawRoundedRect(active_rect, track_h / 2, track_h / 2)

        # Draw handle/thumb if hovering or dragging
        handle_r = 5
        handle_x = progress_w
        handle_y = self.height() / 2

        # Draw a nice glowing thumb
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
        painter.drawEllipse(QPointF(handle_x, handle_y), handle_r, handle_r)


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
    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Save the offset of the click inside the window to allow dragging
            self.drag_start_pos = event.globalPosition().toPoint() - self.window().pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_start_pos is not None:
            # Update parent window position
            new_pos = event.globalPosition().toPoint() - self.drag_start_pos
            self.window().set_manual_position(new_pos.x(), new_pos.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        path = QPainterPath()
        path.addRoundedRect(rect, 28, 28)

        painter.setPen(QPen(QColor(255, 255, 255, 30), 1)) # Subtle white border for liquid-glass effect contrast
        painter.setBrush(CARD_BG_QCOLOR)
        painter.drawPath(path)


class LiquidMusicPanel(QWidget):
    # Pass action type and optional parameters (e.g. action name and seek percent/value)
    action_requested = Signal(str, object)

    def __init__(self):
        super().__init__()

        self.visible_panel = False
        self.pinned = False
        self.last_hot_time = 0
        self.is_large_mode = True  # Start in Large Mode by default

        # Manual position state variables
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

    def set_manual_position(self, x: int, y: int):
        self.manual_pos = True
        self.saved_manual_x = x
        self.saved_manual_y = y
        self.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Match LiquidCard geometry dynamically since it acts as the border and background
        self.card.setGeometry(0, 0, self.width(), self.height())

    def toggle_mode(self):
        self.is_large_mode = not self.is_large_mode
        target_h = PANEL_H_LARGE if self.is_large_mode else PANEL_H_SMALL

        # Cleanly stop any existing size transition animations
        try:
            self.geo_anim.disconnect()
        except Exception:
            pass

        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(250)
        self.geo_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Build start & end geometry rects
        start_rect = self.geometry()
        end_rect = QRectF(start_rect.x(), start_rect.y(), PANEL_W, target_h).toRect()

        self.geo_anim.setStartValue(start_rect)
        self.geo_anim.setEndValue(end_rect)

        # Before expanding to Large mode, make bottom widgets and cover art visible
        if self.is_large_mode:
            self.cover.show()
            self.visualizer.show()
            self.slider.show()
            # Switch back to beautiful spacious margins
            self.main_row.setContentsMargins(16, 16, 16, 16)
            self.main_row.setSpacing(14)
            self.text_block.setSpacing(2)

        def on_animation_finished():
            # Finalize constraints after smooth transitions
            self.setFixedSize(PANEL_W, target_h)
            self.card.setGeometry(0, 0, PANEL_W, target_h)

            # If shrunken to Small mode, hide those elements post-animation to prevent snap glitches
            if not self.is_large_mode:
                self.cover.hide()
                self.visualizer.hide()
                self.slider.hide()
            else:
                self.cover.show()
                self.visualizer.show()
                self.slider.show()

        self.geo_anim.finished.connect(on_animation_finished)

        # Configure layout styling dynamically to maintain Windows visual aesthetic
        if not self.is_large_mode:
            # Compact mode layouts
            self.main_row.setContentsMargins(16, 0, 16, 0)
            self.main_row.setSpacing(14)
            self.text_block.setSpacing(0)
            self.text_block.setContentsMargins(0, 0, 0, 0)

        self.geo_anim.start()

    def _build_ui(self):
        self.card = LiquidCard(self)
        self.card.setGeometry(0, 0, PANEL_W, PANEL_H)
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

        # Custom controls/features
        self.visualizer = SpectrumVisualizer()
        self.slider = CustomSlider()
        self.slider.seek_requested.connect(lambda pct: self.action_requested.emit("seek", pct))

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

        self.text_block = QVBoxLayout()
        self.text_block.setContentsMargins(0, 0, 0, 0)
        self.text_block.setSpacing(2)
        self.text_block.addWidget(self.title)
        self.text_block.addWidget(self.artist)
        self.text_block.addWidget(self.app_label)
        # Stack visualizer and slider under labels in Large Mode
        self.text_block.addWidget(self.visualizer)
        self.text_block.addWidget(self.slider)
        self.text_block.addStretch(1)

        text_container = QWidget()
        text_container.setLayout(self.text_block)
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

        self.main_row = QHBoxLayout(self.card)
        self.main_row.setContentsMargins(16, 16, 16, 16)
        self.main_row.setSpacing(14)
        self.main_row.addWidget(self.cover)
        self.main_row.addWidget(text_container, 1)
        self.main_row.addWidget(controls_widget, 0, Qt.AlignVCenter)

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

    def update_media(self, data: dict):
        title = data.get("title") or "Яндекс Музыка не найдена"
        artist = data.get("artist") or "Открой Яндекс Музыка.exe"
        app = data.get("app") or ""
        playing = data.get("playing", False)

        metadata_changed = data.get("metadata_changed", True)

        if metadata_changed:
            self.title.setText(self._elide(title, self.title, 270))
            self.artist.setText(self._elide(artist, self.artist, 270))

            if app:
                clean_app = app.replace("Microsoft.", "").replace("_", " ")
                self.app_label.setText(self._elide(clean_app, self.app_label, 270))
            else:
                self.app_label.setText("Только Яндекс Музыка.exe")

            self.cover.set_cover_bytes(data.get("cover"))

        # Always update play button state and range info on poll
        self.play_btn.set_icon("pause" if playing else "play")
        self.visualizer.set_playing(playing)
        self.slider.set_playing(playing)
        self.slider.set_range(data.get("position", 0.0), data.get("duration", 1.0))

    def _elide(self, text, label, width):
        metrics = label.fontMetrics()
        return metrics.elidedText(text, Qt.ElideRight, width)

    def reposition(self, hidden=False):
        if self.manual_pos:
            # Under manual position mode, reposition handles the manual screen coordinates
            if hidden:
                # Avoid layout/clicking block by moving panel far off-screen
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

        # Allow revealing top panel on near-top hover even if placed elsewhere manually
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
            # Jump directly to avoid slide-in animation from -5000 off-screen y coordinate
            self.move(self.saved_manual_x, self.saved_manual_y)
            self._animate_to(self.saved_manual_x, self.saved_manual_y, 1.0)
            self._refresh_topmost()
            return

        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geo = screen.availableGeometry()

        target_x = geo.x() + geo.width() // 2 - self.width() // 2
        target_y = geo.y() + SHOW_Y_OFFSET

        self._animate_to(target_x, target_y, 1.0)
        self._refresh_topmost()

    def hide_panel(self):
        self.visible_panel = False

        if self.manual_pos:
            self._animate_to(self.saved_manual_x, self.saved_manual_y, 0.0)
            # After opacity fades, shift position to -5000 y coordinate to allow clicks to pass through
            QTimer.singleShot(160, lambda: self.move(self.saved_manual_x, -5000) if not self.visible_panel else None)
            return

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