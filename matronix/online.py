"""Selective texture downloads from public versioned Minecraft asset mirrors."""
import hashlib
import struct
import urllib.request
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from .core import VERSIONS, valid_key
from .sources import get_json

PREFIX = 'assets/minecraft/textures/'


def repository(version):
    if version not in VERSIONS:
        raise ValueError('Неподдерживаемая версия Minecraft')
    if version in ('1.12.2', '1.13', '1.13.1', '1.13.2'):
        return 'InventivetalentDev/minecraft-assets', version
    return 'misode/mcmeta', version + '-assets'


def texture_index(version):
    repo, ref = repository(version)
    tree = get_json(f'https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Сайт вернул неполный каталог. Используйте клиентский JAR.')
    entries = {}
    for item in tree['tree']:
        path = item['path']
        if item['type'] != 'blob' or not path.startswith(PREFIX) or not path.endswith('.png'):
            continue
        key = path[len(PREFIX):-4]
        if valid_key(key, version) and 0 < item.get('size', 0) <= 1_000_000:
            entries[key] = {'sha': item['sha'], 'size': item['size'],
                            'url': f'https://github.com/{repo}/raw/refs/{"heads" if repo.startswith("Invent") else "tags"}/{ref}/{path}'}
    if not entries:
        raise ValueError('В этой версии нет доступных текстур на сайте. Используйте JAR.')
    return entries


def download_selected(version, entries, keys, directory, progress=lambda text: None, cancelled=lambda: False):
    """Atomic accumulated cache; originals are never automatically added to a project."""
    repository(version)
    if not keys or len(keys) > 256 or len(set(keys)) != len(keys):
        raise ValueError('Выберите от 1 до 256 разных текстур за одну загрузку')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{version}-selected.jar'
    images = {}
    skipped = []
    for number, key in enumerate(keys, 1):
        if cancelled():
            raise InterruptedError('Загрузка отменена')
        if not valid_key(key, version) or key not in entries:
            raise ValueError('Недопустимая текстура')
        entry = entries[key]
        progress(f'Текстура {number}/{len(keys)}: {key}')
        request = urllib.request.Request(entry['url'], headers={'User-Agent': 'Matronix-Resource-Editor'})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(1_000_001)
        digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if len(data) != entry['size'] or digest != entry['sha']:
            raise ValueError(f'Проверка загруженной текстуры не прошла: {key}')
        if len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError(f'Не PNG: {key}')
        width, height = struct.unpack('>II', data[16:24])
        if width != height or width not in (16, 32, 64):
            skipped.append(key)
            continue
        images[PREFIX + key + '.png'] = data
    if cancelled():
        raise InterruptedError('Загрузка отменена')
    if not images:
        raise ValueError('Выбранные текстуры анимированные или неподдерживаемого размера. Скачайте другие.')
    # Keep previously downloaded textures but never extract paths from an archive.
    if target.exists():
        with ZipFile(target) as archive:
            for info in archive.infolist():
                name = info.filename
                if name.startswith(PREFIX) and name.endswith('.png') and valid_key(name[len(PREFIX):-4], version) and info.file_size <= 1_000_000:
                    images.setdefault(name, archive.read(info))
    if sum(map(len, images.values())) > 64_000_000:
        raise ValueError('Кэш текстур превышает 64 МБ')
    tmp = target.with_suffix('.tmp')
    try:
        with ZipFile(tmp, 'w', ZIP_DEFLATED) as archive:
            for name, data in images.items():
                archive.writestr(name, data)
            archive.writestr('version.json', '{"id": "' + version + '"}')
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return str(target), skipped
