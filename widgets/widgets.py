"""
widgets.py  –  Lógica de las puertas y el interruptor.
"""

import copy


class Widget:
    """Clase base para todos los elementos lógicos."""

    def __init__(self, id, n_enter=2, n_exit=1):
        self.id = id
        self.graphic = None
        self.delay_ms = 0

        self.enter: list[bool] = [False] * n_enter
        self.exit:  list[bool] = [False] * n_exit

        self.connections: dict[int, list[tuple["Widget", int]]] = {
            i: [] for i in range(n_exit)
        }

        self.add_enter = True
        self.add_exit  = True
        self.min_enter = 1

    # ── Configuración de puertos ──────────────────────────────────────────

    def set_enter(self, num: int):
        if not self.add_enter:
            return
        num = max(self.min_enter, min(8, int(num)))
        self.enter = (self.enter + [False] * num)[:num]
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
        for i in range(num):
            self.connections.setdefault(i, [])
        if self.graphic:
            self.graphic.rebuild_ports()

    def can_set_enter(self): return self.add_enter
    def can_set_exit(self):  return self.add_exit

    # ── Delay ─────────────────────────────────────────────────────────────

    def set_delay(self, ms: int):
        self.delay_ms = max(0, int(ms))

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
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        self.exit[:] = [all(self.enter)] * len(self.exit)


class OR(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        self.exit[:] = [any(self.enter)] * len(self.exit)


class XOR(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        value = self.enter.count(True) % 2 == 1
        self.exit[:] = [value] * len(self.exit)


class NOT(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=1, n_exit=1)
        self.add_enter = False
        self.add_exit  = False

    def logic(self):
        self.exit[0] = not self.enter[0]


class NAND(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        self.exit[:] = [not all(self.enter)] * len(self.exit)


class NOR(Widget):
    def __init__(self, id):
        super().__init__(id, n_enter=2, n_exit=1)
        self.min_enter = 2
        self.add_exit = False

    def logic(self):
        self.exit[:] = [not any(self.enter)] * len(self.exit)


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


class Module(Widget):
    """Circuito encapsulado como una única puerta reutilizable.

    ``truth_table`` guarda filas legibles de entradas, salidas y tiempo de
    respuesta. Los módulos antiguos con salidas empaquetadas en enteros se
    convierten al cargarlos.
    """

    def __init__(self, id, name: str, inputs: int, outputs: int,
                 truth_table: list | None = None,
                 input_numbers: list[int] | None = None,
                 output_numbers: list[int] | None = None,
                 stateful_circuit: dict | None = None,
                 stateful_state: dict | None = None):
        super().__init__(id, n_enter=inputs, n_exit=outputs)
        self.name = name or "Módulo"
        self.stateful_circuit = (copy.deepcopy(stateful_circuit)
                                 if isinstance(stateful_circuit, dict) else None)
        if self.stateful_circuit:
            self.input_numbers = self._normalize_port_numbers(input_numbers, inputs)
            self.output_numbers = self._normalize_port_numbers(output_numbers, outputs)
            self.truth_table = []
        else:
            (self.input_numbers, self.output_numbers, self.truth_table,
             _input_order, _output_order) = self.canonicalize_port_order(
                inputs, outputs, truth_table, input_numbers, output_numbers)
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
        node_types = {"AND": AND, "OR": OR, "XOR": XOR, "NOT": NOT,
                      "NAND": NAND, "NOR": NOR, "RETARDO": Delay}
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
                              nested_state)
            elif cls is not None:
                node = cls(int(spec["id"]))
            else:
                raise ValueError(f"Tipo interno de módulo no compatible: {spec.get('type')}")
            if node.can_set_enter() and len(node.enter) != int(spec.get("inputs", len(node.enter))):
                node.set_enter(int(spec["inputs"]))
            node.delay_ms = max(0, int(spec.get("delay_ms", node.delay_ms)))
            if isinstance(saved.get("enter"), list):
                node.enter = ([bool(v) for v in saved["enter"]] +
                              [False] * len(node.enter))[:len(node.enter)]
            if isinstance(saved.get("exit"), list):
                node.exit = ([bool(v) for v in saved["exit"]] +
                             [False] * len(node.exit))[:len(node.exit)]
            self._stateful_nodes[node_id] = node

        for edge in self.stateful_circuit.get("connections", []):
            source_id = str(edge["source"])
            source = self._stateful_nodes[source_id]
            destination = self._stateful_nodes[str(edge["destination"])]
            output_index, input_index = int(edge["output"]), int(edge["input"])
            source.connect_to(output_index, destination, input_index)
            drivers = self._stateful_drivers.setdefault((destination.id, input_index), {})
            drivers[(source_id, output_index)] = bool(
                source.exit[output_index] if output_index < len(source.exit) else False)
        if isinstance(saved_state, dict):
            previous = saved_state.get("inputs", [])
            if isinstance(previous, list):
                self._stateful_previous_inputs = ([bool(v) for v in previous] +
                    [False] * len(self.enter))[:len(self.enter)]
            self._stateful_initialized = bool(saved_state.get("initialized", False))

    def export_stateful_state(self):
        if not self.stateful_circuit:
            return None
        return {
            "initialized": self._stateful_initialized,
            "inputs": list(self._stateful_previous_inputs),
            "nodes": {node_id: {"enter": list(node.enter), "exit": list(node.exit),
                                **({"stateful_state": node.export_stateful_state()}
                                   if isinstance(node, Module) and node.stateful_circuit else {})}
                      for node_id, node in self._stateful_nodes.items()},
        }

    def _run_stateful_circuit(self, board=None):
        from collections import deque

        queue = deque()
        steps = [0]

        def emit(node_id, node, previous):
            for output_index, value in enumerate(node.exit):
                old_value = previous[output_index] if output_index < len(previous) else False
                if bool(value) == bool(old_value):
                    continue
                for destination, input_index in node.connections.get(output_index, []):
                    event = (destination, input_index, bool(value), (node_id, output_index))
                    delay = max(0, int(destination.delay_ms))
                    if delay and board is not None:
                        board.enqueue_action(delay, lambda item=event: delayed_event(item))
                    else:
                        queue.append(event)

        def publish_outputs():
            new_outputs = [False] * len(self.exit)
            current_inputs = [bool(value) for value in self.enter]
            for binding in self.stateful_circuit.get("output_bindings", []):
                output_index = int(binding["output"])
                if not 0 <= output_index < len(new_outputs):
                    continue
                for source in binding.get("sources", []):
                    if "input" in source:
                        input_index = int(source["input"])
                        value = current_inputs[input_index] if 0 <= input_index < len(current_inputs) else False
                    else:
                        node = self._stateful_nodes.get(str(source.get("node")))
                        port = int(source.get("port", -1))
                        value = bool(node.exit[port]) if node and 0 <= port < len(node.exit) else False
                    new_outputs[output_index] |= value
            old_outputs = self.exit.copy()
            self.exit = new_outputs
            for output_index, value in enumerate(self.exit):
                if value == old_outputs[output_index] or board is None:
                    continue
                if self.graphic:
                    self.graphic.update_port_color(output_index, is_input=False)
                for destination, input_index in self.connections.get(output_index, []):
                    board.enqueue_signal(destination, input_index, value,
                                         source=(self, output_index))
            if self.graphic:
                self.graphic.update_all_output_wires()

        def apply_event(event):
            destination, input_index, value, driver = event
            steps[0] += 1
            if steps[0] > 10000 or not 0 <= input_index < len(destination.enter):
                return
            pin = (destination.id, input_index)
            drivers = self._stateful_drivers.setdefault(pin, {})
            drivers[driver] = value
            combined = any(drivers.values())
            if destination.enter[input_index] == combined:
                return
            destination.enter[input_index] = combined
            previous = destination.exit.copy()
            destination.logic()
            emit(str(destination.id), destination, previous)
            publish_outputs()

        def drain():
            while queue and steps[0] < 10000:
                apply_event(queue.popleft())

        def delayed_event(event):
            queue.append(event)
            drain()

        if not self._stateful_initialized:
            for node_id, node in self._stateful_nodes.items():
                previous = node.exit.copy()
                node.logic()
                emit(node_id, node, previous)
                drain()
            self._stateful_initialized = True

        current_inputs = [bool(value) for value in self.enter]
        for binding in self.stateful_circuit.get("input_bindings", []):
            index = int(binding["input"])
            if not 0 <= index < len(current_inputs):
                continue
            value = current_inputs[index]
            if value == self._stateful_previous_inputs[index]:
                continue
            for target in binding.get("targets", []):
                node = self._stateful_nodes.get(str(target["node"]))
                if node is not None:
                    event = (node, int(target["port"]), value, ("module-input", index))
                    delay = max(0, int(node.delay_ms))
                    if delay and board is not None:
                        board.enqueue_action(delay, lambda item=event: delayed_event(item))
                    else:
                        queue.append(event)
        drain()
        self._stateful_previous_inputs = current_inputs
        publish_outputs()

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

    @classmethod
    def canonicalize_port_order(cls, inputs, outputs, truth_table,
                                input_numbers=None, output_numbers=None):
        input_numbers = cls._normalize_port_numbers(input_numbers, inputs)
        output_numbers = cls._normalize_port_numbers(output_numbers, outputs)
        input_order = sorted(range(inputs), key=lambda index: input_numbers[index])
        output_order = sorted(range(outputs), key=lambda index: output_numbers[index])
        rows = cls.normalize_truth_table(inputs, outputs, truth_table)
        for row in rows:
            row["inputs"] = [row["inputs"][index] for index in input_order]
            row["outputs"] = [row["outputs"][index] for index in output_order]
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
                initial_state["inputs"] = [bool(old_values[i]) if i < len(old_values) else False
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
                input_numbers, output_numbers)
            input_order, output_order = _input_order, _output_order
        self.enter = [self.enter[index] for index in input_order]
        self.exit = [self.exit[index] for index in output_order]
        self.input_numbers, self.output_numbers = new_inputs, new_outputs
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

    @staticmethod
    def normalize_truth_table(inputs: int, outputs: int, truth_table: list | None) -> list[dict]:
        """Normalize legacy bit-packed rows and new explicit rows to JSON data."""
        expected = 1 << inputs
        raw_rows = list(truth_table or [])
        normalized = []
        for row_index in range(expected):
            raw = raw_rows[row_index] if row_index < len(raw_rows) else None
            input_values = [bool(row_index & (1 << i)) for i in range(inputs)]
            if isinstance(raw, dict):
                input_values = [bool(value) for value in raw.get("inputs", input_values)][:inputs]
                input_values.extend([False] * (inputs - len(input_values)))
                raw_outputs = raw.get("outputs", [])
                if isinstance(raw_outputs, int):
                    output_values = [bool(raw_outputs & (1 << i)) for i in range(outputs)]
                else:
                    output_values = [bool(value) for value in raw_outputs][:outputs]
                output_values.extend([False] * (outputs - len(output_values)))
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
        return self._truth_rows.get(tuple(bool(value) for value in self.enter),
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
