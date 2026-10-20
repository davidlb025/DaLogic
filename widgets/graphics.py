from resources import translate_text as tr, module_display_name, SELECTION_COLOR
"""
graphics.py  –  Representación visual: Graphic, Port, Wire, ConfigDialog.
"""

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem,
    QGraphicsRectItem,
    QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGroupBox, QScrollArea, QWidget, QLineEdit,
    QMessageBox, QColorDialog, QMenu, QDialogButtonBox, QTabWidget, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QStyle
)
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath, QFont, QPainter, QFontMetricsF, QTransform
import copy
import math
import re
from pathlib import Path


from resources import translate_text, set_language_translations

# ── Colores ───────────────────────────────────────────────────────────────────
COLOR_PORT_IN_OFF  = QColor(105, 135, 245)
COLOR_PORT_IN_ON   = QColor(73, 213, 151)
COLOR_PORT_OUT_OFF = QColor(239, 139, 126)
COLOR_PORT_OUT_ON  = QColor(255, 205, 105)
COLOR_WIRE_OFF     = QColor(126, 145, 166)
COLOR_WIRE_ON      = QColor(73, 213, 151)
COLOR_WIRE_SEL     = SELECTION_COLOR

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

from resources import LocalizedInputDialog as QInputDialog, LocalizedFileDialog as QFileDialog


def _delete_canvas_item(item):
    if not item.scene() or not item.scene().views():
        return
    view = item.scene().views()[0]
    owner = view.window()
    owner._capture_history_change()
    item.scene().clearSelection()
    item.setSelected(True)
    owner.eliminar_seleccion()
    owner._capture_history_change()

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
        from widgets.widgets import (Module, Splitter, Combiner, TriState,
                                     BusInput, BusLamp, BusViewer)
        kind = translate_text("Entrada" if self.is_input else "Salida")
        if isinstance(self.graphic.widg, Module):
            numbers = (self.graphic.widg.input_numbers if self.is_input
                       else self.graphic.widg.output_numbers)
            labels = (self.graphic.widg.input_labels if self.is_input
                      else self.graphic.widg.output_labels)
            number = numbers[self.port_index] if self.port_index < len(numbers) else self.port_index
            label = labels[self.port_index] if self.port_index < len(labels) else ""
            display = label or str(number)
            detail = display
            widths = (self.graphic.widg.input_widths if self.is_input else
                      self.graphic.widg.output_widths)
            width = widths[self.port_index] if self.port_index < len(widths) else 1
            suffix = f" · {width} bits" if width > 1 else ""
            self.setToolTip(tr('{v0} {v1}{v2} · {v3}', v0=kind, v1=detail, v2=suffix, v3=module_display_name(self.graphic.widg)))
        else:
            widget = self.graphic.widg
            widths = widget.input_widths if self.is_input else widget.output_widths
            width = widths[self.port_index] if self.port_index < len(widths) else 1
            suffix = f" · {width} bits" if width > 1 else ""
            port_name = ""
            labels = getattr(widget, "input_labels" if self.is_input else "output_labels", [])
            if self.port_index < len(labels):
                port_name = f" · {labels[self.port_index]}"
            component_names = {BusInput: "Bus de entrada", BusLamp: "Bus de salida",
                               BusViewer: "Visor de bus",
                               Splitter: "Divisor de bus", Combiner: "Combinador de bus",
                               TriState: "Controlador triestado"}
            component_name = next((name for component, name in component_names.items()
                                   if isinstance(widget, component)), type(widget).__name__)
            if isinstance(widget, Splitter):
                port_name = f" · bit {self.port_index}" if not self.is_input else " · bus"
            elif isinstance(widget, Combiner):
                port_name = f" · bit {self.port_index}" if self.is_input else " · bus"
            elif isinstance(widget, TriState):
                port_name = (" · datos" if self.is_input and self.port_index == 0 else
                             " · enable" if self.is_input else " · bus")
            if isinstance(widget, (BusInput, BusLamp)):
                self.setToolTip(tr('{v0}{v1}', v0=tr(component_name), v1=suffix))
            else:
                self.setToolTip(tr('{v0} {v1}{v2} · {v3} {v4}{v5}', v0=kind, v1=self.port_index, v2=tr(port_name), v3=tr(component_name), v4=widget.id, v5=suffix))

    def update_color(self):
        widg = self.graphic.widg
        if self.is_input:
            val = widg.enter[self.port_index] if self.port_index < len(widg.enter) else False
            col = COLOR_PORT_IN_ON if val is not False and val != 0 and val != "Z" else COLOR_PORT_IN_OFF
        else:
            val = widg.exit[self.port_index] if self.port_index < len(widg.exit) else False
            col = COLOR_PORT_OUT_ON if val is not False and val != 0 and val != "Z" else COLOR_PORT_OUT_OFF

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
            if (view and hasattr(view, "toggle_probe") and
                    e.modifiers() & Qt.ControlModifier):
                view.toggle_probe(self)
                e.accept()
                return
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
            tr("Nexo · doble clic para cambiar a Puente"),
            tr("Puente · doble clic para cambiar al otro lado"),
            tr("Puente hacia el otro lado · doble clic para volver a empezar"),
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
        points = self.wire._routed_points()
        if len(points) >= 3:
            node_pos = self.scenePos()
            node_index = next((index for index, point in enumerate(points)
                               if math.hypot(point.x() - node_pos.x(),
                                             point.y() - node_pos.y()) < 0.01), None)
            if node_index is None or node_index == 0 or node_index >= len(points) - 1:
                return
            node = points[node_index]
            incoming = _unit_vector(node - points[node_index - 1])
            outgoing = _unit_vector(points[node_index + 1] - node)
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
        self._signal = False
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
            tr("Nexo · doble clic para cambiar a Puente"),
            tr("Puente · doble clic para cambiar al otro lado"),
            tr("Puente hacia el otro lado · doble clic para volver a empezar"),
        )
        self.setToolTip(translate_text(messages[self.bridge_mode]))

    def boundingRect(self):
        return QRectF(-10, -11, 20, 18)

    def _bridge_directions(self):
        directions = []
        for wire in self._wires:
            points = wire._routed_points()
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
            if self.isSelected():
                pen.setColor(SELECTION_COLOR)
                pen.setWidthF(max(2, pen.widthF()))
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
        col = SELECTION_COLOR if self.isSelected() else COLOR_WIRE_ON if self._on else COLOR_WIRE_OFF
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
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._apply_style()
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
        width = max((endpoint.graphic.widg.output_widths[endpoint.port_index]
                     if isinstance(endpoint, Port) and not endpoint.is_input else
                     endpoint.graphic.widg.input_widths[endpoint.port_index]
                     if isinstance(endpoint, Port) else 1
                     for endpoint in (src, dst)), default=1)
        self.setToolTip((translate_text("Clic derecho para ver las opciones del cable") + (tr(' · bus de {v0} bits', v0=width) if width > 1 else "")))

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
        bus = any(isinstance(endpoint, Port) and
                  (endpoint.graphic.widg.output_widths[endpoint.port_index]
                   if not endpoint.is_input else
                   endpoint.graphic.widg.input_widths[endpoint.port_index]) > 1
                  for endpoint in (getattr(self, "src_port", None),
                                   getattr(self, "dst_port", None)))
        if self.isSelected():
            col, w = COLOR_WIRE_SEL, 4 if bus else 3
        elif self.custom_color is not None:
            col = self.custom_color.lighter(125) if self._on else self.custom_color
            w = (3.4 if self._on else 3.0) if bus else (2 if self._on else 1.5)
        elif self._on:
            col, w = COLOR_WIRE_ON, 3.4 if bus else 2
        else:
            col, w = COLOR_WIRE_OFF, 3.0 if bus else 1.5
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
        dialog.setWindowTitle(tr("Color del cable"))
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_custom_color(dialog.currentColor())

    def set_active(self, on: bool):
        if self._on != on:
            self._on = on
            self._update_pen()
            for mp in self._mid_pts:
                mp.set_active(on)
        # A bus can change from 3 to 7 without changing its active color.
        # Repaint the label on every signal refresh as well.
        if self._bus_endpoint()[0] is not None:
            self.update()

    def signal_value(self):
        from widgets.widgets import combine_driver_values
        endpoints = getattr(self, "_network_ports", (self.src_port, self.dst_port))
        drivers = {(endpoint.graphic.widg, endpoint.port_index):
                   endpoint.graphic.widg.exit[endpoint.port_index]
                   for endpoint in endpoints if isinstance(endpoint, Port) and not endpoint.is_input
                   and endpoint.port_index < len(endpoint.graphic.widg.exit)}
        if drivers:
            if all(value == "Z" for value in drivers.values()):
                return "Z"
            return combine_driver_values(drivers, self._bus_endpoint()[1])
        for endpoint in endpoints:
            if isinstance(endpoint, Port) and endpoint.is_input:
                widget = endpoint.graphic.widg
                if endpoint.port_index < len(widget.enter):
                    return widget.enter[endpoint.port_index]
        return False

    def _bus_endpoint(self):
        for endpoint in getattr(self, "_network_ports", (self.dst_port, self.src_port)):
            if isinstance(endpoint, Port):
                widths = endpoint.graphic.widg.input_widths if endpoint.is_input else endpoint.graphic.widg.output_widths
                if endpoint.port_index < len(widths) and widths[endpoint.port_index] > 1:
                    return endpoint, widths[endpoint.port_index]
        return None, 1

    def boundingRect(self):
        rect = super().boundingRect()
        if hasattr(self, 'src_port') and self._bus_endpoint()[0] is not None and not self.path().isEmpty():
            center = self.path().pointAtPercent(0.5)
            width = self._bus_endpoint()[1]
            label_width = max(110, width * 6 + 24)
            rect = rect.united(QRectF(center.x() - label_width / 2, center.y() - 36, label_width, 32))
        return rect

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        endpoint, width = self._bus_endpoint()
        if endpoint is None or self.path().isEmpty():
            return
        value = self.signal_value()
        text = str(value) if value in ('X', 'Z') else f'{int(value)} · 0x{int(value):X}\n{int(value):0{width}b}'
        center = self.path().pointAtPercent(0.5)
        label_width = max(110, width * 6 + 24)
        label = QRectF(center.x() - label_width / 2, center.y() - 36, label_width, 32)
        dark = bool(self.scene() and self.scene().views() and self.scene().views()[0].theme_mode == 'dark')
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#101722' if dark else '#f7f9fc'))
        painter.drawRoundedRect(label, 3, 3)
        painter.setPen(QColor('#bfd7f6' if dark else '#354f70'))
        painter.setFont(QFont('Consolas', 7))
        painter.drawText(label, Qt.AlignCenter, tr(text))

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
            e.ignore()
            return
        if e.button() == Qt.LeftButton:
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if (view and hasattr(view, "toggle_probe") and
                    e.modifiers() & Qt.ControlModifier):
                view.toggle_probe(self)
                e.accept()
                return
            if view and hasattr(view, "on_wire_clicked"):
                if not self.isSelected():
                    self.scene().clearSelection()
                    self.setSelected(True)
                else:
                    view.on_wire_clicked(self, e.scenePos(), self._closest_segment(e.scenePos()))
                e.accept()
                return
        super().mousePressEvent(e)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.screenPos(), event.scenePos())
        event.accept()

    def context_menu(self, scene_pos):
        view = self.scene().views()[0]
        menu = QMenu(view.window())
        menu.addAction(tr("Crear nodo"), lambda: view.on_wire_clicked(
            self, scene_pos, self._closest_segment(scene_pos)))
        menu.addAction(tr("Cambiar color"), self.show_color_editor)
        menu.addAction(tr("Eliminar"), lambda: _delete_canvas_item(self))
        return menu

    def show_context_menu(self, screen_pos, scene_pos):
        self.scene().clearSelection()
        self.setSelected(True)
        self.context_menu(scene_pos).exec(screen_pos)

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

    def _routed_points(self, preview_end: QPointF | None = None) -> list[QPointF]:
        anchors = self._all_points()
        if preview_end is not None:
            anchors.append(preview_end)
        if len(anchors) < 2:
            return anchors
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if not view or not getattr(view, "orthogonal_wires", False):
            return anchors
        routed = [anchors[0]]
        for point in anchors[1:]:
            previous = routed[-1]
            if abs(point.x() - previous.x()) > 0.01 and abs(point.y() - previous.y()) > 0.01:
                routed.append(QPointF(point.x(), previous.y()))
            routed.append(point)
        return routed

    def update_path(self, preview_end: QPointF | None = None):
        pts = self._routed_points(preview_end)
        if len(pts) < 2:
            self.setPath(QPainterPath())
            return

        midpoint_bridges = set()
        for midpoint in self._mid_pts:
            if not midpoint.bridge:
                continue
            midpoint_position = midpoint.scenePos()
            midpoint_bridges.add(next((index for index, point in enumerate(pts)
                                       if math.hypot(point.x() - midpoint_position.x(),
                                                     point.y() - midpoint_position.y()) < 0.01), -1))
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
        self.rotation_degrees = 0
        self.mirrored = False
        self.setTransformOriginPoint(self.boundingRect().center())

    def _theme_is_dark(self):
        scene = self.scene()
        if scene and scene.views():
            return getattr(scene.views()[0], "theme_mode", "light") == "dark"
        return bool(scene and scene.property("theme_mode") == "dark")

    def _paint_selection(self, painter, rect, radius=8):
        if self.isSelected():
            painter.save()
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(SELECTION_COLOR, 1.4, Qt.DashLine))
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), radius, radius)
            painter.restore()

    def paint(self, painter, option, widget=None):
        pass

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSceneHasChanged:
            if self.scene():
                self.rebuild_ports()
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            views = self.scene().views()
            view = views[0] if views else None
            if view and getattr(view, "snap_to_grid", False):
                grid = getattr(view, "grid_size", 20)
                value = QPointF(round(value.x() / grid) * grid,
                                round(value.y() / grid) * grid)
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
        bRect = self.boundingRect()
        w = bRect.width()
        h = bRect.height()

        n_in = len(self._ports_in)
        for i, p in enumerate(self._ports_in):
            y = h * (i + 1) / (n_in + 1)
            p.setPos(self.mapToScene(QPointF(0, y)))

        n_out = len(self._ports_out)
        for i, p in enumerate(self._ports_out):
            y = h * (i + 1) / (n_out + 1)
            p.setPos(self.mapToScene(QPointF(w, y)))

    def set_orientation(self, rotation=0, mirrored=False):
        self.rotation_degrees = int(rotation) % 360
        self.mirrored = bool(mirrored)
        self.setTransformOriginPoint(self.boundingRect().center())
        transform = QTransform()
        if self.mirrored:
            transform.scale(-1, 1)
        self.setTransform(transform)
        self.setRotation(self.rotation_degrees)
        self._reposition_ports()
        for wire in self.wires:
            wire.update_path()

    def _draw_upright_text(self, painter, rect, alignment, text):
        """Dibuja texto sin reflejarlo ni rotarlo con el símbolo del CI."""
        transform = self.sceneTransform()
        origin = transform.map(QPointF(0, 0))
        x_axis = transform.map(QPointF(1, 0)) - origin
        y_axis = transform.map(QPointF(0, 1)) - origin
        x_length = math.hypot(x_axis.x(), x_axis.y())
        y_length = math.hypot(y_axis.x(), y_axis.y())
        if not x_length or not y_length:
            painter.drawText(rect, alignment, text)
            return
        a, b = x_axis.x() / x_length, x_axis.y() / x_length
        c, d = y_axis.x() / y_length, y_axis.y() / y_length
        determinant = a * d - b * c
        if abs(determinant) < 1e-9:
            painter.drawText(rect, alignment, text)
            return
        # Invierte solo giro y espejo. Conserva el tamaño normal del rótulo.
        ia, ib = d / determinant, -b / determinant
        ic, id_ = -c / determinant, a / determinant
        center = rect.center()
        dx = center.x() - ia * center.x() - ic * center.y()
        dy = center.y() - ib * center.x() - id_ * center.y()
        upright = QTransform()
        upright.setMatrix(ia, ib, 0, ic, id_, 0, dx, dy, 1)
        painter.save()
        painter.setWorldTransform(upright, True)
        painter.drawText(rect, alignment, text)
        painter.restore()

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
                    w.set_active(val is not False and val != 0 and val != "Z")

    def update_all_output_wires(self):
        """Refresca el color de TODOS los wires de salida según el estado actual."""
        for w in self.wires:
            src = w.src_port
            if isinstance(src, Port) and not src.is_input and src.graphic is self:
                out_idx = src.port_index
                val = self.widg.exit[out_idx] if out_idx < len(self.widg.exit) else False
                w.set_active(val is not False and val != 0 and val != "Z")

    def update_switch_look(self):
        self.update_port_color(0, is_input=False)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            # Let the separate context-menu event open the popup, after the
            # mouse press has returned to QGraphicsView's drag state machine.
            e.ignore()
            return
        from widgets.widgets import Button
        if e.button() == Qt.LeftButton and isinstance(self.widg, Button):
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                self.widg.press(view.board_ref)
            e.accept()
            return
        super().mousePressEvent(e)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.screenPos())
        event.accept()

    def context_menu(self):
        view = self.scene().views()[0]
        menu = QMenu(view.window())
        menu.addAction(tr("Eliminar"), lambda: _delete_canvas_item(self))
        if isinstance(self, ModuleGraphic):
            menu.addAction(tr("Cambiar aspecto"), self.show_appearance_editor)
        else:
            menu.addAction(tr("Editar"), self.show_config)
        return menu

    def show_context_menu(self, screen_pos):
        self.scene().clearSelection()
        self.setSelected(True)
        self.context_menu().exec(screen_pos)

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
        self._position_logic_ports(self._ports_in, True, self)
        self._position_logic_ports(self._ports_out, False, self)

    def shape(self):
        if self._has_many_ports():
            path = QPainterPath()
            path.addRoundedRect(self._linear_body_rect(), 10, 10)
            return path
        from widgets.widgets import Splitter, Combiner
        if isinstance(self.widg, (Splitter, Combiner)):
            path = QPainterPath()
            path.addRoundedRect(QRectF(-58, -30, 116, 60), 10, 10)
            return path
        return super().shape()

    def boundingRect(self):
        if self._has_many_ports():
            return self._linear_body_rect().adjusted(-12, -8, 12, 8)
        from widgets.widgets import BusInput, BusLamp
        if isinstance(self.widg, (BusInput, BusLamp)):
            return QRectF(-62, -42, 124, 84)
        from widgets.widgets import Splitter, Combiner
        if isinstance(self.widg, (Splitter, Combiner)) and not (
                len(self._ports_in) > 6 or len(self._ports_out) > 6):
            return QRectF(-76, -42, 152, 84)
        return QRectF(-62, -42, 124, 84)

    def _has_many_ports(self):
        return max(len(self._ports_in), len(self._ports_out)) > 6

    def _linear_body_rect(self):
        count = max(len(self._ports_in), len(self._ports_out))
        height = max(136, count * 24 + 20)
        return QRectF(-100, -height / 2, 200, height)

    @staticmethod
    def _position_logic_ports(ports, is_input, graphic):
        from widgets.widgets import Splitter, Combiner
        count = len(ports)
        if graphic._has_many_ports():
            x = -104 if is_input else 104
            for index, port in enumerate(ports):
                y = (index - (count - 1) / 2) * 24
                port.setPos(graphic.mapToScene(QPointF(x, y)))
            return
        wide_bus_component = isinstance(graphic.widg, (Splitter, Combiner))
        port_x = 68 if wide_bus_component else 58
        x = -port_x if is_input else port_x
        for index, port in enumerate(ports):
            y = -28 + 56 * (index + 1) / (count + 1)
            port.setPos(graphic.mapToScene(QPointF(x, y)))

    def _paint_port_identifiers(self, painter):
        if not self._has_many_ports():
            return
        painter.save()
        painter.setPen(QPen(QColor(190, 207, 222) if self._theme_is_dark()
                            else QColor(72, 91, 109)))
        font = QFont("Arial", 7, QFont.Weight.Bold)
        painter.setFont(font)
        for is_input, ports in ((True, self._ports_in), (False, self._ports_out)):
            count = len(ports)
            for index in range(count):
                y = (index - (count - 1) / 2) * 24
                label_rect = QRectF(-92 if is_input else 72, y - 7, 20, 14)
                self._draw_upright_text(painter, label_rect, Qt.AlignCenter, tr(str(index + 1)))
        painter.restore()

    def paint(self, painter: QPainter, option, widget=None):
        kind = type(self.widg).__name__.upper()
        is_switch = kind == "SWITCH"
        is_delay = kind == "DELAY"
        is_button = kind == "BUTTON"
        is_clock = kind == "CLOCK"
        is_bus_component = kind in {"BUSINPUT", "BUSLAMP", "BUSVIEWER", "SPLITTER", "COMBINER", "TRISTATE"}
        dark = self._theme_is_dark()
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
        elif is_clock:
            if self.widg.state:
                fill, accent = (QColor(25, 78, 82), QColor(81, 224, 217)) if dark else (QColor(222, 248, 246), QColor(29, 137, 143))
            else:
                fill, accent = (QColor(42, 57, 72), QColor(132, 177, 195)) if dark else (QColor(235, 245, 248), QColor(72, 127, 145))

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(accent, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QBrush(fill))

        if self._has_many_ports() and not is_bus_component:
            painter.drawRoundedRect(self._linear_body_rect(), 10, 10)
        elif is_bus_component:
            is_screen = kind in {"BUSINPUT", "BUSLAMP", "BUSVIEWER"}
            painter.setPen(QPen(accent, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(QBrush(fill))
            is_wide_bus_component = kind in {"SPLITTER", "COMBINER"}
            half_width = 58 if is_wide_bus_component else (54 if is_screen else 48)
            half_height = 36 if is_screen else 30
            if self._has_many_ports():
                half_width = self._linear_body_rect().width() / 2
                half_height = self._linear_body_rect().height() / 2
            painter.drawRoundedRect(QRectF(-half_width, -half_height,
                                           half_width * 2, half_height * 2), 10, 10)
            if is_screen:
                title = "BUS ENTRADA" if kind == "BUSINPUT" else "BUS SALIDA"
                value = (self.widg.value if kind == "BUSINPUT" else self.widg.enter[0])
                if value in ("X", "Z"):
                    number = str(value)
                    detail = tr("{width} bits · estado {value}", width=self.widg.width, value=value)
                else:
                    numeric = int(value)
                    number = str(numeric)
                    digits = max(2, (self.widg.width + 3) // 4)
                    detail = f"0x{numeric:0{digits}X} · {self.widg.width} bits"
                painter.setPen(QPen(label_color))
                painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                if kind != "BUSVIEWER":
                    self._draw_upright_text(painter, QRectF(-48, -32, 96, 15), Qt.AlignCenter, tr(title))
                screen = QRectF(-47, -27 if kind == "BUSVIEWER" else -13,
                               94, 48 if kind == "BUSVIEWER" else 34)
                painter.setPen(QPen(QColor(89, 113, 130) if dark else QColor(182, 197, 207), 1))
                painter.setBrush(QBrush(QColor(20, 30, 40) if dark else QColor(227, 237, 239)))
                painter.drawRoundedRect(screen, 5, 5)
                number_font = QFont("Consolas", 16, QFont.Weight.Bold)
                metrics = QFontMetricsF(number_font)
                while metrics.horizontalAdvance(number) > 86 and number_font.pointSize() > 9:
                    number_font.setPointSize(number_font.pointSize() - 1)
                    metrics = QFontMetricsF(number_font)
                painter.setPen(QPen(QColor(129, 245, 194) if dark else QColor(28, 112, 91)))
                painter.setFont(number_font)
                self._draw_upright_text(painter, screen.adjusted(2, 0, -2, 0), Qt.AlignCenter, tr(number))
                painter.setPen(QPen(QColor(173, 192, 207) if dark else QColor(83, 105, 118)))
                painter.setFont(QFont("Arial", 7, QFont.Weight.DemiBold))
                self._draw_upright_text(painter, QRectF(-49, 22, 98, 11), Qt.AlignCenter, tr(detail))
            else:
                title = {"SPLITTER": "DIVISOR DE BUS",
                         "COMBINER": "COMBINADOR DE BUS",
                         "TRISTATE": "BUS TRIESTADO"}.get(kind, "BUS")
                if kind == "TRISTATE":
                    value = self.widg.exit[0]
                    shown = value if value in ("X", "Z") else f"0x{int(value):X}"
                elif kind == "SPLITTER":
                    shown = f"{self.widg.width} bits → 1 bit"
                elif kind == "COMBINER":
                    shown = f"1 bit → {self.widg.width} bits"
                else:
                    shown = f"{self.widg.width} bits"
                painter.setPen(QPen(label_color))
                text_half_width = 54 if is_wide_bus_component else 44
                painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
                self._draw_upright_text(painter, QRectF(-text_half_width, -23,
                                                        text_half_width * 2, 16), Qt.AlignCenter, tr(title))
                painter.setFont(QFont("Consolas", 9, QFont.Weight.DemiBold))
                self._draw_upright_text(painter, QRectF(-text_half_width, -2,
                                                        text_half_width * 2, 22), Qt.AlignCenter, tr(shown))
        elif is_switch or is_delay or is_button or is_clock:
            painter.drawRoundedRect(QRectF(-44, -26, 88, 52), 12, 12)
            if is_switch:
                painter.setPen(QPen(QColor(238, 247, 255), 2.5, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(-20, 12, 18 if self.widg.state else -2, -12)
                painter.setBrush(QBrush(accent))
                painter.drawEllipse(QPointF(20 if self.widg.state else -20, 0), 7, 7)
            elif is_clock:
                painter.setPen(QPen(accent, 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                wave = QPainterPath(QPointF(-25, 9))
                wave.lineTo(-15, 9)
                wave.lineTo(-15, -9)
                wave.lineTo(-2, -9)
                wave.lineTo(-2, 9)
                wave.lineTo(11, 9)
                wave.lineTo(11, -9)
                wave.lineTo(25, -9)
                painter.drawPath(wave)
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
        elif is_clock:
            label = "CLK"
        elif is_delay:
            label = "Δt"
        elif is_button:
            label = translate_text("PULSADO" if self.widg.state else "PULSAR")
        elif is_bus_component:
            label = ""
        else:
            label = kind
        self._paint_port_identifiers(painter)
        if label:
            painter.setPen(QPen(label_color))
            font = QFont()
            font.setBold(True); font.setPointSize(9 if len(label) < 5 else 8)
            painter.setFont(font)
            self._draw_upright_text(painter, QRectF(-31, -9, 62, 18), Qt.AlignCenter, tr(label))
        rect = self._linear_body_rect() if self._has_many_ports() else QRectF(-57, -37, 114, 74)
        self._paint_selection(painter, rect, 11)

    def update_switch_look(self):
        self.update()


class ModuleGraphic(Graphic):
    """Símbolo vectorial para un circuito guardado como módulo."""

    def __init__(self, widg):
        super().__init__(widg, svg_path=None, scale=1.0)
        self.appearance = {}

    @staticmethod
    def normalize_appearance(data):
        if not isinstance(data, dict):
            raise ValueError(tr("Aspecto de módulo no válido."))
        colors = {}
        for key in ("fill", "border", "text"):
            if key in data:
                if not isinstance(data[key], str) or not QColor(data[key]).isValid():
                    raise ValueError(tr("Color de módulo no válido."))
                colors[key] = QColor(data[key]).name()
        if "radius" in data:
            if type(data["radius"]) is not int or not 0 <= data["radius"] <= 24:
                raise ValueError(tr("Radio de módulo no válido."))
            colors["radius"] = data["radius"]
        return colors

    def set_appearance(self, data):
        self.appearance = self.normalize_appearance(data)
        self.update()

    def show_appearance_editor(self):
        ModuleAppearanceDialog(self).exec()

    def _module_layout(self):
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(9)
        port_font = QFont(title_font)
        port_font.setPointSize(7)
        title_metrics = QFontMetricsF(title_font)
        port_metrics = QFontMetricsF(port_font)
        title = module_display_name(self.widg)
        # Wrap long multi-word titles, but always fit their longest word.
        # Pin labels occupy their own lanes, outside the title's rectangle.
        longest_word = max((title_metrics.horizontalAdvance(word)
                            for word in title.split()), default=0)
        title_width = math.ceil(max(96, longest_word + 4,
                                   min(260, title_metrics.horizontalAdvance(title) + 4)))
        title_height = math.ceil(title_metrics.boundingRect(
            QRectF(0, 0, title_width, 10000), Qt.AlignCenter | Qt.TextWordWrap, title).height())
        texts = []
        lanes = []
        for values, labels, numbers in (
                (self.widg.enter, self.widg.input_labels, self.widg.input_numbers),
                (self.widg.exit, self.widg.output_labels, self.widg.output_numbers)):
            side = [labels[i] or str(numbers[i]) for i in range(len(values))]
            texts.append(side)
            lanes.append(math.ceil(max((port_metrics.horizontalAdvance(text)
                                       for text in side), default=0)) + (18 if side else 0))
        row_height = math.ceil(port_metrics.height()) + 10
        height = max(72, title_height + 24, max(map(len, texts)) * row_height + 20)
        left = -title_width / 2 - lanes[0] - 12
        width = title_width + sum(lanes) + 24
        body = QRectF(left, -height / 2, width, height)
        title_rect = QRectF(-title_width / 2, -title_height / 2, title_width, title_height)
        ports = []
        for side, labels in enumerate(texts):
            count = len(labels)
            positions = []
            for index, text in enumerate(labels):
                y = -row_height * (count - 1) / 2 + index * row_height
                x = body.left() if side == 0 else body.right()
                label_x = x + 9 if side == 0 else x - lanes[1] + 9
                rect = QRectF(label_x, y - port_metrics.height() / 2,
                              max(0, lanes[side] - 18), port_metrics.height())
                positions.append((QPointF(x, y), rect, text))
            ports.append(positions)
        return body, title_rect, title_font, port_font, ports

    def boundingRect(self):
        return self._module_layout()[0].adjusted(-7, -7, 7, 7)

    def paint(self, painter: QPainter, option, widget=None):
        rect, title_rect, title_font, port_font, ports = self._module_layout()
        dark = self._theme_is_dark()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(self.appearance.get("border", "#6597d3" if dark else "#3769a9")), 2))
        painter.setBrush(QBrush(QColor(self.appearance.get("fill", "#243244" if dark else "#f2f7fd"))))
        radius = self.appearance.get("radius", 10)
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QPen(QColor(self.appearance.get("text", "#eff5fc" if dark else "#1f2f42"))))
        painter.setFont(title_font)
        self._draw_upright_text(painter, title_rect, Qt.AlignCenter | Qt.TextWordWrap,
                                module_display_name(self.widg))
        painter.setFont(port_font)
        for side, labels in enumerate(ports):
            alignment = (Qt.AlignLeft if side == 0 else Qt.AlignRight) | Qt.AlignVCenter
            for position, label_rect, text in labels:
                self._draw_upright_text(painter, label_rect, alignment, text)
        self._paint_selection(painter, rect, radius + 2)

    def _reposition_ports(self):
        layout = self._module_layout()[4]
        for side, ports in enumerate((self._ports_in, self._ports_out)):
            for port, (position, label_rect, text) in zip(ports, layout[side]):
                port.setPos(self.mapToScene(position))
                port.update_tooltip()


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
        self.setToolTip(tr('Bombilla {v0} · clic derecho → Editar para ajustar el retardo', v0=widg.id))

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
        self._selection_outline.setPen(QPen(SELECTION_COLOR, 1.4, Qt.DashLine))
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
            self.show_context_menu(e.screenPos())
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

    W        = 90
    H        = 156
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
        self._selection_outline.setPen(QPen(SELECTION_COLOR, 1.4, Qt.DashLine))
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
        painter.setPen(QColor("#eff5fc" if self._theme_is_dark() else "#1f2f42"))
        painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        for index, port in enumerate(self._ports_in):
            y = self.mapFromScene(port.scenePos()).y()
            self._draw_upright_text(painter, QRectF(-10, y - 7, 8, 14),
                                    Qt.AlignCenter, "abcdefg"[index])

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
        x = -self.PORT_GAP + PORT_RADIUS + 2
        for index, port in enumerate(self._ports_in):
            y = 12 + 22 * index
            port.setPos(self.mapToScene(QPointF(x, y)))

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
            self.show_context_menu(e.screenPos())
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
        self.setText(tr(self.color.name().upper()))
        text_color = "#101820" if self.color.lightness() > 140 else "#ffffff"
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self.color.name()}; "
            "border: 1px solid #718096; border-radius: 4px; padding: 3px 8px; "
            f"color: {text_color}; font-weight: 600; }}"
            "QPushButton:hover { border: 2px solid #2684ff; }")

    def choose_color(self):
        color = QColorDialog.getColor(self.color, self, tr("Elegir color"))
        if color.isValid():
            self.color = color
            self._refresh_swatch()


# ── ConfigDialog ─────────────────────────────────────────────────────────────

class ConfigDialog(QDialog):

    def __init__(self, graphic: Graphic, parent=None):
        if parent is None and graphic.scene() and graphic.scene().views():
            parent = graphic.scene().views()[0].window()
        super().__init__(parent)
        self.graph = graphic
        self.widg  = graphic.widg

        from widgets.widgets import Module, Switch, Button, Clock, Bulb, Display, Delay, BusViewer
        self._is_module = isinstance(self.widg, Module)
        if self._is_module:
            self._build_module_editor()
            return
        if isinstance(self.widg, Module):
            component_name = self.widg.name
        else:
            component_name = next((label for kind, label in (
                (Switch, "Interruptor"), (Button, "Botón"), (Bulb, "Bombilla"),
                (Clock, "Reloj"), (Display, "Display"), (Delay, "RETARDO"),
                (BusViewer, "Visor de bus"))
                if isinstance(self.widg, kind)), type(self.widg).__name__)
        self.setWindowTitle(tr('Editar {v0} {v1}', v0=(component_name if isinstance(self.widg, Module) else tr(component_name)), v1=self.widg.id))
        self.setMinimumWidth(340)

        lay = QVBoxLayout()
        from widgets.widgets import Module, BusInput, BusLamp, BusViewer, Splitter, Combiner, TriState
        self.bus_width_field = None
        self.bus_value_field = None
        if isinstance(self.widg, (BusInput, BusLamp, Splitter, Combiner, TriState)):
            group = QGroupBox(tr("Configuración del bus"), self)
            bus_layout = QVBoxLayout(group)
            width_row = QHBoxLayout()
            width_row.addWidget(QLabel(tr("Ancho:"), group))
            self.bus_width_field = QSpinBox(group)
            self.bus_width_field.setRange(2, 32)
            self.bus_width_field.setSuffix(tr(" bits"))
            self.bus_width_field.setValue(self.widg.width)
            width_row.addWidget(self.bus_width_field)
            bus_layout.addLayout(width_row)
            if isinstance(self.widg, BusInput):
                value_row = QHBoxLayout()
                value_row.addWidget(QLabel(tr("Valor decimal:"), group))
                self.bus_value_field = QLineEdit(str(self.widg.value), group)
                self.bus_value_field.setPlaceholderText(tr("0 o 0xFF"))
                value_row.addWidget(self.bus_value_field)
                bus_layout.addLayout(value_row)
            lay.addWidget(group)

        if self.widg.can_set_enter():
            self.sp_in = QSpinBox(self)
            self.sp_in.setRange(self.widg.min_enter, 8)
            self.sp_in.setValue(max(self.widg.min_enter, len(self.widg.enter)))
            self.sp_in.setToolTip(tr("Cambia el número de entradas de este componente"))
            self.sp_in.valueChanged.connect(self._set_input_count)
            row = QHBoxLayout()
            row.addWidget(QLabel(tr("Número de entradas:")))
            row.addWidget(self.sp_in)
            lay.addLayout(row)

        if isinstance(self.widg, Clock):
            interval_layout = QHBoxLayout()
            interval_layout.addWidget(QLabel(tr("Intervalo de cambio:")))
            self.sp_clock_interval = QSpinBox(self)
            self.sp_clock_interval.setRange(10, 60000)
            self.sp_clock_interval.setValue(self.widg.interval_ms)
            self.sp_clock_interval.setSuffix(tr(" ms"))
            interval_layout.addWidget(self.sp_clock_interval)
            lay.addLayout(interval_layout)
        elif isinstance(self.widg, BusViewer):
            lay.addWidget(QLabel(tr("El visor se adapta automáticamente al cable conectado."), self))
        else:
            delay_layout = QHBoxLayout()
            delay_layout.addWidget(QLabel(tr("Retardo de señal (ms):")))
            self.sp_delay = QSpinBox(self)
            self.sp_delay.setRange(0, 10000)
            self.sp_delay.setValue(self.widg.delay_ms)
            self.sp_delay.setSuffix(tr(" ms"))
            delay_layout.addWidget(self.sp_delay)
            lay.addLayout(delay_layout)
            gate_delay_layout = QHBoxLayout()
            gate_delay_layout.addWidget(QLabel(tr("Retraso de cálculo:")))
            self.sp_delay_gates = QSpinBox(self)
            self.sp_delay_gates.setRange(0, 10000)
            self.sp_delay_gates.setValue(self.widg.delay_gates)
            self.sp_delay_gates.setToolTip(
                tr("Añade etapas de cálculo antes de propagar el resultado."))
            gate_delay_layout.addWidget(self.sp_delay_gates)
            lay.addLayout(gate_delay_layout)

        self.segment_color_fields = []
        if isinstance(self.widg, Display):
            group = QGroupBox(tr("Color de cada segmento encendido"), self)
            group_layout = QVBoxLayout(group)
            names = ("a · superior", "b · superior derecha", "c · inferior derecha",
                     "d · inferior", "e · inferior izquierda", "f · superior izquierda",
                     "g · medio")
            saved_colors = getattr(self.widg, "segment_colors", [None] * 7)
            for index, name in enumerate(names):
                row = QHBoxLayout()
                row.addWidget(QLabel(tr(name), group), 1)
                color = (saved_colors[index] if index < len(saved_colors) and saved_colors[index]
                         else COLOR_SEG_ON)
                picker = ColorPickerButton(color, group)
                row.addWidget(picker)
                group_layout.addLayout(row)
                self.segment_color_fields.append(picker)
            lay.addWidget(group)
            self.resize(360, 470)

        self.module_name_field = None
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._apply_config)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.setLayout(lay)

    def _build_module_editor(self):
        self.setWindowTitle(tr('Editar {v0} {v1}', v0=self.widg.name, v1=self.widg.id))
        self.setMinimumSize(520, 420)
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        self.module_name_field = QLineEdit(self.widg.name, self)
        self.module_name_field.setMaxLength(120)
        form.addRow(tr("Nombre del módulo:"), self.module_name_field)
        layout.addLayout(form)
        self.module_tabs = QTabWidget(self)
        layout.addWidget(self.module_tabs, 1)

        labels_page = QWidget(self)
        labels_layout = QVBoxLayout(labels_page)
        help_text = QLabel(tr("Edita las etiquetas y usa Subir o Bajar para ordenar los puertos de arriba abajo. Los cables conservan su conexión."), labels_page)
        help_text.setWordWrap(True)
        labels_layout.addWidget(help_text)
        columns = QHBoxLayout()
        self.input_labels_table = self._port_labels_table(columns, "Entradas", self.widg.input_labels, self.widg.input_widths)
        self.output_labels_table = self._port_labels_table(columns, "Salidas", self.widg.output_labels, self.widg.output_widths)
        labels_layout.addLayout(columns, 1)
        self.module_tabs.addTab(labels_page, tr("Etiquetas"))

        appearance_page = QWidget(self)
        appearance_layout = QVBoxLayout(appearance_page)
        appearance_form = QFormLayout()
        view = self.graph.scene().views()[0]
        dark = view.theme_mode == "dark"
        self._appearance_defaults = {"fill": "#243244" if dark else "#f2f7fd",
                                     "border": "#6597d3" if dark else "#3769a9",
                                     "text": "#eff5fc" if dark else "#1f2f42", "radius": 10}
        self._initial_appearance = dict(self.graph.appearance)
        self._reset_requested = False
        self.colors = {}
        for key, title in (("fill", "Fondo"), ("border", "Borde"), ("text", "Texto")):
            picker = ColorPickerButton(self.graph.appearance.get(key, self._appearance_defaults[key]), self)
            self.colors[key] = picker
            appearance_form.addRow(tr(title), picker)
        self.radius = QSpinBox(self)
        self.radius.setRange(0, 24)
        self.radius.setValue(self.graph.appearance.get("radius", 10))
        appearance_form.addRow(tr("Redondeado de esquinas:"), self.radius)
        appearance_layout.addLayout(appearance_form)
        reset = QPushButton(tr("Restablecer aspecto"), self)
        reset.clicked.connect(self.reset_appearance)
        appearance_layout.addWidget(reset, 0, Qt.AlignLeft)
        appearance_layout.addStretch(1)
        self.module_tabs.addTab(appearance_page, tr("Aspecto"))

        simulation_page = QWidget(self)
        simulation_form = QFormLayout(simulation_page)
        self.sp_delay = QSpinBox(self)
        self.sp_delay.setRange(0, 10000)
        self.sp_delay.setValue(self.widg.delay_ms)
        self.sp_delay.setSuffix(tr(" ms"))
        simulation_form.addRow(tr("Retardo de señal (ms):"), self.sp_delay)
        self.sp_delay_gates = QSpinBox(self)
        self.sp_delay_gates.setRange(0, 10000)
        self.sp_delay_gates.setValue(self.widg.delay_gates)
        self.sp_delay_gates.setToolTip(tr("Añade etapas de cálculo antes de propagar el resultado."))
        simulation_form.addRow(tr("Retraso de cálculo:"), self.sp_delay_gates)
        self.module_tabs.addTab(simulation_page, tr("Simulación"))

        hint = QLabel(tr("Aceptar aplica los cambios al circuito. Guardar también actualiza el archivo .dmodule."), self)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        source = getattr(self.widg, "module_path", None)
        self.module_file_label = QLabel(tr("Archivo: {name}", name=Path(source).name) if source else tr("Guardar creará un archivo .dmodule en la biblioteca."), self)
        self.module_file_label.setWordWrap(True)
        self.module_file_label.setToolTip(str(source or ""))
        layout.addWidget(self.module_file_label)
        self.module_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        for role, title in ((QDialogButtonBox.Ok, "Aceptar"), (QDialogButtonBox.Save, "Guardar"), (QDialogButtonBox.Cancel, "Cancelar")):
            self.module_buttons.button(role).setText(tr(title))
            self.module_buttons.button(role).setAutoDefault(False)
        self.module_buttons.button(QDialogButtonBox.Ok).setDefault(True)
        self.module_buttons.button(QDialogButtonBox.Ok).clicked.connect(self.accept)
        self.module_buttons.button(QDialogButtonBox.Save).clicked.connect(self._save_module)
        self.module_buttons.rejected.connect(self.reject)
        layout.addWidget(self.module_buttons)

    def _port_labels_table(self, columns, title, labels, widths):
        group = QGroupBox(tr(title), self)
        layout = QVBoxLayout(group)
        table = QTableWidget(len(labels), 2, group)
        table.setHorizontalHeaderLabels([tr("Etiqueta"), tr("Ancho")])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setMinimumHeight(80)
        for index, label in enumerate(labels):
            item = QTableWidgetItem(label)
            item.setData(Qt.UserRole, index)
            table.setItem(index, 0, item)
            width_item = QTableWidgetItem(tr("{width} bits", width=widths[index]) if widths[index] > 1 else tr("1 bit"))
            width_item.setFlags(width_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(index, 1, width_item)
        layout.addWidget(table, 1)
        actions = QHBoxLayout()
        up = QPushButton(tr("Subir"), group)
        down = QPushButton(tr("Bajar"), group)
        up.setProperty("portDirection", "up")
        down.setProperty("portDirection", "down")
        for button in (up, down):
            button.setAutoDefault(False)
        actions.addWidget(up)
        actions.addWidget(down)
        actions.addStretch(1)
        def update_buttons():
            row = table.currentRow()
            up.setEnabled(row > 0)
            down.setEnabled(0 <= row < table.rowCount() - 1)
        table.currentCellChanged.connect(update_buttons)
        up.clicked.connect(lambda: self._move_port_label(table, -1))
        down.clicked.connect(lambda: self._move_port_label(table, 1))
        if labels:
            table.setCurrentCell(0, 0)
        update_buttons()
        layout.addLayout(actions)
        columns.addWidget(group, 1)
        return table

    @staticmethod
    def _move_port_label(table, direction):
        row = table.currentRow()
        target = row + direction
        if not 0 <= row < table.rowCount() or not 0 <= target < table.rowCount():
            return
        current = [table.takeItem(row, column) for column in range(table.columnCount())]
        other = [table.takeItem(target, column) for column in range(table.columnCount())]
        for column in range(table.columnCount()):
            table.setItem(target, column, current[column])
            table.setItem(row, column, other[column])
        table.setCurrentCell(target, 0)

    def reset_appearance(self):
        self._reset_requested = True
        for key, picker in self.colors.items():
            picker.color = QColor(self._appearance_defaults[key])
            picker._refresh_swatch()
        self.radius.setValue(10)

    def _module_changes(self):
        from project_io import module_definition
        name = self.module_name_field.text().strip()
        if not name:
            raise ValueError(tr("Introduce un nombre para el módulo."))
        def ports(table, original_numbers):
            numbers, labels = list(original_numbers), [""] * table.rowCount()
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                original = item.data(Qt.UserRole)
                numbers[original] = original_numbers[row]
                labels[original] = item.text().strip()
            return numbers, labels
        inputs, in_labels = ports(self.input_labels_table, self.widg.input_numbers)
        outputs, out_labels = ports(self.output_labels_table, self.widg.output_numbers)
        circuit = copy.deepcopy(self.widg.stateful_circuit)
        if circuit:
            circuit["initial_state"] = self.widg.export_stateful_state()
        definition = module_definition(name, len(inputs), len(outputs), self.widg.truth_table,
            self.sp_delay.value(), inputs, outputs, circuit, in_labels, out_labels,
            self.widg.input_widths, self.widg.output_widths, "auto", self.sp_delay_gates.value())
        chosen = {**{key: picker.color.name() for key, picker in self.colors.items()}, "radius": self.radius.value()}
        initial = {**self._appearance_defaults, **self._initial_appearance}
        appearance = ({} if self._reset_requested and chosen == self._appearance_defaults else
                      dict(self._initial_appearance) if not self._reset_requested and chosen == initial else chosen)
        if appearance:
            definition["appearance"] = appearance
        return definition, inputs, outputs, appearance

    def _module_save_path(self, name):
        module_path = getattr(self.widg, "module_path", None)
        if module_path:
            path = Path(module_path).resolve()
            if path.suffix.lower() != ".dmodule":
                raise ValueError(tr("El archivo de origen debe tener la extensión .dmodule."))
            return path
        from app_runtime import CI_LIBRARY_DIR
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "Modulo"
        if re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', stem, re.I):
            stem = "_" + stem
        path = CI_LIBRARY_DIR / (stem + ".dmodule")
        suffix = 2
        while path.exists():
            path = CI_LIBRARY_DIR / f"{stem} ({suffix}).dmodule"
            suffix += 1
        return path

    def _commit_module(self, save=False):
        from project_io import write_json_atomic
        try:
            definition, inputs, outputs, appearance = self._module_changes()
            path = self._module_save_path(definition["name"]) if save else None
            if path is not None:
                write_json_atomic(path, definition)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(self, tr("No se pudo guardar el CI") if save else tr("Nombre no válido"), str(error))
            return
        owner = self.graph.scene().views()[0].window()
        owner._capture_history_change()
        self.graph.prepareGeometryChange()
        self.widg.name = definition["name"]
        self.widg.set_port_numbers(inputs, outputs)
        self.widg.set_port_labels(definition.get("input_labels", []), definition.get("output_labels", []))
        self.widg.set_delay(self.sp_delay.value())
        self.widg.set_delay_gates(self.sp_delay_gates.value())
        self.graph.set_appearance(appearance)
        if path is not None:
            self.widg.module_path = str(path.resolve())
            from app_runtime import CI_LIBRARY_DIR
            if path.resolve().is_relative_to(CI_LIBRARY_DIR.resolve()):
                self.widg.module_source = "library"
            for index, imported in enumerate(owner.imported_modules):
                source = imported.get("module_path")
                if source and Path(source).resolve() == path.resolve():
                    owner.imported_modules[index] = {**definition, "module_path": str(path.resolve())}
            owner.statusBar().showMessage(tr("Módulo guardado: {name}", name=path.name), 5000)
        owner.actualizar_biblioteca_ci()
        owner._capture_history_change()
        super().accept()

    def accept(self):
        if self._is_module:
            self._commit_module(save=False)
        else:
            super().accept()

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
        if self._is_module:
            self._commit_module(save=True)

    def _apply_config(self):
        if self._is_module:
            self._commit_module(save=False)
            return
        from widgets.widgets import Module, Display, Clock, BusInput, BusViewer
        if self.widg.can_set_enter():
            self.widg.set_enter(self.sp_in.value())
        if isinstance(self.widg, Clock):
            self.widg.set_interval(self.sp_clock_interval.value())
            scene = self.graph.scene()
            if scene and scene.views():
                scene.views()[0].sync_clock_timers()
        elif not isinstance(self.widg, BusViewer):
            self.widg.set_delay(self.sp_delay.value())
            self.widg.set_delay_gates(self.sp_delay_gates.value())
        if self.bus_width_field is not None:
            width = self.bus_width_field.value()
            if isinstance(self.widg, BusInput):
                try:
                    value = int(self.bus_value_field.text().strip() or "0", 0)
                except ValueError:
                    QMessageBox.warning(self, tr("Valor no válido"),
                                        tr("Escribe un entero decimal o hexadecimal, por ejemplo 25 o 0x19."))
                    return
                self.widg.set_bus(width, value)
            else:
                self.widg.set_bus_width(width)
            self._refresh_port_connections()
        if isinstance(self.widg, Display):
            self.widg.segment_colors = [picker.color.name() for picker in self.segment_color_fields]
            self.graph._refresh_look()
        self._notify_history_change()
        self.accept()

class ModuleAppearanceDialog(ConfigDialog):
    """The appearance entry point shares the module's labels and save actions."""
    def __init__(self, graphic):
        super().__init__(graphic, graphic.scene().views()[0].window())
        self.module_tabs.setCurrentIndex(1)


class BulbDelayDialog(QDialog):
    """Editor sencillo del retardo de señal de una bombilla."""

    def __init__(self, graphic: BulbGraphic, parent=None):
        super().__init__(parent)
        self.graphic = graphic
        self.widg = graphic.widg
        self.setWindowTitle(tr('Editar Bombilla {v0}', v0=self.widg.id))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Retardo de señal (ms):"), self))
        self.delay = QSpinBox(self)
        self.delay.setRange(0, 10000)
        self.delay.setValue(int(self.widg.delay_ms))
        self.delay.setSuffix(tr(" ms"))
        row.addWidget(self.delay)
        layout.addLayout(row)

        gate_row = QHBoxLayout()
        gate_row.addWidget(QLabel(tr("Retraso de cálculo:"), self))
        self.delay_gates = QSpinBox(self)
        self.delay_gates.setRange(0, 10000)
        self.delay_gates.setValue(int(self.widg.delay_gates))
        gate_row.addWidget(self.delay_gates)
        layout.addLayout(gate_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(tr("Color al encender:"), self))
        self.color_picker = ColorPickerButton(
            getattr(self.widg, "bulb_color", None) or "#ffc832", self)
        color_row.addWidget(self.color_picker)
        layout.addLayout(color_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton(tr("Guardar"), self)
        save.clicked.connect(self._save)
        cancel = QPushButton(tr("Cancelar"), self)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _save(self):
        self.widg.set_delay(self.delay.value())
        self.widg.set_delay_gates(self.delay_gates.value())
        self.widg.bulb_color = self.color_picker.color.name()
        self.graphic._refresh_look()
        scene = self.graphic.scene()
        if scene and scene.views():
            window = scene.views()[0].window()
            if hasattr(window, "_schedule_history_capture"):
                window._schedule_history_capture()
        self.accept()
