import os
import sys
import time
from importlib.machinery import SourceFileLoader

# Set offscreen platform before importing PySide6
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt

def test_panel_behavior():
    app = QApplication.instance() or QApplication(sys.argv)

    # Load yandex-liquid-panel.pyw dynamically
    module = SourceFileLoader("yandex_liquid_panel", "yandex-liquid-panel.pyw").load_module()

    # Create the panel
    panel = module.LiquidMusicPanel()
    # Stop background timers to prevent them from interfering with manual checks
    panel.hover_timer.stop()

    assert panel.is_large_mode is True
    assert panel.height() == module.PANEL_H_LARGE

    # Toggle mode to Small mode
    panel.toggle_mode()

    # Run the event loop briefly for the QPropertyAnimation to trigger callbacks
    start_time = time.time()
    while time.time() - start_time < 0.5:
        app.processEvents()
        time.sleep(0.02)

    assert panel.is_large_mode is False
    assert panel.height() == module.PANEL_H_SMALL
    assert panel.bottom_widget.isHidden() is True

    # Toggle mode back to Large mode
    panel.toggle_mode()
    start_time = time.time()
    while time.time() - start_time < 0.5:
        app.processEvents()
        time.sleep(0.02)

    assert panel.is_large_mode is True
    assert panel.height() == module.PANEL_H_LARGE
    assert panel.bottom_widget.isVisible() is True

    # Test seek slider emission
    emitted = []
    panel.action_requested.connect(lambda action, value: emitted.append((action, value)))

    # Click on seek slider
    slider = panel.slider
    # Mocking mouse event or direct emission triggering
    slider.seek_requested.emit(123.45)
    assert len(emitted) == 1
    assert emitted[0] == ("seek", 123.45)

    print("All tests passed successfully!")

if __name__ == "__main__":
    test_panel_behavior()
