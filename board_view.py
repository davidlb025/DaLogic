from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor


class BoardView(QGraphicsView):
    GRID_SIZE = 50
    GRID_X =  100
    GRID_Y = 100
    MAP_WIDTH = GRID_SIZE * GRID_X
    MAP_HEIGHT = GRID_SIZE* GRID_Y
    # Límites de zoom
    MIN_ZOOM = 0.20  # 25% del tamaño original
    MAX_ZOOM = 4.0   # 400% del tamaño original

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)

        # El grid empieza en (0, 0) y termina en el max
        self.scene.setSceneRect(QRectF(0, 0, self.MAP_WIDTH, self.MAP_HEIGHT))
        self.setScene(self.scene)

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

        # zoom actual
        self.zoom_act = 1.0

        # Centrar
        self.centerOn(self.MAP_WIDTH / 2, self.MAP_HEIGHT / 2)

    def drawBackground(self, painter, rect):
        """Dibuja la cuadrícula alineada con el grid real"""
        super().drawBackground(painter, rect)

        pen = QPen(QColor(205,205,205))
        pen.setWidth(1)
        pen.setCosmetic(True)
        painter.setPen(pen)

        start_x = 0
        end_x = self.MAP_WIDTH
        start_y = 0
        end_y = self.MAP_HEIGHT

        # arr-abaj
        x = start_x
        while x <= end_x:
            painter.drawLine(x, start_y, x, end_y)
            x += self.GRID_SIZE

        # izq-der
        y = start_y
        while y <= end_y:
            painter.drawLine(start_x, y, end_x, y)
            y += self.GRID_SIZE

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

    def ajustar(self, pos: QPointF) -> QPointF:
        x = round(pos.x() / self.GRID_SIZE) * self.GRID_SIZE
        y = round(pos.y() / self.GRID_SIZE) * self.GRID_SIZE
        return QPointF(x, y)

    def grid_pos(self, pos: QPointF) -> tuple[int, int]:
        return (
            int(pos.x() // self.GRID_SIZE),
            int(pos.y() // self.GRID_SIZE)
        )

    def get_grid_num(self) -> tuple[int, int]:
        return (
            self.MAP_WIDTH // self.GRID_SIZE,
            self.MAP_HEIGHT // self.GRID_SIZE
        )
