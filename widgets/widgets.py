from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QGraphicsItem, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QColor
import os


from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor
from PySide6.QtSvgWidgets import QGraphicsSvgItem


class Widget():

    def __init__(self,id,graphic=None):
        self.id = id
        self.graphic = graphic
        self.enter = []
        self.exit = []
        self.destino = {}
        self.add_exit = True
        self.add_enter = True
        self.delay_ms = 0

    def set_delay(self, ms):
        self.delay_ms = max(0, int(ms))

    def get_changed_exits(self):
        old_dest = self.destino.copy()
        self.logic()
        for k in self.destino:
            self.destino[k] = self.exit[0]
        changed = {k:v for k,v in self.destino.items() if old_dest[k] != v}
        return changed

    def logic(self,):
        pass

    def set_enter(self,num):
        if self.add_enter:
            self.enter = [0 for i in range(1,num+1)]

    def set_exit(self,num):
        if self.add_exit:
            dst = [k for k,v in self.destino.values()]
            self.exit = [0 for i in range(1,num+1)]
            self.destino = {}
            return dst


    def can_set_enter(self):
        return self.add_enter
    def can_set_exit(self):
        return self.add_exit

    def add_destino(self,id,exit_id):
        self.destino[id] = self.exit[exit_id]

    def change_enter(self,id,value):
        if not self.enter[id] == value:
            self.enter[id] = value
            return self.get_changed_exits()
        else:
            return None

class AND(Widget):

    def __init__(self,id):
        super().__init__(id)
        self.enter = [0,0]
        self.exit = [0]
        self.add_exit = False
        self.add_enter = True

    def logic(self,):
        val = self.enter
        if val and all(v == val[0] for v in val):
            self.exit[0] = True
        else:
            self.exit[0] = False



