import copy
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRectF, QThread, QStandardPaths, QSize
from PySide6.QtGui import QColor, QPainter, QImage, QAction, QKeySequence, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QLineEdit,
    QComboBox, QFileDialog, QMessageBox, QColorDialog, QInputDialog, QCheckBox,
    QSplitter, QButtonGroup)

from .core import Project, CATALOG, VERSION, VERSIONS, blank
from .sources import TextureSource, download_client
from zipfile import BadZipFile


class DownloadWorker(QThread):
    progress = Signal(str)
    loaded = Signal(str)
    failed = Signal(str)

    def __init__(self, version, directory):
        super().__init__()
        self.version, self.directory = version, directory

    def run(self):
        try:
            path = download_client(self.version, self.directory, self.progress.emit)
            self.loaded.emit(str(path))
        except Exception as error:
            self.failed.emit(f'Не удалось загрузить оригиналы: {error}\nМожно выбрать установленный клиентский JAR вручную.')


class Canvas(QWidget):
    changed = Signal()
    sampled = Signal(object)

    def __init__(self):
        super().__init__()
        self.data = blank()
        self.color = [137, 116, 255, 255]
        self.tool = 'Карандаш'
        self.grid = True
        self.history = []
        self.future = []
        self.drawing = False
        self.last = None
        self.setMinimumSize(320, 320)

    def geometry_info(self):
        side = min(self.width(), self.height()) - 32
        return (self.width()-side)/2, (self.height()-side)/2, side/self.data['size']

    def paintEvent(self, event):
        painter = QPainter(self)
        x0, y0, step = self.geometry_info()
        n = self.data['size']
        for y in range(n):
            for x in range(n):
                rect = QRectF(x0+x*step, y0+y*step, step, step)
                painter.fillRect(rect, QColor('#303442' if (x+y) % 2 else '#242834'))
                painter.fillRect(rect, QColor(*self.data['pixels'][y*n+x]))
        if self.grid and step >= 8:
            painter.setPen(QColor(255, 255, 255, 28))
            for i in range(n+1):
                painter.drawLine(QRectF(x0+i*step, y0, 0, n*step).topLeft(), QRectF(x0+i*step, y0, 0, n*step).bottomLeft())
                painter.drawLine(QRectF(x0, y0+i*step, n*step, 0).topLeft(), QRectF(x0, y0+i*step, n*step, 0).topRight())

    def snapshot(self):
        self.history.append(copy.deepcopy(self.data))
        self.history = self.history[-60:]
        self.future.clear()

    def undo(self):
        if self.history:
            self.future.append(copy.deepcopy(self.data))
            self.data = self.history.pop()
            self.changed.emit()
            self.update()

    def redo(self):
        if self.future:
            self.history.append(copy.deepcopy(self.data))
            self.data = self.future.pop()
            self.changed.emit()
            self.update()

    def point(self, event):
        x0, y0, step = self.geometry_info()
        x, y = int((event.position().x()-x0)//step), int((event.position().y()-y0)//step)
        return (x, y) if 0 <= x < self.data['size'] and 0 <= y < self.data['size'] else None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.point(event) is None:
            return
        if self.tool == 'Пипетка':
            x, y = self.point(event)
            self.sampled.emit(self.data['pixels'][y*self.data['size']+x][:])
            return
        self.snapshot()
        self.drawing = True
        self.last = None
        self.apply(event)

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.apply(event)

    def mouseReleaseEvent(self, event):
        self.drawing = False
        self.last = None

    def apply(self, event):
        point = self.point(event)
        if point is None:
            self.last = None
            return
        x, y = point
        n = self.data['size']
        pixels = self.data['pixels']
        color = [0, 0, 0, 0] if self.tool == 'Ластик' else self.color[:]
        if self.tool == 'Заливка':
            old = pixels[y*n+x][:]
            if old != color:
                queue = [(x, y)]
                while queue:
                    a, b = queue.pop()
                    if not (0 <= a < n and 0 <= b < n) or pixels[b*n+a] != old:
                        continue
                    pixels[b*n+a] = color[:]
                    queue.extend(((a-1,b), (a+1,b), (a,b-1), (a,b+1)))
            self.drawing = False
        else:
            start = self.last or point
            count = max(abs(x-start[0]), abs(y-start[1]), 1)
            for i in range(count+1):
                a = round(start[0]+(x-start[0])*i/count)
                b = round(start[1]+(y-start[1])*i/count)
                pixels[b*n+a] = color[:]
            self.last = point
        self.changed.emit()
        self.update()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = Project()
        self.path = None
        self.dirty = False
        self.current = None
        self.source = None
        self.catalog = list(CATALOG)
        self.worker = None
        self.cache = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / 'clients'

        self.resize(1180, 780)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 16)
        top = QHBoxLayout()
        title = QLabel('MATRONIX  /  Ресурс-паки без сложностей')
        title.setObjectName('brand')
        top.addWidget(title)
        top.addStretch()
        self.button(top, 'Новый', self.new)
        self.button(top, 'Открыть', self.open)
        self.button(top, 'Сохранить', self.save)
        export = self.button(top, 'Собрать ZIP →', self.export)
        export.setObjectName('primary')
        layout.addLayout(top)
        metadata = QHBoxLayout()
        self.name = QLineEdit(self.project.name)
        self.name.setPlaceholderText('Название пака')
        self.description = QLineEdit(self.project.description)
        self.description.setPlaceholderText('Описание в Minecraft')
        metadata.addWidget(self.name)
        metadata.addWidget(self.description, 2)
        self.version = QComboBox()
        self.version.addItems(list(VERSIONS))
        self.version.setCurrentText(VERSION)
        self.version.setToolTip('Minecraft Java. Смена версии создаёт новый проект.')
        self.version.currentTextChanged.connect(self.change_version)
        metadata.addWidget(self.version)
        layout.addLayout(metadata)
        sources = QHBoxLayout()
        self.download_button = self.button(sources, '↓ Загрузить оригиналы Mojang', self.download_originals)
        self.local_button = self.button(sources, 'Открыть Minecraft JAR…', self.open_jar)
        self.source_label = QLabel('Оригиналы не подключены — чистый холст')
        sources.addWidget(self.source_label, 1)
        layout.addLayout(sources)
        self.name.textChanged.connect(self.metadata_changed)
        self.description.textChanged.connect(self.metadata_changed)
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel('КАТАЛОГ ТЕКСТУР'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Найти блок или предмет…')
        self.search.textChanged.connect(self.filter)
        ll.addWidget(self.search)
        self.category = QComboBox()
        self.category.addItems(['Все', 'Блоки', 'Предметы'])
        self.category.currentTextChanged.connect(self.filter)
        ll.addWidget(self.category)
        self.list = QListWidget()
        for key, label, category in self.catalog:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            item.setToolTip(key)
            self.list.addItem(item)
        self.list.currentItemChanged.connect(self.select)
        ll.addWidget(self.list)
        hint = QLabel('● — текстура добавлена в пак\nОстальные останутся стандартными.')
        hint.setWordWrap(True)
        ll.addWidget(hint)
        splitter.addWidget(left)
        center = QWidget()
        cl = QVBoxLayout(center)
        self.texture_title = QLabel('Выберите текстуру')
        self.texture_title.setObjectName('heading')
        cl.addWidget(self.texture_title)
        tools = QHBoxLayout()
        group = QButtonGroup(self)
        self.canvas = Canvas()
        for label in ['Карандаш', 'Ластик', 'Заливка', 'Пипетка']:
            button = self.button(tools, label, lambda checked=False, t=label: setattr(self.canvas, 'tool', t))
            button.setCheckable(True)
            group.addButton(button)
            if label == 'Карандаш':
                button.setChecked(True)
        cl.addLayout(tools)
        cl.addWidget(self.canvas, 1)
        bottom = QHBoxLayout()
        self.button(bottom, '↶ Отмена', self.canvas.undo)
        self.button(bottom, '↷ Повтор', self.canvas.redo)
        grid = QCheckBox('Сетка')
        grid.setChecked(True)
        grid.toggled.connect(lambda value: (setattr(self.canvas, 'grid', value), self.canvas.update()))
        bottom.addWidget(grid)
        self.button(bottom, 'Размер', self.resize_texture)
        cl.addLayout(bottom)
        splitter.addWidget(center)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel('ЦВЕТ И ПРЕДПРОСМОТР'))
        self.swatch = self.button(rl, 'Выбрать цвет', self.choose_color)
        palette = QHBoxLayout()
        for value in ['#8974ff', '#f2bf67', '#72d9a1', '#ffffff', '#181b24']:
            b = self.button(palette, '', lambda checked=False, c=value: self.set_color(QColor(c).getRgb()))
            b.setFixedSize(28, 28)
            b.setStyleSheet(f'background: {value}; border: 1px solid #606478;')
        rl.addLayout(palette)
        self.preview = QLabel()
        self.preview.setFixedSize(192, 192)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet('background: #292e3b; border: 1px solid #40465b;')
        rl.addWidget(self.preview, alignment=Qt.AlignHCenter)
        rl.addWidget(QLabel('Плоский предпросмотр • без сетки'))
        self.button(rl, 'Импорт PNG', self.import_png)
        self.button(rl, 'Экспорт PNG', self.export_png)
        self.button(rl, 'Убрать из пака', self.remove_texture)
        note = QLabel('Начните с чистого холста или импортируйте свою PNG.\n\nНажмите «Загрузить оригиналы» или выберите клиентский JAR Minecraft.\n\nРазмеры: 16×16, 32×32, 64×64. Анимации пока не поддерживаются.')
        note.setWordWrap(True)
        rl.addWidget(note)
        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([245, 650, 245])
        self.canvas.changed.connect(self.edited)
        self.canvas.sampled.connect(self.set_color)
        self.set_color(self.canvas.color)
        self.list.setCurrentRow(0)
        self.shortcut('Ctrl+S', self.save)
        self.shortcut('Ctrl+O', self.open)
        self.shortcut('Ctrl+N', self.new)
        self.shortcut('Ctrl+Z', self.canvas.undo)
        self.shortcut('Ctrl+Shift+Z', self.canvas.redo)
        self.try_cached_source()
        if self.source:
            self.rebuild_catalog()
        self.refresh_title()
        self.statusBar().showMessage('Готово. Выберите текстуру и начните рисовать.')

    def button(self, layout, text, callback):
        b = QPushButton(text)
        b.clicked.connect(callback)
        layout.addWidget(b)
        return b

    def shortcut(self, key, callback):
        action = QAction(self)
        action.setShortcut(QKeySequence(key))
        action.triggered.connect(callback)
        self.addAction(action)

    def refresh_title(self):
        self.setWindowTitle(f'{"• " if self.dirty else ""}{self.project.name} — Matronix')

    def mark(self):
        self.dirty = True
        self.refresh_title()

    def metadata_changed(self):
        self.project.name = self.name.text()
        self.project.description = self.description.text()
        self.mark()

    def filter(self):
        query = self.search.text().casefold()
        category = self.category.currentText()
        for i, (key, label, cat) in enumerate(self.catalog):
            self.list.item(i).setHidden(query not in (key+' '+label).casefold() or category not in ('Все', cat))

    def badges(self):
        for i, (key, label, _) in enumerate(self.catalog):
            self.list.item(i).setText(('●  ' if key in self.project.textures else '')+label)

    def select(self, item, previous=None):
        if not item:
            return
        self.current = item.data(Qt.UserRole)
        self.canvas.data = copy.deepcopy(self.project.textures.get(self.current) or self.original(self.current))
        self.canvas.history.clear()
        self.canvas.future.clear()
        self.texture_title.setText(next(label for key, label, _ in self.catalog if key == self.current))
        self.canvas.update()
        self.update_preview()

    def edited(self):
        self.project.textures[self.current] = copy.deepcopy(self.canvas.data)
        self.badges()
        self.update_preview()
        self.mark()

    def image(self):
        n = self.canvas.data['size']
        image = QImage(n, n, QImage.Format_RGBA8888)
        for y in range(n):
            for x in range(n):
                image.setPixelColor(x, y, QColor(*self.canvas.data['pixels'][y*n+x]))
        return image

    def update_preview(self):
        from PySide6.QtGui import QPixmap
        self.preview.setPixmap(QPixmap.fromImage(self.image()).scaled(176, 176, Qt.KeepAspectRatio, Qt.FastTransformation))

    def set_color(self, color):
        self.canvas.color = list(color)
        self.swatch.setStyleSheet(f'background: {QColor(*color).name()}; color: {"#111111" if QColor(*color).lightness() > 140 else "#ffffff"};')

    def choose_color(self):
        color = QColorDialog.getColor(QColor(*self.canvas.color), self, 'Цвет пикселя', QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.set_color(color.getRgb())

    def resize_texture(self):
        size, ok = QInputDialog.getItem(self, 'Размер текстуры', 'Изменить размер (без сглаживания):', ['16', '32', '64'], [16,32,64].index(self.canvas.data['size']), False)
        if ok and int(size) != self.canvas.data['size']:
            self.replace_image(self.image().scaled(int(size), int(size), Qt.IgnoreAspectRatio, Qt.FastTransformation))

    def replace_image(self, image):
        self.canvas.snapshot()
        n = image.width()
        self.canvas.data = {'size': n, 'pixels': [list(image.pixelColor(x,y).getRgb()) for y in range(n) for x in range(n)]}
        self.canvas.update()
        self.edited()

    def import_png(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Импорт текстуры', '', 'PNG (*.png)')
        if not path:
            return
        from PySide6.QtGui import QImageReader
        reader = QImageReader(path)
        size = reader.size()
        if size.width() not in (16,32,64) or size.height() != size.width():
            self.error('Нужна квадратная PNG: 16×16, 32×32 или 64×64.')
            return
        image = reader.read()
        if image.isNull():
            self.error('Не удалось прочитать PNG.')
            return
        self.replace_image(image)

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Экспорт текстуры', self.current.split('/')[-1]+'.png', 'PNG (*.png)')
        if path and not self.image().save(self.extension(path, '.png'), 'PNG'):
            self.error('Не удалось сохранить PNG.')

    def remove_texture(self):
        if self.current not in self.project.textures:
            return
        if QMessageBox.question(self, 'Убрать текстуру?', 'В игре будет использована стандартная текстура. Продолжить?') != QMessageBox.Yes:
            return
        del self.project.textures[self.current]
        self.select(self.list.currentItem())
        self.badges()
        self.mark()

    def error(self, message):
        QMessageBox.warning(self, 'Matronix', str(message))

    @staticmethod
    def extension(path, suffix):
        return path if path.lower().endswith(suffix) else path+suffix

    def save(self):
        path = self.path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, 'Сохранить проект', 'Мой пак.matronix', 'Проект Matronix (*.matronix)')
        if not path:
            return False
        path = self.extension(path, '.matronix')
        try:
            self.project.save(path)
        except (OSError, ValueError) as e:
            self.error(e)
            return False
        self.path = path
        self.dirty = False
        self.refresh_title()
        self.statusBar().showMessage(f'Проект сохранён: {path}')
        return True

    def can_discard(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, 'Несохранённые изменения', 'Сохранить изменения проекта?', QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        return answer == QMessageBox.Discard or (answer == QMessageBox.Save and self.save())

    def install_project(self, project, path):
        self.project, self.path = project, path
        self.name.blockSignals(True)
        self.description.blockSignals(True)
        self.name.setText(project.name)
        self.description.setText(project.description)
        self.name.blockSignals(False)
        self.description.blockSignals(False)
        self.version.blockSignals(True)
        self.version.setCurrentText(project.version)
        self.version.blockSignals(False)
        if self.source and self.source.version != project.version:
            self.source = None
        self.try_cached_source()
        self.rebuild_catalog()
        self.dirty = False
        self.refresh_title()

    def new(self):
        if self.can_discard():
            self.install_project(Project(version=self.project.version), None)

    def open(self):
        if not self.can_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Открыть проект', '', 'Проект Matronix (*.matronix)')
        if path:
            try:
                self.install_project(Project.load(path), path)
            except (OSError, ValueError, TypeError, KeyError) as e:
                self.error(e)

    def export(self):
        if not self.project.textures:
            self.error('Сначала нарисуйте или импортируйте хотя бы одну текстуру.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Собрать ресурс-пак', 'Matronix-pack.zip', 'Ресурс-пак (*.zip)')
        if not path:
            return
        try:
            self.project.export(self.extension(path, '.zip'))
            QMessageBox.information(self, 'Пак готов!', f'Ресурс-пак для Java {self.project.version} собран.\n\nВ Minecraft: Настройки → Наборы ресурсов → Открыть папку. Скопируйте туда ZIP и включите пак.\n\nСборка ZIP не заменяет сохранение проекта.')
        except (OSError, ValueError) as e:
            self.error(e)

    def change_version(self, version):
        if not self.can_discard():
            self.version.blockSignals(True)
            self.version.setCurrentText(self.project.version)
            self.version.blockSignals(False)
            return
        if self.project.textures and QMessageBox.question(self, 'Сменить версию?',
                'Будет создан новый проект. Текстуры не конвертируются между версиями. Продолжить?') != QMessageBox.Yes:
            self.version.blockSignals(True)
            self.version.setCurrentText(self.project.version)
            self.version.blockSignals(False)
            return
        self.install_project(Project(version=version), None)

    def original(self, key):
        if self.source and key in self.source.entries:
            try:
                image = QImage.fromData(self.source.png(key), 'PNG')
                if image.isNull():
                    raise ValueError('Не удалось прочитать оригинальную текстуру')
                n = image.width()
                return {'size': n, 'pixels': [list(image.pixelColor(x,y).getRgb()) for y in range(n) for x in range(n)]}
            except (OSError, ValueError, KeyError, BadZipFile) as error:
                self.statusBar().showMessage(f'Оригинал недоступен: {error}')
        return blank()

    def rebuild_catalog(self):
        selected = self.current
        labels = {key: label for key, label, _ in CATALOG}
        if self.project.version == '1.12.2':
            legacy = {'grass_block_top': 'grass_top', 'oak_planks': 'planks_oak', 'diamond_block': 'diamond_block'}
            labels = {key.replace('block/', 'blocks/').replace('item/', 'items/').rsplit('/',1)[0]+'/'+legacy.get(key.rsplit('/',1)[1],key.rsplit('/',1)[1]): label for key, label in labels.items()}
        keys = set(self.source.entries) if self.source else set(labels)
        keys.update(self.project.textures)
        self.catalog = [(key, labels.get(key, key.split('/',1)[1]), 'Блоки' if key.split('/')[0] in ('block', 'blocks') else 'Предметы') for key in sorted(keys)]
        self.list.blockSignals(True)
        self.list.clear()
        for key, label, _ in self.catalog:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            item.setToolTip(key)
            if self.source and key in self.source.entries:
                try:
                    item.setIcon(QIcon(QPixmap.fromImage(QImage.fromData(self.source.png(key), 'PNG'))))
                except (OSError, KeyError, BadZipFile):
                    pass
            self.list.addItem(item)
        self.list.setIconSize(QSize(24,24))
        index = next((i for i, row in enumerate(self.catalog) if row[0] == selected), 0)
        self.list.setCurrentRow(index)
        self.list.blockSignals(False)
        self.select(self.list.currentItem())
        self.badges()
        self.filter()
        self.source_label.setText(f'Оригиналы {self.project.version}: {len(self.source.entries)} текстур; пропущено {self.source.skipped}' if self.source else 'Оригиналы не подключены — чистый холст')

    def attach_source(self, path):
        try:
            source = TextureSource(path, self.project.version)
            self.source = source
            self.rebuild_catalog()
        except (OSError, ValueError, BadZipFile, KeyError) as error:
            self.error(error)

    def try_cached_source(self):
        path = self.cache / f'{self.project.version}.jar'
        if path.exists():
            try:
                self.source = TextureSource(path, self.project.version)
            except (OSError, ValueError, BadZipFile, KeyError):
                self.source = None

    def open_jar(self):
        path, _ = QFileDialog.getOpenFileName(self, f'Клиент Minecraft Java {self.project.version}', str(Path.home()/ 'AppData/Roaming/.minecraft/versions'), 'Minecraft client (*.jar)')
        if path:
            self.attach_source(path)

    def download_originals(self):
        if self.worker and self.worker.isRunning():
            return
        if QMessageBox.question(self, 'Загрузка оригиналов',
                f'Скачать клиент Minecraft Java {self.project.version} с серверов Mojang? Это может занять несколько сотен МБ.\nФайл сохранится в локальном кэше. Minecraft запускаться не будет.\n\nМожно вместо этого открыть JAR уже установленной игры.') != QMessageBox.Yes:
            return
        self.download_button.setEnabled(False)
        self.local_button.setEnabled(False)
        self.version.setEnabled(False)
        self.worker = DownloadWorker(self.project.version, self.cache)
        self.worker.progress.connect(self.statusBar().showMessage)
        self.worker.loaded.connect(self.download_loaded)
        self.worker.failed.connect(self.error)
        self.worker.finished.connect(self.download_finished)
        self.worker.start()

    def download_loaded(self, path):
        # Opening another project during download is allowed; never attach the wrong version.
        if self.worker.version == self.project.version:
            self.attach_source(path)
        self.statusBar().showMessage('Загрузка оригиналов завершена.')

    def download_finished(self):
        self.download_button.setEnabled(True)
        self.local_button.setEnabled(True)
        self.version.setEnabled(True)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.error('Дождитесь окончания загрузки оригиналов перед закрытием программы.')
            event.ignore()
            return
        event.accept() if self.can_discard() else event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Matronix')
    app.setOrganizationName('Matronix')
    app.setStyle('Fusion')
    app.setStyleSheet('''
        QWidget { background: #141720; color: #dfe3f3; font-family: "Segoe UI", sans-serif; font-size: 13px; }
        QLineEdit, QComboBox, QListWidget { background: #1d2230; border: 1px solid #30374b; border-radius: 7px; padding: 9px; }
        QPushButton { background: #272d3f; border: 1px solid #39425b; border-radius: 7px; padding: 9px 12px; }
        QPushButton:hover { background: #353e58; }
        QPushButton:checked, QPushButton#primary { background: #7155dc; border-color: #9a81f3; color: white; }
        QListWidget::item { padding: 10px 4px; border-radius: 5px; }
        QListWidget::item:selected { background: #423364; }
        QLabel#brand { font-size: 18px; font-weight: 700; }
        QLabel#heading { font-size: 22px; font-weight: 600; }
        QSplitter::handle { background: #252b3c; width: 1px; }
        QStatusBar { color: #a7b0c8; }
    ''')
    window = Window()
    window.show()
    sys.exit(app.exec())
