from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QPushButton, QProgressBar, QMessageBox)

from .core import CATALOG
from .online import texture_index, download_selected, repository


class OnlineWorker(QThread):
    progress = Signal(str)

    def __init__(self, task, parent):
        super().__init__(parent)
        self.task = task
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.task(self)
        except Exception as error:
            self.error = str(error)


class TextureDialog(QDialog):
    def __init__(self, version, cache, parent=None):
        super().__init__(parent)
        self.version, self.cache = version, cache
        self.entries = {}
        self.path = None
        self.worker = None
        self.cancelling = False
        self.setWindowTitle('Онлайн-библиотека • Matronix')
        self.resize(740, 670)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24,24,24,24)
        title = QLabel('Выберите текстуры для своего пака')
        title.setObjectName('heading')
        layout.addWidget(title)
        repo, _ = repository(version)
        info = QLabel(f'Java {version}  •  Источник: github.com/{repo}\nСкачиваются только отмеченные PNG, не весь Minecraft. Это стороннее зеркало ресурсов.')
        info.setWordWrap(True)
        layout.addWidget(info)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Поиск: stone, diamond, камень…')
        self.search.textChanged.connect(self.filter)
        row.addWidget(self.search, 1)
        self.category = QComboBox()
        self.category.addItems(['Все', 'Блоки', 'Предметы'])
        self.category.currentTextChanged.connect(self.filter)
        row.addWidget(self.category)
        layout.addLayout(row)
        self.list = QListWidget()
        self.list.itemChanged.connect(self.count)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, checked in [('Отметить видимые', True), ('Снять отметки', False)]:
            button = QPushButton(text)
            button.clicked.connect(lambda _, value=checked: self.check_visible(value))
            row.addWidget(button)
        self.count_label = QLabel('Выбрано: 0 / 256')
        row.addWidget(self.count_label)
        layout.addLayout(row)
        self.status = QLabel('Получаем каталог текстур…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0,0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(5)
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.cancel = QPushButton('Закрыть')
        self.cancel.clicked.connect(self.reject)
        row.addWidget(self.cancel)
        row.addStretch()
        self.download = QPushButton('Скачать выбранные →')
        self.download.setObjectName('primary')
        self.download.clicked.connect(self.download_checked)
        self.download.setEnabled(False)
        row.addWidget(self.download)
        layout.addLayout(row)
        QTimer.singleShot(0, self.load_index)

    def run_task(self, task, callback):
        self.worker = OnlineWorker(task, self)
        self.worker.progress.connect(self.status.setText)
        self.worker.finished.connect(lambda: self.complete(callback))
        self.download.setEnabled(False)
        self.list.setEnabled(False)
        self.progress.show()
        self.worker.start()

    def complete(self, callback):
        self.progress.hide()
        self.list.setEnabled(True)
        if self.cancelling:
            super().reject()
        elif self.worker.error:
            self.status.setText('Не удалось загрузить. Проверьте интернет или используйте локальный JAR.\n' + self.worker.error)
            self.download.setEnabled(bool(self.entries))
        else:
            callback(self.worker.result)

    def load_index(self):
        self.run_task(lambda worker: texture_index(self.version), self.show_entries)

    def show_entries(self, entries):
        self.entries = entries
        labels = {key: label for key, label, _ in CATALOG}
        self.list.blockSignals(True)
        for key in sorted(entries):
            item = QListWidgetItem(labels.get(key, key.split('/',1)[1]) + '  ·  ' + key)
            item.setData(Qt.UserRole, key)
            item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.filter()
        self.status.setText(f'Найдено {len(entries)} PNG. Анимации и нестандартные размеры будут пропущены после проверки.')
        self.count()

    def checked(self):
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.Checked]

    def count(self, *args):
        amount = len(self.checked())
        self.count_label.setText(f'Выбрано: {amount} / 256')
        busy = self.worker and self.worker.isRunning()
        self.download.setEnabled(0 < amount <= 256 and not busy)

    def check_visible(self, checked):
        if self.worker and self.worker.isRunning():
            return
        self.list.blockSignals(True)
        amount = len(self.checked())
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not checked:
                item.setCheckState(Qt.Unchecked)
            elif not item.isHidden() and item.checkState() != Qt.Checked and amount < 256:
                item.setCheckState(Qt.Checked)
                amount += 1
        self.list.blockSignals(False)
        self.count()

    def filter(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.UserRole)
            cat = 'Блоки' if key.split('/')[0] in ('block','blocks') else 'Предметы'
            item.setHidden(self.search.text().casefold() not in item.text().casefold() or self.category.currentText() not in ('Все',cat))

    def download_checked(self):
        keys = self.checked()
        if not 0 < len(keys) <= 256:
            return
        self.run_task(lambda worker: download_selected(self.version, self.entries, keys, self.cache,
            worker.progress.emit, worker.isInterruptionRequested), self.downloaded)

    def downloaded(self, result):
        self.path, skipped = result
        if skipped:
            QMessageBox.information(self, 'Некоторые текстуры пропущены',
                f'Пропущено {len(skipped)} анимированных или неподдерживаемых текстур. Остальные готовы к редактированию.')
        self.accept()

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.cancelling = True
            self.worker.requestInterruption()
            self.status.setText('Отмена… Ожидаем завершения текущего сетевого запроса (до 40 секунд).')
            self.cancel.setEnabled(False)
        else:
            super().reject()

    def closeEvent(self, event):
        event.ignore()
        self.reject()
