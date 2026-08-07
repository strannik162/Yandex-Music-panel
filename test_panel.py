import sys
import os
import time
from PySide6.QtCore import QCoreApplication, QEventLoop, QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
import importlib.machinery

# Load the pyw module
loader = importlib.machinery.SourceFileLoader("panel_module", "yandex-liquid-panel.pyw")
panel_module = loader.load_module()

def run_events(duration=0.5):
    start = time.time()
    while time.time() - start < duration:
        QApplication.processEvents()
        time.sleep(0.01)

def test_all():
    app = QApplication.instance() or QApplication(sys.argv)

    panel = panel_module.LiquidMusicPanel()
    # Stop hover timer to avoid automated interference during assertions
    panel.hover_timer.stop()

    # 1. Test Initial Dimensions & Mode
    assert panel.is_large_mode is True
    assert panel.height() == panel_module.PANEL_H_LARGE
    assert panel.width() == panel_module.PANEL_W

    # 2. Test Double Click Toggle Mode (Large -> Small)
    panel.toggle_mode()
    run_events(0.6) # Allow QPropertyAnimation on geometry to finish
    assert panel.is_large_mode is False
    assert panel.height() == panel_module.PANEL_H_SMALL
    assert panel.cover.isHidden() is True
    assert panel.bottom_widget.isHidden() is True

    # 3. Test Double Click Toggle Mode (Small -> Large)
    panel.toggle_mode()
    run_events(0.6)
    assert panel.is_large_mode is True
    assert panel.height() == panel_module.PANEL_H_LARGE
    assert panel.cover.isVisible() is True
    assert panel.bottom_widget.isVisible() is True

    # 4. Test dragging logic in LiquidCard
    # Dragging card updates manual_pos and saves coordinates
    card = panel.card
    assert panel.manual_pos is False

    # Simulate mouse press
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPoint(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    card.mousePressEvent(press_event)
    assert card.drag_start_pos is not None

    # Simulate mouse move
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPoint(60, 60),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    card.mouseMoveEvent(move_event)
    assert panel.manual_pos is True
    assert panel.saved_manual_x != 0

    # Simulate mouse release
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPoint(60, 60),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    card.mouseReleaseEvent(release_event)
    assert card.drag_start_pos is None

    # 5. Test Media Update and Slider state
    data = {
        "title": "Test Title",
        "artist": "Test Artist",
        "app": "Test App",
        "playing": True,
        "cover": None,
        "position": 10.0,
        "duration": 180.0,
        "metadata_changed": True
    }
    panel.update_media(data)
    assert panel.title.text() == "Test Title"
    assert panel.artist.text() == "Test Artist"
    assert panel.visualizer.playing is True
    assert panel.slider.position == 10.0
    assert panel.slider.duration == 180.0

    # 6. Test Slider Seek Request
    signals_received = []
    panel.action_requested.connect(lambda action, val: signals_received.append((action, val)))
    panel.slider.seek_requested.emit(45.0)
    assert len(signals_received) == 1
    assert signals_received[0] == ("seek", 45.0)

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()
