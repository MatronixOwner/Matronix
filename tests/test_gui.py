"""Headless smoke test. CI on Windows provides the required Qt runtime."""
import os
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtTest import QTest
    from matronix.app import Window
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


@unittest.skipUnless(GUI_AVAILABLE, 'Qt or its system libraries are unavailable')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_edit_save_and_export(self):
        w = Window()
        try:
            from matronix.theme import STYLE
            self.app.setStyleSheet(STYLE)
            w.show()
            self.app.processEvents()
            self.assertFalse(w.dirty)
            self.assertGreaterEqual(w.online_button.width(), 100)
            QTest.mouseClick(w.canvas, Qt.LeftButton, pos=QPoint(w.canvas.width()//2, w.canvas.height()//2))
            self.assertTrue(w.dirty)
            self.assertIn('block/stone', w.project.textures)
            self.assertTrue(any(p[3] for p in w.canvas.data['pixels']))
            w.canvas.undo()
            self.assertFalse(any(p[3] for p in w.canvas.data['pixels']))
            w.canvas.redo()
            self.assertTrue(any(p[3] for p in w.canvas.data['pixels']))
            w.list.setCurrentRow(1)
            self.assertFalse(any(p[3] for p in w.canvas.data['pixels']))
            w.list.setCurrentRow(0)
            self.assertTrue(any(p[3] for p in w.canvas.data['pixels']))
            with tempfile.TemporaryDirectory() as tmp:
                w.path = str(Path(tmp) / 'test.matronix')
                self.assertTrue(w.save())
                w.project.export(Path(tmp) / 'test.zip')
                self.assertTrue((Path(tmp) / 'test.zip').exists())
            # Originals appear immediately, but are exported only after an edit.
            from zipfile import ZipFile
            from matronix.core import Project, blank, png_bytes
            with tempfile.TemporaryDirectory() as tmp:
                jar = Path(tmp)/'client.jar'
                original = blank()
                original['pixels'][0] = [255, 0, 0, 255]
                with ZipFile(jar, 'w') as archive:
                    archive.writestr('version.json', '{"id":"26.2"}')
                    archive.writestr('assets/minecraft/textures/block/stone.png', png_bytes(original))
                w.install_project(Project(version='26.2'), None)
                w.attach_source(str(jar))
                self.assertEqual(w.canvas.data['pixels'][0], [255,0,0,255])
                self.assertFalse(w.project.textures)
                self.assertFalse(w.dirty)
                QTest.mouseClick(w.canvas, Qt.LeftButton, pos=QPoint(w.canvas.width()//2, w.canvas.height()//2))
                self.assertEqual(w.project.textures['block/stone']['pixels'][0], [255,0,0,255])
        finally:
            w.dirty = False
            w.close()
