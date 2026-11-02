"""Read original assets without extracting or redistributing a Minecraft client."""
import hashlib
import json
import struct
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from .core import VERSIONS, valid_key

MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'


def get_json(url):
    with urllib.request.urlopen(url, timeout=40) as response:
        return json.loads(response.read(8_000_000))


def download_client(version, directory, progress=lambda message: None):
    """Called in a worker thread. HTTPS + official manifest SHA-1 verification."""
    if version not in VERSIONS:
        raise ValueError('Неподдерживаемая версия')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{version}.jar'
    progress('Получаем список версий Mojang…')
    manifest = get_json(MANIFEST)
    entry = next((v for v in manifest['versions'] if v['id'] == version), None)
    if entry is None:
        raise ValueError('Версия не найдена в официальном списке Mojang')
    metadata = get_json(entry['url'])
    client = metadata['downloads']['client']
    if target.exists() and hashlib.sha1(target.read_bytes()).hexdigest() == client['sha1']:
        return target
    tmp = target.with_suffix('.download')
    digest = hashlib.sha1()
    total = 0
    try:
        with urllib.request.urlopen(client['url'], timeout=60) as response, tmp.open('wb') as stream:
            while True:
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > client['size'] or total > 600_000_000:
                    raise ValueError('Размер загрузки превышает ожидаемый')
                stream.write(chunk)
                digest.update(chunk)
                progress(f'Загрузка Minecraft {version}: {total//1048576} / {client["size"]//1048576} МБ')
        if total != client['size'] or digest.hexdigest() != client['sha1']:
            raise ValueError('Проверка файла не прошла. Повторите загрузку.')
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


class TextureSource:
    def __init__(self, path, version):
        self.path = Path(path)
        self.version = version
        self.entries = {}
        self.skipped = 0
        self.images = {}
        total_bytes = 0
        with ZipFile(path) as archive:
            if 'version.json' in archive.namelist():
                info = archive.getinfo('version.json')
                if info.file_size > 1_000_000:
                    raise ValueError('Некорректный version.json')
                actual = json.loads(archive.read(info)).get('id')
                if actual != version:
                    raise ValueError(f'Этот JAR относится к {actual}, а выбрана {version}')
            infos = archive.infolist()
            if len(infos) > 150_000:
                raise ValueError('Слишком много файлов в архиве')
            for info in infos:
                name = info.filename
                prefix = 'assets/minecraft/textures/'
                if not name.startswith(prefix) or not name.endswith('.png'):
                    continue
                key = name[len(prefix):-4]
                if not valid_key(key, version):
                    continue
                if info.file_size > 1_000_000:
                    self.skipped += 1
                    continue
                with archive.open(info) as stream:
                    header = stream.read(24)
                if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n':
                    continue
                w, h = struct.unpack('>II', header[16:24])
                # Animated strips and special rectangular atlases need a different editor.
                if w != h or w not in (16, 32, 64):
                    self.skipped += 1
                    continue
                total_bytes += info.file_size
                if total_bytes > 64_000_000:
                    raise ValueError('Слишком большой набор текстур (максимум 64 МБ)')
                self.images[key] = archive.read(info)
                self.entries[key] = name
        if not self.entries:
            raise ValueError('Подходящих текстур нет. Выберите клиентский JAR нужной версии (не серверный).')

    def png(self, key):
        return self.images[key]
