import sys
import os
import unittest
import time
from unittest.mock import MagicMock

# Set headless PySide6 platform before importing modules
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QCoreApplication, QEvent
from PySide6.QtGui import QMouseEvent

# Import the PyW module dynamically or load via source loader since it is a .pyw file
import importlib.machinery

loader = importlib.machinery.SourceFileLoader("yandex_panel", "yandex-liquid-panel.pyw")
panel_module = loader.load_module()

class TestYandexLiquidPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create single QApplication instance
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = panel_module.LiquidMusicPanel()
        # Disable background hover timer so it doesn't close or reposition during testing
        self.panel.hover_timer.stop()

    def tearDown(self):
        self.panel.close()

    def test_dimensions_initial(self):
        # Starts with large mode and height 160
        self.assertEqual(self.panel.width(), panel_module.PANEL_W)
        self.assertEqual(self.panel.height(), panel_module.PANEL_H_LARGE)
        self.assertTrue(self.panel.cover.isVisible())
        self.assertTrue(self.panel.right_column_container.isVisible())

    def test_toggle_mode(self):
        # Toggle mode shrinks panel
        self.panel.toggle_mode()
        # Run event loop for 0.5s to let animation finish
        start = time.time()
        while time.time() - start < 0.5:
            self.app.processEvents()

        self.assertFalse(self.panel.is_large_mode)
        self.assertEqual(self.panel.height(), panel_module.PANEL_H_SMALL)
        self.assertFalse(self.panel.cover.isVisible())
        self.assertFalse(self.panel.right_column_container.isVisible())

        # Toggle back to Large
        self.panel.toggle_mode()
        start = time.time()
        while time.time() - start < 0.5:
            self.app.processEvents()

        self.assertTrue(self.panel.is_large_mode)
        self.assertEqual(self.panel.height(), panel_module.PANEL_H_LARGE)
        self.assertTrue(self.panel.cover.isVisible())
        self.assertTrue(self.panel.right_column_container.isVisible())

    def test_drag_and_manual_positioning(self):
        self.assertFalse(self.panel.manual_pos)

        # Simulate drag press/move/release on Card
        card = self.panel.card
        initial_pos = self.panel.pos()

        # Press mouse
        press_event = QMouseEvent(
            QEvent.MouseButtonPress,
            QPoint(10, 10),
            QPoint(10, 10),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier
        )
        self.app.sendEvent(card, press_event)

        # Move mouse
        move_event = QMouseEvent(
            QEvent.MouseMove,
            QPoint(50, 50),
            QPoint(50, 50),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier
        )
        self.app.sendEvent(card, move_event)

        # Release mouse
        release_event = QMouseEvent(
            QEvent.MouseButtonRelease,
            QPoint(50, 50),
            QPoint(50, 50),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier
        )
        self.app.sendEvent(card, release_event)

        self.assertTrue(self.panel.manual_pos)
        self.assertNotEqual(self.panel.pos(), initial_pos)
        self.assertEqual(self.panel.saved_manual_x, self.panel.pos().x())
        self.assertEqual(self.panel.saved_manual_y, self.panel.pos().y())

    def test_custom_slider_emits_seek(self):
        emitted_signals = []
        def on_action(action_tuple):
            emitted_signals.append(action_tuple)

        self.panel.action_requested.connect(on_action)

        # Set slider details
        self.panel.slider.set_timeline(10.0, 100.0)
        self.assertEqual(self.panel.slider.position, 10.0)
        self.assertEqual(self.panel.slider.duration, 100.0)

        # Mouse click seek on slider
        slider = self.panel.slider
        press_event = QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(135.0, 8.0), # Center of 270 width is ratio 0.5 (50.0 seconds)
            QPointF(135.0, 8.0),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier
        )
        self.app.sendEvent(slider, press_event)

        release_event = QMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(135.0, 8.0),
            QPointF(135.0, 8.0),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier
        )
        self.app.sendEvent(slider, release_event)

        self.assertEqual(len(emitted_signals), 1)
        action, value = emitted_signals[0]
        self.assertEqual(action, "seek")
        self.assertAlmostEqual(value, 50.0, places=1)


if __name__ == "__main__":
    unittest.main()
