"""Explicit Windows CI network smoke check, separate from offline unit tests."""
import tempfile
from matronix.online import texture_index, download_selected
from matronix.sources import TextureSource

with tempfile.TemporaryDirectory() as directory:
    for version in ('1.12.2', '26.2'):
        entries = texture_index(version)
        key = 'blocks/stone' if version == '1.12.2' else 'block/stone'
        path, skipped = download_selected(version, entries, [key], directory)
        assert not skipped
        assert list(TextureSource(path, version).entries) == [key]
        print(f'Online download verified: Java {version}, {key}')
