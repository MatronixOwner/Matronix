import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from matronix.core import blank, png_bytes
from matronix.online import texture_index, download_selected, repository
from matronix.sources import TextureSource


def entry(data):
    return {'url': 'https://github.com/example/test', 'size': len(data),
            'sha': hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}


class OnlineTests(unittest.TestCase):
    def test_mirrors_and_index(self):
        self.assertEqual(repository('1.12.2')[0], 'InventivetalentDev/minecraft-assets')
        self.assertEqual(repository('26.2')[1], '26.2-assets')
        with self.assertRaises(ValueError):
            repository('../evil')
        with patch('matronix.online.get_json', return_value={'truncated':False, 'tree':[
            {'type':'blob','path':'assets/minecraft/textures/block/stone.png', 'size':200,'sha':'abc'},
            {'type':'blob','path':'assets/minecraft/textures/block/../../evil.png', 'size':20,'sha':'bad'},
            {'type':'blob','path':'assets/minecraft/textures/gui/icons.png', 'size':20,'sha':'bad'}]}):
            entries = texture_index('26.2')
            self.assertEqual(list(entries), ['block/stone'])
            self.assertIn('26.2-assets',entries['block/stone']['url'])

    def test_only_selected_and_accumulated(self):
        data = png_bytes(blank())
        entries = {key: entry(data) for key in ['block/stone', 'item/apple']}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('urllib.request.urlopen',return_value=io.BytesIO(data)) as request:
                path, skipped = download_selected('26.2', entries, ['block/stone'], tmp)
                self.assertEqual(request.call_count,1)
                self.assertEqual(skipped,[])
                self.assertEqual(list(TextureSource(path,'26.2').entries),['block/stone'])
            with patch('urllib.request.urlopen',return_value=io.BytesIO(data)):
                path, _ = download_selected('26.2',entries,['item/apple'],tmp)
                self.assertEqual(set(TextureSource(path,'26.2').entries),set(entries))

    def test_bad_digest_and_cancel_preserve_cache(self):
        data = png_bytes(blank())
        with tempfile.TemporaryDirectory() as tmp:
            entries = {'block/stone':entry(data)}
            with patch('urllib.request.urlopen',return_value=io.BytesIO(data)):
                path, _ = download_selected('26.2',entries,['block/stone'],tmp)
            before = Path(path).read_bytes()
            with self.assertRaises(InterruptedError):
                download_selected('26.2',entries,['block/stone'],tmp,cancelled=lambda:True)
            with patch('urllib.request.urlopen',return_value=io.BytesIO(b'corrupt')):
                with self.assertRaises(ValueError):
                    download_selected('26.2',entries,['block/stone'],tmp)
            self.assertEqual(Path(path).read_bytes(), before)
            self.assertFalse(Path(path).with_suffix('.tmp').exists())

    def test_selection_limit(self):
        for keys in [[], ['block/stone']*257, ['../evil']]:
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                download_selected('26.2',{},keys,tmp)

    def test_animation_skipped(self):
        data = bytearray(png_bytes(blank()))
        data[20:24] = (32).to_bytes(4,'big')
        data = bytes(data)
        with tempfile.TemporaryDirectory() as tmp, patch('urllib.request.urlopen',return_value=io.BytesIO(data)):
            with self.assertRaisesRegex(ValueError,'анимированные'):
                download_selected('26.2',{'block/water_still':entry(data)},['block/water_still'],tmp)
            self.assertEqual(list(Path(tmp).iterdir()),[])
