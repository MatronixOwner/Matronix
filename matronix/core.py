"""Project data and Minecraft export. No GUI dependencies."""
import json
import re
import struct
import zlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

VERSION = '1.20.4'
PACK_FORMAT = 22
VERSIONS = json.loads(Path(__file__).with_name('versions.json').read_text(encoding='utf-8'))


def valid_key(key, version):
    if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9_/-]+', key):
        return False
    parts = key.split('/')
    folders = ('blocks', 'items') if version == '1.12.2' else ('block', 'item')
    return len(parts) >= 2 and parts[0] in folders and all(p and p not in ('.', '..') for p in parts)


def pack_metadata(version, description):
    major, minor = VERSIONS[version]
    pack = {'description': description}
    if major >= 65:
        pack.update(min_format=[major, minor], max_format=[major, minor])
    else:
        pack['pack_format'] = major
    return {'pack': pack}
CATALOG = [
    ('block/stone', 'Камень', 'Блоки'),
    ('block/dirt', 'Земля', 'Блоки'),
    ('block/grass_block_top', 'Трава — верх', 'Блоки'),
    ('block/cobblestone', 'Булыжник', 'Блоки'),
    ('block/oak_planks', 'Дубовые доски', 'Блоки'),
    ('block/sand', 'Песок', 'Блоки'),
    ('block/glass', 'Стекло', 'Блоки'),
    ('block/diamond_block', 'Алмазный блок', 'Блоки'),
    ('item/diamond', 'Алмаз', 'Предметы'),
    ('item/diamond_sword', 'Алмазный меч', 'Предметы'),
    ('item/apple', 'Яблоко', 'Предметы'),
    ('item/stick', 'Палка', 'Предметы'),
    ('item/iron_ingot', 'Железный слиток', 'Предметы'),
    ('item/golden_apple', 'Золотое яблоко', 'Предметы'),
    ('item/bow', 'Лук — без натяжения', 'Предметы'),
    ('item/ender_pearl', 'Жемчуг Эндера', 'Предметы'),
]
KEYS = {row[0] for row in CATALOG}


def validate_texture(data):
    if not isinstance(data, dict):
        raise ValueError('Неверные данные текстуры')
    size = data.get('size')
    if type(size) is not int or size not in (16, 32, 64):
        raise ValueError('Размер текстуры должен быть 16, 32 или 64')
    pixels = data.get('pixels')
    if not isinstance(pixels, list) or len(pixels) != size * size:
        raise ValueError('Неверное число пикселей')
    if any(not isinstance(p, list) or len(p) != 4 or
           any(type(c) is not int or not 0 <= c <= 255 for c in p) for p in pixels):
        raise ValueError('Некорректный цвет пикселя')


def blank(size=16):
    data = {'size': size, 'pixels': [[0, 0, 0, 0] for _ in range(size * size)]}
    validate_texture(data)
    return data


def png_bytes(data):
    validate_texture(data)
    size = data['size']
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    raw = b''.join(b'\0' + bytes(c for p in data['pixels'][y*size:(y+1)*size] for c in p) for y in range(size))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class Project:
    def __init__(self, name='Мой ресурс-пак', description='Создано в Matronix', version=VERSION):
        if version not in VERSIONS:
            raise ValueError('Неподдерживаемая версия Minecraft')
        self.version = version
        self.name = name
        self.description = description
        self.textures = {}

    def save(self, path):
        payload = {'schema': 1, 'minecraft': self.version, 'name': self.name,
                   'description': self.description, 'textures': self.textures}
        # Replace only after a complete write, preserving the previous project on failure.
        path = Path(path)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)

    @classmethod
    def load(cls, path):
        if Path(path).stat().st_size > 100_000_000:
            raise ValueError('Проект слишком большой (максимум 100 МБ)')
        obj = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(obj, dict) or obj.get('schema') != 1 or obj.get('minecraft') not in VERSIONS:
            raise ValueError('Неподдерживаемый формат проекта или версия Minecraft')
        if not isinstance(obj.get('name'), str) or not isinstance(obj.get('description'), str):
            raise ValueError('Неверное название или описание')
        textures = obj.get('textures')
        if not isinstance(textures, dict) or not all(valid_key(key, obj['minecraft']) for key in textures):
            raise ValueError('Неизвестные текстуры в проекте')
        for data in textures.values():
            validate_texture(data)
        project = cls(obj['name'], obj['description'], obj['minecraft'])
        project.textures = textures
        return project

    def export(self, path):
        if not self.textures:
            raise ValueError('Сначала нарисуйте или импортируйте хотя бы одну текстуру')
        if not all(valid_key(key, self.version) for key in self.textures):
            raise ValueError('Неизвестная текстура')
        images = {key: png_bytes(data) for key, data in self.textures.items()}
        with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('pack.mcmeta', json.dumps(pack_metadata(self.version, self.description or self.name), ensure_ascii=False))
            for key, image in images.items():
                archive.writestr(f'assets/minecraft/textures/{key}.png', image)
