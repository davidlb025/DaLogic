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

from resources import translate_text as tr

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from widgets.widgets import settle_topology, combine_driver_values, combinational_order, LOGIC_X, LOGIC_Z, TriState
from math import ceil
import time

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsItem, QMessageBox, QApplication, QProgressDialog
)
from PySide6.QtCore import Qt, QRectF, QPointF, QEvent, QTimer, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QMouseEvent, QBrush, QKeyEvent, QCursor

from widgets.graphics import (
    Port, Wire, Graphic, Junction, WireEndpoint, MidPoint,
    translate_text
)
from widgets.visual import VisualItem

SNAP_R = 14


class BoardView(QGraphicsView):
    componentPlacementChanged = Signal(str)
    visualPlacementChanged = Signal(str)
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
        self._visual_placement = None
        self._component_placement = None
        self._component_preview_scene = None
        self._placement_position = None
        self._cancelled_context_press = False
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.theme_mode = "light"
        self.grid_visible = True
        self.snap_to_grid = False
        self.orthogonal_wires = False
        self.grid_size = 20

        self._drawing_wire: Wire | None = None
        self._preview_pos:  QPointF | None = None

        self._signal_queue: deque = deque()
        self._processing_signals = False
        self._signal_steps = 0
        self._signal_visits: dict[tuple, int] = {}
        self._signal_halted = False
        self._topology_edit_depth = 0
        self._topology_rebuild_pending = False
        self._waiting_batch = None
        self._waiting_due = 0.0
        self._input_drivers: dict[tuple[object, int], dict[object, bool]] = {}
        self._network_cache = None
        self._has_feedback = True
        self._clock_timers: dict[object, QTimer] = {}
        self._clocks_paused = False
        self._simulation_paused = False
        self._step_time_ms = 0
        self._breakpoints = set()
        self._breakpoint_hits = set()
        self.probe_history_limit = 10000
        self._probes: list[dict] = []
        self._probe_started = time.monotonic()
        self._probe_pause_total = 0.0
        self._probe_paused_at = None
        self._probe_colors = ["#56b4e9", "#e69f00", "#cc79a7", "#009e73",
                              "#f0e442", "#d55e00", "#7b83eb", "#65c466"]
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
        if not self.grid_visible:
            return
        minor, major = self.grid_size, self.grid_size * 5
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
        if self._component_preview_scene is not None:
            self._component_preview_scene.setProperty("theme_mode", mode)
            self._component_preview_scene.update()
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
        for item in self.scene.items(QRectF(scene_pos.x() - 12, scene_pos.y() - 12, 24, 24)):
            if not isinstance(item, Wire):
                continue
            if item is exclude_wire:
                continue
            pts = item._routed_points()
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
            if src.is_input == dst.is_input:
                QMessageBox.information(self.window(), tr("Cable incompatible"),
                                         tr("Conecta una salida con una entrada."))
                wire.remove_from_scene()
                return
            output = src if not src.is_input else dst
            input_ = dst if output is src else src
            source_width = output.graphic.widg.output_widths[output.port_index]
            target_width = input_.graphic.widg.input_widths[input_.port_index]
            from widgets.widgets import BusViewer
            if (source_width != target_width
                    and not isinstance(output.graphic.widg, BusViewer)
                    and not isinstance(input_.graphic.widg, BusViewer)):
                QMessageBox.information(
                    self.window(), tr("Ancho incompatible"),
                    tr('El cable necesita {v0} bits y la entrada admite {v1}.', v0=source_width, v1=target_width))
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
        points = target_wire._routed_points()
        segment = min(range(len(points) - 1), key=lambda index:
                      Wire._dist_point_segment(junc_pos, points[index], points[index + 1]))
        bridge_modes = {(round(mid.scenePos().x(), 3), round(mid.scenePos().y(), 3)): mid.bridge_mode
                        for mid in target_wire._mid_pts}
        left_points, right_points = points[1:segment + 1], points[segment + 1:-1]
        def modes(vertices):
            return [bridge_modes.get((round(p.x(), 3), round(p.y(), 3)), 0) for p in vertices]
        target_wire._unregister(old_dst)
        for mp in list(target_wire._mid_pts):
            if target_wire.scene():
                target_wire.scene().removeItem(mp)
        target_wire._mid_pts.clear()

        target_wire.dst_port = junc
        target_wire._register(junc)
        target_wire._pending_mid = left_points
        target_wire._pending_mid_bridges = modes(left_points)
        target_wire._build_midpoints()

        wire2 = Wire(junc, old_dst, right_points, midpoint_bridges=modes(right_points),
                     custom_color=target_wire.custom_color)
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

    def rebuild_connections(self, recalculate: bool = False, *, restore_state=False):
        """Reconstruye la red lógica desde los cables visibles.

        Una unión es puramente conductora; por eso se resuelve como un grafo y
        no como dos conexiones independientes. Esto hace que los ramales y los
        puntos de unión creados automáticamente transmitan señal correctamente.
        Las ediciones conservan las salidas y resuelven las entradas afectadas.
        ``restore_state`` conserva los estados guardados al abrir o deshacer;
        ``recalculate`` permite ajustar una carga que normalizó botones pulsados.
        """
        if self._topology_edit_depth:
            self._topology_rebuild_pending = True
            return
        had_pending = self._prop_timer.isActive() or bool(self._signal_queue)
        self._signal_halted = False
        self._prop_timer.stop()
        self._signal_queue.clear()
        self._waiting_batch = None
        # A project may be opened while a delayed propagation is pending. The
        # timer is stopped above, so its old processing flag must not strand
        # every signal queued by the newly loaded project.
        self._processing_signals = False
        self._signal_steps = 0
        self._signal_visits.clear()
        parent = getattr(self, "owner", self.parent())
        widgets = list(getattr(parent, "all_widgets", {}).values())
        for widget in widgets:
            if getattr(widget, "sequential", False):
                widget._prime_clock = True
            widget.connections = {i: [] for i in range(len(widget.exit))}

        adjacency: dict[object, list[tuple[object, Wire]]] = {}
        for item in self.scene.items():
            if not isinstance(item, Wire) or item.dst_port is None:
                continue
            adjacency.setdefault(item.src_port, []).append((item.dst_port, item))
            adjacency.setdefault(item.dst_port, []).append((item.src_port, item))

        self._adapt_viewer_widths(adjacency, widgets)
        incompatible_connections = 0
        self._network_cache = self._network_groups(adjacency)
        for nodes, _wires in self._network_cache:
            sources = [node for node in nodes if isinstance(node, Port) and not node.is_input]
            targets = [node for node in nodes if isinstance(node, Port) and node.is_input]
            for source in sources:
                for node in targets:
                    if (source.graphic.widg.output_widths[source.port_index] !=
                            node.graphic.widg.input_widths[node.port_index]):
                        incompatible_connections += 1
                        continue
                    source.graphic.widg.connect_to(source.port_index, node.graphic.widg, node.port_index)
        self._has_feedback = combinational_order(widgets) is None

        self._rebuilding_native = True
        self._input_drivers, unstable = settle_topology(
            widgets, self._combine_driver_values,
            restore_state=restore_state and not recalculate,
            force=had_pending and not restore_state)
        for widget in widgets:
            if widget.graphic:
                for index in range(len(widget.enter)):
                    widget.graphic.update_port_color(index, is_input=True)
                for index in range(len(widget.exit)):
                    widget.graphic.update_port_color(index, is_input=False)
                widget.graphic.update_all_output_wires()
        self._rebuilding_native = False
        self._finish_native_rebuild()
        if unstable and parent and hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(
                tr("Hay una realimentación que no se estabiliza; sus salidas se muestran como X."), 8000)
        self._refresh_network_colours()
        self.sync_clock_timers()
        self._record_probe_values()
        self.refresh_breakpoint_markers()
        if incompatible_connections and parent and hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(
                tr('Se ignoraron {v0} conexiones: los anchos de bus no coinciden.', v0=incompatible_connections),
                8000)

    def _adapt_viewer_widths(self, adjacency, widgets):
        """Infer a common width through connected inline monitors, before wiring."""
        from widgets.widgets import BusViewer

        viewers = [widget for widget in widgets if isinstance(widget, BusViewer)]
        # For width inference only, join a viewer's input and output. This also
        # handles monitor chains, junctions, and wiring the output end first.
        neighbours = {node: [next_node for next_node, _wire in edges]
                      for node, edges in adjacency.items()}
        for viewer in viewers:
            if viewer.graphic:
                input_port, output_port = viewer.graphic._ports_in[0], viewer.graphic._ports_out[0]
                neighbours.setdefault(input_port, []).append(output_port)
                neighbours.setdefault(output_port, []).append(input_port)
        visited = set()
        for viewer in viewers:
            if not viewer.graphic:
                continue
            start = viewer.graphic._ports_in[0]
            if start in visited:
                continue
            stack, group, source_widths, target_widths = [start], set(), [], []
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                stack.extend(neighbours.get(node, []))
                if not isinstance(node, Port):
                    continue
                widget = node.graphic.widg
                if isinstance(widget, BusViewer):
                    group.add(widget)
                elif node.is_input:
                    target_widths.append(widget.input_widths[node.port_index])
                else:
                    source_widths.append(widget.output_widths[node.port_index])
            width = max(source_widths or target_widths or [1])
            for monitor in group:
                if monitor.width != width:
                    monitor.set_bus_width(width)

    def sync_clock_timers(self):
        """Keep one board-owned timer per clock currently in the project."""
        from widgets.widgets import Clock

        parent = getattr(self, "owner", self.parent())
        clocks = {widget for widget in getattr(parent, "all_widgets", {}).values()
                  if isinstance(widget, Clock)}
        for clock, timer in list(self._clock_timers.items()):
            if clock not in clocks:
                timer.stop()
                timer.deleteLater()
                self._clock_timers.pop(clock, None)
        for clock in clocks:
            timer = self._clock_timers.get(clock)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(False)
                timer.timeout.connect(lambda current=clock: current.tick(self))
                self._clock_timers[clock] = timer
            interval = max(10, int(clock.interval_ms))
            if self._clocks_paused or self._simulation_paused:
                timer.stop()
            elif not timer.isActive() or timer.interval() != interval:
                timer.start(interval)

    def set_clocks_paused(self, paused: bool):
        """Pause or resume every project clock, including clocks added later."""
        now = time.monotonic()
        if paused and not self._clocks_paused:
            self._probe_paused_at = now
        elif not paused and self._probe_paused_at is not None:
            self._probe_pause_total += now - self._probe_paused_at
            self._probe_paused_at = None
        self._clocks_paused = bool(paused)
        self.sync_clock_timers()
        parent = getattr(self, "owner", self.parent())
        if parent and hasattr(parent, "update_probe_plot"):
            parent.update_probe_plot()
        if not self._clocks_paused:
            self._record_probe_values(force=True)

    def toggle_probe(self, target):
        """Add or remove a visual probe for a wire or a signal port."""
        existing = next((probe for probe in self._probes if probe["target"] is target), None)
        if existing:
            self._probes.remove(existing)
        else:
            label = (f"Cable {len(self._probes) + 1}" if isinstance(target, Wire) else
                     target.toolTip())
            probe = {"target": target, "label": label,
                     "color": self._probe_colors[len(self._probes) % len(self._probe_colors)],
                     "history": []}
            self._probes.append(probe)
            self._record_probe_values(force=True)
        parent = getattr(self, "owner", self.parent())
        if parent and hasattr(parent, "refresh_probes"):
            parent.refresh_probes()

    def remove_probe(self, probe):
        if probe in self._probes:
            self._probes.remove(probe)
            parent = getattr(self, "owner", self.parent())
            if parent and hasattr(parent, "refresh_probes"):
                parent.refresh_probes()

    def probe_time(self):
        now = self._probe_paused_at if self._probe_paused_at is not None else time.monotonic()
        return max(0.0, now - self._probe_started - self._probe_pause_total)

    def _record_probe_values(self, force=False):
        if self._clocks_paused and not force:
            return
        now = self.probe_time()
        for probe in self._probes:
            target = probe["target"]
            if isinstance(target, Wire):
                value = target.signal_value()
            elif isinstance(target, Port):
                values = target.graphic.widg.enter if target.is_input else target.graphic.widg.exit
                value = values[target.port_index] if target.port_index < len(values) else False
            else:
                continue
            history = probe["history"]
            if not history or history[-1][1] != value:
                history.append((now, value))
                del history[:-self.probe_history_limit]
        parent = getattr(self, "owner", self.parent())
        if parent and hasattr(parent, "update_probe_plot"):
            parent.update_probe_plot()

    @staticmethod
    def _network_groups(adjacency):
        visited, groups = set(), []
        for start in adjacency:
            if start in visited:
                continue
            stack, nodes, wires = [start], set(), set()
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                nodes.add(node)
                for other, wire in adjacency.get(node, []):
                    wires.add(wire)
                    if other not in visited:
                        stack.append(other)
            groups.append((nodes, wires))
        return groups

    def _refresh_network_colours(self, adjacency=None):
        if adjacency is None and self._network_cache is None:
            adjacency = {}
            for item in self.scene.items():
                if isinstance(item, Wire) and item.dst_port is not None:
                    adjacency.setdefault(item.src_port, []).append((item.dst_port, item))
                    adjacency.setdefault(item.dst_port, []).append((item.src_port, item))
        active_wires: set[Wire] = set()
        groups = self._network_groups(adjacency) if adjacency is not None else self._network_cache
        for nodes, wires in groups:
            ports = tuple(node for node in nodes if isinstance(node, Port))
            for wire in wires:
                if getattr(wire, "_network_ports", ()) != ports:
                    wire.prepareGeometryChange()
                    wire._network_ports = ports
            if any(node.graphic.widg.exit[node.port_index] not in (False, 0, "Z")
                   for node in nodes if isinstance(node, Port) and not node.is_input):
                active_wires.update(wires)
        for item in self.scene.items():
            if isinstance(item, Wire):
                item.set_active(item in active_wires)
            elif isinstance(item, (Junction, WireEndpoint)):
                item.set_active(any(w in active_wires for w in item._wires))

    # ── Eliminar selección ───────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if self._component_placement is not None and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._place_component(self.mapToScene(self.viewport().rect().center()))
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.cancel_visual_placement()
            if self._drawing_wire is not None:
                self._cancel_drawing()
            event.accept()
            return

        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            selected = self.scene.selectedItems()
            with self.topology_edit():
                for i in [x for x in selected if isinstance(x, Wire)]:
                    self._remove_wire(i)
                for i in [x for x in selected if isinstance(x, Graphic)]:
                    self._remove_graphic(i)
                for i in [x for x in selected if isinstance(x, Junction)]:
                    self._remove_junction(i)
                for i in [x for x in selected if isinstance(x, VisualItem)]:
                    self.scene.removeItem(i)
            event.accept()
            return
        super().keyPressEvent(event)

    def _cancel_drawing(self):
        if self._drawing_wire:
            self._drawing_wire.remove_from_scene()
            self._drawing_wire = None
            self._preview_pos  = None
            self.setDragMode(QGraphicsView.RubberBandDrag)

    @contextmanager
    def topology_edit(self):
        """Evaluate a completed deletion once, rather than its intermediate wiring."""
        self._topology_edit_depth += 1
        try:
            yield
        finally:
            self._topology_edit_depth -= 1
            if not self._topology_edit_depth and self._topology_rebuild_pending:
                self._topology_rebuild_pending = False
                self.rebuild_connections(recalculate=True)

    def _remove_wire(self, wire: Wire):
        if wire.scene() is None:
            return
        probe_count = len(self._probes)
        self._probes = [probe for probe in self._probes if probe["target"] is not wire]
        if len(self._probes) != probe_count:
            parent = getattr(self, "owner", self.parent())
            if parent and hasattr(parent, "refresh_probes"):
                parent.refresh_probes()
        src = wire.src_port
        dst = wire.dst_port
        wire.remove_from_scene()
        for ep in (src, dst):
            if isinstance(ep, WireEndpoint) and ep.scene() and not ep._wires:
                self.scene.removeItem(ep)
        self.rebuild_connections(recalculate=True)

    def _remove_junction(self, junc: Junction):
        if junc.scene() is None:
            return
        with self.topology_edit():
            for wire in list(junc._wires):
                self._remove_wire(wire)
            self.scene.removeItem(junc)

    def _remove_graphic(self, graphic: Graphic):
        if graphic.scene() is None:
            return
        probe_count = len(self._probes)
        removed_ports = set(getattr(graphic, "_ports_in", []) + getattr(graphic, "_ports_out", []))
        self._probes = [probe for probe in self._probes
                        if probe["target"] not in removed_ports]
        if len(self._probes) != probe_count:
            parent = getattr(self, "owner", self.parent())
            if parent and hasattr(parent, "refresh_probes"):
                parent.refresh_probes()
        with self.topology_edit():
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
                self._breakpoints.discard(wid)
                self._breakpoint_hits.discard(wid)
            self.scene.removeItem(graphic)
            self.rebuild_connections(recalculate=True)

    # ── Propagación BFS ──────────────────────────────────────────────────────

    def enqueue_signal(self, widget, enter_idx: int, value: bool, source=None):
        self._queue_signal_event((widget, enter_idx, value, widget.propagation_delay, source))

    def set_simulation_paused(self, paused):
        """Suspend both propagation and clocks, retaining pending event delays."""
        paused = bool(paused)
        if paused and self._waiting_batch is not None:
            remaining = max(0, ceil((self._waiting_due - time.monotonic()) * 1000))
            self._signal_queue = deque((w, pin, value, delay + remaining, source)
                                       for w, pin, value, delay, source in self._signal_queue)
            self._signal_queue.extend((w, pin, value, remaining, source)
                                      for w, pin, value, source in self._waiting_batch)
            self._waiting_batch = None
        self._simulation_paused = paused
        if not paused:
            self._breakpoint_hits.clear()
            self.refresh_breakpoint_markers()
        self._prop_timer.stop()
        self._processing_signals = False
        self.sync_clock_timers()
        if not paused and self._signal_queue:
            self._prop_timer.timeout.disconnect()
            self._prop_timer.timeout.connect(self._process_next_signal)
            self._prop_timer.start(0)
        owner = getattr(self, "owner", None)
        action = getattr(owner, "actionPausarSimulacion", None)
        if action is not None:
            action.blockSignals(True)
            action.setChecked(paused)
            action.setText(tr("Reanudar simulación" if paused else "Pausar simulación"))
            action.blockSignals(False)

    def refresh_breakpoint_markers(self):
        owner = getattr(self, "owner", None)
        for identifier, graphic in getattr(owner, "all_graphics", {}).items():
            marker = getattr(graphic, "_breakpoint_marker", None)
            enabled = identifier in self._breakpoints
            if enabled and marker is None:
                marker = QGraphicsEllipseItem(-5, -5, 10, 10, graphic)
                marker.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                marker.setAcceptedMouseButtons(Qt.NoButton)
                marker.setZValue(10)
                graphic._breakpoint_marker = marker
            if marker is not None:
                marker.setVisible(enabled)
                marker.setPos(graphic.boundingRect().topRight() + QPointF(-9, 9))
                marker.setPen(QPen(QColor("#ffffff"), 1.5))
                marker.setBrush(QColor("#d97706" if identifier in self._breakpoint_hits else "#c62828"))
                marker.setToolTip(tr(
                    "Punto de parada: pausa al cambiar una entrada. F9 quita la marca; F8 continúa."))
        if owner and hasattr(owner, "_update_breakpoint_action"):
            owner._update_breakpoint_action()

    def step_simulation(self):
        """Apply one simultaneous event batch; an idle circuit ticks its clocks."""
        self.set_simulation_paused(True)
        self._breakpoint_hits.clear()
        self.refresh_breakpoint_markers()
        if self._signal_halted:
            return False
        if not self._signal_queue:
            from widgets.widgets import Clock
            for clock in list(getattr(self.owner, "all_widgets", {}).values()):
                if isinstance(clock, Clock):
                    clock.tick(self)
        if not self._signal_queue:
            self.owner.statusBar().showMessage(tr("No hay eventos pendientes ni relojes que avanzar."), 4000)
            return False
        minimum = min(event[3] for event in self._signal_queue)
        batch, remaining = [], deque()
        for widget, pin, value, delay, source in self._signal_queue:
            if delay == minimum:
                batch.append((widget, pin, value, source))
            else:
                remaining.append((widget, pin, value, delay - minimum, source))
        self._signal_queue = remaining
        self._processing_signals = True
        try:
            self._apply_signal_batch(batch)
            self._record_probe_values(force=True)
        finally:
            self._processing_signals = False
            self._prop_timer.stop()
        self._step_time_ms += minimum
        if not self._breakpoint_hits:
            self.owner.statusBar().showMessage(
                tr('Paso de {v0} ms · avance acumulado {v1} ms · {v2} eventos pendientes', v0=minimum, v1=self._step_time_ms, v2=len(self._signal_queue)))
        return True

    def enqueue_action(self, delay_ms: int, callback):
        """Queue a delayed component response alongside ordinary input signals."""
        self._queue_signal_event((None, None, callback, max(0, int(delay_ms)), None))

    def _queue_signal_event(self, event):
        if not self._processing_signals or self._waiting_batch is not None:
            # External stimuli start a new settling episode. A running clock
            # must not accumulate the event budget of earlier clock cycles.
            self._signal_steps = 0
            self._signal_visits.clear()
        if self._signal_halted:
            self._signal_halted = False
            self._signal_visits.clear()
        if self._waiting_batch is not None:
            # A new source may change while a long response is waiting. Put the
            # pending batch back on the queue relative to now, so the new event
            # can run earlier rather than waiting for the old timer to finish.
            remaining = max(0, ceil((self._waiting_due - time.monotonic()) * 1000))
            self._signal_queue = deque((w, pin, value, delay + remaining, source)
                                       for w, pin, value, delay, source in self._signal_queue)
            self._signal_queue.extend((w, pin, value, remaining, source)
                                      for w, pin, value, source in self._waiting_batch)
            self._waiting_batch = None
            self._prop_timer.stop()
            self._processing_signals = False
        self._signal_queue.append(event)
        if not self._simulation_paused and not self._prop_timer.isActive() and not self._processing_signals:
            # Collect all branches of this source transition before selecting
            # the next time step. Selecting the first branch immediately used
            # to give subsequent branches a different time origin.
            self._prop_timer.timeout.disconnect()
            self._prop_timer.timeout.connect(self._process_next_signal)
            self._prop_timer.start(0)

    def _finish_native_rebuild(self):
        if getattr(self, '_rebuilding_native', False):
            return
        parent = getattr(self, "owner", self.parent())
        for widget in getattr(parent, "all_widgets", {}).values():
            if getattr(widget, "_prime_clock", False):
                widget.previous_clock = widget.enter[widget.input_labels.index('CLK')]
                widget._prime_clock = False

    def _process_next_signal(self):
        if self._simulation_paused:
            return
        if not self._signal_queue:
            self._processing_signals = False
            self._signal_steps = 0
            self._signal_visits.clear()
            self._finish_native_rebuild()
            return
        # A local pin can toggle several times while a finite feedback network
        # settles. Only a repeated complete network and pending queue proves a
        # cycle; callbacks and stateful components retain the step limit.
        parent = getattr(self, "owner", self.parent())
        widgets = set(getattr(parent, "all_widgets", {}).values())
        for widget, _index, _value, _delay, source in self._signal_queue:
            if widget is not None:
                widgets.add(widget)
            if isinstance(source, tuple) and source and hasattr(source[0], "exit"):
                widgets.add(source[0])
        if (self._has_feedback and all(event[0] is not None for event in self._signal_queue)
                and not any(getattr(widget, "sequential", False)
                            or getattr(widget, "stateful_circuit", False)
                            for widget in widgets)):
            state = (tuple((id(widget), tuple(widget.enter), tuple(widget.exit))
                           for widget in sorted(widgets, key=id)),
                     repr(self._input_drivers), repr(self._signal_queue))
            if state in self._signal_visits:
                self._stop_signal_oscillation()
                return
            self._signal_visits[state] = 1
        else:
            self._signal_visits.clear()
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
            self._waiting_batch = current_batch
            self._waiting_due = time.monotonic() + min_delay / 1000
            def fire():
                self._waiting_batch = None
                self._apply_signal_batch(current_batch)
                if self._signal_halted or self._simulation_paused:
                    return
                self._processing_signals = False
                if self._signal_queue:
                    self._process_next_signal()
                else:
                    self._signal_steps = 0
                    self._signal_visits.clear()
                    self._finish_native_rebuild()
            self._prop_timer.timeout.disconnect()
            self._prop_timer.timeout.connect(fire)
            self._prop_timer.start(min_delay)
            return

        self._apply_signal_batch(current_batch)
        if self._signal_halted or self._simulation_paused:
            return
        self._processing_signals = False
        if self._signal_queue:
            self._prop_timer.timeout.disconnect()
            self._prop_timer.timeout.connect(self._process_next_signal)
            self._prop_timer.start(0)
        else:
            self._signal_steps = 0
            self._signal_visits.clear()
            self._finish_native_rebuild()

    def _stop_signal_oscillation(self):
        """Stop a detected signal cycle and explain how to recover."""
        parent = getattr(self, "owner", self.parent())
        self._signal_queue.clear()
        self._waiting_batch = None
        self._signal_visits.clear()
        self._signal_steps = 0
        self._processing_signals = False
        self._signal_halted = True
        self._prop_timer.stop()
        for timer in self._clock_timers.values():
            timer.stop()
        self._clocks_paused = True
        pause_action = getattr(parent, "actionPausarRelojes", None)
        if pause_action is not None:
            pause_action.blockSignals(True)
            pause_action.setChecked(True)
            pause_action.blockSignals(False)
        QMessageBox.warning(parent, translate_text("Oscilación o bucle infinito"),
                            translate_text("Se detectó una oscilación o un bucle infinito en una realimentación combinacional. La simulación se detuvo y los relojes se pausaron. Revisa las conexiones antes de continuar."))
        if parent and hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(
                translate_text("Simulación detenida: oscilación o bucle infinito detectado"),
                8000)

    def _apply_signal_batch(self, events):
        """Apply simultaneous pin changes before evaluating their components."""
        changed = set()
        for widget, enter_idx, value, source in events:
            if self._signal_halted:
                return
            if widget is None:
                value()
            elif self._apply_signal(widget, enter_idx, value, source):
                changed.add(widget)
        for widget in sorted(changed, key=lambda item: item.id):
            if self._signal_halted:
                return
            widget.compute_and_propagate(self)
            if widget.graphic:
                widget.graphic.update_all_output_wires()
        if changed:
            self._refresh_network_colours()
            self._record_probe_values()
            hits = self._breakpoints.intersection(widget.id for widget in changed)
            if hits:
                self._breakpoint_hits = hits
                self.set_simulation_paused(True)
                self.owner.mostrar_punto_parada(hits)

    def _apply_signal(self, widget, enter_idx: int, value: bool, source=None):
        # Zero-delay combinational events represent the current driver value.
        # An older value superseded within the same instant must not re-enter
        # a latch and create an artificial alternating feedback wave.
        if (widget.propagation_delay == 0 and isinstance(source, tuple) and len(source) == 2
                and hasattr(source[0], "exit")
                and not getattr(source[0], "sequential", False)
                and not getattr(source[0], "stateful_circuit", False)
                and source[0].propagation_delay == 0
                and source[0].exit[source[1]] != value):
            return
        self._signal_steps += 1
        parent = getattr(self, "owner", self.parent())
        if self._signal_steps > max(10_000, len(getattr(parent, "all_widgets", {})) * 128):
            self._stop_signal_oscillation()
            return
        if not 0 <= enter_idx < len(widget.enter):
            return
        pin_key = (widget, enter_idx)
        drivers = self._input_drivers.setdefault(pin_key, {})
        driver = source if source is not None else ("direct", id(widget), enter_idx)
        if value == "Z":
            drivers.pop(driver, None)
        else:
            drivers[driver] = value
        combined_value = self._combine_driver_values(drivers, widget.input_widths[enter_idx])
        from widgets.widgets import TriState
        active_tri_states = {key[0] for key in drivers
                             if isinstance(key, tuple) and key and isinstance(key[0], TriState)}
        if len(active_tri_states) > 1:
            message = tr('Conflicto en bus: {v0} buffers tri-state conducen la entrada {v1}.', v0=len(active_tri_states), v1=enter_idx)
            if getattr(widget, "_last_bus_conflict", None) != message:
                widget._last_bus_conflict = message
                parent = getattr(self, "owner", self.parent())
                if parent and hasattr(parent, "statusBar"):
                    parent.statusBar().showMessage(tr(message), 8000)
        if widget.enter[enter_idx] == combined_value:
            return
        widget.enter[enter_idx] = combined_value
        if widget.graphic:
            widget.graphic.update_port_color(enter_idx, is_input=True)
        return True

    _combine_driver_values = staticmethod(combine_driver_values)

    # ── Eventos de ratón ─────────────────────────────────────────────────────

    def cancel_visual_placement(self):
        self._visual_placement = None
        self.visualPlacementChanged.emit("")
        self._component_placement = None
        self._placement_position = None
        if self._component_preview_scene is not None:
            self._component_preview_scene.deleteLater()
            self._component_preview_scene = None
        self.componentPlacementChanged.emit("")
        self.viewport().unsetCursor()
        self.viewport().update()
        self.owner.statusBar().clearMessage()

    def begin_component_placement(self, kind, data=None):
        if self._component_placement == (kind, data or {}):
            self.cancel_visual_placement()
            return
        self.cancel_visual_placement()
        self._cancel_drawing()
        self._component_placement = (kind, dict(data or {}))
        # Keep the preview outside the document: no IDs, timers or undo entries.
        _, graphic = self.owner._create_component(kind, data or {}, self.owner.next_id)
        self._component_preview_scene = QGraphicsScene(self)
        self._component_preview_scene.setProperty("theme_mode", self.theme_mode)
        self._component_preview_scene.addItem(graphic)
        graphic.set_orientation((data or {}).get("rotation", 0), (data or {}).get("mirrored", False))
        # Scene rendering sets the painter opacity from each item's opacity.
        # Apply transparency to roots so bodies, children and separate ports
        # all appear as a ghost, without changing the real component.
        for item in self._component_preview_scene.items():
            if item.parentItem() is None:
                item.setOpacity(.4)
        self._component_preview_center = graphic.mapRectToScene(graphic.boundingRect()).center()
        cursor = self.viewport().mapFromGlobal(QCursor.pos())
        if self.viewport().rect().contains(cursor):
            self._placement_position = self.mapToScene(cursor)
        self.componentPlacementChanged.emit(kind)
        self.viewport().setCursor(Qt.CrossCursor)
        self.setFocus()
        title = (data or {}).get("name", kind)
        self.owner.statusBar().showMessage(tr('{v0} · Haz clic para colocar · Enter: centro · Esc: cancelar', v0=title))
        self.viewport().update()

    def _component_origin(self, scene_pos):
        origin = scene_pos - self._component_preview_center
        if self.snap_to_grid:
            origin = QPointF(round(origin.x() / self.grid_size) * self.grid_size,
                             round(origin.y() / self.grid_size) * self.grid_size)
        return origin

    def _place_component(self, scene_pos):
        kind, data = self._component_placement
        origin = self._component_origin(scene_pos)
        self.owner._capture_history_change()
        graphic = self.owner.crear_widget(kind, origin, data)
        self.scene.clearSelection()
        graphic.setSelected(True)
        self.cancel_visual_placement()
        self.owner._capture_history_change()
        self.owner.statusBar().showMessage(tr('{v0} añadido', v0=data.get('name', kind)), 3000)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if self._component_preview_scene is None or self._placement_position is None:
            return
        source = self._component_preview_scene.itemsBoundingRect()
        target = source.translated(self._component_origin(self._placement_position))
        painter.save()
        self._component_preview_scene.render(painter, target, source, Qt.IgnoreAspectRatio)
        painter.restore()

    def leaveEvent(self, event):
        self._placement_position = None
        self.viewport().update()
        super().leaveEvent(event)

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat("application/x-dalogic-component"):
            kind = bytes(mime.data("application/x-dalogic-component")).decode("utf-8", errors="replace")
            if kind in self.owner.WIDGET_DEFS:
                self.begin_component_placement(kind)
                event.setDropAction(Qt.CopyAction)
                event.accept()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if self._component_placement is not None and event.mimeData().hasFormat("application/x-dalogic-component"):
            self._placement_position = self.mapToScene(event.position().toPoint())
            self.viewport().update()
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.cancel_visual_placement()
        event.accept()

    def dropEvent(self, event):
        if self._component_placement is not None and event.mimeData().hasFormat("application/x-dalogic-component"):
            self._place_component(self.mapToScene(event.position().toPoint()))
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        event.ignore()

    def begin_visual_placement(self, kind):
        self.cancel_visual_placement()
        self._cancel_drawing()
        self._visual_placement = kind
        self.visualPlacementChanged.emit(kind)
        self.viewport().setCursor(Qt.CrossCursor)
        self.setFocus()
        self.owner.statusBar().showMessage(tr("Haz clic para colocar el elemento visual · Esc para cancelar"))

    def mousePressEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())

        if self._component_placement is not None and event.button() == Qt.LeftButton:
            self._place_component(scene_pos)
            event.accept()
            return

        if self._visual_placement is not None and event.button() == Qt.LeftButton:
            kind = self._visual_placement
            self.cancel_visual_placement()
            self.owner.add_visual(kind, scene_pos)
            event.accept()
            return

        if event.button() == Qt.MiddleButton:
            self.last_drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            fake = QMouseEvent(QEvent.MouseButtonPress, event.pos(),
                               Qt.LeftButton, Qt.LeftButton, event.modifiers())
            super().mousePressEvent(fake)
            return

        if event.button() == Qt.RightButton:
            self._cancelled_context_press = False
            if self._visual_placement is not None or self._component_placement is not None:
                self.cancel_visual_placement()
                self._cancelled_context_press = True
                event.accept()
                return
            if self._drawing_wire is not None:
                self._cancel_drawing()
                self._cancelled_context_press = True
                event.accept()
                return
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())

            if (self._drawing_wire is None and item is not None and
                    event.modifiers() & Qt.ShiftModifier and
                    item.flags() & QGraphicsItem.ItemIsSelectable):
                item.setSelected(not item.isSelected())
                event.accept()
                return

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

    def contextMenuEvent(self, event):
        if self._cancelled_context_press:
            self._cancelled_context_press = False
            event.accept()
            return
        super().contextMenuEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if self._component_placement is not None:
            self.mousePressEvent(event)
            return
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
        if self._component_placement is not None:
            self._placement_position = self.mapToScene(event.pos())
            self.viewport().update()
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
        if event.angleDelta().y() > 0:
            self.zoom_by_factor(1.25)
        else:
            self.zoom_by_factor(1 / 1.25)

    def zoom_by_factor(self, factor):
        new_zoom = self.zoom_act * factor
        if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
            self.scale(factor, factor)
            self.zoom_act = new_zoom


# Cancellable circuit calculations and read-only diagnostics.

class CalculationCancelled(Exception):
    pass

def cancellable(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except CalculationCancelled:
            self.statusBar().showMessage(tr("Cálculo cancelado; el circuito conserva su estado."), 5000)
    return wrapped

class CalculationProgress:
    def __init__(self, owner, total, label=tr("Calculando combinaciones…")):
        self.owner = owner
        self.dialog = None
        self.timers = []
        self.previous_history_flag = getattr(owner, "_history_restoring", False)
        if total < 4096:
            return
        for timer in owner.findChildren(QTimer):
            if timer.isActive():
                self.timers.append((timer, timer.remainingTime() if timer.isSingleShot() else timer.interval()))
                timer.stop()
        if hasattr(owner, "_history_restoring"):
            owner._history_restoring = True
        self.dialog = QProgressDialog(tr(label), tr("Cancelar"), 0, total, owner)
        self.dialog.setWindowTitle(tr("DaLogic"))
        self.dialog.setWindowModality(Qt.ApplicationModal)
        self.dialog.setMinimumDuration(0)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)
        self.dialog.show()
        self.last_update = 0.0

    def advance(self, value):
        if self.dialog is None or value % 64:
            return
        now = time.monotonic()
        if now - self.last_update < .05:
            return
        self.last_update = now
        self.dialog.setValue(value)
        QApplication.processEvents()
        if self.dialog.wasCanceled():
            raise CalculationCancelled()

    def close(self):
        if self.dialog is None:
            return
        self.dialog.close()
        self.dialog.deleteLater()
        if hasattr(self.owner, "_history_restoring"):
            self.owner._history_restoring = self.previous_history_flag
        for timer, interval in self.timers:
            timer.start(interval)
        self.dialog = None

@dataclass(frozen=True)
class CircuitIssue:
    severity: str
    message: str
    target: object

def inspect_circuit(window):
    board = window.ui.graphicsView
    issues, adjacency, connected = [], {}, set()
    for item in board.scene.items():
        if isinstance(item, Wire) and item.dst_port is not None:
            a, b = item.src_port, item.dst_port
            adjacency.setdefault(a, []).append((b, item))
            adjacency.setdefault(b, []).append((a, item))
            connected.update((a, b))
    for nodes, wires in board._network_groups(adjacency):
        sources = [p for p in nodes if isinstance(p, Port) and not p.is_input]
        targets = [p for p in nodes if isinstance(p, Port) and p.is_input]
        widths = {p.graphic.widg.input_widths[p.port_index] if p.is_input else
                  p.graphic.widg.output_widths[p.port_index]
                  for p in sources + targets}
        target = next(iter(wires), next(iter(nodes)))
        if len(widths) > 1:
            issues.append(CircuitIssue(tr("Error"), ((tr("Anchos incompatibles en la red: ") + tr(", ".join(map(str, sorted(widths))))) + tr(" bits.")), target))
        if targets and not sources:
            issues.append(CircuitIssue(tr("Aviso"), tr("Red con entradas y sin fuente de señal."), target))
        active = [p for p in sources if p.graphic.widg.exit[p.port_index] != LOGIC_Z
                  and not getattr(p.graphic.widg, "weak_driver", False)]
        if len(active) > 1 and any(isinstance(p.graphic.widg, TriState) for p in active):
            issues.append(CircuitIssue(tr("Error"), tr("Varios drivers activos en la misma red tri-state."), target))
        if any(isinstance(p, WireEndpoint) for p in nodes):
            issues.append(CircuitIssue(tr("Aviso"), tr("Cable con extremo libre."), target))
    for graphic in window.all_graphics.values():
        widget = graphic.widg
        for index, port in enumerate(graphic._ports_in):
            if port not in connected:
                issues.append(CircuitIssue(tr("Aviso"), tr('{v0} {v1}: entrada {v2} sin conexión.', v0=window.type_for_widget(widget), v1=widget.id, v2=index), graphic))
        if any(value == LOGIC_X for value in widget.enter + widget.exit):
            issues.append(CircuitIssue(tr("Aviso"), tr('Componente {v0}: señal indeterminada X.', v0=widget.id), graphic))
    if board._signal_halted:
        issues.append(CircuitIssue(tr("Error"), tr("Simulación detenida por una realimentación inestable."), None))
    return issues
