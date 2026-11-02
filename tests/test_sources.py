import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch

from matronix.core import Project, VERSIONS, blank, png_bytes, pack_metadata
from matronix.sources import TextureSource, download_client


class SourceTests(unittest.TestCase):
    def test_all_versions_export(self):
        self.assertIn('1.12.2', VERSIONS)
        self.assertIn('26.2', VERSIONS)
        with tempfile.TemporaryDirectory() as tmp:
            for version in VERSIONS:
                p = Project(version=version)
                key = 'blocks/stone' if version == '1.12.2' else 'block/stone'
                p.textures[key] = blank()
                p.save(Path(tmp)/'project.matronix')
                self.assertEqual(Project.load(Path(tmp)/'project.matronix').version, version)
                p.export(Path(tmp)/'pack.zip')
                with ZipFile(Path(tmp)/'pack.zip') as archive:
                    self.assertIn(f'assets/minecraft/textures/{key}.png', archive.namelist())
                    self.assertEqual(json.loads(archive.read('pack.mcmeta')), pack_metadata(version, p.description))
        self.assertEqual(pack_metadata('1.12.2','')['pack']['pack_format'], 3)
        self.assertEqual(pack_metadata('26.2','')['pack']['min_format'], [88,0])
        self.assertEqual(pack_metadata('26.2','')['pack']['max_format'], [88,0])

    def test_dynamic_originals_and_version_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'client.jar'
            with ZipFile(path, 'w') as archive:
                archive.writestr('version.json', json.dumps({'id':'26.2'}))
                archive.writestr('assets/minecraft/textures/block/copper_block.png', png_bytes(blank()))
                archive.writestr('assets/minecraft/textures/item/diamond.png', png_bytes(blank(32)))
                archive.writestr('assets/minecraft/textures/block/../../evil.png', png_bytes(blank()))
            source = TextureSource(path, '26.2')
            self.assertEqual(set(source.entries), {'block/copper_block', 'item/diamond'})
            self.assertEqual(source.png('item/diamond'), png_bytes(blank(32)))
            with self.assertRaises(ValueError):
                TextureSource(path, '1.20.4')

    def test_legacy_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'legacy.jar'
            with ZipFile(path, 'w') as archive:
                archive.writestr('assets/minecraft/textures/blocks/planks_oak.png', png_bytes(blank()))
                archive.writestr('assets/minecraft/textures/items/apple.png', png_bytes(blank()))
            self.assertEqual(len(TextureSource(path,'1.12.2').entries), 2)
            with self.assertRaises(ValueError):
                TextureSource(path,'1.13')

    def test_download_verified_and_partial_removed(self):
        import io
        import hashlib
        data = b'client test data'
        meta = {'downloads': {'client': {'url':'https://example.invalid/client', 'size':len(data), 'sha1':hashlib.sha1(data).hexdigest()}}}
        manifest = {'versions':[{'id':'26.2','url':'https://example.invalid/version'}]}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('matronix.sources.get_json', side_effect=[manifest,meta]), patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
                path = download_client('26.2',tmp)
                self.assertEqual(path.read_bytes(),data)
            path.unlink()
            meta['downloads']['client']['sha1'] = 'bad'
            with patch('matronix.sources.get_json', side_effect=[manifest,meta]), patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
                with self.assertRaises(ValueError):
                    download_client('26.2',tmp)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix('.download').exists())
