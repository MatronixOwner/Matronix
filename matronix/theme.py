STYLE = '''
* { font-family: "Segoe UI", sans-serif; font-size: 13px; }
QWidget { background: #101218; color: #e7e9f0; }
QWidget#panel { background: #191c25; border: 1px solid #292e3c; border-radius: 12px; }
QWidget#panel QLabel, QWidget#panel QCheckBox { background: transparent; border: none; }
QWidget#header { background: #101218; }
QLabel#brand { font-size: 25px; font-weight: 800; letter-spacing: 3px; color: #f6f5ff; }
QLabel#heading { font-size: 22px; font-weight: 700; }
QLabel#muted { color: #929bad; font-size: 12px; }
QLabel#section { color: #9b92bc; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#badge { color: #b9a7ff; background: #28213d; border-radius: 7px; padding: 6px 12px; }
QLineEdit, QComboBox { background: #11141c; border: 1px solid #33394b; border-radius: 7px; padding: 9px 10px; selection-background-color: #6950c8; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #9d82ff; }
QComboBox QAbstractItemView { background: #202432; selection-background-color: #483471; }
QPushButton { background: #262b39; border: 1px solid #383f52; border-radius: 7px; padding: 9px 12px; font-weight: 600; }
QPushButton:hover { background: #343b50; border-color: #70618e; }
QPushButton:pressed { background: #48376e; }
QPushButton:disabled { color: #626b80; background: #20242e; border-color: #292f3c; }
QPushButton:checked { background: #35284e; border-color: #b49cff; color: #d8cbff; }
QPushButton#primary { background: #8762e9; border-color: #a889ff; color: white; padding: 11px 19px; }
QPushButton#primary:hover { background: #9c79f4; }
QPushButton#primary:disabled { background: #373045; color: #847a99; border-color: #4e435e; }
QPushButton#quiet { background: transparent; border-color: transparent; color: #b1bbcd; }
QPushButton#quiet:hover { background: #252936; }
QPushButton#danger { color: #ef9ea6; background: transparent; border-color: #54363e; }
QListWidget { background: #151821; border: none; outline: none; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 10px 7px; border-radius: 6px; margin: 2px 0; }
QListWidget::item:hover { background: #262b39; }
QListWidget::item:selected { background: #352b4d; color: #f1eaff; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #5e667e; border-radius: 4px; background: #141822; }
QCheckBox::indicator:checked { background: #a789ff; border-color: #c4afff; }
QSplitter::handle { background: #101218; width: 12px; }
QScrollBar:vertical { background: #151821; width: 9px; margin: 0; }
QScrollBar::handle:vertical { background: #42485c; min-height: 26px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #282337; border: none; border-radius: 2px; }
QProgressBar::chunk { background: #a789ff; border-radius: 2px; }
QStatusBar { color: #929bad; background: #101218; padding: 4px; }
QToolTip { color: #eee6ff; background: #30283e; border: 1px solid #78628f; padding: 7px; }
'''
