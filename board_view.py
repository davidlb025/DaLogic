"""
board_view.py  –  Vista del tablero.

Sistema de cables:
  · Click en puerto/junction/endpoint → inicia trazado
  · Clicks intermedios → añaden vértices (codos)
  · Click final en puerto/junction/endpoint → completa el cable
  · Click final en vacío → deja extremo libre (WireEndpoint)
  · Click en cable existente → inserta punto medio arrastrable
  · Soltar cable sobre otro cable → crea Junction automático
  · Doble-click en vacío → crea Junction explícito
  · Tecla Escape → cancela trazado en curso
  · Supr/Backspace → elimina selección (wires, graphics, junctions)
"""

from __future__ import annotations

from collections import deque

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsItem
)
from PySide6.QtCore import Qt, QRectF, QPointF, QEvent, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QMouseEvent, QBrush, QKeyEvent

from widgets.graphics import (
    Port, Wire, Graphic, Junction, WireEndpoint, MidPoint,
    COLOR_WIRE_OFF, COLOR_WIRE_ON
)

SNAP_R = 14


class BoardView(QGraphicsView):
    # Un rectángulo enorme evita que el usuario llegue a un borde en el uso
    # normal. El grid se pinta bajo demanda, por lo que no crea miles de items.
    MAP_WIDTH  = 2_000_000
    MAP_HEIGHT = 2_000_000
    MIN_ZOOM   = 0.20
    MAX_ZOOM   = 4.0

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(QRectF(-self.MAP_WIDTH / 2, -self.MAP_HEIGHT / 2,
                                       self.MAP_WIDTH, self.MAP_HEIGHT))
        self.setScene(self.scene)

        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        self._draw_center()
        self.zoom_act       = 1.0
        self.last_drag_mode = self.dragMode()

        self.board_ref = None
        self.theme_mode = "light"

        self._drawing_wire: Wire | None = None
        self._preview_pos:  QPointF | None = None

        self._signal_queue: deque = deque()
        self._processing_signals = False
        self._signal_steps = 0
        self._input_drivers: dict[tuple[object, int], dict[object, bool]] = {}
        self._prop_timer = QTimer(self)
        self._prop_timer.setSingleShot(True)
        self._prop_timer.timeout.connect(self._process_next_signal)

    # ── Centro ───────────────────────────────────────────────────────────────

    def _draw_center(self):
        x, y, r = 0, 0, 5
        pt = QGraphicsEllipseItem(x - r, y - r, r * 2, r * 2)
        pt.setBrush(QBrush(QColor(78, 98, 122)))
        pt.setPen(QPen(QColor(78, 98, 122)))
        pt.setZValue(-1)
        self.scene.addItem(pt)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Cuadrícula ligera, infinita a efectos prácticos y sin widgets extra."""
        if self.theme_mode == "dark":
            background, minor_col, major_col = QColor(16, 23, 34), QColor(31, 42, 57), QColor(47, 62, 81)
        else:
            background, minor_col, major_col = QColor(247, 249, 252), QColor(225, 231, 240), QColor(203, 214, 229)
        painter.fillRect(rect, background)
        minor, major = 20, 100
        left = int(rect.left() // minor) * minor
        top = int(rect.top() // minor) * minor
        painter.setPen(QPen(minor_col, 0))
        x = left
        while x <= rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += minor
        y = top
        while y <= rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += minor
        left = int(rect.left() // major) * major
        top = int(rect.top() // major) * major
        painter.setPen(QPen(major_col, 0))
        x = left
        while x <= rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += major
        y = top
        while y <= rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += major

    def set_theme(self, mode: str):
        self.theme_mode = mode
        center = next((item for item in self.scene.items()
                       if isinstance(item, QGraphicsEllipseItem) and item.zValue() == -1), None)
        if center:
            color = QColor(78, 98, 122) if mode == "dark" else QColor(151, 166, 184)
            center.setBrush(QBrush(color))
            center.setPen(QPen(color))
        self.viewport().update()

    # ── Helpers de snap ──────────────────────────────────────────────────────

    def _snap_target(self, scene_pos: QPointF, exclude_wire: Wire | None = None):
        best, best_d = None, float("inf")
        for item in self.scene.items(QRectF(
                scene_pos.x() - SNAP_R, scene_pos.y() - SNAP_R,
                SNAP_R * 2, SNAP_R * 2)):
            if not isinstance(item, (Port, Junction, WireEndpoint)):
                continue
            if exclude_wire is not None and item is exclude_wire.src_port:
                continue
            import math
            d = math.hypot(item.scenePos().x() - scene_pos.x(),
                           item.scenePos().y() - scene_pos.y())
            if d < best_d:
                best, best_d = item, d
        return best, best_d

    def _snap_wire(self, scene_pos: QPointF, exclude_wire: Wire | None = None):
        best_wire, best_pos, best_d = None, None, 12.0
        for item in self.scene.items():
            if not isinstance(item, Wire):
                continue
            if item is exclude_wire:
                continue
            pts = item._all_points()
            for i in range(len(pts) - 1):
                d = Wire._dist_point_segment(scene_pos, pts[i], pts[i+1])
                if d < best_d:
                    best_d    = d
                    best_wire = item
                    a, b = pts[i], pts[i+1]
                    ab   = b - a
                    ab2  = ab.x()**2 + ab.y()**2
                    if ab2 > 0:
                        t = max(0, min(1, ((scene_pos.x()-a.x())*ab.x() +
                                          (scene_pos.y()-a.y())*ab.y()) / ab2))
                        best_pos = a + t * ab
                    else:
                        best_pos = a
        return best_wire, best_pos

    # ── Inicio de trazado ────────────────────────────────────────────────────

    def _start_wire(self, src, scene_pos: QPointF):
        wire = Wire(src, dst=None)
        self.scene.addItem(wire)
        self._drawing_wire = wire
        self._preview_pos  = scene_pos
        self.setDragMode(QGraphicsView.NoDrag)

    # ── Callbacks desde ítems ────────────────────────────────────────────────

    def on_port_clicked(self, port: Port):
        if self._drawing_wire is None:
            self._start_wire(port, port.scenePos())
        else:
            self._finish_wire(port)

    def on_junction_clicked(self, junc: Junction):
        if self._drawing_wire is None:
            self._start_wire(junc, junc.scenePos())
        else:
            self._finish_wire(junc)

    def on_endpoint_clicked(self, ep: WireEndpoint):
        if self._drawing_wire is None:
            self._start_wire(ep, ep.scenePos())
        else:
            self._finish_wire(ep)

    def on_wire_clicked(self, wire: Wire, pos: QPointF, idx: int):
        if self._drawing_wire is None:
            wire.insert_midpoint(pos, idx)

    # ── Vértice intermedio ───────────────────────────────────────────────────

    def _add_vertex(self, scene_pos: QPointF):
        if self._drawing_wire is None:
            return
        self._drawing_wire.insert_midpoint(scene_pos)
        self._preview_pos = scene_pos

    # ── Completar cable ──────────────────────────────────────────────────────

    def _finish_wire(self, dst):
        wire = self._drawing_wire
        if wire is None:
            return
        self._drawing_wire = None
        self._preview_pos  = None
        self.setDragMode(QGraphicsView.RubberBandDrag)

        src = wire.src_port
        if dst is src:
            wire.remove_from_scene()
            return

        if isinstance(src, Port) and isinstance(dst, Port):
            if src.graphic is dst.graphic:
                wire.remove_from_scene()
                return
            for existing in self.scene.items():
                if not isinstance(existing, Wire):
                    continue
                if ((existing.src_port is src and existing.dst_port is dst) or
                        (existing.src_port is dst and existing.dst_port is src)):
                    wire.remove_from_scene()
                    return

        wire.dst_port = dst
        wire._register(dst)
        wire.update_path()
        self.rebuild_connections()

    def _finish_wire_at_empty(self, scene_pos: QPointF):
        wire = self._drawing_wire
        if wire is None:
            return
        self._drawing_wire = None
        self._preview_pos  = None
        self.setDragMode(QGraphicsView.RubberBandDrag)

        ep = WireEndpoint(scene_pos)
        self.scene.addItem(ep)
        wire.dst_port = ep
        wire._register(ep)
        wire.update_path()
        self.rebuild_connections()

    def _finish_wire_on_wire(self, target_wire: Wire, junc_pos: QPointF):
        wire = self._drawing_wire
        if wire is None:
            return
        if target_wire is wire:
            self._finish_wire_at_empty(junc_pos)
            return

        self._drawing_wire = None
        self._preview_pos  = None
        self.setDragMode(QGraphicsView.RubberBandDrag)

        junc = Junction(junc_pos)
        self.scene.addItem(junc)

        old_dst = target_wire.dst_port
        target_wire._unregister(old_dst)
        for mp in list(target_wire._mid_pts):
            if target_wire.scene():
                target_wire.scene().removeItem(mp)
        target_wire._mid_pts.clear()

        target_wire.dst_port = junc
        target_wire._register(junc)
        target_wire.update_path()

        wire2 = Wire(junc, old_dst)
        self.scene.addItem(wire2)

        wire.dst_port = junc
        wire._register(junc)
        wire.update_path()
        self.rebuild_connections()

    # ── Conexión lógica ──────────────────────────────────────────────────────

    def _connect_logic(self, wire: Wire):
        src = wire.src_port
        dst = wire.dst_port
        if not (isinstance(src, Port) and isinstance(dst, Port)):
            return
        if src.is_input and not dst.is_input:
            src, dst = dst, src
        if src.is_input or not dst.is_input:
            return
        src.graphic.widg.connect_to(src.port_index,
                                    dst.graphic.widg, dst.port_index)

    def _propagate_wire(self, wire: Wire):
        src = wire.src_port
        dst = wire.dst_port
        if not isinstance(src, Port) or not isinstance(dst, Port):
            return
        if src.is_input or not dst.is_input:
            return
        val = src.graphic.widg.exit[src.port_index] \
            if src.port_index < len(src.graphic.widg.exit) else False
        if val:
            self.enqueue_signal(dst.graphic.widg, dst.port_index, val,
                                source=(src.graphic.widg, src.port_index))

    def _refresh_junction(self, junc: Junction):
        on = any(w._on for w in junc._wires)
        junc.set_active(on)

    def rebuild_connections(self):
        """Reconstruye la red lógica desde los cables visibles.

        Una unión es puramente conductora; por eso se resuelve como un grafo y
        no como dos conexiones independientes. Esto hace que los ramales y los
        puntos de unión creados automáticamente transmitan señal correctamente.
        """
        self._prop_timer.stop()
        self._signal_queue.clear()
        self._signal_steps = 0
        parent = getattr(self, "owner", self.parent())
        widgets = list(getattr(parent, "all_widgets", {}).values())
        for widget in widgets:
            widget.connections = {i: [] for i in range(len(widget.exit))}

        adjacency: dict[object, list[tuple[object, Wire]]] = {}
        for item in self.scene.items():
            if not isinstance(item, Wire) or item.dst_port is None:
                continue
            adjacency.setdefault(item.src_port, []).append((item.dst_port, item))
            adjacency.setdefault(item.dst_port, []).append((item.src_port, item))

        for graphic in getattr(parent, "all_graphics", {}).values():
            for source in getattr(graphic, "_ports_out", []):
                seen, stack = {source}, [source]
                while stack:
                    node = stack.pop()
                    for next_node, _wire in adjacency.get(node, []):
                        if next_node in seen:
                            continue
                        seen.add(next_node)
                        stack.append(next_node)
                for node in seen:
                    if isinstance(node, Port) and node.is_input:
                        source.graphic.widg.connect_to(
                            source.port_index, node.graphic.widg, node.port_index)

        # Recalcular todos los estados evita que un proyecto cargado o un cable
        # nuevo dependa de un cambio de interruptor posterior para actualizarse.
        for widget in widgets:
            widget.enter = [False] * len(widget.enter)
        self._input_drivers.clear()
        for widget in widgets:
            if hasattr(widget, "truth_row"):
                self.enqueue_action(widget.delay_ms,
                                    lambda current=widget: current.compute_and_propagate(self))
            else:
                widget.compute_and_propagate(self)
        # Un interruptor ya encendido no cambia de estado al reconstruir la red,
        # así que se envían también los valores actuales de todas las salidas.
        for widget in widgets:
            for out_index, destinations in widget.connections.items():
                value = widget.exit[out_index] if out_index < len(widget.exit) else False
                for destination, in_index in destinations:
                    self.enqueue_signal(destination, in_index, value,
                                        source=(widget, out_index))
        for graphic in getattr(parent, "all_graphics", {}).values():
            graphic.update_all_output_wires()
        self._refresh_network_colours(adjacency)

    def _refresh_network_colours(self, adjacency=None):
        if adjacency is None:
            adjacency = {}
            for item in self.scene.items():
                if isinstance(item, Wire) and item.dst_port is not None:
                    adjacency.setdefault(item.src_port, []).append((item.dst_port, item))
                    adjacency.setdefault(item.dst_port, []).append((item.src_port, item))
        active_wires: set[Wire] = set()
        parent = getattr(self, "owner", self.parent())
        for graphic in getattr(parent, "all_graphics", {}).values():
            for source in getattr(graphic, "_ports_out", []):
                if not source.graphic.widg.exit[source.port_index]:
                    continue
                seen, stack = {source}, [source]
                while stack:
                    node = stack.pop()
                    for next_node, wire in adjacency.get(node, []):
                        active_wires.add(wire)
                        if next_node not in seen:
                            seen.add(next_node)
                            stack.append(next_node)
        for item in self.scene.items():
            if isinstance(item, Wire):
                item.set_active(item in active_wires)
            elif isinstance(item, (Junction, WireEndpoint)):
                item.set_active(any(w in active_wires for w in item._wires))

    # ── Eliminar selección ───────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            if self._drawing_wire is not None:
                self._cancel_drawing()
            event.accept()
            return

        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            selected = self.scene.selectedItems()
            for i in [x for x in selected if isinstance(x, Wire)]:
                self._remove_wire(i)
            for i in [x for x in selected if isinstance(x, Graphic)]:
                self._remove_graphic(i)
            for i in [x for x in selected if isinstance(x, Junction)]:
                self._remove_junction(i)
            event.accept()
            return
        super().keyPressEvent(event)

    def _cancel_drawing(self):
        if self._drawing_wire:
            self._drawing_wire.remove_from_scene()
            self._drawing_wire = None
            self._preview_pos  = None
            self.setDragMode(QGraphicsView.RubberBandDrag)

    def _remove_wire(self, wire: Wire):
        if wire.scene() is None:
            return
        src = wire.src_port
        dst = wire.dst_port
        wire.remove_from_scene()
        for ep in (src, dst):
            if isinstance(ep, WireEndpoint) and ep.scene() and not ep._wires:
                self.scene.removeItem(ep)
        self.rebuild_connections()

    def _remove_junction(self, junc: Junction):
        if junc.scene() is None:
            return
        for wire in list(junc._wires):
            self._remove_wire(wire)
        self.scene.removeItem(junc)

    def _remove_graphic(self, graphic: Graphic):
        if graphic.scene() is None:
            return
        for wire in list(graphic.wires):
            self._remove_wire(wire)
        for p in getattr(graphic, "_ports_in", []) + getattr(graphic, "_ports_out", []):
            if p.scene():
                self.scene.removeItem(p)
        view_parent = getattr(self, "owner", self.parent())
        if view_parent and hasattr(view_parent, "all_widgets"):
            wid = graphic.widg.id
            view_parent.all_widgets.pop(wid, None)
            view_parent.all_graphics.pop(wid, None)
        self.scene.removeItem(graphic)
        self.rebuild_connections()

    # ── Propagación BFS ──────────────────────────────────────────────────────

    def enqueue_signal(self, widget, enter_idx: int, value: bool, source=None):
        self._signal_queue.append((widget, enter_idx, value, widget.delay_ms, source))
        if not self._prop_timer.isActive() and not self._processing_signals:
            self._process_next_signal()

    def enqueue_action(self, delay_ms: int, callback):
        """Queue a delayed component response alongside ordinary input signals."""
        self._signal_queue.append((None, None, callback, max(0, int(delay_ms)), None))
        if not self._prop_timer.isActive() and not self._processing_signals:
            self._process_next_signal()

    def _process_next_signal(self):
        if not self._signal_queue:
            self._processing_signals = False
            return
        self._processing_signals = True
        min_delay = min(item[3] for item in self._signal_queue)
        current_batch, remaining = [], deque()
        for item in self._signal_queue:
            widget, enter_idx, value, delay, source = item
            if delay == min_delay:
                current_batch.append((widget, enter_idx, value, source))
            else:
                remaining.append((widget, enter_idx, value, delay - min_delay, source))
        self._signal_queue = remaining

        if min_delay > 0:
            def fire():
                for widget, enter_idx, value, source in current_batch:
                    if widget is None:
                        value()
                    else:
                        self._apply_signal(widget, enter_idx, value, source)
                self._processing_signals = False
                if self._signal_queue:
                    self._process_next_signal()
            self._prop_timer.timeout.disconnect()
            self._prop_timer.timeout.connect(fire)
            self._prop_timer.start(min_delay)
            return

        for widget, enter_idx, value, source in current_batch:
            if widget is None:
                value()
            else:
                self._apply_signal(widget, enter_idx, value, source)
        self._processing_signals = False
        if self._signal_queue:
            self._prop_timer.timeout.disconnect()
            self._prop_timer.timeout.connect(self._process_next_signal)
            self._prop_timer.start(0)

    def _apply_signal(self, widget, enter_idx: int, value: bool, source=None):
        self._signal_steps += 1
        if self._signal_steps > 10_000:
            self._signal_queue.clear()
            parent = getattr(self, "owner", self.parent())
            if parent and hasattr(parent, "statusBar"):
                parent.statusBar().showMessage("Simulación detenida: se detectó un bucle de señal", 5000)
            return
        if enter_idx >= len(widget.enter):
            return
        pin_key = (widget, enter_idx)
        drivers = self._input_drivers.setdefault(pin_key, {})
        driver = source if source is not None else ("direct", id(widget), enter_idx)
        drivers[driver] = bool(value)
        combined_value = any(drivers.values())
        if widget.enter[enter_idx] == combined_value:
            return
        widget.enter[enter_idx] = combined_value
        if widget.graphic:
            widget.graphic.update_port_color(enter_idx, is_input=True)
        widget.compute_and_propagate(self)
        if widget.graphic:
            widget.graphic.update_all_output_wires()
        self._refresh_network_colours()

    # ── Eventos de ratón ─────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())

        if event.button() == Qt.MiddleButton:
            self.last_drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            fake = QMouseEvent(QEvent.MouseButtonPress, event.pos(),
                               Qt.LeftButton, Qt.LeftButton, event.modifiers())
            super().mousePressEvent(fake)
            return

        if event.button() == Qt.RightButton:
            if self._drawing_wire is not None:
                self._cancel_drawing()
                event.accept()
                return
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())

            if self._drawing_wire is not None:
                # Snap a puerto/junction/endpoint
                snap, dist = self._snap_target(scene_pos, self._drawing_wire)
                if snap is not None and dist <= SNAP_R:
                    self._finish_wire(snap)
                    event.accept()
                    return

                # Snap a cable → Junction
                target_wire, junc_pos = self._snap_wire(scene_pos, self._drawing_wire)
                if target_wire is not None:
                    self._finish_wire_on_wire(target_wire, junc_pos)
                    event.accept()
                    return

                # Click en vacío → vértice intermedio
                # (pero no si es un Wire ya existente — ese lo gestiona on_wire_clicked)
                if item is None or not isinstance(item, Wire):
                    self._add_vertex(scene_pos)
                    event.accept()
                    return
                # Si es un Wire: dejamos que suba el evento para que Wire.mousePressEvent
                # llame a on_wire_clicked y añada el punto
                super().mousePressEvent(event)
                return

            else:
                if item is None:
                    self.scene.clearSelection()
                super().mousePressEvent(event)
                return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        item = self.itemAt(event.pos())
        if event.button() == Qt.LeftButton and isinstance(item, (Junction, MidPoint)):
            if isinstance(item, Junction) and self._drawing_wire is not None:
                self._cancel_drawing()
            item.toggle_bridge()
            event.accept()
            return
        if event.button() == Qt.LeftButton and item is None:
            if self._drawing_wire is not None:
                self._finish_wire_at_empty(scene_pos)
                event.accept()
                return
            if self._drawing_wire is None:
                junc = Junction(scene_pos)
                self.scene.addItem(junc)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drawing_wire is not None:
            self._preview_pos = self.mapToScene(event.pos())
            self._drawing_wire.update_path(preview_end=self._preview_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            fake = QMouseEvent(QEvent.MouseButtonRelease, event.pos(),
                               Qt.LeftButton, Qt.LeftButton, event.modifiers())
            super().mouseReleaseEvent(fake)
            self.setDragMode(self.last_drag_mode)
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        factor = 1.25
        if event.angleDelta().y() > 0:
            new_zoom = self.zoom_act * factor
            if new_zoom <= self.MAX_ZOOM:
                self.scale(factor, factor)
                self.zoom_act = new_zoom
        else:
            new_zoom = self.zoom_act / factor
            if new_zoom >= self.MIN_ZOOM:
                self.scale(1 / factor, 1 / factor)
                self.zoom_act = new_zoom
