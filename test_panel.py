import sys
import os
import time
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt, QRect

# Ensure offscreen platform is configured
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Create a single QApplication instance for tests if not already created
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

import importlib.machinery
import importlib.util

loader = importlib.machinery.SourceFileLoader('yandex_liquid_panel', 'yandex-liquid-panel.pyw')
spec = importlib.util.spec_from_loader(loader.name, loader)
panel_mod = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = panel_mod
loader.exec_module(panel_mod)


class TestYandexLiquidPanel(unittest.TestCase):
    def setUp(self):
        self.panel = panel_mod.LiquidMusicPanel()
        # Stop background hover detection to prevent interference with tests
        if hasattr(self.panel, "hover_timer"):
            self.panel.hover_timer.stop()

    def tearDown(self):
        self.panel.close()

    def test_default_sizes_and_modes(self):
        # Default mode should be Large with 160 height
        self.assertEqual(self.panel.height(), panel_mod.PANEL_H_LARGE)
        self.assertEqual(self.panel.width(), panel_mod.PANEL_W)
        self.assertFalse(self.panel.cover.isHidden())
        self.assertFalse(self.panel.visualizer.isHidden())
        self.assertFalse(self.panel.slider.isHidden())

    def test_toggle_mode(self):
        # Initially Large
        self.assertEqual(self.panel.height(), panel_mod.PANEL_H_LARGE)

        # Trigger mode toggle to Small
        self.panel.toggle_mode()

        # Run event loop for 0.5s to let animations run and trigger their finished slot
        start = time.time()
        while time.time() - start < 0.5:
            app.processEvents()
            time.sleep(0.01)

        # In Small mode, elements must be hidden, and height should be PANEL_H_SMALL
        self.assertEqual(self.panel.height(), panel_mod.PANEL_H_SMALL)
        self.assertTrue(self.panel.cover.isHidden())
        self.assertTrue(self.panel.visualizer.isHidden())
        self.assertTrue(self.panel.slider.isHidden())

        # Trigger mode toggle back to Large
        self.panel.toggle_mode()

        # Run event loop for 0.5s
        start = time.time()
        while time.time() - start < 0.5:
            app.processEvents()
            time.sleep(0.01)

        self.assertEqual(self.panel.height(), panel_mod.PANEL_H_LARGE)
        self.assertFalse(self.panel.cover.isHidden())
        self.assertFalse(self.panel.visualizer.isHidden())
        self.assertFalse(self.panel.slider.isHidden())

    def test_dragging_behavior(self):
        # Dragging on LiquidCard
        self.assertFalse(self.panel.manual_pos)

        # Simulate drag start
        self.panel.card.drag_started.emit(QPoint(100, 100))
        # Simulate dragging by 50px right and 30px down
        self.panel.card.dragged.emit(QPoint(50, 30))

        # Verify manual_pos flag and coordinate changes
        self.assertTrue(self.panel.manual_pos)
        self.assertEqual(self.panel.saved_manual_x, self.panel.pos().x())
        self.assertEqual(self.panel.saved_manual_y, self.panel.pos().y())

    def test_seek_slider_emission(self):
        # Monitor signals emitted from panel
        emitted_signals = []
        self.panel.action_requested.connect(lambda action, value: emitted_signals.append((action, value)))

        # Simulate seek requested
        self.panel.slider.seek_requested.emit(123.45)

        # Verify correct signal payload
        self.assertIn(("seek", 123.45), emitted_signals)


if __name__ == "__main__":
    unittest.main()
