import sys
import os
import time
from importlib.machinery import SourceFileLoader

# Force offscreen QPA platform for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Load the pyw module
panel_module = SourceFileLoader("yandex_liquid_panel", "yandex-liquid-panel.pyw").load_module()

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtWidgets import QApplication

def run_event_loop(seconds=0.5):
    app = QApplication.instance() or QApplication(sys.argv)
    start_time = time.time()
    while time.time() - start_time < seconds:
        app.processEvents()
        time.sleep(0.01)

def test_panel_behavior():
    app = QApplication.instance() or QApplication(sys.argv)

    # Initialize the panel
    panel = panel_module.LiquidMusicPanel()

    # Stop the hover timer so automated hover checks don't interfere with our assertions
    if hasattr(panel, "hover_timer") and panel.hover_timer.isActive():
        panel.hover_timer.stop()

    # Verify default state
    assert panel.is_large is True, "Should initialize in Large mode"
    assert panel.height() == panel_module.PANEL_H_LARGE, "Should have PANEL_H_LARGE height"
    assert panel.cover.isVisible() is True, "Cover should be visible in Large mode"
    assert panel.visualizer.isVisible() is True, "Visualizer should be visible in Large mode"
    assert panel.slider.isVisible() is True, "Slider should be visible in Large mode"

    # Let's mock a mouse event class with needed methods for PySide6 compatibility
    class MockMouseEvent:
        def __init__(self, button, local_pos, global_pos):
            self._button = button
            self._local_pos = local_pos
            self._global_pos = global_pos

        def button(self):
            return self._button

        def globalPosition(self):
            class Pos:
                def __init__(self, p):
                    self._p = p
                def toPoint(self):
                    return self._p
            return Pos(self._global_pos)

        def accept(self):
            pass

    # 1. Test Mode Toggle: Large -> Small
    dbl_click_event = MockMouseEvent(Qt.LeftButton, QPoint(20, 20), QPoint(120, 120))
    panel.card.mouseDoubleClickEvent(dbl_click_event) # Simulating double click on card
    run_event_loop(0.5) # Allow animations to complete

    assert panel.is_large is False, "Should be in Small mode after double click"
    assert panel.height() == panel_module.PANEL_H_SMALL, f"Should have height PANEL_H_SMALL, got {panel.height()}"
    assert panel.cover.isHidden() is True, "Cover should be hidden in Small mode"
    assert panel.visualizer.isHidden() is True, "Visualizer should be hidden in Small mode"
    assert panel.slider.isHidden() is True, "Slider should be hidden in Small mode"

    # Test Mode Toggle: Small -> Large
    panel.card.mouseDoubleClickEvent(dbl_click_event)
    run_event_loop(0.5)

    assert panel.is_large is True, "Should be back in Large mode after another double click"
    assert panel.height() == panel_module.PANEL_H_LARGE, "Should have PANEL_H_LARGE height"
    assert panel.cover.isVisible() is True, "Cover should be visible in Large mode again"
    assert panel.visualizer.isVisible() is True, "Visualizer should be visible in Large mode again"
    assert panel.slider.isVisible() is True, "Slider should be visible in Large mode again"

    # 2. Test Window Dragging (Manual Positioning)
    # Position panel at (100, 100) initially
    panel.move(100, 100)

    # Mouse press on card at global (120, 120)
    press_event = MockMouseEvent(Qt.LeftButton, QPoint(20, 20), QPoint(120, 120))
    panel.card.mousePressEvent(press_event)

    # Mouse drag to global (150, 180) -> panel moves to new position (130, 160)
    move_event = MockMouseEvent(Qt.LeftButton, QPoint(50, 80), QPoint(150, 180))
    panel.card.mouseMoveEvent(move_event)

    # Release drag
    release_event = MockMouseEvent(Qt.LeftButton, QPoint(50, 80), QPoint(150, 180))
    panel.card.mouseReleaseEvent(release_event)

    assert panel.manual_pos is True, "manual_pos flag must be True after dragging"
    assert panel.saved_manual_x == 130, f"Expected saved_manual_x to be 130, got {panel.saved_manual_x}"
    assert panel.saved_manual_y == 160, f"Expected saved_manual_y to be 160, got {panel.saved_manual_y}"
    assert panel.pos() == QPoint(130, 160), f"Expected panel to move to (130, 160), got {panel.pos()}"

    # 3. Test Slider Seek Emission
    emitted_seek = []

    panel.action_requested.connect(lambda action, val: emitted_seek.append((action, val)))

    # Force some duration on the slider
    panel.slider.set_media_state(0.0, 100.0, False)

    # Mock mouse click on the slider
    # Let's calculate: margin is 42. Total width is 240. track_w = 240 - 84 = 156.
    # If we click at x = 120 (exactly the center of slider/track), ratio is (120 - 42) / 156 = 78 / 156 = 0.5.
    # Position should be 0.5 * 100.0 = 50.0.
    class MockSliderMouseEvent:
        def __init__(self, pos_x):
            self._pos_x = pos_x
        def position(self):
            class Pos:
                def __init__(self, x):
                    self._x = x
                def x(self):
                    return self._x
            return Pos(self._pos_x)
        def accept(self):
            pass

    press_slider = MockSliderMouseEvent(120.0)
    panel.slider.mousePressEvent(press_slider)
    panel.slider.mouseReleaseEvent(press_slider)

    assert len(emitted_seek) == 1, "Should have emitted seek action once"
    assert emitted_seek[0] == ("seek", 50.0), f"Expected seek value to be 50.0, got {emitted_seek[0]}"

    # 4. Test Panel Pinning
    assert panel.pinned is False, "Panel should not be pinned initially"
    panel._toggle_pin()
    assert panel.pinned is True, "Panel should be pinned after toggle_pin()"
    assert panel.pin_btn.accent is True, "Pin button accent should be True when pinned"

    # Ensure show_panel was triggered when pinning
    assert panel.visible_panel is True, "Panel should be visible when pinned"

    # Calling _check_hover when unhovered should not hide panel when pinned
    panel.last_hot_time = time.time() - 10.0  # simulate old hot time
    panel._check_hover()
    assert panel.visible_panel is True, "Panel should remain visible after check_hover when pinned"

    # Unpin
    panel._toggle_pin()
    assert panel.pinned is False, "Panel should be unpinned after toggling again"
    assert panel.pin_btn.accent is False, "Pin button accent should be False when unpinned"

    print("All tests passed successfully!")

if __name__ == "__main__":
    test_panel_behavior()
