"""
widgets.py  –  Lógica de las puertas y el interruptor.
"""


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
                 output_numbers: list[int] | None = None):
        super().__init__(id, n_enter=inputs, n_exit=outputs)
        self.name = name or "Módulo"
        (self.input_numbers, self.output_numbers, self.truth_table,
         _input_order, _output_order) = self.canonicalize_port_order(
            inputs, outputs, truth_table, input_numbers, output_numbers)
        self._truth_rows = {tuple(row["inputs"]): row for row in self.truth_table}
        self.response_ms = 0
        self._pending_response = 0
        self.add_enter = False
        self.add_exit = False

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
        (new_inputs, new_outputs, rows,
         input_order, output_order) = self.canonicalize_port_order(
            len(self.enter), len(self.exit), self.truth_table,
            input_numbers, output_numbers)
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
        row = self.truth_row()
        self.response_ms = row["time_ms"]
        self.exit = row["outputs"].copy()

    def compute_and_propagate(self, board):
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
