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


def timespan_to_seconds(ts) -> float:
    if ts is None:
        return 0.0
    if hasattr(ts, "total_seconds"):
        return ts.total_seconds()
    if hasattr(ts, "duration"):
        return getattr(ts, "duration", 0) / 10000000.0
    return 0.0


class MediaWorker(QObject):
    # Dict will contain the metadata, playback state, and current timeline info.
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

            # metadata_signature contains parts of track info that determine label/artwork updates
            metadata_signature = (
                data.get("title", ""),
                data.get("artist", ""),
                data.get("album", ""),
                data.get("app", ""),
                cover_hash,
            )

            # Detect if metadata changed
            if metadata_signature != self.last_metadata_signature:
                self.last_metadata_signature = metadata_signature
                data["metadata_changed"] = True
            else:
                data["metadata_changed"] = False

            # Always emit to update play state and timeline position
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

            if not title:
                title = "Музыка не найдена"
            if not artist:
                artist = "Включи трек в приложении Яндекс Музыка"

            # Get timeline position and duration
            position = 0.0
            duration = 0.0
            try:
                timeline = session.get_timeline_properties()
                if timeline:
                    pos_val = getattr(timeline, "position", None)
                    position = timespan_to_seconds(pos_val)

                    end_val = getattr(timeline, "end_time", None)
                    if end_val is None:
                        end_val = getattr(timeline, "end_position", None)
                    if end_val is None:
                        end_val = getattr(timeline, "duration", None)
                    duration = timespan_to_seconds(end_val)
            except Exception:
                pass

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

            elif action == "seek" and value is not None:
                try:
                    target_td = timedelta(seconds=float(value))
                    await session.try_change_playback_position_async(target_td)
                except Exception:
                    pass

        except Exception:
            pass


class SpectrumVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 32)
        self.playing = False
        self.bar_heights = [2.0] * 32

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(50)

    def set_playing(self, playing):
        self.playing = playing

    def _animate(self):
        t = time.time()
        for i in range(32):
            if self.playing:
                # Procedural thumping and flickering
                # Left (bass/thump): low frequencies
                if i < 10:
                    # Low-frequency thumping: periodic high-amplitude peaks
                    thump = abs(random.uniform(0.3, 1.0) * (30.0 * abs(random.uniform(0.2, 1.0) * (0.6 + 0.4 * (1.0 + (t * 8) % 3.14)))))
                    thump = max(1.5, min(32.0, thump))
                    target = thump if (i % 2 == 0) else thump * 0.6
                # Middle: moderate activity
                elif i < 22:
                    target = random.uniform(3.0, 18.0) + 4.0 * abs(random.uniform(0.1, 1.0) * (t * 5) % 2.0)
                # Right: high-frequency flickering
                else:
                    target = random.uniform(1.5, 12.0) if random.random() > 0.4 else random.uniform(1.5, 28.0)

                # Smooth interpolation
                self.bar_heights[i] = self.bar_heights[i] * 0.5 + target * 0.5
            else:
                # Decay to idle/flat state
                self.bar_heights[i] = max(1.5, self.bar_heights[i] * 0.8 - 0.2)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        bar_w = 6.0
        spacing = 2.5
        total_w = 32 * bar_w + 31 * spacing
        start_x = (self.width() - total_w) / 2.0

        for i in range(32):
            h = self.bar_heights[i]
            x = start_x + i * (bar_w + spacing)
            y = self.height() - h

            rect = QRectF(x, y, bar_w, h)

            # Use semi-transparent white/accent color for liquid-glass style
            color = QColor(255, 255, 255, 160)
            if self.playing:
                # Subtle neon/blue touch for active visualizer
                alpha = int(140 + 80 * (h / 32.0))
                color = QColor(255, 255, 255, min(255, alpha))
            else:
                color = QColor(255, 255, 255, 80)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(rect, 1.5, 1.5)


class CustomSlider(QWidget):
    # Emits position in seconds when seeking
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 16)
        self.setCursor(Qt.PointingHandCursor)

        self.position = 0.0
        self.duration = 0.0
        self.playing = False
        self.dragging = False

        # Internal timer to interpolate track progress smoothly between pollers
        self.interpolator = QTimer(self)
        self.interpolator.timeout.connect(self._interpolate)
        self.interpolator.start(100)

    def set_duration(self, duration):
        self.duration = duration
        self.update()

    def set_position(self, position):
        if not self.dragging:
            self.position = position
            self.update()

    def set_playing(self, playing):
        self.playing = playing

    def _interpolate(self):
        if self.playing and not self.dragging and self.duration > 0:
            new_pos = self.position + 0.1
            if new_pos <= self.duration:
                self.position = new_pos
                self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self._update_val_from_x(event.position().x())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._update_val_from_x(event.position().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.seek_requested.emit(self.position)

    def _update_val_from_x(self, x):
        if self.duration <= 0:
            return
        pct = max(0.0, min(1.0, x / self.width()))
        self.position = pct * self.duration
        self.update()

    def _format_time(self, seconds):
        if seconds < 0:
            seconds = 0
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Track height and dimensions
        track_h = 4.0
        ty = (self.height() - track_h) / 2.0

        # Background track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 45)))
        painter.drawRoundedRect(QRectF(0, ty, self.width(), track_h), 2.0, 2.0)

        # Progress fraction
        pct = 0.0
        if self.duration > 0:
            pct = max(0.0, min(1.0, self.position / self.duration))

        # Filled track
        fill_w = pct * self.width()
        if fill_w > 0:
            painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
            painter.drawRoundedRect(QRectF(0, ty, fill_w, track_h), 2.0, 2.0)

        # Slider Handle (Thumb)
        if pct > 0 or self.dragging:
            hx = pct * self.width()
            hy = self.height() / 2.0
            r = 5.0 if not self.dragging else 7.0
            painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
            painter.drawEllipse(QPointF(hx, hy), r, r)


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


class LiquidCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint() - self.window().pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and (event.buttons() & Qt.LeftButton):
            new_pos = event.globalPosition().toPoint() - self.drag_start_pos
            self.window().move(new_pos)
            if hasattr(self.window(), "manual_pos"):
                self.window().manual_pos = True
                self.window().saved_manual_x = new_pos.x()
                self.window().saved_manual_y = new_pos.y()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if hasattr(self.window(), "toggle_mode"):
                self.window().toggle_mode()
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        path = QPainterPath()
        path.addRoundedRect(rect, 28, 28)

        # Subtle white border (1px width, alpha 30) for improved contrast in the liquid-glass style
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
        self.current_mode = "large"
        self.manual_pos = False
        self.saved_manual_x = 0
        self.saved_manual_y = 0

        self.setFixedSize(PANEL_W, PANEL_H_LARGE)

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
        self.card = LiquidCard(self)
        self.card.setGeometry(0, 0, PANEL_W, PANEL_H_LARGE)

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

        # Create main layouts
        self.main_layout = QVBoxLayout(self.card)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        # Top row layout
        self.top_row_layout = QHBoxLayout()
        self.top_row_layout.setContentsMargins(0, 0, 0, 0)
        self.top_row_layout.setSpacing(14)
        self.top_row_layout.addWidget(self.cover)
        self.top_row_layout.addWidget(text_container, 1)
        self.top_row_layout.addWidget(controls_widget, 0, Qt.AlignVCenter)

        self.main_layout.addLayout(self.top_row_layout)

        # Bottom row components (Visualizer and Slider)
        self.bottom_layout = QVBoxLayout()
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(6)

        self.visualizer = SpectrumVisualizer()
        self.slider = CustomSlider()
        self.slider.seek_requested.connect(lambda pos: self.action_requested.emit("seek", pos))

        self.bottom_layout.addWidget(self.visualizer, 0, Qt.AlignLeft)
        self.bottom_layout.addWidget(self.slider, 0, Qt.AlignLeft)

        self.bottom_container = QWidget()
        self.bottom_container.setLayout(self.bottom_layout)
        self.main_layout.addWidget(self.bottom_container)

        self.main_layout.addStretch(1)

    def resizeEvent(self, event):
        self.card.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

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

        # Geometry animation is configured and run during toggle_mode
        self.geo_anim = QPropertyAnimation(self, b"geometry")

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
        try:
            self.geo_anim.finished.disconnect()
        except Exception:
            pass

        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geo = screen.availableGeometry()

        if self.current_mode == "large":
            target_h = PANEL_H_SMALL
            new_mode = "small"
        else:
            target_h = PANEL_H_LARGE
            new_mode = "large"

        if self.manual_pos:
            target_x = self.x()
            target_y = self.y()
        else:
            target_x = geo.x() + geo.width() // 2 - PANEL_W // 2
            target_y = geo.y() + SHOW_Y_OFFSET

        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(250)
        self.geo_anim.setEasingCurve(QEasingCurve.OutCubic)

        start_rect = QRect(self.x(), self.y(), PANEL_W, self.height())
        end_rect = QRect(target_x, target_y, PANEL_W, target_h)

        self.geo_anim.setStartValue(start_rect)
        self.geo_anim.setEndValue(end_rect)

        self.setMinimumSize(PANEL_W, min(start_rect.height(), target_h))
        self.setMaximumSize(PANEL_W, max(start_rect.height(), target_h))

        if new_mode == "large":
            self.cover.show()
            self.visualizer.show()
            self.slider.show()
            self.main_layout.setContentsMargins(16, 16, 16, 16)
            self.main_layout.setSpacing(12)
        else:
            self.main_layout.setContentsMargins(16, 0, 16, 0)
            self.main_layout.setSpacing(0)

        def on_anim_finished():
            self.current_mode = new_mode
            self.setFixedSize(PANEL_W, target_h)
            if new_mode == "small":
                self.cover.hide()
                self.visualizer.hide()
                self.slider.hide()

        self.geo_anim.finished.connect(on_anim_finished)
        self.geo_anim.start()

    def update_media(self, data: dict):
        playing = data.get("playing", False)
        self.visualizer.set_playing(playing)
        self.slider.set_playing(playing)

        self.slider.set_duration(data.get("duration", 0.0))
        self.slider.set_position(data.get("position", 0.0))

        self.play_btn.set_icon("pause" if playing else "play")

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

    def _elide(self, text, label, width):
        metrics = label.fontMetrics()
        return metrics.elidedText(text, Qt.ElideRight, width)

    def reposition(self, hidden=False):
        if self.manual_pos:
            if hidden:
                self.move(self.x(), -5000)
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

        near_trigger = (
            geo.y() <= cursor.y() <= geo.y() + TRIGGER_Y
            and abs(cursor.x() - center_x) <= TRIGGER_WIDTH // 2
        )

        inside_panel = self.frameGeometry().contains(cursor)
        now = time.time()

        if near_trigger or inside_panel:
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
            target_x = self.x()
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