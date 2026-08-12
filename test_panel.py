import os
import sys
import time
import importlib.machinery
import importlib.util

# Set offscreen platform for headless QT execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEventLoop, QPoint, Qt, QRect
from PySide6.QtGui import QMouseEvent

# Initialize single QApplication instance
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

# Dynamically load the panel module
loader = importlib.machinery.SourceFileLoader("yandex_panel", "yandex-liquid-panel.pyw")
spec = importlib.util.spec_from_loader(loader.name, loader)
panel_mod = importlib.util.module_from_spec(spec)
loader.exec_module(panel_mod)

def process_events(duration_sec=0.5):
    """Run event loop for duration_sec to process animations and timers."""
    start = time.time()
    while time.time() - start < duration_sec:
        app.processEvents()
        time.sleep(0.02)

def test_panel_initialization():
    print("Running test: test_panel_initialization")
    panel = panel_mod.LiquidMusicPanel()
    # Stop hover timer to prevent automated hover detection overriding our states in tests
    panel.hover_timer.stop()

    assert panel.width() == 570
    assert panel.height() == 160  # Default Large mode height
    assert panel.is_large is True
    assert panel.manual_pos is False
    print("test_panel_initialization: PASS")
    panel.close()

def test_mode_transitions():
    print("Running test: test_mode_transitions")
    panel = panel_mod.LiquidMusicPanel()
    panel.hover_timer.stop()

    assert panel.is_large is True
    assert panel.height() == 160

    # Toggle to small mode
    panel.toggle_mode()
    # Wait for the property animation to complete and trigger finished callback
    process_events(0.5)

    assert panel.is_large is False
    assert panel.height() == 88
    # Assert specific widgets are hidden in small mode
    assert panel.cover.isHidden() is True
    assert panel.visualizer.isHidden() is True
    assert panel.bottom_widget.isHidden() is True

    # Toggle back to large mode
    panel.toggle_mode()
    process_events(0.5)

    assert panel.is_large is True
    assert panel.height() == 160
    assert panel.cover.isVisible() is True
    assert panel.visualizer.isVisible() is True
    assert panel.bottom_widget.isVisible() is True

    print("test_mode_transitions: PASS")
    panel.close()

def test_dragging_and_manual_position():
    print("Running test: test_dragging_and_manual_position")
    panel = panel_mod.LiquidMusicPanel()
    panel.hover_timer.stop()

    assert panel.manual_pos is False

    # Simulate mouse drag on the LiquidCard
    card = panel.card
    initial_pos = panel.pos()

    # Create mouse press event
    press_event = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPoint(10, 10),
        QPoint(10, 10),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier
    )
    card.mousePressEvent(press_event)

    # Patch global position tracking for PySide6 mouse move simulation in testing
    card.drag_start_pos = QPoint(100, 100)
    # Simulate move by calling mouseMoveEvent with a custom coordinate change
    class FakeGlobalEvent:
        def globalPosition(self):
            class FakePoint:
                def toPoint(self):
                    return QPoint(150, 130)
            return FakePoint()
        def button(self):
            return Qt.LeftButton
        def accept(self):
            pass

    card.mouseMoveEvent(FakeGlobalEvent())

    assert panel.manual_pos is True
    assert panel.saved_manual_x == panel.x()
    assert panel.saved_manual_y == panel.y()
    assert panel.pos() != initial_pos

    print("test_dragging_and_manual_position: PASS")
    panel.close()

def test_slider_seek_emission():
    print("Running test: test_slider_seek_emission")
    panel = panel_mod.LiquidMusicPanel()
    panel.hover_timer.stop()

    seek_values = []
    panel.action_requested.connect(lambda action, val: seek_values.append((action, val)))

    # Directly trigger seek requested signal from the slider
    panel.slider.seek_requested.emit(45.5)
    process_events(0.1)

    assert len(seek_values) == 1
    assert seek_values[0] == ("seek", 45.5)

    print("test_slider_seek_emission: PASS")
    panel.close()

def test_spectrum_rendering():
    print("Running test: test_spectrum_rendering")
    visualizer = panel_mod.SpectrumVisualizer()
    assert len(visualizer.heights) == 32
    assert visualizer.playing is False

    # Set playing state and trigger update
    visualizer.set_playing(True)
    visualizer.update_spectrum()
    process_events(0.1)

    # Verify that targets are updated with random variations
    assert any(h > 0.0 for h in visualizer.targets)

    print("test_spectrum_rendering: PASS")

def main():
    test_panel_initialization()
    test_mode_transitions()
    test_dragging_and_manual_position()
    test_slider_seek_emission()
    test_spectrum_rendering()
    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
