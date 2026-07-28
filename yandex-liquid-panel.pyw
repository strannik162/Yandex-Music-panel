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
    QRect,
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


def format_time(seconds: float) -> str:
    if seconds < 0 or seconds is None:
        seconds = 0
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes}:{secs:02d}"


class SpectrumVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 32)
        self.bars_count = 32
        self.heights = [2.0] * self.bars_count
        self.targets = [2.0] * self.bars_count
        self.playing = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_bars)
        self.timer.start(50)

    def set_playing(self, playing: bool):
        self.playing = playing

    def update_bars(self):
        for i in range(self.bars_count):
            if self.playing:
                if i < 8:
                    max_val = random.uniform(15, 30)
                elif i < 20:
                    max_val = random.uniform(8, 22)
                else:
                    max_val = random.uniform(4, 14)
                self.targets[i] = max_val
            else:
                self.targets[i] = 2.0

            diff = self.targets[i] - self.heights[i]
            self.heights[i] += diff * 0.25
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        spacing = 2
        bar_w = (w - (self.bars_count - 1) * spacing) / self.bars_count

        for i in range(self.bars_count):
            bar_h = max(2.0, min(self.heights[i], float(h)))
            x = i * (bar_w + spacing)
            y = h - bar_h

            rect = QRectF(x, y, bar_w, bar_h)
            path = QPainterPath()
            path.addRoundedRect(rect, 1.5, 1.5)

            grad_color = QColor(42, 112, 255, 200)
            if i > 20:
                grad_color = QColor(255, 42, 112, 200)
            elif i > 10:
                grad_color = QColor(42, 212, 255, 200)

            painter.fillPath(path, QBrush(grad_color))


class CustomSlider(QWidget):
    slider_moved = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 20)
        self.value = 0.0
        self.max_value = 1.0
        self.dragging = False
        self.playing = False

        self.last_update_time = time.time()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._interpolate_position)
        self.timer.start(100)

    def set_playing(self, playing: bool):
        self.playing = playing
        self.last_update_time = time.time()

    def set_range(self, val: float, max_val: float):
        if not self.dragging:
            self.value = val
            self.max_value = max_val if max_val > 0 else 1.0
            self.last_update_time = time.time()
            self.update()

    def _interpolate_position(self):
        if self.playing and not self.dragging and self.value < self.max_value:
            now = time.time()
            dt = now - self.last_update_time
            self.last_update_time = now
            self.value = min(self.value + dt, self.max_value)
            self.update()
        else:
            self.last_update_time = time.time()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self._update_val_from_pos(event.position().x())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._update_val_from_pos(event.position().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.slider_moved.emit(self.value)
            self.last_update_time = time.time()

    def _update_val_from_pos(self, x):
        ratio = max(0.0, min(x / self.width(), 1.0))
        self.value = ratio * self.max_value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        h = self.height()
        w = self.width()

        track_h = 4
        track_y = (h - track_h) / 2

        track_rect = QRectF(0, track_y, w, track_h)
        path = QPainterPath()
        path.addRoundedRect(track_rect, 2, 2)
        painter.fillPath(path, QColor(255, 255, 255, 45))

        ratio = self.value / self.max_value if self.max_value > 0 else 0.0
        fill_w = ratio * w

        if fill_w > 0:
            fill_rect = QRectF(0, track_y, fill_w, track_h)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, 2, 2)
            painter.fillPath(fill_path, QColor(42, 112, 255, 220))

        handle_x = ratio * w
        handle_r = 6
        handle_rect = QRectF(handle_x - handle_r, (h / 2) - handle_r, handle_r * 2, handle_r * 2)
        handle_path = QPainterPath()
        handle_path.addEllipse(handle_rect)
        painter.fillPath(handle_path, QColor(255, 255, 255, 255))


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
                "pos": 0.0,
                "dur": 0.0,
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

    def command(self, action: str, val: object = None):
        if not self.loop:
            return

        try:
            asyncio.run_coroutine_threadsafe(self._control(action, val), self.loop)
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
                "pos": 0.0,
                "dur": 0.0,
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
                "pos": 0.0,
                "dur": 0.0,
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

            metadata_changed = (signature != self.last_signature)
            if metadata_changed:
                self.last_signature = signature

            data["metadata_changed"] = metadata_changed
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
                    "pos": 0.0,
                    "dur": 0.0,
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

            pos = 0.0
            dur = 0.0
            try:
                timeline = session.get_timeline_properties()
                if timeline:
                    # Windows SMTC provides timeline properties in 100-nanosecond units (ticks) or standard timedelta
                    pos_val = timeline.position
                    dur_val = timeline.end_time - timeline.start_time

                    if hasattr(pos_val, "total_seconds"):
                        pos = pos_val.total_seconds()
                    elif hasattr(pos_val, "duration"):
                        pos = pos_val.duration / 10000000.0
                    else:
                        pos = float(pos_val) / 10000000.0

                    if hasattr(dur_val, "total_seconds"):
                        dur = dur_val.total_seconds()
                    elif hasattr(dur_val, "duration"):
                        dur = dur_val.duration / 10000000.0
                    else:
                        dur = float(dur_val) / 10000000.0
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
                "pos": pos,
                "dur": dur,
            }

        except Exception as e:
            return {
                "title": "Ошибка чтения Яндекс Музыки",
                "artist": str(e),
                "album": "",
                "app": "",
                "playing": False,
                "cover": None,
                "pos": 0.0,
                "dur": 0.0,
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

    async def _control(self, action: str, val: object = None):
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

            elif action == "seek" and val is not None:
                try:
                    target_pos = timedelta(seconds=float(val))
                    await session.try_change_playback_position_async(target_pos)
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
            self.window().move(event.globalPosition().toPoint() - self.drag_start_pos)
            self.window().manual_pos = True
            # Cache the coordinates for manual mode window repositioning
            self.window().saved_manual_x = self.window().pos().x()
            self.window().saved_manual_y = self.window().pos().y()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window().toggle_mode()
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        path = QPainterPath()
        path.addRoundedRect(rect, 28, 28)

        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(CARD_BG_QCOLOR)
        painter.drawPath(path)


class LiquidMusicPanel(QWidget):
    action_requested = Signal(str, object)

    def __init__(self):
        super().__init__()

        self.visible_panel = False
        self.pinned = False
        self.last_hot_time = 0

        self.is_large_mode = True
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
        super().resizeEvent(event)
        self.card.setGeometry(0, 0, self.width(), self.height())

    def _build_ui(self):
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

        # Upper row containing cover, text, and playback controls
        upper_row_layout = QHBoxLayout()
        upper_row_layout.setContentsMargins(0, 0, 0, 0)
        upper_row_layout.setSpacing(14)
        upper_row_layout.addWidget(self.cover)
        upper_row_layout.addWidget(text_container, 1)
        upper_row_layout.addWidget(controls_widget, 0, Qt.AlignVCenter)

        upper_row_widget = QWidget()
        upper_row_widget.setLayout(upper_row_layout)

        # Lower row widgets
        self.visualizer = SpectrumVisualizer()

        self.slider = CustomSlider()
        self.slider.slider_moved.connect(lambda val: self.action_requested.emit("seek", val))

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setFont(QFont("Segoe UI", 8))
        self.time_label.setStyleSheet("color: rgba(255,255,255,140); background: transparent;")
        self.time_label.setFixedWidth(70)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lower_row_layout = QHBoxLayout()
        lower_row_layout.setContentsMargins(0, 0, 0, 0)
        lower_row_layout.setSpacing(10)
        lower_row_layout.addWidget(self.visualizer)
        lower_row_layout.addWidget(self.slider)
        lower_row_layout.addWidget(self.time_label)

        self.lower_row_widget = QWidget()
        self.lower_row_widget.setLayout(lower_row_layout)

        # Base layout with layout stretch optimization
        self.base_layout = QVBoxLayout(self.card)
        self.base_layout.setContentsMargins(16, 16, 16, 16)
        self.base_layout.setSpacing(12)
        self.base_layout.addWidget(upper_row_widget)
        self.base_layout.addWidget(self.lower_row_widget)
        self.base_layout.addStretch(1)

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

        # Height expansion animation config
        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(250)
        self.geo_anim.setEasingCurve(QEasingCurve.OutCubic)

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
        self.anim_group.stop()
        self.geo_anim.stop()

        # Safely disconnect any previously bound finished callbacks to prevent snapping/flickers
        try:
            self.geo_anim.finished.disconnect()
        except Exception:
            pass

        self.is_large_mode = not self.is_large_mode

        # Calculate coordinates ensuring window remains centered when changing heights
        curr_rect = self.geometry()
        target_h = PANEL_H_LARGE if self.is_large_mode else PANEL_H_SMALL

        if not self.manual_pos:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            target_x = geo.x() + geo.width() // 2 - PANEL_W // 2
            target_y = geo.y() + SHOW_Y_OFFSET if self.visible_panel else geo.y() - target_h - 6
        else:
            target_x = curr_rect.x()
            target_y = curr_rect.y()

        start_rect = QRect(curr_rect.x(), curr_rect.y(), PANEL_W, curr_rect.height())
        end_rect = QRect(target_x, target_y, PANEL_W, target_h)

        # Pre-expansion layout optimizations to prevent layout snaps/glitches
        if self.is_large_mode:
            self.setMinimumHeight(0)
            self.setMaximumHeight(2000)
            self.lower_row_widget.setVisible(True)
            self.base_layout.setContentsMargins(16, 16, 16, 16)
            self.base_layout.setSpacing(12)

        self.geo_anim.setStartValue(start_rect)
        self.geo_anim.setEndValue(end_rect)

        def on_anim_finished():
            self.setFixedSize(PANEL_W, target_h)
            if not self.is_large_mode:
                self.lower_row_widget.setVisible(False)
            self._refresh_topmost()

        self.geo_anim.finished.connect(on_anim_finished)

        # Shrinking mode adjustments
        if not self.is_large_mode:
            self.setMinimumHeight(0)
            self.setMaximumHeight(2000)
            self.base_layout.setContentsMargins(16, 10, 16, 10)
            self.base_layout.setSpacing(0)

        self.geo_anim.start()

    def update_media(self, data: dict):
        playing = data.get("playing", False)
        self.visualizer.set_playing(playing)
        self.slider.set_playing(playing)

        # Skip UI updates when details are identical
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

        # Explicitly keep play state synchronized independent of track change boundaries
        self.play_btn.set_icon("pause" if playing else "play")

        pos = data.get("pos", 0.0)
        dur = data.get("dur", 0.0)
        self.slider.set_range(pos, dur)

        self.time_label.setText(f"{format_time(pos)} / {format_time(dur)}")

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
            # Shift panel instantly to position to prevent long slide from off-screen
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
            self._animate_to(self.saved_manual_x, -5000, 0.0)
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