from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem
from PySide6.QtCore import Qt, QRectF, QPointF, QEvent
from PySide6.QtGui import QPainter, QPen, QColor, QMouseEvent,QBrush
from PySide6.QtSvgWidgets import QGraphicsSvgItem

from widgets import *

class BoardView(QGraphicsView):
    MAP_WIDTH = 4000
    MAP_HEIGHT = 4000

    MIN_ZOOM = 0.20  # 25%
    MAX_ZOOM = 4.0   # 400%

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)

        self.scene.setSceneRect(QRectF(0, 0, self.MAP_WIDTH, self.MAP_HEIGHT))
        self.setScene(self.scene)

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.center_grid_point()
        self.last_drag_mode = self.dragMode()

        self.zoom_act = 1.0

    def center_grid_point(self):
            x = self.MAP_WIDTH / 2
            y = self.MAP_HEIGHT / 2
            radius = 5



            pen = QPen(QColor(128, 128, 128))
            pen.setWidth(0.5)

            v_line = QGraphicsLineItem(x, -self.MAP_HEIGHT*100, x, self.MAP_HEIGHT*100)
            v_line.setPen(pen)
            #self.scene.addItem(v_line)

            h_line = QGraphicsLineItem(-self.MAP_WIDTH*100, y, self.MAP_WIDTH*100, y)
            h_line.setPen(pen)
            #self.scene.addItem(h_line)

            point = QGraphicsEllipseItem(
                x - radius,
                y - radius,
                radius * 2,
                radius * 2
            )

            point.setBrush(QBrush(QColor(255, 0, 0)))
            point.setPen(QPen(QColor(255, 0, 0)))
            self.scene.addItem(point)

            
    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.last_drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            fake_event = QMouseEvent(
                QEvent.MouseButtonPress,
                event.pos(),
                Qt.LeftButton,
                Qt.LeftButton,
                event.modifiers()
            )
            super().mousePressEvent(fake_event)
            return

        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())

            if not item:
                self.scene.clearSelection()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
            if event.button() == Qt.MiddleButton:
                fake_event = QMouseEvent(
                    QEvent.MouseButtonRelease,
                    event.pos(),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    event.modifiers()
                )
                super().mouseReleaseEvent(fake_event)

                self.setDragMode(self.last_drag_mode)
                return

            super().mouseReleaseEvent(event)
    def wheelEvent(self, event):
        zoom_factor = 1.25

        if event.angleDelta().y() > 0:
            # in
            new_zoom = self.zoom_act * zoom_factor
            if new_zoom <= self.MAX_ZOOM:
                self.scale(zoom_factor, zoom_factor)
                self.zoom_act = new_zoom
        else:
            # out
            new_zoom = self.zoom_act / zoom_factor
            if new_zoom >= self.MIN_ZOOM:
                self.scale(1 / zoom_factor, 1 / zoom_factor)
                self.zoom_act = new_zoom
