from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QGraphicsItem, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout,QPushButton, QStyle
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QColor
import os


class Graphic(QGraphicsSvgItem):

    def __init__(self, widg, svg_path=None, scale=0.2):
        super().__init__(svg_path)

        self.widg = widg
        self.widg.graphic = self

        self.setScale(scale)
        self.setZValue(1)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.show_config()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.show_config()
        super().mouseDoubleClickEvent(e)

    def show_config(self):
        dialog = ConfigDialog(self)
        dialog.exec()



class ConfigDialog(QDialog):

    def __init__(self, graphic, parent=None):
        super().__init__(parent)

        self.graph = graphic
        self.widg = graphic.widg

        self.setWindowTitle(f"Config (ID: {self.widg.id})")
        self.setGeometry(100, 100, 300, 200)

        main_lay = QVBoxLayout()

        enter_lay = QHBoxLayout()
        enter_lay.addWidget(QLabel("Entradas:"))
        self.enter_sp = QSpinBox()
        self.enter_sp.setRange(1, 8)
        self.enter_sp.setValue(len(self.widg.enter))
        if self.widg.can_set_enter():
            self.enter_sp.valueChanged.connect(self.set_enter)
        else:
            self.enter_sp.setEnabled(False)
        enter_lay.addWidget(self.enter_sp)
        main_lay.addLayout(enter_lay)

        exit_lay = QHBoxLayout()
        exit_lay.addWidget(QLabel("Salidas:"))
        self.exit_sp = QSpinBox()
        self.exit_sp.setRange(1, 8)
        self.exit_sp.setValue(len(self.widg.exit))
        if self.widg.can_set_exit():
            self.exit_sp.valueChanged.connect(self.set_exit)
        else:
            self.exit_sp.setEnabled(False)
        exit_lay.addWidget(self.exit_sp)
        main_lay.addLayout(exit_lay)

        delay_lay = QHBoxLayout()
        delay_lay.addWidget(QLabel("Delay (ms):"))
        self.delay_sp = QSpinBox()
        self.delay_sp.setRange(0, 10000)
        self.delay_sp.setValue(self.widg.delay_ms)
        self.delay_sp.valueChanged.connect(self.set_delay)
        delay_lay.addWidget(self.delay_sp)
        main_lay.addLayout(delay_lay)

        btn_lay = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_lay.addWidget(ok_btn)
        btn_lay.addWidget(cancel_btn)
        main_lay.addLayout(btn_lay)

        self.setLayout(main_lay)

    def set_enter(self, val):
        self.widg.set_enter(val)

    def set_exit(self, val):
        self.widg.set_exit(val)

    def set_delay(self, val):
        self.widg.set_delay(val)
