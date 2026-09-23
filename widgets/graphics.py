"""
graphics.py  –  Representación visual: Graphic, Port, Wire, ConfigDialog.
"""

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem,
    QGraphicsRectItem, QGraphicsEllipseItem as QGEllipse,
    QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGraphicsTextItem, QGroupBox, QScrollArea, QWidget, QFileDialog,
    QMessageBox, QColorDialog
)
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath, QFont, QPainter
import json
import math
from pathlib import Path


_LANGUAGE_TRANSLATIONS = {}


def set_language_translations(translations):
    global _LANGUAGE_TRANSLATIONS
    _LANGUAGE_TRANSLATIONS = dict(translations or {})


def translate_text(text):
    return _LANGUAGE_TRANSLATIONS.get(text, text)

# ── Colores ───────────────────────────────────────────────────────────────────
COLOR_PORT_IN_OFF  = QColor(105, 135, 245)
COLOR_PORT_IN_ON   = QColor(73, 213, 151)
COLOR_PORT_OUT_OFF = QColor(239, 139, 126)
COLOR_PORT_OUT_ON  = QColor(255, 205, 105)
COLOR_WIRE_OFF     = QColor(126, 145, 166)
COLOR_WIRE_ON      = QColor(73, 213, 151)
COLOR_WIRE_SEL     = QColor(255, 178, 91)

PORT_RADIUS = 6
BRIDGE_HALF_GAP = 6.0


def _unit_vector(vector: QPointF) -> QPointF:
    length = math.hypot(vector.x(), vector.y())
    return QPointF(vector.x() / length, vector.y() / length) if length else QPointF(1, 0)


def _bridge_curve(start: QPointF, incoming: QPointF,
                  end: QPointF, outgoing: QPointF,
                  opposite_side: bool = False) -> QPainterPath:
    """Build an arch whose ends and opening follow the adjoining cable legs."""
    normal_in = QPointF(-incoming.y(), incoming.x())
    normal_out = QPointF(-outgoing.y(), outgoing.x())
    normal = _unit_vector(normal_in + normal_out)
    if normal.y() > 0:
        normal = normal * -1
    if opposite_side:
        normal = normal * -1
    dot = max(-1.0, min(1.0, incoming.x() * outgoing.x() + incoming.y() * outgoing.y()))
    turn = math.acos(dot)
    height = BRIDGE_HALF_GAP * (0.72 + 0.22 * turn / math.pi)
    control = BRIDGE_HALF_GAP * 0.55
    first_control = start + incoming * control + normal * height
    second_control = end - outgoing * control + normal * height
    path = QPainterPath(start)
    path.cubicTo(first_control, second_control, end)
    return path


# ── Port ─────────────────────────────────────────────────────────────────────

class Port(QGraphicsEllipseItem):
    def __init__(self, graphic: "Graphic", port_index: int, is_input: bool):
        r = PORT_RADIUS
        super().__init__(-r, -r, r * 2, r * 2)

        self.graphic    = graphic
        self.port_index = port_index
        self.is_input   = is_input
        self.update_tooltip()

        self.setZValue(3)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable,    False)

        self.update_color()

    def update_tooltip(self):
        from widgets.widgets import Module
        kind = translate_text("Entrada" if self.is_input else "Salida")
        if isinstance(self.graphic.widg, Module):
            numbers = (self.graphic.widg.input_numbers if self.is_input
                       else self.graphic.widg.output_numbers)
            number = numbers[self.port_index] if self.port_index < len(numbers) else self.port_index
            self.setToolTip(f"{kind} {number} · {self.graphic.widg.name}")
        else:
            widget = self.graphic.widg
            self.setToolTip(f"{kind} {self.port_index} · {type(widget).__name__} {widget.id}")

    def update_color(self):
        widg = self.graphic.widg
        if self.is_input:
            val = widg.enter[self.port_index] if self.port_index < len(widg.enter) else False
            col = COLOR_PORT_IN_ON if val else COLOR_PORT_IN_OFF
        else:
            val = widg.exit[self.port_index] if self.port_index < len(widg.exit) else False
            col = COLOR_PORT_OUT_ON if val else COLOR_PORT_OUT_OFF

        self.setBrush(QBrush(col))
        self.setPen(QPen(col.darker(150), 1))

    def hoverEnterEvent(self, e):
        self.setPen(QPen(QColor(255, 255, 255), 2))
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self.update_color()
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            view = self.scene().views()[0] if self.scene().views() else None
            if view and hasattr(view, "on_port_clicked"):
                view.on_port_clicked(self)
                e.accept()
                return
        super().mousePressEvent(e)


# ── WireEndpoint  (punto flotante — extremo libre de un cable) ─────────────────

class WireEndpoint(QGraphicsEllipseItem):
    """Círculo hueco que representa un extremo de cable no conectado a ningún puerto."""
    R = 5

    def __init__(self, pos: QPointF):
        r = self.R
        super().__init__(-r, -r, r * 2, r * 2)
        self.setPos(pos)
        self.setZValue(3)
        self.setFlag(QGraphicsItem.ItemIsMovable,    True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)
        self._wires: list["Wire"] = []
        self._apply_style()

    def _apply_style(self):
        self.setBrush(QBrush(Qt.NoBrush))
        self.setPen(QPen(COLOR_WIRE_OFF, 1.8))

    def set_active(self, on: bool):
        col = COLOR_WIRE_ON if on else COLOR_WIRE_OFF
        self.setPen(QPen(col, 1.8))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for w in self._wires:
                w.update_path()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, e):
        self.setPen(QPen(QColor(255, 255, 255), 2))
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self._apply_style()
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view and hasattr(view, "on_endpoint_clicked"):
                view.on_endpoint_clicked(self)
                e.accept()
                return
        super().mousePressEvent(e)

    def scenePos(self):
        return super().scenePos()


# ── MidPoint  (vértice arrastrable en mitad de un cable) ──────────────────────

class MidPoint(QGraphicsEllipseItem):
    """Punto intermedio de un Wire — se puede arrastrar para doblar el cable."""
    R = 4

    def __init__(self, wire: "Wire", index: int, pos: QPointF, bridge: bool = False,
                 bridge_mode: int | None = None):
        r = self.R
        super().__init__(-r, -r, r * 2, r * 2)
        self.wire  = wire
        self.index = index          # posición en wire._mid_pts
        self.bridge_mode = self._normalize_bridge_mode(
            bridge_mode if bridge_mode is not None else (1 if bridge else 0))
        self.setPos(pos)
        self.setZValue(4)
        self.setFlag(QGraphicsItem.ItemIsMovable,    True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.SizeAllCursor)
        self._update_bridge_tooltip()
        self._apply_style(False)

    @staticmethod
    def _normalize_bridge_mode(mode):
        try:
            value = int(mode)
        except (TypeError, ValueError):
            value = 0
        return value if value in (0, 1, 2) else 0

    @property
    def bridge(self):
        return self.bridge_mode != 0

    @bridge.setter
    def bridge(self, value):
        self.bridge_mode = 1 if value else 0

    def _update_bridge_tooltip(self):
        messages = (
            "Nexo · doble clic para cambiar a Puente",
            "Puente · doble clic para cambiar al otro lado",
            "Puente hacia el otro lado · doble clic para volver a empezar",
        )
        self.setToolTip(translate_text(messages[self.bridge_mode]))

    def boundingRect(self):
        if self.bridge:
            return QRectF(-14, -14, 28, 28)
        return super().boundingRect()

    def paint(self, painter, option, widget=None):
        if not self.bridge:
            super().paint(painter, option, widget)
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.wire.pen())
        pen.setWidthF(self.wire.pen().widthF())
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        points = self.wire._all_points()
        if len(points) >= 3:
            node = points[self.index + 1]
            incoming = _unit_vector(node - points[self.index])
            outgoing = _unit_vector(points[self.index + 2] - node)
            start = QPointF(-incoming.x() * BRIDGE_HALF_GAP,
                            -incoming.y() * BRIDGE_HALF_GAP)
            end = QPointF(outgoing.x() * BRIDGE_HALF_GAP,
                          outgoing.y() * BRIDGE_HALF_GAP)
            painter.drawPath(_bridge_curve(start, incoming, end, outgoing,
                                           opposite_side=self.bridge_mode == 2))

    def toggle_bridge(self):
        self.prepareGeometryChange()
        self.bridge_mode = (self.bridge_mode + 1) % 3
        self._update_bridge_tooltip()
        self.wire.update_path()
        self.update()

    def _apply_style(self, hover: bool):
        col = QColor(255, 255, 255) if hover else QColor(180, 180, 180)
        self.setBrush(QBrush(col))
        self.setPen(QPen(QColor(80, 80, 80), 1))
        self.update()

    def set_active(self, on: bool):
        col = COLOR_WIRE_ON if on else QColor(180, 180, 180)
        self.setBrush(QBrush(col))
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.wire.update_path()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, e):
        self._apply_style(True)
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self._apply_style(False)
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        # Clic derecho → eliminar este punto medio
        if e.button() == Qt.RightButton:
            self.wire._remove_midpoint(self)
            e.accept()
            return
        super().mousePressEvent(e)


# ── Junction  (nodo de unión entre varios cables) ─────────────────────────────

class Junction(QGraphicsEllipseItem):
    """Punto de unión donde confluyen ≥2 cables. Actúa como router lógico."""
    R = 5

    def __init__(self, pos: QPointF, bridge: bool = False,
                 bridge_mode: int | None = None):
        r = self.R
        super().__init__(-r, -r, r * 2, r * 2)
        self.setPos(pos)
        self.setZValue(5)
        self.setFlag(QGraphicsItem.ItemIsMovable,    True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)
        self._wires: list["Wire"] = []
        self._on = False
        self.bridge_mode = MidPoint._normalize_bridge_mode(
            bridge_mode if bridge_mode is not None else (1 if bridge else 0))
        self._update_bridge_tooltip()
        self._apply_style()

    @property
    def bridge(self):
        return self.bridge_mode != 0

    @bridge.setter
    def bridge(self, value):
        self.bridge_mode = 1 if value else 0

    def _update_bridge_tooltip(self):
        messages = (
            "Nexo · doble clic para cambiar a Puente",
            "Puente · doble clic para cambiar al otro lado",
            "Puente hacia el otro lado · doble clic para volver a empezar",
        )
        self.setToolTip(translate_text(messages[self.bridge_mode]))

    def boundingRect(self):
        return QRectF(-10, -11, 20, 18)

    def _bridge_directions(self):
        directions = []
        for wire in self._wires:
            points = wire._all_points()
            if len(points) < 2:
                continue
            if wire.src_port is self:
                direction = points[1] - points[0]
            elif wire.dst_port is self:
                direction = points[-2] - points[-1]
            else:
                continue
            if direction.x() or direction.y():
                directions.append((wire, _unit_vector(direction)))
        if len(directions) < 2:
            return directions
        best_pair = None
        best_dot = float("inf")
        for i, (wire_a, dir_a) in enumerate(directions):
            for wire_b, dir_b in directions[i + 1:]:
                dot = dir_a.x() * dir_b.x() + dir_a.y() * dir_b.y()
                if dot < best_dot:
                    best_dot, best_pair = dot, [(wire_a, dir_a), (wire_b, dir_b)]
        return best_pair or directions[:1]

    def _bridge_wires(self):
        return {wire for wire, _direction in self._bridge_directions()}

    def _bridge_path(self):
        pair = self._bridge_directions()
        if len(pair) >= 2:
            _wire_a, dir_a = pair[0]
            _wire_b, dir_b = pair[1]
        elif pair:
            _wire_a, dir_a = pair[0]
            dir_b = QPointF(-dir_a.x(), -dir_a.y())
        else:
            dir_a, dir_b = QPointF(-1, 0), QPointF(1, 0)
        start_direction = QPointF(-dir_a.x(), -dir_a.y())
        start = dir_a * BRIDGE_HALF_GAP
        end = dir_b * BRIDGE_HALF_GAP
        return _bridge_curve(start, start_direction, end, dir_b,
                             opposite_side=self.bridge_mode == 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.bridge:
            pen = QPen(self._wires[0].pen()) if self._wires else QPen(self.pen())
            pen.setWidthF(self._wires[0].pen().widthF() if self._wires else 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._bridge_path())
        else:
            painter.setPen(self.pen())
            painter.setBrush(self.brush())
            painter.drawEllipse(self.rect())

    def _apply_style(self):
        col = COLOR_WIRE_ON if self._on else COLOR_WIRE_OFF
        self.setBrush(QBrush(col))
        self.setPen(QPen(col.darker(150), 1))
        self.update()

    def set_active(self, on: bool):
        if self._on != on:
            self._on = on
            self._apply_style()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for w in self._wires:
                w.update_path()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, e):
        self.setPen(QPen(QColor(255, 255, 255), 2))
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self._apply_style()
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view and hasattr(view, "on_junction_clicked"):
                view.on_junction_clicked(self)
                e.accept()
                return
        super().mousePressEvent(e)

    def toggle_bridge(self):
        self.bridge_mode = (self.bridge_mode + 1) % 3
        self._update_bridge_tooltip()
        for wire in self._wires:
            wire.update_path()
        self.update()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            views = self.scene().views() if self.scene() else []
            if views and getattr(views[0], "_drawing_wire", None) is not None:
                views[0]._cancel_drawing()
            self.toggle_bridge()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)


# ── Wire ──────────────────────────────────────────────────────────────────────

class Wire(QGraphicsPathItem):
    """
    Cable recto con vértices intermedios arrastrables (MidPoints).

    Extremos:
      src  →  Port | Junction | WireEndpoint
      dst  →  Port | Junction | WireEndpoint | None (en construcción)
    """

    def __init__(self, src, dst=None, mid_pts: list[QPointF] | None = None,
                 midpoint_bridges: list[int] | None = None, custom_color=None):
        super().__init__()

        self.src_port = src   # puede ser Port, Junction o WireEndpoint
        self.dst_port = dst   # puede ser Port, Junction, WireEndpoint o None

        self._mid_pts:  list[MidPoint] = []
        self._pending_mid: list[QPointF] = mid_pts or []
        self._pending_mid_bridges = midpoint_bridges or []
        color = QColor(custom_color) if custom_color else QColor()
        self.custom_color = color if color.isValid() else None

        # Registrar en extremos
        self._register(src)
        if dst is not None:
            self._register(dst)

        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setToolTip(translate_text("Clic derecho para cambiar el color del cable"))

        self._on = False
        self._update_pen()
        self.update_path()

    # ── extremos ─────────────────────────────────────────────────────────────

    def _register(self, ep):
        if ep is None:
            return
        if isinstance(ep, Port):
            ep.graphic.wires.append(self)
        elif isinstance(ep, (Junction, WireEndpoint)):
            ep._wires.append(self)

    def _unregister(self, ep):
        if ep is None:
            return
        if isinstance(ep, Port):
            if self in ep.graphic.wires:
                ep.graphic.wires.remove(self)
        elif isinstance(ep, (Junction, WireEndpoint)):
            if self in ep._wires:
                ep._wires.remove(self)

    # ── puntos medios ─────────────────────────────────────────────────────────

    def _build_midpoints(self):
        """Crear MidPoint items para los puntos pendientes (llamado al entrar en escena)."""
        scene = self.scene()
        if not scene:
            return
        for index, pos in enumerate(self._pending_mid):
            bridge = (self._pending_mid_bridges[index]
                      if index < len(self._pending_mid_bridges) else False)
            mp = MidPoint(self, len(self._mid_pts), pos, bridge_mode=bridge)
            scene.addItem(mp)
            self._mid_pts.append(mp)
        self._pending_mid = []
        self._pending_mid_bridges = []
        self._reindex_midpoints()
        self.update_path()

    def _reindex_midpoints(self):
        for i, mp in enumerate(self._mid_pts):
            mp.index = i

    def insert_midpoint(self, pos: QPointF, index: int | None = None):
        """Insertar un nuevo MidPoint en la posición dada (o al final)."""
        scene = self.scene()
        if not scene:
            return
        if index is None:
            index = len(self._mid_pts)
        mp = MidPoint(self, index, pos)
        scene.addItem(mp)
        self._mid_pts.insert(index, mp)
        self._reindex_midpoints()
        self.update_path()

    def _remove_midpoint(self, mp: MidPoint):
        scene = self.scene()
        if scene and mp.scene():
            scene.removeItem(mp)
        if mp in self._mid_pts:
            self._mid_pts.remove(mp)
        self._reindex_midpoints()
        self.update_path()

    def _pt(self, ep) -> QPointF | None:
        if ep is None:
            return None
        return ep.scenePos()

    # ── apariencia ────────────────────────────────────────────────────────────

    def _update_pen(self):
        if self.isSelected():
            col, w = COLOR_WIRE_SEL, 3
        elif self.custom_color is not None:
            col = self.custom_color.lighter(125) if self._on else self.custom_color
            w = 2 if self._on else 1.5
        elif self._on:
            col, w = COLOR_WIRE_ON, 2
        else:
            col, w = COLOR_WIRE_OFF, 1.5
        self.setPen(QPen(col, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for midpoint in getattr(self, "_mid_pts", []):
            midpoint.update()
        for endpoint in (getattr(self, "src_port", None), getattr(self, "dst_port", None)):
            if isinstance(endpoint, Junction) and endpoint.bridge:
                endpoint.update()

    def set_custom_color(self, color: QColor | None):
        self.custom_color = QColor(color) if color is not None and color.isValid() else None
        self._update_pen()
        self.update()

    def show_color_editor(self):
        parent = self.scene().views()[0].window() if self.scene() and self.scene().views() else None
        dialog = QColorDialog(self.custom_color or QColor(COLOR_WIRE_OFF), parent)
        dialog.setWindowTitle("Color del cable")
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_custom_color(dialog.currentColor())

    def set_active(self, on: bool):
        if self._on != on:
            self._on = on
            self._update_pen()
            for mp in self._mid_pts:
                mp.set_active(on)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSceneHasChanged and self.scene():
            self._build_midpoints()
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._update_pen()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, e):
        pen = self.pen()
        pen.setWidthF(pen.widthF() + 1)
        self.setPen(pen)
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self._update_pen()
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.show_color_editor()
            e.accept()
            return
        if e.button() == Qt.LeftButton:
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view and hasattr(view, "on_wire_clicked"):
                # Insertar punto medio donde se clicó
                pos = e.scenePos()
                idx = self._closest_segment(pos)
                view.on_wire_clicked(self, pos, idx)
                e.accept()
                return
        super().mousePressEvent(e)

    def _closest_segment(self, pos: QPointF) -> int:
        """Devuelve el índice de inserción del punto medio más cercano al click."""
        pts = self._all_points()
        best_idx, best_d = 1, float("inf")
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            d = self._dist_point_segment(pos, a, b)
            if d < best_d:
                best_d = d
                best_idx = i + 1  # insertar DESPUÉS del punto i
        # best_idx - 1 porque _mid_pts no incluye src
        return max(0, best_idx - 1)

    @staticmethod
    def _dist_point_segment(p: QPointF, a: QPointF, b: QPointF) -> float:
        import math
        ab = b - a
        ab2 = ab.x()**2 + ab.y()**2
        if ab2 == 0:
            return math.hypot(p.x() - a.x(), p.y() - a.y())
        t = max(0, min(1, ((p.x()-a.x())*ab.x() + (p.y()-a.y())*ab.y()) / ab2))
        proj = a + t * ab
        return math.hypot(p.x() - proj.x(), p.y() - proj.y())

    # ── geometría ─────────────────────────────────────────────────────────────

    def _all_points(self) -> list[QPointF]:
        pts = []
        if (p := self._pt(self.src_port)) is not None:
            pts.append(p)
        for mp in self._mid_pts:
            pts.append(mp.scenePos())
        if self.dst_port is not None:
            if (p := self._pt(self.dst_port)) is not None:
                pts.append(p)
        return pts

    def update_path(self, preview_end: QPointF | None = None):
        pts = self._all_points()
        if preview_end is not None:
            pts.append(preview_end)
        if len(pts) < 2:
            self.setPath(QPainterPath())
            return

        midpoint_bridges = {index + 1 for index, midpoint in enumerate(self._mid_pts)
                            if midpoint.bridge}
        junction_notches = set()
        if isinstance(self.src_port, Junction) and self.src_port.bridge:
            junction_notches.add(0)
        if isinstance(self.dst_port, Junction) and self.dst_port.bridge:
            junction_notches.add(len(pts) - 1)

        path = QPainterPath()
        last_end = None
        for index, (a, b) in enumerate(zip(pts, pts[1:])):
            delta = b - a
            length = math.hypot(delta.x(), delta.y())
            if not length:
                continue
            gap_start = (BRIDGE_HALF_GAP
                         if index in midpoint_bridges or index in junction_notches else 0.0)
            gap_end = (BRIDGE_HALF_GAP
                       if index + 1 in midpoint_bridges or index + 1 in junction_notches else 0.0)
            if gap_start + gap_end >= length:
                continue
            start_t = gap_start / length
            end_t = 1.0 - gap_end / length
            start = a + delta * start_t
            end = a + delta * end_t
            if last_end is None or math.hypot(last_end.x() - start.x(),
                                              last_end.y() - start.y()) > 0.01:
                path.moveTo(start)
            else:
                path.lineTo(start)
            path.lineTo(end)
            last_end = end
        self.setPath(path)
        for midpoint in self._mid_pts:
            if midpoint.bridge:
                midpoint.update()
        for endpoint in (self.src_port, self.dst_port):
            if isinstance(endpoint, Junction) and endpoint.bridge:
                endpoint.update()

    def shape(self):
        from PySide6.QtGui import QPainterPathStroker
        ps = QPainterPathStroker()
        ps.setWidth(12)
        return ps.createStroke(self.path())

    # ── limpieza ──────────────────────────────────────────────────────────────

    def remove_from_scene(self):
        scene = self.scene()
        self._unregister(self.src_port)
        self._unregister(self.dst_port)
        for mp in list(self._mid_pts):
            if scene and mp.scene():
                scene.removeItem(mp)
        self._mid_pts.clear()
        if scene:
            scene.removeItem(self)


# ── Graphic ───────────────────────────────────────────────────────────────────

class Graphic(QGraphicsItem):
    SVG_W = 100
    SVG_H = 100

    def __init__(self, widg, svg_path: str = None, scale: float = 0.2):
        QGraphicsItem.__init__(self)

        self.widg  = widg
        self.wires: list[Wire] = []

        widg.graphic = self

        self.setScale(scale)
        self.setZValue(1)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

        self._ports_in:  list[Port] = []
        self._ports_out: list[Port] = []

    def paint(self, painter, option, widget=None):
        pass

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSceneHasChanged:
            if self.scene():
                self.rebuild_ports()
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._reposition_ports()
            for w in self.wires:
                w.update_path()
        return super().itemChange(change, value)

    def rebuild_ports(self):
        scene = self.scene()
        if not scene:
            return
        self.prepareGeometryChange()

        # Conserva los puertos existentes al cambiar el número. Así los
        # cables ya conectados siguen apuntando al mismo objeto Port.
        for ports, count, is_input in (
                (self._ports_in, len(self.widg.enter), True),
                (self._ports_out, len(self.widg.exit), False)):
            while len(ports) > count:
                port = ports.pop()
                for wire in list(self.wires):
                    if wire.src_port is port or wire.dst_port is port:
                        wire.remove_from_scene()
                scene.removeItem(port)
            while len(ports) < count:
                port = Port(self, len(ports), is_input=is_input)
                scene.addItem(port)
                ports.append(port)

        self._reposition_ports()
        for wire in list(self.wires):
            wire.update_path()

    def _reposition_ports(self):
        bRect  = self.boundingRect()
        scale  = self.scale()
        origin = self.scenePos()

        w = bRect.width()  * scale
        h = bRect.height() * scale

        n_in = len(self._ports_in)
        for i, p in enumerate(self._ports_in):
            y = h * (i + 1) / (n_in + 1)
            p.setPos(origin + QPointF(0, y))

        n_out = len(self._ports_out)
        for i, p in enumerate(self._ports_out):
            y = h * (i + 1) / (n_out + 1)
            p.setPos(origin + QPointF(w, y))

    def update_port_color(self, idx: int, is_input: bool):
        """Actualiza solo el puerto indicado y los wires que salen de ÉL."""
        ports = self._ports_in if is_input else self._ports_out
        if 0 <= idx < len(ports):
            ports[idx].update_color()

        if not is_input:
            for w in self.wires:
                src = w.src_port
                if isinstance(src, Port) and not src.is_input and src.port_index == idx and src.graphic is self:
                    val = self.widg.exit[idx] if idx < len(self.widg.exit) else False
                    w.set_active(bool(val))

    def update_all_output_wires(self):
        """Refresca el color de TODOS los wires de salida según el estado actual."""
        for w in self.wires:
            src = w.src_port
            if isinstance(src, Port) and not src.is_input and src.graphic is self:
                out_idx = src.port_index
                val = self.widg.exit[out_idx] if out_idx < len(self.widg.exit) else False
                w.set_active(bool(val))

    def update_switch_look(self):
        self.update_port_color(0, is_input=False)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.show_config()
            e.accept()
            return
        from widgets.widgets import Button
        if e.button() == Qt.LeftButton and isinstance(self.widg, Button):
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                self.widg.press(view.board_ref)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        from widgets.widgets import Button
        if e.button() == Qt.LeftButton and isinstance(self.widg, Button):
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                self.widg.release(view.board_ref)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        from widgets.widgets import Switch, Button
        if e.button() == Qt.LeftButton:
            if isinstance(self.widg, Button):
                e.accept()
                return
            if isinstance(self.widg, Switch):
                view = self.scene().views()[0] if self.scene().views() else None
                if view and hasattr(view, "board_ref"):
                    self.widg.toggle(view.board_ref)
                e.accept()
                return
            self.show_config()
        super().mouseDoubleClickEvent(e)

    def show_config(self):
        dlg = ConfigDialog(self)
        dlg.exec()

    def remove_from_scene(self):
        scene = self.scene()
        if not scene:
            return
        for p in self._ports_in + self._ports_out:
            scene.removeItem(p)
        scene.removeItem(self)


class LogicGateGraphic(Graphic):
    """Símbolos vectoriales consistentes para puertas, interruptor y retardo."""

    def __init__(self, widg):
        super().__init__(widg, svg_path=None, scale=1.0)

    def _reposition_ports(self):
        origin = self.scenePos()
        self._position_logic_ports(self._ports_in, True, origin)
        self._position_logic_ports(self._ports_out, False, origin)

    def boundingRect(self):
        if len(self._ports_in) > 6 or len(self._ports_out) > 6:
            return QRectF(-114, -58, 228, 116)
        return QRectF(-62, -42, 124, 84)

    @staticmethod
    def _position_logic_ports(ports, is_input, origin):
        count = len(ports)
        if count > 6:
            split = (count + 1) // 2
            for index, port in enumerate(ports):
                column = 0 if index < split else 1
                row = index if column == 0 else index - split
                rows = split if column == 0 else count - split
                y = -42 + 84 * (row + 1) / (rows + 1)
                x = (-84 if column == 0 else -64) if is_input else (84 if column == 0 else 64)
                port.setPos(origin + QPointF(x, y))
            return
        x = -58 if is_input else 58
        for index, port in enumerate(ports):
            y = -28 + 56 * (index + 1) / (count + 1)
            port.setPos(origin + QPointF(x, y))

    def paint(self, painter: QPainter, option, widget=None):
        kind = type(self.widg).__name__.upper()
        is_switch = kind == "SWITCH"
        is_delay = kind == "DELAY"
        is_button = kind == "BUTTON"
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        dark = bool(view and getattr(view, "theme_mode", "dark") == "dark")
        if dark:
            accent, fill, label_color = QColor(116, 174, 248), QColor(36, 50, 68), QColor(239, 245, 252)
            bubble_fill = QColor(36, 50, 68)
        else:
            accent, fill, label_color = QColor(53, 105, 177), QColor(242, 247, 253), QColor(31, 47, 66)
            bubble_fill = QColor(242, 247, 253)
        if is_switch:
            if self.widg.state:
                fill, accent = (QColor(27, 83, 62), QColor(112, 231, 172)) if dark else (QColor(220, 246, 230), QColor(37, 126, 82))
            else:
                fill, accent = (QColor(48, 61, 78), QColor(174, 190, 208)) if dark else (QColor(237, 241, 246), QColor(105, 121, 141))
        elif is_delay:
            fill, accent = (QColor(57, 43, 80), QColor(204, 170, 255)) if dark else (QColor(242, 234, 252), QColor(121, 83, 169))
        elif is_button:
            if self.widg.state:
                fill, accent = (QColor(98, 59, 34), QColor(255, 190, 130)) if dark else (QColor(255, 238, 222), QColor(168, 91, 37))
            else:
                fill, accent = (QColor(55, 45, 41), QColor(230, 174, 137)) if dark else (QColor(250, 244, 239), QColor(168, 111, 75))

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(accent, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QBrush(fill))

        if is_switch or is_delay or is_button:
            painter.drawRoundedRect(QRectF(-44, -26, 88, 52), 12, 12)
            if is_switch:
                painter.setPen(QPen(QColor(238, 247, 255), 2.5, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(-20, 12, 18 if self.widg.state else -2, -12)
                painter.setBrush(QBrush(accent))
                painter.drawEllipse(QPointF(20 if self.widg.state else -20, 0), 7, 7)
            else:
                painter.setPen(QPen(QColor(238, 225, 255), 2.3, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(-22, 0, 16, 0)
                painter.drawLine(8, -8, 18, 0)
                painter.drawLine(8, 8, 18, 0)
                if is_button:
                    painter.setPen(QPen(accent, 1.5))
                    painter.setBrush(QBrush(accent))
                    painter.drawEllipse(QPointF(0, 0), 14 if self.widg.state else 12,
                                        14 if self.widg.state else 12)
        elif kind == "NOT":
            path = QPainterPath(QPointF(-42, -30))
            path.lineTo(26, 0); path.lineTo(-42, 30); path.closeSubpath()
            painter.drawPath(path)
            painter.setBrush(QBrush(bubble_fill))
            painter.drawEllipse(QPointF(36, 0), 9, 9)
        else:
            # Cuerpo de AND/NAND o de OR/NOR/XOR, construido como path para
            # conservar una silueta limpia a cualquier escala.
            if kind in ("AND", "NAND"):
                path = QPainterPath(QPointF(-46, -30))
                path.lineTo(3, -30)
                path.cubicTo(57, -30, 57, 30, 3, 30)
                path.lineTo(-46, 30); path.closeSubpath()
            else:
                path = QPainterPath(QPointF(-48, -30))
                path.cubicTo(-15, -28, 3, -18, 37, 0)
                path.cubicTo(3, 18, -15, 28, -48, 30)
                path.cubicTo(-30, 12, -30, -12, -48, -30)
                path.closeSubpath()
            painter.drawPath(path)
            if kind == "XOR":
                painter.setBrush(QBrush(Qt.NoBrush))
                painter.drawArc(QRectF(-59, -30, 42, 60), -55 * 16, 110 * 16)
            if kind in ("NAND", "NOR"):
                painter.setBrush(QBrush(bubble_fill))
                painter.drawEllipse(QPointF(46, 0), 8, 8)

        if is_switch:
            label = "ON" if self.widg.state else "OFF"
        elif is_delay:
            label = "Δt"
        elif is_button:
            label = translate_text("PULSADO" if self.widg.state else "PULSAR")
        else:
            label = kind
        painter.setPen(QPen(label_color))
        font = QFont()
        font.setBold(True); font.setPointSize(9 if len(label) < 5 else 8)
        painter.setFont(font)
        painter.drawText(QRectF(-31, -9, 62, 18), Qt.AlignCenter, label)
        if self.isSelected():
            painter.setBrush(QBrush(Qt.NoBrush))
            painter.setPen(QPen(QColor(139, 193, 255), 1.4, Qt.DashLine))
            painter.drawRoundedRect(QRectF(-60, -40, 120, 80), 11, 11)

    def update_switch_look(self):
        self.update()


class ModuleGraphic(Graphic):
    """Símbolo vectorial para un circuito guardado como módulo."""

    def __init__(self, widg):
        super().__init__(widg, svg_path=None, scale=1.0)

    def boundingRect(self):
        if len(self.widg.enter) > 6 or len(self.widg.exit) > 6:
            return QRectF(-114, -58, 228, 116)
        return QRectF(-64, -42, 128, 84)

    def paint(self, painter: QPainter, option, widget=None):
        expanded = len(self.widg.enter) > 6 or len(self.widg.exit) > 6
        rect = QRectF(-58, -48, 116, 96) if expanded else QRectF(-58, -36, 116, 72)
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        dark = bool(view and getattr(view, "theme_mode", "dark") == "dark")
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(101, 151, 211) if dark else QColor(55, 105, 169), 2))
        painter.setBrush(QBrush(QColor(36, 50, 68) if dark else QColor(242, 247, 253)))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(QPen(QColor(239, 245, 252) if dark else QColor(31, 47, 66)))
        label_color = QColor(239, 245, 252) if dark else QColor(31, 47, 66)
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(QRectF(-36, rect.top() + 5, 72, rect.height() - 10),
                         Qt.AlignCenter | Qt.TextWordWrap,
                         getattr(self.widg, "name", "Módulo"))
        painter.setPen(QPen(label_color))
        port_font = QFont()
        port_font.setBold(True)
        port_font.setPointSize(7)
        painter.setFont(port_font)
        for is_input, count, numbers in (
                (True, len(self._ports_in), self.widg.input_numbers),
                (False, len(self._ports_out), self.widg.output_numbers)):
            for index in range(count):
                if count > 6:
                    split = (count + 1) // 2
                    column = 0 if index < split else 1
                    row = index if column == 0 else index - split
                    rows = split if column == 0 else count - split
                    y = -42 + 84 * (row + 1) / (rows + 1)
                    if column == 0:
                        label_rect = (QRectF(-112, y - 7, 19, 14) if is_input
                                      else QRectF(93, y - 7, 19, 14))
                    else:
                        label_rect = (QRectF(-56, y - 7, 14, 14) if is_input
                                      else QRectF(42, y - 7, 14, 14))
                else:
                    extent = 42 if expanded else 30
                    y = -extent + 2 * extent * (index + 1) / (count + 1)
                    label_rect = (QRectF(-56, y - 7, 14, 14) if is_input
                                  else QRectF(42, y - 7, 14, 14))
                alignment = Qt.AlignRight | Qt.AlignVCenter if is_input else Qt.AlignLeft | Qt.AlignVCenter
                number = numbers[index] if index < len(numbers) else index
                painter.drawText(label_rect, alignment, str(number))

    def _reposition_ports(self):
        origin = self.scenePos()
        self._position_module_ports(self._ports_in, True, origin)
        self._position_module_ports(self._ports_out, False, origin)

    def _position_module_ports(self, ports, is_input, origin):
        count = len(ports)
        if count > 6:
            split = (count + 1) // 2
            for i, port in enumerate(ports):
                column = 0 if i < split else 1
                row = i if column == 0 else i - split
                rows = split if column == 0 else count - split
                y = -42 + 84 * (row + 1) / (rows + 1)
                x = (-84 if column == 0 else -64) if is_input else (84 if column == 0 else 64)
                port.setPos(origin + QPointF(x, y))
        else:
            x = -64 if is_input else 64
            extent = 42 if len(self.widg.enter) > 6 or len(self.widg.exit) > 6 else 30
            for i, port in enumerate(ports):
                y = -extent + 2 * extent * (i + 1) / (count + 1)
                port.setPos(origin + QPointF(x, y))


# ── BulbGraphic ───────────────────────────────────────────────────────────────

from PySide6.QtWidgets import QGraphicsPathItem as _QGPathItem
from PySide6.QtGui     import QPainterPath as _QPPath, QRadialGradient as _QRGrad

class BulbGraphic(Graphic):
    """Bombilla translúcida con filamento, cuello y base segmentada."""

    # Dimensiones (px, coordenadas locales del item)
    RX       = 26   # radio horizontal del globo
    RY       = 28   # radio vertical del globo
    CX       = 0    # centro X del globo
    CY       = 0    # centro Y del globo (tope)
    NECK_W   = 12   # ancho del cuello
    SEG_H    = 5    # alto de cada franja de la base
    N_SEGS   = 2    # número de franjas
    CONTACT_W = 6
    CONTACT_H = 8

    def __init__(self, widg):
        QGraphicsItem.__init__(self)
        self.widg  = widg
        self.wires: list[Wire] = []
        widg.graphic = self
        self.setToolTip(f"Bombilla {widg.id} · clic derecho para ajustar el retardo")

        self.setZValue(1)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self._ports_in:  list[Port] = []
        self._ports_out: list[Port] = []

        self._glow:     _QGPathItem | None = None
        self._globe:    QGraphicsEllipseItem | None = None
        self._specular: QGraphicsEllipseItem | None = None
        self._filament: _QGPathItem | None = None
        self._neck:     _QGPathItem | None = None
        self._segs:     list = []
        self._contact:  QGraphicsRectItem | None = None
        self._selection_outline: QGraphicsRectItem | None = None

    # ── construcción ─────────────────────────────────────────────────────────

    def _build_shapes(self):
        from PySide6.QtWidgets import QGraphicsPolygonItem, QGraphicsEllipseItem as _E
        rx, ry = self.RX, self.RY
        cx, cy = self.CX, self.CY
        nw     = self.NECK_W
        globe_bottom = cy + ry          # Y donde acaba el globo
        neck_top     = globe_bottom - 4
        neck_bottom  = neck_top + 10
        base_top     = neck_bottom
        seg_h        = self.SEG_H

        # — halo de brillo (detrás de todo) —
        gp = _QPPath()
        gp.addEllipse(QPointF(cx, cy), rx + 18, ry + 18)
        self._glow = _QGPathItem(gp, self)
        self._glow.setZValue(0)
        self._glow.setPen(QPen(Qt.NoPen))

        # — globo principal —
        self._globe = _E(cx - rx, cy - ry, rx * 2, ry * 2, self)
        self._globe.setZValue(2)
        self._globe.setPen(QPen(Qt.NoPen))

        # — reflejo especular (elipse pequeña arriba-izquierda) —
        self._specular = _E(cx - rx * 0.48, cy - ry * 0.60,
                            rx * 0.55, ry * 0.38, self)
        self._specular.setZValue(4)
        self._specular.setPen(QPen(Qt.NoPen))
        self._specular.setBrush(QBrush(QColor(255, 255, 255, 90)))

        # — filamento (dos patas + bucle) —
        fp = _QPPath()
        fp.moveTo(cx - 5, neck_top)
        fp.lineTo(cx - 5, cy + ry * 0.35)
        fp.quadTo(cx - 5, cy - ry * 0.10, cx, cy - ry * 0.25)
        fp.quadTo(cx + 5, cy - ry * 0.10, cx + 5, cy + ry * 0.35)
        fp.lineTo(cx + 5, neck_top)
        self._filament = _QGPathItem(fp, self)
        self._filament.setZValue(3)
        self._filament.setBrush(QBrush(Qt.NoBrush))

        # — cuello trapezoidal —
        from PySide6.QtGui import QPolygonF as _PF
        neck_poly = _PF([
            QPointF(cx - rx * 0.50, neck_top),
            QPointF(cx + rx * 0.50, neck_top),
            QPointF(cx + nw / 2,    neck_bottom),
            QPointF(cx - nw / 2,    neck_bottom),
        ])
        from PySide6.QtWidgets import QGraphicsPolygonItem as _PI
        self._neck = _PI(neck_poly, self)
        self._neck.setZValue(2)
        self._neck.setPen(QPen(Qt.NoPen))

        # — franjas de la base —
        self._segs = []
        for i in range(self.N_SEGS):
            shrink = i * 1.5
            w_seg  = max(4, self.NECK_W - shrink * 2)
            seg = QGraphicsRectItem(
                cx - w_seg / 2,
                base_top + i * seg_h,
                w_seg, seg_h, self
            )
            seg.setZValue(2)
            self._segs.append(seg)

        # — contacto inferior —
        cw, ch = self.CONTACT_W, self.CONTACT_H
        self._contact = QGraphicsRectItem(
            cx - cw / 2,
            base_top + self.N_SEGS * seg_h,
            cw, ch, self
        )
        self._contact.setZValue(2)

        body_bottom = base_top + self.N_SEGS * seg_h + self.CONTACT_H
        outline_rect = QRectF(cx - rx - 3, cy - ry - 3,
                              rx * 2 + 6, body_bottom - (cy - ry) + 6)
        self._selection_outline = QGraphicsRectItem(outline_rect, self)
        self._selection_outline.setZValue(10)
        self._selection_outline.setPen(QPen(QColor(139, 193, 255), 1.4, Qt.DashLine))
        self._selection_outline.setBrush(QBrush(Qt.NoBrush))
        self._selection_outline.setVisible(self.isSelected())
        self._refresh_look()

    def _refresh_look(self):
        on = bool(self.widg.enter[0]) if self.widg.enter else False
        chosen_color = QColor(getattr(self.widg, "bulb_color", None) or "#ffc832")
        if not chosen_color.isValid():
            chosen_color = QColor(255, 200, 50)

        rx, ry = self.RX, self.RY
        cx, cy = self.CX, self.CY

        if self._glow:
            if on:
                glow_color = QColor(chosen_color)
                glow_color.setAlpha(55)
                self._glow.setBrush(QBrush(glow_color))
            else:
                self._glow.setBrush(QBrush(Qt.NoBrush))

        if self._globe:
            grad = _QRGrad(QPointF(cx - rx * 0.22, cy - ry * 0.28), rx * 1.1)
            if on:
                center_color = chosen_color.lighter(150)
                center_color.setAlpha(230)
                middle_color = QColor(chosen_color)
                middle_color.setAlpha(170)
                edge_color = chosen_color.darker(150)
                edge_color.setAlpha(90)
                grad.setColorAt(0.00, center_color)
                grad.setColorAt(0.50, middle_color)
                grad.setColorAt(1.00, edge_color)
            else:
                grad.setColorAt(0.00, QColor(200, 220, 235, 140))
                grad.setColorAt(0.55, QColor(130, 170, 195,  77))
                grad.setColorAt(1.00, QColor( 80, 130, 160,  51))
            self._globe.setBrush(QBrush(grad))
            if on:
                border = chosen_color.lighter(125)
                border.setAlpha(200)
            else:
                border = QColor(120, 170, 200, 130)
            self._globe.setPen(QPen(border, 1.2))

        if self._filament:
            col = chosen_color.lighter(110) if on else QColor(140, 140, 140, 180)
            self._filament.setPen(QPen(col, 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

        if self._neck:
            if on:
                col = chosen_color.lighter(115)
                col.setAlpha(115)
            else:
                col = QColor(140, 175, 200, 102)
            self._neck.setBrush(QBrush(col))
            self._neck.setPen(QPen(QColor(100, 130, 160, 100), 0.8))

        seg_colors_off = [
            QColor(160, 185, 200, 140),
            QColor(130, 155, 170, 155),
        ]
        seg_lit = chosen_color.lighter(115)
        seg_lit.setAlpha(155)
        seg_lit_dark = chosen_color.darker(125)
        seg_lit_dark.setAlpha(170)
        seg_colors_on = [seg_lit, seg_lit_dark]
        seg_border_off = QColor( 90, 125, 150, 100)
        seg_border_on  = chosen_color.darker(135)
        seg_border_on.setAlpha(130)
        for i, seg in enumerate(self._segs):
            cols = seg_colors_on if on else seg_colors_off
            seg.setBrush(QBrush(cols[i] if i < len(cols) else cols[-1]))
            seg.setPen(QPen(seg_border_on if on else seg_border_off, 0.7))

        if self._contact:
            if on:
                col = chosen_color.lighter(135)
                col.setAlpha(215)
            else:
                col = QColor(190, 210, 225, 205)
            self._contact.setBrush(QBrush(col))
            self._contact.setPen(QPen(QColor(140, 160, 180, 150), 0.7))

    # ── geometría ─────────────────────────────────────────────────────────────

    def boundingRect(self):
        rx, ry = self.RX, self.RY
        extra  = 20  # espacio para el halo
        total_h = ry * 2 + 10 + self.N_SEGS * self.SEG_H + self.CONTACT_H
        return QRectF(-rx - extra, -ry - extra,
                      rx * 2 + extra * 2, total_h + extra * 2)

    def paint(self, painter, option, widget=None):
        pass

    # ── ciclo de vida ─────────────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSceneHasChanged and self.scene():
            self._build_shapes()
            self.rebuild_ports()
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._reposition_ports()
            for w in self.wires:
                w.update_path()
        if change == QGraphicsItem.ItemSelectedHasChanged and self._selection_outline:
            self._selection_outline.setVisible(bool(value))
        return QGraphicsItem.itemChange(self, change, value)

    def rebuild_ports(self):
        scene = self.scene()
        if not scene:
            return
        for p in self._ports_in + self._ports_out:
            scene.removeItem(p)
        self._ports_in  = []
        self._ports_out = []

        for i in range(len(self.widg.enter)):
            p = Port(self, i, is_input=True)
            scene.addItem(p)
            self._ports_in.append(p)

        self._reposition_ports()

    def _reposition_ports(self):
        origin  = self.scenePos()
        rx, ry  = self.RX, self.RY
        total_h = ry * 2 + 10 + self.N_SEGS * self.SEG_H + self.CONTACT_H
        n_in = len(self._ports_in)
        for i, p in enumerate(self._ports_in):
            y = -ry + total_h * (i + 1) / (n_in + 1)
            p.setPos(origin + QPointF(-rx - PORT_RADIUS - 2, y))

    def update_port_color(self, idx: int, is_input: bool):
        ports = self._ports_in if is_input else self._ports_out
        if 0 <= idx < len(ports):
            ports[idx].update_color()
        self._refresh_look()

    def update_all_output_wires(self):
        pass

    def update_switch_look(self):
        self._refresh_look()

    def show_config(self):
        parent = self.scene().views()[0].window() if self.scene() and self.scene().views() else None
        dialog = BulbDelayDialog(self, parent)
        dialog.exec()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.show_config()
            e.accept()
            return
        super(Graphic, self).mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        super(Graphic, self).mouseDoubleClickEvent(e)


# ── DisplayGraphic ────────────────────────────────────────────────────────────
#
# 7 entradas, una por segmento en orden: a b c d e f g
#   a = horizontal top
#   b = vertical top-right
#   c = vertical bot-right
#   d = horizontal bottom
#   e = vertical bot-left
#   f = vertical top-left
#   g = horizontal middle
#
# Cada segmento es un hexágono alargado (forma de palito real).
# Sin fondo: solo los palitos, transparente.

from PySide6.QtGui import QPolygonF

COLOR_SEG_ON  = QColor(255, 60,  20)
COLOR_SEG_OFF = QColor(145, 165, 190, 125)   # apagado pero claramente visible en ambos temas

# Etiquetas de los 7 segmentos
_SEG_LABELS = ["a", "b", "c", "d", "e", "f", "g"]


def _hpoly(x: float, y: float, length: float, sw: float) -> QPolygonF:
    """Hexágono horizontal: palito con puntas a izquierda y derecha."""
    h = sw / 2
    tip = h * 0.7
    pts = [
        QPointF(x + tip,          y),
        QPointF(x + length - tip, y),
        QPointF(x + length,       y + h),
        QPointF(x + length - tip, y + sw),
        QPointF(x + tip,          y + sw),
        QPointF(x,                y + h),
    ]
    return QPolygonF(pts)


def _vpoly(x: float, y: float, length: float, sw: float) -> QPolygonF:
    """Hexágono vertical: palito con puntas arriba y abajo."""
    h = sw / 2
    tip = h * 0.7
    pts = [
        QPointF(x + h,  y + tip),
        QPointF(x + sw, y + tip),
        QPointF(x + sw, y + length - tip),
        QPointF(x + h,  y + length),
        QPointF(x,      y + length - tip),
        QPointF(x,      y + tip),
    ]
    return QPolygonF(pts)


class DisplayGraphic(Graphic):
    """Display 7 segmentos: 7 entradas (a-g)"""

    W        = 44
    H        = 76
    SW       = 8
    M        = 0
    OVL      = 0
    PORT_GAP = 24

    def __init__(self, widg):
        QGraphicsItem.__init__(self)
        self.widg  = widg
        self.wires: list[Wire] = []
        widg.graphic = self

        self.setZValue(1)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self._ports_in: list[Port] = []
        self._segs:     list      = []
        self._selection_outline: QGraphicsRectItem | None = None

    def _build_shapes(self):
        from PySide6.QtWidgets import QGraphicsPolygonItem
        w, h, sw, m, ovl = self.W, self.H, self.SW, self.M, self.OVL

        inner_w  = w - 2 * m
        half_h   = h / 2
        ya       = m
        yg       = half_h - sw / 2
        yd       = h - m - sw
        yv_top_s = ya + ovl
        yv_top_e = yg + sw - ovl
        yv_bot_s = yg + ovl
        yv_bot_e = yd + sw - ovl
        xr, xl   = w - m - sw, m

        polys = [
            (3, _hpoly(m,  ya,       inner_w,              sw)),  # a
            (2, _vpoly(xr, yv_top_s, yv_top_e - yv_top_s, sw)),  # b
            (2, _vpoly(xr, yv_bot_s, yv_bot_e - yv_bot_s, sw)),  # c
            (3, _hpoly(m,  yd,       inner_w,              sw)),  # d
            (2, _vpoly(xl, yv_bot_s, yv_bot_e - yv_bot_s, sw)),  # e
            (2, _vpoly(xl, yv_top_s, yv_top_e - yv_top_s, sw)),  # f
            (3, _hpoly(m,  yg,       inner_w,              sw)),  # g
        ]

        self._segs = []
        for zv, poly in polys:
            item = QGraphicsPolygonItem(poly, self)
            item.setZValue(zv)
            item.setPen(QPen(Qt.NoPen))
            self._segs.append(item)

        self._selection_outline = QGraphicsRectItem(
            QRectF(-2, -2, w + 4, h + 4), self)
        self._selection_outline.setZValue(10)
        self._selection_outline.setPen(QPen(QColor(139, 193, 255), 1.4, Qt.DashLine))
        self._selection_outline.setBrush(QBrush(Qt.NoBrush))
        self._selection_outline.setVisible(self.isSelected())
        self._refresh_look()

    def _refresh_look(self):
        colors = getattr(self.widg, "segment_colors", [])
        for i, seg in enumerate(self._segs):
            on = bool(self.widg.enter[i]) if i < 7 else False
            custom = QColor(colors[i]) if i < len(colors) and colors[i] else QColor()
            col = (custom if custom.isValid() else COLOR_SEG_ON) if on else COLOR_SEG_OFF
            seg.setBrush(QBrush(col))

    def boundingRect(self):
        return QRectF(-self.PORT_GAP - 2, -2,
                      self.W + self.PORT_GAP + 4, self.H + 4)

    def paint(self, painter, option, widget=None):
        pass

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSceneHasChanged and self.scene():
            self._build_shapes()
            self.rebuild_ports()
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._reposition_ports()
            for w in self.wires:
                w.update_path()
        if change == QGraphicsItem.ItemSelectedHasChanged and self._selection_outline:
            self._selection_outline.setVisible(bool(value))
        return QGraphicsItem.itemChange(self, change, value)

    def rebuild_ports(self):
        scene = self.scene()
        if not scene:
            return
        for p in self._ports_in:
            scene.removeItem(p)
        self._ports_in = []

        for i in range(7):
            p = Port(self, i, is_input=True)
            scene.addItem(p)
            self._ports_in.append(p)

        self._reposition_ports()

    def _reposition_ports(self):
        origin = self.scenePos()
        sw, m, h, ovl, gap = self.SW, self.M, self.H, self.OVL, self.PORT_GAP
        half_h = h / 2

        yv_top_mid = (m + sw - ovl + half_h - sw / 2 + ovl) / 2
        yv_bot_mid = (half_h + sw / 2 - ovl + h - m - sw - ovl) / 2

        # (y, x_offset)  — dos columnas para que b/f y c/e no se solapen
        # columna izquierda  (x = -gap + PORT_RADIUS + 2)
        # columna derecha    (x = -gap + PORT_RADIUS + 2 + PORT_RADIUS*2 + 4)
        xl = -gap + PORT_RADIUS + 2
        xr = xl + PORT_RADIUS * 2 + 4

        coords = [
            (m + sw / 2,     xl),   # a  – horizontal top    → columna izq
            (yv_top_mid,     xr),   # b  – vertical top-right → columna der
            (yv_bot_mid,     xr),   # c  – vertical bot-right → columna der
            (h - m - sw / 2, xl),   # d  – horizontal bottom  → columna izq
            (yv_bot_mid,     xl),   # e  – vertical bot-left  → columna izq
            (yv_top_mid,     xl),   # f  – vertical top-left  → columna izq
            (half_h,         xl),   # g  – horizontal middle  → columna izq
        ]

        for i, p in enumerate(self._ports_in):
            y, x = coords[i]
            p.setPos(origin + QPointF(x, y))

    def update_port_color(self, idx: int, is_input: bool):
        if 0 <= idx < len(self._ports_in):
            self._ports_in[idx].update_color()
        self._refresh_look()

    def update_switch_look(self):
        self._refresh_look()

    def show_config(self):
        parent = self.scene().views()[0].window() if self.scene() and self.scene().views() else None
        dialog = ConfigDialog(self, parent)
        dialog.exec()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.show_config()
            e.accept()
            return
        super(Graphic, self).mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        super(Graphic, self).mouseDoubleClickEvent(e)


class ColorPickerButton(QPushButton):
    """Compact color swatch that opens the native color picker."""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        if not self.color.isValid():
            self.color = QColor("#ffffff")
        self.setMinimumWidth(92)
        self.clicked.connect(self.choose_color)
        self._refresh_swatch()

    def _refresh_swatch(self):
        self.setText(self.color.name().upper())
        text_color = "#101820" if self.color.lightness() > 140 else "#ffffff"
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self.color.name()}; "
            "border: 1px solid #718096; border-radius: 4px; padding: 3px 8px; "
            f"color: {text_color}; font-weight: 600; }}"
            "QPushButton:hover { border: 2px solid #2684ff; }")

    def choose_color(self):
        color = QColorDialog.getColor(self.color, self, "Elegir color")
        if color.isValid():
            self.color = color
            self._refresh_swatch()


# ── ConfigDialog ─────────────────────────────────────────────────────────────

class ConfigDialog(QDialog):

    def __init__(self, graphic: Graphic, parent=None):
        super().__init__(parent)
        self.graph = graphic
        self.widg  = graphic.widg

        from widgets.widgets import Module, Switch, Button, Bulb, Display, Delay
        if isinstance(self.widg, Module):
            component_name = self.widg.name
        else:
            component_name = next((label for kind, label in (
                (Switch, "Interruptor"), (Button, "Botón"), (Bulb, "Bombilla"),
                (Display, "Display"), (Delay, "RETARDO"))
                if isinstance(self.widg, kind)), type(self.widg).__name__)
        self.setWindowTitle(f"Editar {component_name} {self.widg.id}")
        self.setMinimumWidth(340)

        lay = QVBoxLayout()

        if self.widg.can_set_enter():
            self.sp_in = QSpinBox(self)
            self.sp_in.setRange(self.widg.min_enter, 8)
            self.sp_in.setValue(max(self.widg.min_enter, len(self.widg.enter)))
            self.sp_in.setToolTip("Cambia el número de entradas de este componente")
            self.sp_in.valueChanged.connect(self._set_input_count)
            row = QHBoxLayout()
            row.addWidget(QLabel("Número de entradas:"))
            row.addWidget(self.sp_in)
            lay.addLayout(row)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Retardo de señal (ms):"))
        self.sp_delay = QSpinBox(self)
        self.sp_delay.setRange(0, 10000)
        self.sp_delay.setValue(self.widg.delay_ms)
        self.sp_delay.setSuffix(" ms")
        delay_layout.addWidget(self.sp_delay)
        lay.addLayout(delay_layout)

        self.segment_color_fields = []
        if isinstance(self.widg, Display):
            group = QGroupBox("Color de cada segmento encendido", self)
            group_layout = QVBoxLayout(group)
            names = ("a · superior", "b · superior derecha", "c · inferior derecha",
                     "d · inferior", "e · inferior izquierda", "f · superior izquierda",
                     "g · medio")
            saved_colors = getattr(self.widg, "segment_colors", [None] * 7)
            for index, name in enumerate(names):
                row = QHBoxLayout()
                row.addWidget(QLabel(name, group), 1)
                color = (saved_colors[index] if index < len(saved_colors) and saved_colors[index]
                         else COLOR_SEG_ON)
                picker = ColorPickerButton(color, group)
                row.addWidget(picker)
                group_layout.addLayout(row)
                self.segment_color_fields.append(picker)
            lay.addWidget(group)
            self.resize(360, 470)

        self.input_number_fields = []
        self.output_number_fields = []
        from widgets.widgets import Module
        if isinstance(self.widg, Module):
            group = QGroupBox("Número visible de cada puerto")
            group_layout = QVBoxLayout(group)
            scroll = QScrollArea(group)
            scroll.setWidgetResizable(True)
            contents = QWidget()
            number_layout = QVBoxLayout(contents)
            number_layout.setContentsMargins(4, 4, 4, 4)
            number_layout.setSpacing(3)
            for title, numbers, fields in (
                    ("Entradas", self.widg.input_numbers, self.input_number_fields),
                    ("Salidas", self.widg.output_numbers, self.output_number_fields)):
                heading = QLabel(title, contents)
                heading.setStyleSheet("font-weight: 600; padding-top: 3px;")
                number_layout.addWidget(heading)
                for index, number in enumerate(numbers):
                    row = QHBoxLayout()
                    row.addWidget(QLabel(f"{title[:-1]} · pin {index + 1}", contents))
                    value = QSpinBox(contents)
                    value.setRange(0, 99)
                    value.setValue(number)
                    value.setFixedWidth(68)
                    row.addWidget(value)
                    number_layout.addLayout(row)
                    fields.append(value)
            self._connect_unique_fields(self.input_number_fields)
            self._connect_unique_fields(self.output_number_fields)
            number_layout.addStretch(1)
            scroll.setWidget(contents)
            scroll.setFixedHeight(min(180, max(80, 30 * (len(self.input_number_fields)
                                                        + len(self.output_number_fields) + 2))))
            group_layout.addWidget(scroll)
            lay.addWidget(group)
            self.resize(320, 360)

        btn_lay = QHBoxLayout()
        if isinstance(self.widg, Module):
            save_ci = QPushButton("Guardar CI")
            save_ci.clicked.connect(self._save_module)
            btn_lay.addWidget(save_ci)
        ok  = QPushButton("Guardar");   ok.clicked.connect(self._apply_config)
        can = QPushButton("Cancelar"); can.clicked.connect(self.reject)
        btn_lay.addWidget(ok); btn_lay.addWidget(can)
        lay.addLayout(btn_lay)

        self.setLayout(lay)

    @staticmethod
    def _connect_unique_fields(fields):
        previous = [field.value() for field in fields]
        for index, field in enumerate(fields):
            def keep_unique(value, edited=index, values=fields, old=previous):
                duplicate = next((other for other, candidate in enumerate(values)
                                  if other != edited and candidate.value() == value), None)
                if duplicate is not None:
                    values[duplicate].blockSignals(True)
                    values[duplicate].setValue(old[edited])
                    values[duplicate].blockSignals(False)
                old[:] = [candidate.value() for candidate in values]
            field.valueChanged.connect(keep_unique)

    def _apply_module_ports(self):
        self.widg.set_port_numbers(
            [field.value() for field in self.input_number_fields],
            [field.value() for field in self.output_number_fields])
        for fields, values in ((self.input_number_fields, self.widg.input_numbers),
                               (self.output_number_fields, self.widg.output_numbers)):
            for field, value in zip(fields, values):
                field.blockSignals(True)
                field.setValue(value)
                field.blockSignals(False)

    def _refresh_port_connections(self):
        scene = self.graph.scene()
        if scene and scene.views():
            view = scene.views()[0]
            if hasattr(view, "rebuild_connections"):
                view.rebuild_connections()

    def _notify_history_change(self):
        scene = self.graph.scene()
        if scene and scene.views():
            window = scene.views()[0].window()
            if hasattr(window, "_schedule_history_capture"):
                window._schedule_history_capture()
    def _set_input_count(self, count):
        self.widg.set_enter(count)
        self._refresh_port_connections()
        self._notify_history_change()

    def _save_module(self):
        from widgets.widgets import Module
        from project_io import module_definition
        if not isinstance(self.widg, Module):
            return
        self._apply_module_ports()
        self.widg.set_delay(self.sp_delay.value())
        module_path = getattr(self.widg, "module_path", None)
        if module_path:
            path = Path(module_path)
        else:
            library = Path(__file__).resolve().parents[1] / "user" / "Biblioteca"
            suggested = library / f"{self.widg.name}.dmodule"
            save, _ = QFileDialog.getSaveFileName(
                self, "Guardar CI", str(suggested), "Módulo DaLogic (*.dmodule)")
            if not save:
                return
            path = Path(save).with_suffix(".dmodule")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            definition = module_definition(
                self.widg.name, len(self.widg.enter), len(self.widg.exit),
                self.widg.truth_table, self.widg.delay_ms,
                self.widg.input_numbers, self.widg.output_numbers)
            path.write_text(json.dumps(definition, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "No se pudo guardar el CI", str(exc))
            return
        self.widg.module_path = str(path.resolve())
        library = Path(__file__).resolve().parents[1] / "user" / "Biblioteca"
        try:
            path.resolve().relative_to(library.resolve())
            self.widg.module_source = "library"
        except ValueError:
            pass
        scene = self.graphic.scene()
        if scene and scene.views():
            window = scene.views()[0].window()
            if hasattr(window, "actualizar_biblioteca_ci"):
                window.actualizar_biblioteca_ci()
        QMessageBox.information(self, "CI guardado", f"Se guardó {path.name}.")

    def _apply_config(self):
        from widgets.widgets import Module
        if isinstance(self.widg, Module):
            self._apply_module_ports()
        elif self.widg.can_set_enter():
            self.widg.set_enter(self.sp_in.value())
        self.widg.set_delay(self.sp_delay.value())
        if isinstance(self.widg, Display):
            self.widg.segment_colors = [picker.color.name() for picker in self.segment_color_fields]
            self.graph._refresh_look()
        self._notify_history_change()
        self.accept()

class BulbDelayDialog(QDialog):
    """Editor sencillo del retardo de señal de una bombilla."""

    def __init__(self, graphic: BulbGraphic, parent=None):
        super().__init__(parent)
        self.graphic = graphic
        self.widg = graphic.widg
        self.setWindowTitle(f"Editar Bombilla {self.widg.id}")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Retardo de señal (ms):", self))
        self.delay = QSpinBox(self)
        self.delay.setRange(0, 10000)
        self.delay.setValue(int(self.widg.delay_ms))
        self.delay.setSuffix(" ms")
        row.addWidget(self.delay)
        layout.addLayout(row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color al encender:", self))
        self.color_picker = ColorPickerButton(
            getattr(self.widg, "bulb_color", None) or "#ffc832", self)
        color_row.addWidget(self.color_picker)
        layout.addLayout(color_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Guardar", self)
        save.clicked.connect(self._save)
        cancel = QPushButton("Cancelar", self)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _save(self):
        self.widg.set_delay(self.delay.value())
        self.widg.bulb_color = self.color_picker.color.name()
        self.graphic._refresh_look()
        scene = self.graphic.scene()
        if scene and scene.views():
            window = scene.views()[0].window()
            if hasattr(window, "_schedule_history_capture"):
                window._schedule_history_capture()
        self.accept()
