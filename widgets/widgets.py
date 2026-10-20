from resources import translate_text as tr
"""
widgets.py  –  Lógica de las puertas y el interruptor.
"""

import copy
from collections import deque


LOGIC_X = "X"
LOGIC_Z = "Z"


def normalize_logic_value(value, width=1):
    """Restore a signal without interpreting the strings X/Z as true."""
    if value in (LOGIC_X, LOGIC_Z):
        return value
    if type(value) not in (int, bool):
        raise ValueError(tr("Valor lógico no válido."))
    return bool(value) if width == 1 else int(value) & ((1 << width) - 1)


def combine_logic_or(current, incoming):
    """Kleene wired-OR: 1 dominates, while X and Z remain observable."""
    if incoming == LOGIC_Z:
        return current
    if current == LOGIC_Z:
        current = False
    if current is True or current == 1 or incoming is True or incoming == 1:
        return True
    if current == LOGIC_X or incoming == LOGIC_X:
        return LOGIC_X
    return bool(current or incoming)


class Widget:
    """Clase base para todos los elementos lógicos."""

    def __init__(self, id, n_enter=2, n_exit=1):
        self.id = id
        self.graphic = None
        self.delay_ms = 0
        self.delay_gates = 0
        self.gate_stages = 0

        self.enter: list[bool] = [False] * n_enter
        self.exit:  list[bool] = [False] * n_exit

        self.connections: dict[int, list[tuple["Widget", int]]] = {
            i: [] for i in range(n_exit)
        }
        self.input_widths = [1] * n_enter
        self.output_widths = [1] * n_exit

        self.add_enter = True
        self.add_exit  = True
        self.min_enter = 1

    # ── Configuración de puertos ──────────────────────────────────────────

    def set_enter(self, num: int):
        if not self.add_enter:
            return
        num = max(self.min_enter, min(8, int(num)))
        self.enter = (self.enter + [False] * num)[:num]
        self.input_widths = (self.input_widths + [1] * num)[:num]
        if self.graphic:
            self.graphic.rebuild_ports()

    def set_exit(self, num: int):
        if not self.add_exit:
            return
        num = max(1, min(8, num))
        for i in list(self.connections.keys()):
            if i >= num:
                self.connections.pop(i)
        self.exit = (self.exit + [False] * num)[:num]
        self.output_widths = (self.output_widths + [1] * num)[:num]
        for i in range(num):
            self.connections.setdefault(i, [])
        if self.graphic:
            self.graphic.rebuild_ports()

    def can_set_enter(self): return self.add_enter
    def can_set_exit(self):  return self.add_exit

    def default_input_values(self):
        return [LOGIC_Z if width > 1 else False for width in self.input_widths]

    # ── Delay ─────────────────────────────────────────────────────────────

    def set_delay(self, ms: int):
        self.delay_ms = max(0, int(ms))

    def set_delay_gates(self, gates: int):
        self.delay_gates = max(0, min(10000, int(gates)))

    @property
    def propagation_delay(self):
        """Scheduler ticks from configured milliseconds and gate stages."""
        return max(0, int(self.delay_ms)) + max(0, int(self.delay_gates)) + max(
            0, int(self.gate_stages))

    # ── Lógica ────────────────────────────────────────────────────────────

    def logic(self):
        pass

    # ── Propagación ───────────────────────────────────────────────────────

    def compute_and_propagate(self, board):
        old_exit = self.exit.copy()
        self.logic()

        for out_idx, new_val in enumerate(self.exit):
            if new_val == old_exit[out_idx]:
                continue
            if self.graphic:
                self.graphic.update_port_color(out_idx, is_input=False)
            for dest_widget, dest_enter_idx in self.connections.get(out_idx, []):
                board.enqueue_signal(dest_widget, dest_enter_idx, new_val,
                                     source=(self, out_idx))

    # ── Conexiones ────────────────────────────────────────────────────────

    def connect_to(self, out_idx: int, dest_widget: "Widget", dest_enter_idx: int):
        self.connections.setdefault(out_idx, [])
        self.connections[out_idx].append((dest_widget, dest_enter_idx))

    def disconnect(self, out_idx: int, dest_widget: "Widget", dest_enter_idx: int):
        lst = self.connections.get(out_idx, [])
        try:
            lst.remove((dest_widget, dest_enter_idx))
        except ValueError:
            pass


# ── Puertas básicas ──────────────────────────────────────────────────────────

class AND(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.gate_stages = 1
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        value = (False if any(bit is False or bit == 0 for bit in self.enter) else
                 LOGIC_X if any(bit in (LOGIC_X, LOGIC_Z) for bit in self.enter) else True)
        self.exit[:] = [value] * len(self.exit)


class OR(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.gate_stages = 1
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        value = (True if any(bit is True or (isinstance(bit, int) and bit > 0) for bit in self.enter) else
                 LOGIC_X if any(bit in (LOGIC_X, LOGIC_Z) for bit in self.enter) else False)
        self.exit[:] = [value] * len(self.exit)


class XOR(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.gate_stages = 1
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        value = (LOGIC_X if any(bit in (LOGIC_X, LOGIC_Z) for bit in self.enter)
                 else sum(bool(bit) for bit in self.enter) % 2 == 1)
        self.exit[:] = [value] * len(self.exit)


class NOT(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=1, n_exit=1)
        self.gate_stages = 1
        self.add_enter = False
        self.add_exit  = False

    def logic(self):
        value = self.enter[0]
        self.exit[0] = (LOGIC_X if value in (LOGIC_X, LOGIC_Z) else not bool(value))


class NAND(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.gate_stages = 1
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        value = (True if any(bit is False or bit == 0 for bit in self.enter) else
                 LOGIC_X if any(bit in (LOGIC_X, LOGIC_Z) for bit in self.enter) else False)
        self.exit[:] = [value] * len(self.exit)


class NOR(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.gate_stages = 1
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        value = (False if any(bit is True or (isinstance(bit, int) and bit > 0) for bit in self.enter) else
                 LOGIC_X if any(bit in (LOGIC_X, LOGIC_Z) for bit in self.enter) else True)
        self.exit[:] = [value] * len(self.exit)


class Switch(Widget):
    """Interruptor: sin entradas, una salida. Toggle al hacer doble click."""

    def __init__(self, id):
        super().__init__(id, n_enter=0, n_exit=1)
        self.add_enter = False
        self.add_exit  = False
        self.state = False

    def toggle(self, board):
        self.state   = not self.state
        self.exit[0] = self.state
        if self.graphic:
            self.graphic.update_port_color(0, is_input=False)
            self.graphic.update_switch_look()
        for dest_widget, dest_enter_idx in self.connections.get(0, []):
            board.enqueue_signal(dest_widget, dest_enter_idx, self.state,
                                 source=(self, 0))

    def logic(self):
        self.exit[0] = self.state


class Clock(Widget):
    """Señal cuadrada periódica, gestionada por el temporizador del tablero."""

    def __init__(self, id):
        super().__init__(id, n_enter=0, n_exit=1)
        self.add_enter = False
        self.add_exit = False
        self.state = False
        self.interval_ms = 500

    def set_interval(self, ms: int):
        self.interval_ms = max(10, min(60000, int(ms)))

    def logic(self):
        self.exit[0] = bool(self.state)

    def tick(self, board):
        self.state = not self.state
        self.compute_and_propagate(board)
        if self.graphic:
            self.graphic.update_switch_look()


class Button(Widget):
    """Pulsador momentáneo: la salida está activa mientras se mantiene pulsado."""

    def __init__(self, id):
        super().__init__(id, n_enter=0, n_exit=1)
        self.add_enter = False
        self.add_exit = False
        self.state = False

    def _set_pressed(self, pressed: bool, board):
        pressed = bool(pressed)
        if self.state == pressed:
            return
        self.state = pressed
        self.exit[0] = pressed
        if self.graphic:
            self.graphic.update_port_color(0, is_input=False)
            self.graphic.update_switch_look()
        for dest_widget, dest_enter_idx in self.connections.get(0, []):
            board.enqueue_signal(dest_widget, dest_enter_idx, pressed,
                                 source=(self, 0))

    def press(self, board):
        self._set_pressed(True, board)

    def release(self, board):
        self._set_pressed(False, board)

    def logic(self):
        self.exit[0] = self.state


class Delay(Widget):
    """Bloque vacío de un canal que retrasa la propagación de una señal."""

    def __init__(self, id):
        super().__init__(id, n_enter=1, n_exit=1)
        self.add_enter = False
        self.add_exit = False
        self.delay_ms = 250

    def logic(self):
        self.exit[0] = self.enter[0]


# ── Salidas ──────────────────────────────────────────────────────────────────

class Bulb(Widget):
    """Bombilla: 1 entrada, sin salidas. Se ilumina cuando la entrada es True."""

    def __init__(self, id):
        super().__init__(id, n_enter=1, n_exit=0)
        self.bulb_color: str | None = None
        self.add_enter = False
        self.add_exit  = False
        # Sin conexiones de salida
        self.connections = {}

    def logic(self):
        # La bombilla no tiene lógica de salida; solo reacciona visualmente
        pass

    def compute_and_propagate(self, board):
        # Solo actualizamos el aspecto visual; no hay salidas que propagar
        self.logic()
        if self.graphic:
            self.graphic.update_port_color(0, is_input=True)


class Display(Widget):
    """Display 7 segmentos: 7 entradas (a b c d e f g), sin salidas."""

    def __init__(self, id):
        super().__init__(id, n_enter=7, n_exit=0)
        self.segment_colors: list[str | None] = [None] * 7
        self.add_enter = False
        self.add_exit  = False
        self.connections = {}

    def logic(self):
        pass

    def compute_and_propagate(self, board):
        self.logic()
        if self.graphic:
            # Refrescar todos los puertos de entrada y el aspecto visual
            for i in range(len(self.enter)):
                self.graphic.update_port_color(i, is_input=True)


class BusInput(Widget):
    """Editable unsigned bus source, with widths from 2 to 32 bits."""

    def __init__(self, id, width=8, value=0):
        super().__init__(id, n_enter=0, n_exit=1)
        self.add_enter = self.add_exit = False
        self.width = max(2, min(32, int(width)))
        self.output_widths = [self.width]
        self.value = int(value) & ((1 << self.width) - 1)
        self.exit[0] = self.value

    def set_bus(self, width, value=None):
        self.width = max(2, min(32, int(width)))
        self.output_widths = [self.width]
        self.value = (self.value if value is None else int(value)) & ((1 << self.width) - 1)
        self.exit[0] = self.value
        if self.graphic:
            self.graphic.prepareGeometryChange()
            self.graphic.update()
            self.graphic._reposition_ports()
            for port in self.graphic._ports_out:
                port.update_tooltip()
        return self.value

    set_bus_width = set_bus

    def set_value(self, value, board):
        self.value = int(value) & ((1 << self.width) - 1)
        self.compute_and_propagate(board)
        if self.graphic:
            self.graphic.update()

    def logic(self):
        self.exit[0] = self.value


class BusLamp(Widget):
    """Readable unsigned bus sink."""

    def __init__(self, id, width=8):
        super().__init__(id, n_enter=1, n_exit=0)
        self.add_enter = self.add_exit = False
        self.width = max(2, min(32, int(width)))
        self.input_widths = [self.width]
        self.connections = {}

    def logic(self):
        pass

    def set_bus_width(self, width, value=None):
        self.width = max(2, min(32, int(width)))
        self.input_widths = [self.width]
        if self.graphic:
            self.graphic._reposition_ports()
            self.graphic.update()

    def compute_and_propagate(self, board):
        if self.graphic:
            self.graphic.update_port_color(0, is_input=True)
            self.graphic.update()


class BusViewer(Widget):
    """Transparent inline monitor: preserve the input value, including X/Z."""

    def __init__(self, id, width=1):
        super().__init__(id, n_enter=1, n_exit=1)
        self.add_enter = self.add_exit = False
        self.width = max(1, min(32, int(width)))
        self.input_widths, self.output_widths = [self.width], [self.width]

    def logic(self):
        self.exit[0] = self.enter[0]

    def compute_and_propagate(self, board):
        super().compute_and_propagate(board)
        if self.graphic:
            self.graphic.update()

    def set_bus_width(self, width, value=None):
        if self.graphic:
            for wire in self.graphic.wires:
                wire.prepareGeometryChange()
        self.width = max(1, min(32, int(width)))
        self.input_widths, self.output_widths = [self.width], [self.width]
        if self.graphic:
            self.graphic._reposition_ports()
            for port in self.graphic._ports_in + self.graphic._ports_out:
                port.update_tooltip()
            for wire in self.graphic.wires:
                wire._update_pen()
                wire.update()
            self.graphic.update()


class Splitter(Widget):
    """Splits an unsigned bus into scalar outputs, bit zero first."""

    def __init__(self, id, width=8):
        width = max(2, min(32, int(width)))
        super().__init__(id, n_enter=1, n_exit=width)
        self.add_enter = self.add_exit = False
        self.width = width
        self.input_widths = [width]
        self.output_widths = [1] * width

    def logic(self):
        value = self.enter[0]
        if value in (LOGIC_X, LOGIC_Z):
            self.exit[:] = [LOGIC_X if value == LOGIC_X else LOGIC_Z] * self.width
        else:
            value = int(value)
            self.exit[:] = [(value >> bit) & 1 == 1 for bit in range(self.width)]

    def set_bus_width(self, width, value=None):
        self.width = max(2, min(32, int(width)))
        previous = self.enter[0]
        self.enter = [previous if previous in (LOGIC_X, LOGIC_Z) else
                      int(previous) & ((1 << self.width) - 1)]
        self.exit = ([previous] * self.width if previous in (LOGIC_X, LOGIC_Z) else
                     [(self.enter[0] >> bit) & 1 == 1 for bit in range(self.width)])
        self.input_widths, self.output_widths = [self.width], [1] * self.width
        self.connections = {index: self.connections.get(index, [])
                            for index in range(self.width)}
        if self.graphic:
            self.graphic.rebuild_ports()


class Combiner(Widget):
    """Combines scalar inputs into an unsigned bus, bit zero first."""

    def __init__(self, id, width=8):
        width = max(2, min(32, int(width)))
        super().__init__(id, n_enter=width, n_exit=1)
        self.add_enter = self.add_exit = False
        self.width = width
        self.input_widths = [1] * width
        self.output_widths = [width]

    def logic(self):
        if any(value == LOGIC_X for value in self.enter):
            self.exit[0] = LOGIC_X
        elif any(value == LOGIC_Z for value in self.enter):
            self.exit[0] = LOGIC_X
        else:
            self.exit[0] = sum((1 << bit) for bit, value in enumerate(self.enter) if value)

    def set_bus_width(self, width, value=None):
        self.width = max(2, min(32, int(width)))
        self.enter = (self.enter + [False] * self.width)[:self.width]
        previous = self.exit[0]
        self.exit = [previous if previous in (LOGIC_X, LOGIC_Z) else
                     int(previous) & ((1 << self.width) - 1)]
        self.input_widths, self.output_widths = [1] * self.width, [self.width]
        self.connections = {0: self.connections.get(0, [])}
        if self.graphic:
            self.graphic.rebuild_ports()


class TriState(Widget):
    """Bus driver: outputs Z while disabled; enable is input port 1."""

    def __init__(self, id, width=8):
        width = max(2, min(32, int(width)))
        super().__init__(id, n_enter=2, n_exit=1)
        self.add_enter = self.add_exit = False
        self.width = width
        self.input_widths = [width, 1]
        self.output_widths = [width]
        self.enter[0] = 0
        self.exit[0] = "Z"

    def logic(self):
        if self.enter[1] in (LOGIC_X, LOGIC_Z):
            self.exit[0] = LOGIC_X
        elif bool(self.enter[1]):
            self.exit[0] = (self.enter[0] if self.enter[0] in (LOGIC_X, LOGIC_Z)
                            else int(self.enter[0]) & ((1 << self.width) - 1))
        else:
            self.exit[0] = LOGIC_Z

    def set_bus_width(self, width, value=None):
        self.width = max(2, min(32, int(width)))
        self.input_widths, self.output_widths = [self.width, 1], [self.width]
        self.enter[0] = (self.enter[0] if self.enter[0] in (LOGIC_X, LOGIC_Z) else
                         int(self.enter[0]) & ((1 << self.width) - 1))
        if not self.enter[1]:
            self.exit[0] = "Z"
        else:
            self.exit[0] = self.enter[0]
        if self.graphic:
            self.graphic._reposition_ports()
            self.graphic.update()


class Module(Widget):
    """Circuito encapsulado como una única puerta reutilizable.

    ``truth_table`` guarda filas legibles de entradas, salidas y tiempo de
    respuesta. Los archivos importados deben usar los formatos publicados.
    """

    def __init__(self, id, name: str, inputs: int, outputs: int,
                 truth_table: list | None = None,
                 input_numbers: list[int] | None = None,
                 output_numbers: list[int] | None = None,
                 stateful_circuit: dict | None = None,
                 stateful_state: dict | None = None,
                 input_labels: list[str] | None = None,
                 output_labels: list[str] | None = None,
                 input_widths: list[int] | None = None,
                 output_widths: list[int] | None = None):
        super().__init__(id, n_enter=inputs, n_exit=outputs)
        self.gate_stages = 1
        self.input_widths = self._normalize_widths(input_widths, inputs)
        self.output_widths = self._normalize_widths(output_widths, outputs)
        if stateful_circuit and stateful_circuit.get("version", 1) < 2 and (any(width != 1 for width in
                                     self.input_widths + self.output_widths)):
            raise ValueError(tr("Los módulos secuenciales con puertos multi-bit aún no son compatibles."))
        self.name = name or "Módulo"
        self.stateful_circuit = (copy.deepcopy(stateful_circuit)
                                 if isinstance(stateful_circuit, dict) else None)
        if self.stateful_circuit:
            self.input_numbers = self._normalize_port_numbers(input_numbers, inputs)
            self.output_numbers = self._normalize_port_numbers(output_numbers, outputs)
            self.input_labels = self._normalize_port_labels(input_labels, inputs)
            self.output_labels = self._normalize_port_labels(output_labels, outputs)
            self.truth_table = []
        else:
            (self.input_numbers, self.output_numbers, self.truth_table,
             input_order, output_order) = self.canonicalize_port_order(
                inputs, outputs, truth_table, input_numbers, output_numbers,
                self.input_widths, self.output_widths)
            input_labels = self._normalize_port_labels(input_labels, inputs)
            output_labels = self._normalize_port_labels(output_labels, outputs)
            self.input_labels = [input_labels[index] for index in input_order]
            self.output_labels = [output_labels[index] for index in output_order]
            self.input_widths = [self.input_widths[index] for index in input_order]
            self.output_widths = [self.output_widths[index] for index in output_order]
        self._truth_rows = {tuple(row["inputs"]): row for row in self.truth_table}
        self.response_ms = 0
        self._pending_response = 0
        self.add_enter = False
        self.add_exit = False
        self._stateful_nodes = {}
        self._stateful_drivers = {}
        self._stateful_previous_inputs = [False] * inputs
        self._stateful_initialized = False
        if self.stateful_circuit:
            self._init_stateful_runtime(stateful_state)

    def _init_stateful_runtime(self, saved_state=None):
        from .native import COMPONENTS, Native
        node_types = {"AND": AND, "OR": OR, "XOR": XOR, "NOT": NOT,
                      "NAND": NAND, "NOR": NOR, "RETARDO": Delay,
                      "BUS_VISOR": BusViewer, "SPLITTER": Splitter,
                      "COMBINER": Combiner, "TRIESTADO": TriState}
        if saved_state is None:
            saved_state = self.stateful_circuit.get("initial_state")
        saved_nodes = saved_state.get("nodes", {}) if isinstance(saved_state, dict) else {}
        for spec in self.stateful_circuit.get("components", []):
            node_id = str(spec["id"])
            kind = str(spec.get("type", "")).upper()
            cls = node_types.get(kind)
            saved = saved_nodes.get(node_id, {})
            if kind == "MODULO":
                nested_state = saved.get("stateful_state") or spec.get("stateful_state")
                node = Module(int(spec["id"]), str(spec.get("name", "Módulo")),
                              int(spec.get("inputs", 1)), int(spec.get("outputs", 1)),
                              spec.get("truth_table", []), spec.get("input_numbers"),
                              spec.get("output_numbers"), spec.get("stateful_circuit"),
                              nested_state, spec.get("input_labels"),
                              spec.get("output_labels"), spec.get("input_widths"), spec.get("output_widths"))
            elif kind in COMPONENTS and issubclass(COMPONENTS[kind], Native):
                if self.stateful_circuit.get("version", 1) < 2:
                    raise ValueError(tr("La memoria nativa necesita el formato de CI 1.3."))
                node = COMPONENTS[kind](int(spec["id"]), width=spec.get("bus_width", 8),
                    address_bits=spec.get("address_bits", 4), channels=spec.get("channels", 4))
                node.restore_native(saved.get("native", spec.get("native_data", {})))
            elif cls in (BusViewer, Splitter, Combiner, TriState):
                node = cls(int(spec["id"]), spec.get("bus_width", 8))
            elif cls is not None:
                node = cls(int(spec["id"]))
            else:
                raise ValueError(tr('Tipo interno de módulo no compatible: {v0}', v0=spec.get('type')))
            if node.can_set_enter() and len(node.enter) != int(spec.get("inputs", len(node.enter))):
                node.set_enter(int(spec["inputs"]))
            node.delay_ms = max(0, int(spec.get("delay_ms", node.delay_ms)))
            node.set_delay_gates(spec.get("delay_gates", 0))
            if isinstance(saved.get("enter"), list):
                node.enter = ([normalize_logic_value(v, node.input_widths[i]) for i, v in enumerate(saved["enter"][:len(node.enter)])] +
                              [False] * len(node.enter))[:len(node.enter)]
            if isinstance(saved.get("exit"), list):
                node.exit = ([normalize_logic_value(v, node.output_widths[i]) for i, v in enumerate(saved["exit"][:len(node.exit)])] +
                             [False] * len(node.exit))[:len(node.exit)]
            if node_id in self._stateful_nodes:
                raise ValueError(tr("Identificador interno de CI repetido."))
            self._stateful_nodes[node_id] = node

        for edge in self.stateful_circuit.get("connections", []):
            source_id = str(edge["source"])
            source = self._stateful_nodes[source_id]
            destination = self._stateful_nodes[str(edge["destination"])]
            output_index, input_index = int(edge["output"]), int(edge["input"])
            if not 0 <= output_index < len(source.exit) or not 0 <= input_index < len(destination.enter):
                raise ValueError(tr("Conexión interna a un puerto inexistente."))
            source.connect_to(output_index, destination, input_index)
            drivers = self._stateful_drivers.setdefault((destination.id, input_index), {})
            drivers[(source, output_index)] = normalize_logic_value(
                source.exit[output_index] if output_index < len(source.exit) else False, source.output_widths[output_index])
        if isinstance(saved_state, dict):
            previous = saved_state.get("inputs", [])
            if isinstance(previous, list):
                self._stateful_previous_inputs = ([normalize_logic_value(v, self.input_widths[i]) for i, v in enumerate(previous[:len(self.enter)])] +
                    [False] * len(self.enter))[:len(self.enter)]
            self._stateful_initialized = bool(saved_state.get("initialized", False))
        for binding in self.stateful_circuit.get("input_bindings", []):
            if not 0 <= int(binding["input"]) < len(self.enter):
                raise ValueError(tr("Entrada de CI secuencial inexistente."))
            for target in binding.get("targets", []):
                node = self._stateful_nodes[str(target["node"])]
                if not 0 <= int(target["port"]) < len(node.enter):
                    raise ValueError(tr("Puerto interno de CI secuencial inexistente."))
        for binding in self.stateful_circuit.get("output_bindings", []):
            if not 0 <= int(binding["output"]) < len(self.exit):
                raise ValueError(tr("Salida de CI secuencial inexistente."))
            for source in binding.get("sources", []):
                if "input" in source:
                    if not 0 <= int(source["input"]) < len(self.enter):
                        raise ValueError(tr("Entrada de CI secuencial inexistente."))
                else:
                    node = self._stateful_nodes[str(source["node"])]
                    if not 0 <= int(source["port"]) < len(node.exit):
                        raise ValueError(tr("Salida interna de CI secuencial inexistente."))

    def export_stateful_state(self):
        from .native import Native
        if not self.stateful_circuit:
            return None
        return {
            "initialized": self._stateful_initialized,
            "inputs": list(self._stateful_previous_inputs),
            "nodes": {node_id: {"enter": list(node.enter), "exit": list(node.exit),
                                **({"native": node.export_native()} if isinstance(node, Native) else {}),
                                **({"stateful_state": node.export_stateful_state()}
                                   if isinstance(node, Module) and node.stateful_circuit else {})}
                      for node_id, node in self._stateful_nodes.items()},
        }

    def _run_stateful_circuit(self, board=None):
        """Resolve simultaneous internal waves, retaining native and nested state."""
        queue = deque()
        scheduled = {}
        steps = [0]

        def route(event, delay):
            if delay and board is not None:
                scheduled.setdefault(delay, []).append(event)
            else:
                queue.append(event)

        def emit(node_id, node, previous):
            for index, value in enumerate(node.exit):
                if index < len(previous) and value == previous[index]:
                    continue
                for destination, pin in node.connections.get(index, []):
                    route((destination, pin, value, (node, index)), destination.propagation_delay)

        def publish_outputs():
            new_outputs = self.exit.copy()
            for binding in self.stateful_circuit.get("output_bindings", []):
                index = int(binding["output"])
                drivers = {}
                for number, source in enumerate(binding.get("sources", [])):
                    if "input" in source:
                        value = self.enter[int(source["input"])]
                        key = ("input", int(source["input"]))
                    else:
                        node = self._stateful_nodes[str(source["node"])]
                        value = node.exit[int(source["port"])]
                        key = (node, int(source["port"]))
                    drivers[key] = value
                new_outputs[index] = combine_driver_values(drivers, self.output_widths[index])
            previous = self.exit
            self.exit = new_outputs
            if board is not None:
                for index, value in enumerate(self.exit):
                    if value == previous[index]:
                        continue
                    if self.graphic:
                        self.graphic.update_port_color(index, is_input=False)
                    for destination, pin in self.connections.get(index, []):
                        board.enqueue_signal(destination, pin, value, source=(self, index))
            if self.graphic:
                self.graphic.update_all_output_wires()

        def drain():
            while queue and steps[0] < 10000:
                wave = list(queue)
                queue.clear()
                changed = set()
                for node, pin, value, driver in wave:
                    steps[0] += 1
                    if not 0 <= pin < len(node.enter):
                        continue
                    drivers = self._stateful_drivers.setdefault((node.id, pin), {})
                    if value == LOGIC_Z:
                        drivers.pop(driver, None)
                    else:
                        drivers[driver] = value
                    combined = combine_driver_values(drivers, node.input_widths[pin])
                    if node.enter[pin] != combined:
                        node.enter[pin] = combined
                        changed.add(node)
                # All input pins in a wave are applied before any clock samples D.
                for node in sorted(changed, key=lambda item: item.id):
                    previous = node.exit.copy()
                    node.logic()
                    emit(str(node.id), node, previous)
            if queue:
                queue.clear()
                scheduled.clear()
                for node in self._stateful_nodes.values():
                    node.exit = [LOGIC_X] * len(node.exit)
            publish_outputs()
            batches = list(scheduled.items())
            scheduled.clear()
            for delay, events in batches:
                def delayed(items=events):
                    queue.extend(items)
                    steps[0] = 0
                    drain()
                board.enqueue_action(delay, delayed)

        if not self._stateful_initialized:
            for node_id, node in self._stateful_nodes.items():
                previous = node.exit.copy()
                node.logic()
                emit(node_id, node, previous)
            self._stateful_initialized = True
        current = [normalize_logic_value(value, self.input_widths[i]) for i, value in enumerate(self.enter)]
        for binding in self.stateful_circuit.get("input_bindings", []):
            index = int(binding["input"])
            value = current[index]
            if value == self._stateful_previous_inputs[index]:
                continue
            for target in binding.get("targets", []):
                node = self._stateful_nodes[str(target["node"])]
                route((node, int(target["port"]), value, ("module-input", index)), node.propagation_delay)
        self._stateful_previous_inputs = current
        drain()

    @staticmethod
    def _normalize_widths(widths, count):
        values = list(widths or [])[:count]
        result = []
        for index in range(count):
            try:
                width = int(values[index]) if index < len(values) else 1
            except (TypeError, ValueError):
                width = 1
            result.append(max(1, min(32, width)))
        return result

    @staticmethod
    def _normalize_port_numbers(numbers, count):
        values = list(numbers or [])[:count]
        normalized = []
        for index, value in enumerate(values):
            try:
                candidate = min(99, max(0, int(value)))
            except (TypeError, ValueError):
                candidate = index
            if candidate in normalized:
                candidate = next((number for number in range(100)
                                 if number not in normalized), 0)
            normalized.append(candidate)
        while len(normalized) < count:
            normalized.append(next(number for number in range(100)
                                    if number not in normalized))
        return normalized

    @staticmethod
    def _normalize_port_labels(labels, count):
        values = list(labels or [])[:count]
        normalized = [str(value or "").strip() for value in values]
        return normalized + [""] * (count - len(normalized))

    @classmethod
    def canonicalize_port_order(cls, inputs, outputs, truth_table,
                                input_numbers=None, output_numbers=None,
                                input_widths=None, output_widths=None):
        input_numbers = cls._normalize_port_numbers(input_numbers, inputs)
        output_numbers = cls._normalize_port_numbers(output_numbers, outputs)
        input_order = sorted(range(inputs), key=lambda index: input_numbers[index])
        output_order = sorted(range(outputs), key=lambda index: output_numbers[index])
        in_widths = cls._normalize_widths(input_widths, inputs)
        out_widths = cls._normalize_widths(output_widths, outputs)
        rows = cls.normalize_truth_table(inputs, outputs, truth_table, in_widths, out_widths)
        for row in rows:
            row["inputs"] = [row["inputs"][index] for index in input_order]
            row["outputs"] = [row["outputs"][index] for index in output_order]
        in_widths = [in_widths[index] for index in input_order]
        out_widths = [out_widths[index] for index in output_order]
        return ([input_numbers[index] for index in input_order],
                [output_numbers[index] for index in output_order], rows,
                input_order, output_order)

    def set_port_numbers(self, input_numbers, output_numbers):
        if self.stateful_circuit:
            normalized_inputs = self._normalize_port_numbers(input_numbers, len(self.enter))
            normalized_outputs = self._normalize_port_numbers(output_numbers, len(self.exit))
            input_order = sorted(range(len(normalized_inputs)), key=lambda i: normalized_inputs[i])
            output_order = sorted(range(len(normalized_outputs)), key=lambda i: normalized_outputs[i])
            input_remap = {old: new for new, old in enumerate(input_order)}
            output_remap = {old: new for new, old in enumerate(output_order)}
            for binding in self.stateful_circuit.get("input_bindings", []):
                binding["input"] = input_remap.get(int(binding["input"]), int(binding["input"]))
            for binding in self.stateful_circuit.get("output_bindings", []):
                binding["output"] = output_remap.get(int(binding["output"]), int(binding["output"]))
                for source in binding.get("sources", []):
                    if "input" in source:
                        source["input"] = input_remap.get(int(source["input"]), int(source["input"]))
            initial_state = self.stateful_circuit.get("initial_state", {})
            if isinstance(initial_state, dict) and isinstance(initial_state.get("inputs"), list):
                old_values = initial_state["inputs"]
                initial_state["inputs"] = [normalize_logic_value(old_values[i], self.input_widths[i]) if i < len(old_values) else False
                                            for i in input_order]
            self._stateful_previous_inputs = [self._stateful_previous_inputs[i]
                                              for i in input_order]
            new_inputs = [normalized_inputs[index] for index in input_order]
            new_outputs = [normalized_outputs[index] for index in output_order]
            rows = []
        else:
            (new_inputs, new_outputs, rows,
             _input_order, _output_order) = self.canonicalize_port_order(
                len(self.enter), len(self.exit), self.truth_table,
                input_numbers, output_numbers, self.input_widths, self.output_widths)
            input_order, output_order = _input_order, _output_order
        self.enter = [self.enter[index] for index in input_order]
        self.exit = [self.exit[index] for index in output_order]
        self.input_numbers, self.output_numbers = new_inputs, new_outputs
        self.input_widths = [self.input_widths[index] for index in input_order]
        self.output_widths = [self.output_widths[index] for index in output_order]
        self.input_labels = [self.input_labels[index] for index in input_order]
        self.output_labels = [self.output_labels[index] for index in output_order]
        self.truth_table = rows
        self._truth_rows = {tuple(row["inputs"]): row for row in rows}
        if self.graphic:
            self.graphic._ports_in = [self.graphic._ports_in[index] for index in input_order]
            self.graphic._ports_out = [self.graphic._ports_out[index] for index in output_order]
            for index, port in enumerate(self.graphic._ports_in):
                port.port_index = index
                port.update_tooltip()
                port.update_color()
            for index, port in enumerate(self.graphic._ports_out):
                port.port_index = index
                port.update_tooltip()
                port.update_color()
            self.graphic._reposition_ports()
            self.graphic.update()
            scene = self.graphic.scene()
            if scene and scene.views():
                view = scene.views()[0]
                if hasattr(view, "rebuild_connections"):
                    view.rebuild_connections()

    def set_port_labels(self, input_labels, output_labels):
        if self.graphic:
            self.graphic.prepareGeometryChange()
        self.input_labels = self._normalize_port_labels(input_labels, len(self.enter))
        self.output_labels = self._normalize_port_labels(output_labels, len(self.exit))
        if self.graphic:
            self.graphic._reposition_ports()
            for port in self.graphic._ports_in + self.graphic._ports_out:
                port.update_tooltip()
            self.graphic.update()
            scene = self.graphic.scene()
            if scene and scene.views():
                view = scene.views()[0]
                if hasattr(view, "rebuild_connections"):
                    view.rebuild_connections()

    @staticmethod
    def normalize_truth_table(inputs: int, outputs: int, truth_table: list | None,
                              input_widths=None, output_widths=None) -> list[dict]:
        """Normalize legacy bit-packed rows and new explicit rows to JSON data."""
        input_widths = Module._normalize_widths(input_widths, inputs)
        output_widths = Module._normalize_widths(output_widths, outputs)
        total_input_bits = sum(input_widths)
        if total_input_bits > 16:
            raise ValueError(tr("Una tabla combinacional admite como máximo 16 bits de entrada."))
        expected = 1 << total_input_bits
        raw_rows = list(truth_table or [])
        normalized = []
        for row_index in range(expected):
            raw = raw_rows[row_index] if row_index < len(raw_rows) else None
            input_values = []
            bit_offset = 0
            for width in input_widths:
                input_values.append((row_index >> bit_offset) & ((1 << width) - 1))
                bit_offset += width
            if isinstance(raw, dict):
                raw_inputs = raw.get("inputs", input_values)
                input_values = [int(value) & ((1 << input_widths[index]) - 1)
                                for index, value in enumerate(list(raw_inputs)[:inputs])]
                input_values.extend([0] * (inputs - len(input_values)))
                raw_outputs = raw.get("outputs", [])
                if isinstance(raw_outputs, int):
                    output_values = [bool(raw_outputs & (1 << i)) for i in range(outputs)]
                else:
                    output_values = [value if value in (LOGIC_X, LOGIC_Z) else
                                     (int(value) & ((1 << output_widths[index]) - 1)
                                      if output_widths[index] > 1 else bool(value))
                                     for index, value in enumerate(list(raw_outputs)[:outputs])]
                output_values.extend([0] * (outputs - len(output_values)))
                time_ms = max(0, int(raw.get("time_ms", raw.get("delay_ms", 0))))
            elif isinstance(raw, (list, tuple)):
                output_values = [bool(value) for value in raw[:outputs]]
                output_values.extend([False] * (outputs - len(output_values)))
                time_ms = 0
            elif isinstance(raw, int):
                output_values = [bool(raw & (1 << i)) for i in range(outputs)]
                time_ms = 0
            else:
                output_values = [False] * outputs
                time_ms = 0
            normalized.append({"inputs": input_values, "outputs": output_values,
                               "time_ms": time_ms})
        return normalized

    def truth_row(self):
        if any(value in (LOGIC_X, LOGIC_Z) for value in self.enter):
            return {"outputs": [LOGIC_X] * len(self.exit), "time_ms": 0}
        return self._truth_rows.get(tuple(int(value) if self.input_widths[index] > 1 else bool(value)
                                          for index, value in enumerate(self.enter)),
                                    {"outputs": [False] * len(self.exit), "time_ms": 0})

    def logic(self):
        if self.stateful_circuit:
            self._run_stateful_circuit()
            return
        row = self.truth_row()
        self.response_ms = row["time_ms"]
        self.exit = row["outputs"].copy()

    def compute_and_propagate(self, board):
        if self.stateful_circuit:
            self._run_stateful_circuit(board)
            return
        row = self.truth_row()
        self.response_ms = row["time_ms"]
        self._pending_response += 1
        response_id = self._pending_response

        def commit():
            if response_id != self._pending_response:
                return
            old_exit = self.exit.copy()
            self.exit = row["outputs"].copy()
            for index, value in enumerate(self.exit):
                if value == old_exit[index]:
                    continue
                if self.graphic:
                    self.graphic.update_port_color(index, is_input=False)
                for destination, input_index in self.connections.get(index, []):
                    board.enqueue_signal(destination, input_index, value,
                                         source=(self, index))
            if self.graphic:
                self.graphic.update_all_output_wires()

        if row["time_ms"]:
            board.enqueue_action(row["time_ms"], commit)
        else:
            commit()


def combine_driver_values(drivers, width=1):
    """Resolve wired-OR drivers, retaining unknowns and weak pull semantics."""
    active = {key: value for key, value in drivers.items() if value != LOGIC_Z}
    strong = {key: value for key, value in active.items()
              if not (isinstance(key, tuple) and key and getattr(key[0], "weak_driver", False))}
    values = list((strong or active).values())
    if not values:
        return LOGIC_Z if width > 1 else False
    if LOGIC_X in values:
        return LOGIC_X
    result = 0
    for value in values:
        result |= int(value)
    return result & ((1 << width) - 1)


def combinational_order(widgets, edges=None):
    """Return a deterministic topological order, or None for state/feedback."""
    widgets = sorted(widgets, key=lambda item: item.id)
    if any(getattr(widget, "sequential", False) or getattr(widget, "stateful_circuit", False)
           for widget in widgets):
        return None
    chosen = set(widgets)
    if edges is None:
        edges = [(src, index, dst, pin) for src in widgets
                 for index, targets in src.connections.items()
                 for dst, pin in targets if dst in chosen]
    adjacency = {widget: [] for widget in widgets}
    indegree = dict.fromkeys(widgets, 0)
    for src, _index, dst, _pin in edges:
        adjacency[src].append(dst)
        indegree[dst] += 1
    pending = deque(widget for widget in widgets if indegree[widget] == 0)
    order = []
    while pending:
        widget = pending.popleft()
        order.append(widget)
        for dst in adjacency[widget]:
            indegree[dst] -= 1
            if indegree[dst] == 0:
                pending.append(dst)
    return order if len(order) == len(widgets) else None


def combinational_plan(widgets, edges):
    """Compile incoming edges once for all rows of a combinational table."""
    order = combinational_order(widgets, edges)
    if order is None:
        raise ValueError(tr("El circuito contiene memoria o realimentación; no admite tabla combinacional."))
    incoming = {widget: [] for widget in order}
    for src, index, dst, pin in edges:
        incoming[dst].append((src, index, pin))
    return order, incoming


def evaluate_combinational(plan, base_inputs=None):
    """Evaluate each block exactly once in dependency order, preserving X/Z."""
    order, incoming = plan
    for widget in order:
        drivers = {}
        for index, value in (base_inputs or {}).get(widget, {}).items():
            drivers.setdefault(index, {})[("external", index)] = value
        for source, index, pin in incoming[widget]:
            drivers.setdefault(pin, {})[(source, index)] = source.exit[index]
        widget.enter = [combine_driver_values(drivers.get(index, {}), width)
                        for index, width in enumerate(widget.input_widths)]
        widget.logic()


def settle_topology(widgets, combine, *, restore_state=False, force=False):
    """Resolve the finished wiring from current outputs, preserving stored memory.

    Editing is a topology transaction, not a pulse on every wire. Only changed
    inputs and new components need evaluating. Outputs update their drivers
    immediately, so feedback reads the current network rather than stale events.
    A real unstable loop becomes X without stopping independent circuits.
    """
    widgets = sorted(widgets, key=lambda item: item.id)
    order = combinational_order(widgets)
    if order is not None:
        widgets = order
    drivers = {}
    old_inputs = {widget: list(widget.enter) for widget in widgets}
    for source in widgets:
        for out_index, destinations in source.connections.items():
            for destination, in_index in destinations:
                if 0 <= in_index < len(destination.enter):
                    value = source.exit[out_index]
                    if value != "Z":
                        drivers.setdefault((destination, in_index), {})[(source, out_index)] = value
    for widget in widgets:
        widget.enter = [combine(drivers.get((widget, index), {}), width)
                        for index, width in enumerate(widget.input_widths)]
        if getattr(widget, "_prime_clock", False):
            widget.previous_clock = widget.enter[widget.input_labels.index("CLK")]

    dirty = deque()
    queued = set()
    unstable = set()

    def enqueue(widget):
        if widget not in queued and widget not in unstable:
            queued.add(widget)
            dirty.append(widget)

    for widget in widgets:
        preserved = restore_state and getattr(widget, "_has_saved_logic_state", False)
        if not preserved and (force or widget.enter != old_inputs[widget]
                              or not getattr(widget, "_simulation_initialized", False)):
            enqueue(widget)

    def emit(widget, previous):
        for out_index, value in enumerate(widget.exit):
            if value == previous[out_index]:
                continue
            for destination, in_index in widget.connections.get(out_index, []):
                pin = (destination, in_index)
                active = drivers.setdefault(pin, {})
                if value == "Z":
                    active.pop((widget, out_index), None)
                else:
                    active[(widget, out_index)] = value
                resolved = combine(active, destination.input_widths[in_index])
                if resolved != destination.enter[in_index]:
                    destination.enter[in_index] = resolved
                    enqueue(destination)

    seen = {}
    evaluated = []
    budget = max(10000, len(widgets) * 128)
    while dirty:
        state = ((tuple((tuple(widget.enter), tuple(widget.exit)) for widget in widgets),
                  tuple(widget.id for widget in dirty)) if order is None else None)
        start = seen.get(state) if state is not None else None
        if start is not None or len(evaluated) >= budget:
            participants = set(evaluated[start:] if start is not None else dirty)
            oscillators = {widget for widget in participants if widget.enter and widget.exit
                           and not getattr(widget, "sequential", False)}
            if not oscillators:
                break
            unstable.update(oscillators)
            for widget in sorted(oscillators, key=lambda item: item.id):
                previous = widget.exit.copy()
                widget.exit = ["X"] * len(widget.exit)
                emit(widget, previous)
            dirty = deque(widget for widget in dirty if widget not in unstable)
            queued = set(dirty)
            seen.clear()
            evaluated.clear()
            continue
        if state is not None:
            seen[state] = len(evaluated)
        widget = dirty.popleft()
        queued.remove(widget)
        previous = widget.exit.copy()
        widget.logic()
        evaluated.append(widget)
        emit(widget, previous)

    for widget in widgets:
        widget._simulation_initialized = True
    return drivers, unstable
