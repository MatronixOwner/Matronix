import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from matronix.core import Project, blank, png_bytes


class CoreTests(unittest.TestCase):
    def test_project_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.matronix'
            p = Project('Тест', 'Привет')
            p.textures['block/stone'] = blank()
            p.save(path)
            loaded = Project.load(path)
            self.assertEqual(loaded.name, 'Тест')
            self.assertEqual(loaded.textures, p.textures)

    def test_pack_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pack.zip'
            p = Project()
            p.textures['item/diamond'] = blank(32)
            p.export(path)
            with ZipFile(path) as z:
                self.assertEqual(set(z.namelist()), {'pack.mcmeta', 'assets/minecraft/textures/item/diamond.png'})
                self.assertEqual(json.loads(z.read('pack.mcmeta'))['pack']['pack_format'], 22)
                self.assertTrue(z.read('assets/minecraft/textures/item/diamond.png').startswith(b'\x89PNG'))

    def test_empty_export_rejected(self):
        with self.assertRaises(ValueError):
            Project().export('unused.zip')

    def test_invalid_pixels(self):
        for data in ({'size': 17, 'pixels': []}, {'size': 16, 'pixels': [[999,0,0,0]]*256}):
            with self.assertRaises(ValueError):
                png_bytes(data)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.matronix'
            path.write_text(json.dumps({'schema': 1, 'minecraft': '1.20.4', 'name': '', 'description': '', 'textures': {'../../evil': blank()}}))
            with self.assertRaises(ValueError):
                Project.load(path)


if __name__ == '__main__':
    unittest.main()
