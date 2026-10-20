from resources import translate_text as tr
"""Native components. Ports are listed in their visible order, bit 0 first."""
from .widgets import Widget, BusInput, BusLamp, LOGIC_X, LOGIC_Z


SEGMENTS = (0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07,
            0x7F, 0x6F, 0x77, 0x7C, 0x39, 0x5E, 0x79, 0x71)


class Native(Widget):
    title = "Componente"
    sequential = False
    configurable_width = True
    configurable_address = False
    configurable_channels = False

    def __init__(self, id, width=8, address_bits=4, channels=4):
        self.width = max(1, min(32, int(width)))
        self.address_bits = max(1, min(12, int(address_bits)))
        self.channels = int(channels) if int(channels) in (2, 4, 8, 16) else 4
        self.value = 0
        self.memory = [0] * (1 << self.address_bits) if self.configurable_address else []
        self.previous_clock = False
        ins, outs = self.layout()
        super().__init__(id, len(ins), len(outs))
        self.gate_stages = 1
        self.add_enter = self.add_exit = False
        self.input_labels = [label for label, _width in ins]
        self.output_labels = [label for label, _width in outs]
        self.input_widths = [width for _label, width in ins]
        self.output_widths = [width for _label, width in outs]

    @property
    def mask(self):
        return (1 << self.width) - 1

    def layout(self):
        return [], []

    def known(self, *indices):
        return all(self.enter[i] not in (LOGIC_X, LOGIC_Z) for i in indices)

    def rising(self, index):
        clock = self.enter[index]
        if getattr(self, '_prime_clock', False):
            self.previous_clock = clock
            return False
        rising = clock is not False and clock == 1 and self.previous_clock == 0
        self.previous_clock = clock
        return rising

    def export_native(self):
        return {"bus_width": self.width, "address_bits": self.address_bits,
                "channels": self.channels, "native_value": self.value,
                "memory": list(self.memory) if self.configurable_address else [],
                "previous_clock": self.previous_clock}

    def restore_native(self, data):
        value = data.get("native_value", 0)
        if value not in (LOGIC_X, LOGIC_Z) and type(value) not in (int, bool):
            raise ValueError(tr("Estado interno no válido"))
        # High impedance describes a net, not the contents of a register.
        self.value = LOGIC_X if value in (LOGIC_X, LOGIC_Z) else int(value) & self.mask
        clock = data.get("previous_clock", False)
        if clock not in (False, True, LOGIC_X, LOGIC_Z):
            raise ValueError(tr("Estado de reloj no válido"))
        self.previous_clock = clock
        if self.configurable_address:
            values = data.get("memory", [])
            if not isinstance(values, list) or len(values) > len(self.memory):
                raise ValueError(tr("Contenido de memoria no válido"))
            if any(v != LOGIC_X and type(v) not in (int, bool) for v in values):
                raise ValueError(tr("Contenido de memoria no válido"))
            self.memory = [LOGIC_X if v == LOGIC_X else int(v) & self.mask for v in values]
            self.memory += [0] * ((1 << self.address_bits) - len(self.memory))


class Adder(Native):
    title = "Sumador"

    def layout(self):
        return [("A", self.width), ("B", self.width), ("Cin", 1)], [("S", self.width), ("Cout", 1)]

    def logic(self):
        if not self.known(0, 1, 2):
            self.exit[:] = [LOGIC_X, LOGIC_X]
            return
        total = int(self.enter[0]) + int(self.enter[1]) + int(self.enter[2])
        self.exit[:] = [total & self.mask, total > self.mask]


class AddSubtract(Adder):
    title = "Sumador / restador"

    def layout(self):
        return [("A", self.width), ("B", self.width), ("SUB", 1)], [("R", self.width), ("C/B", 1)]

    def logic(self):
        if not self.known(0, 1, 2):
            self.exit[:] = [LOGIC_X, LOGIC_X]
            return
        a, b, sub = map(int, self.enter)
        total = a - b if sub else a + b
        self.exit[:] = [total & self.mask, a < b if sub else total > self.mask]


class Comparator(Native):
    title = "Comparador"

    def layout(self):
        return [("A", self.width), ("B", self.width)], [("=", 1), (">", 1), ("<", 1)]

    def logic(self):
        a, b = self.enter
        self.exit[:] = [a == b, a > b, a < b] if self.known(0, 1) else [LOGIC_X] * 3


class ALU(Native):
    title = "ALU"

    def layout(self):
        return [("A", self.width), ("B", self.width), ("OP", 3)], [("R", self.width), ("C/B", 1), ("Z", 1)]

    def logic(self):
        if not self.known(0, 1, 2):
            self.exit[:] = [LOGIC_X] * 3
            return
        a, b, op = map(int, self.enter)
        results = (a + b, a - b, a & b, a | b, a ^ b, a << 1, a >> 1, (~a) & self.mask)
        result = results[op & 7]
        carry = a < b if op == 1 else bool(a & 1) if op == 6 else result > self.mask
        self.exit[:] = [result & self.mask, carry, (result & self.mask) == 0]


class Multiplexer(Native):
    title = "Multiplexor"
    configurable_channels = True

    def layout(self):
        return ([(f"D{i}", self.width) for i in range(self.channels)] +
                [("SEL", self.channels.bit_length() - 1)]), [("Y", self.width)]

    def logic(self):
        self.exit[0] = self.enter[int(self.enter[-1]) % self.channels] if self.known(len(self.enter) - 1) else LOGIC_X


class Demultiplexer(Native):
    title = "Demultiplexor"
    configurable_channels = True

    def layout(self):
        return [("D", self.width), ("SEL", self.channels.bit_length() - 1)], [(f"Y{i}", self.width) for i in range(self.channels)]

    def logic(self):
        self.exit[:] = [0] * self.channels if self.known(1) else [LOGIC_X] * self.channels
        if self.known(1):
            self.exit[int(self.enter[1]) % self.channels] = self.enter[0]


class Decoder(Native):
    title = "Decodificador"
    configurable_width = False
    configurable_channels = True

    def layout(self):
        return [("A", self.channels.bit_length() - 1), ("EN", 1)], [(f"Y{i}", 1) for i in range(self.channels)]

    def logic(self):
        if self.enter[1] == 0:
            self.exit[:] = [False] * self.channels
        elif self.known(0, 1):
            self.exit[:] = [i == int(self.enter[0]) for i in range(self.channels)]
        else:
            self.exit[:] = [LOGIC_X] * self.channels


class BCDDecoder(Native):
    title = "BCD → 7 segmentos"
    configurable_width = False

    def layout(self):
        return [("BCD", 4)], [(label, 1) for label in "abcdefg"]

    def logic(self):
        if not self.known(0):
            self.exit[:] = [LOGIC_X] * 7
        else:
            value = int(self.enter[0])
            mask = SEGMENTS[value] if 0 <= value < 10 else 0
            self.exit[:] = [bool(mask & (1 << bit)) for bit in range(7)]


class RAM(Native):
    title = "RAM"
    sequential = True
    configurable_address = True

    def layout(self):
        return [("ADDR", self.address_bits), ("D", self.width), ("WE", 1), ("CLK", 1)], [("Q", self.width)]

    def logic(self):
        edge = self.rising(3)
        if edge and self.enter[2] != 0:
            if self.known(0):
                address = int(self.enter[0]) & (len(self.memory) - 1)
                self.memory[address] = int(self.enter[1]) & self.mask if self.known(1, 2) else LOGIC_X
            else:
                self.memory[:] = [LOGIC_X] * len(self.memory)
        self.exit[0] = self.memory[int(self.enter[0]) & (len(self.memory) - 1)] if self.known(0) else LOGIC_X


class ROM(RAM):
    title = "ROM"
    sequential = False

    def layout(self):
        return [("ADDR", self.address_bits)], [("Q", self.width)]

    def logic(self):
        self.exit[0] = self.memory[int(self.enter[0]) & (len(self.memory) - 1)] if self.known(0) else LOGIC_X


class Counter(Native):
    title = "Contador"
    sequential = True

    def layout(self):
        return [("CLK", 1), ("EN", 1), ("DOWN", 1), ("LOAD", 1), ("D", self.width), ("RST", 1)], [("Q", self.width)]

    def logic(self):
        edge = self.rising(0)
        if self.enter[5] == 1:
            self.value = 0
        elif self.enter[5] in (LOGIC_X, LOGIC_Z):
            self.value = LOGIC_X
        elif edge:
            if not self.known(3):
                self.value = LOGIC_X
            elif self.enter[3]:
                self.value = int(self.enter[4]) & self.mask if self.known(4) else LOGIC_X
            elif not self.known(1):
                self.value = LOGIC_X
            elif self.enter[1]:
                self.value = ((int(self.value) + (-1 if self.enter[2] else 1)) & self.mask
                              if self.known(2) and self.value != LOGIC_X else LOGIC_X)
        self.exit[0] = self.value


class ShiftRegister(Native):
    title = "Registro de desplazamiento"
    sequential = True

    def layout(self):
        return [("CLK", 1), ("EN", 1), ("SER", 1), ("RST", 1)], [("Q", self.width), ("SERout", 1)]

    def logic(self):
        edge = self.rising(0)
        if self.enter[3] == 1:
            self.value = 0
        elif not self.known(3):
            self.value = LOGIC_X
        elif edge and self.enter[1] != 0:
            self.value = (((int(self.value) << 1) | int(self.enter[2])) & self.mask
                          if self.known(1, 2) and self.value != LOGIC_X else LOGIC_X)
        self.exit[:] = [self.value, LOGIC_X if self.value == LOGIC_X else bool(self.value & (1 << (self.width - 1)))]


class DIPSwitch(BusInput):
    title = "DIP switch"


class HexKeyboard(BusInput):
    title = "Teclado hexadecimal"

    def __init__(self, id, width=4, value=0):
        super().__init__(id, 4, value)

    def set_bus(self, width, value=None):
        return super().set_bus(4, value)

    set_bus_width = set_bus


class Constant(Native):
    title = "Constante"

    def layout(self):
        return [], [("Q", self.width)]

    def logic(self):
        self.exit[0] = self.value


class PullUp(Constant):
    title = "Pull-up"
    weak_driver = True
    configurable_width = False

    def __init__(self, id, **kwargs):
        super().__init__(id, width=1)
        self.value = 1

    def restore_native(self, data):
        self.value = 1


class PullDown(PullUp):
    title = "Pull-down"

    def __init__(self, id, **kwargs):
        super().__init__(id)
        self.value = 0

    def restore_native(self, data):
        self.value = 0


class LEDBar(BusLamp):
    title = "Barra de LED"


class NumericDisplay(BusLamp):
    title = "Display numérico"


class LEDMatrix(BusLamp):
    title = "Matriz de LED"

    def __init__(self, id, width=8):
        super().__init__(id, width)
        self._infer_dimensions()

    def _infer_dimensions(self):
        self.rows = next((n for n in range(min(8, int(self.width ** 0.5)), 1, -1)
                          if self.width % n == 0), 1)
        self.columns = self.width // self.rows

    def set_bus_width(self, width, value=None):
        if self.graphic:
            self.graphic.prepareGeometryChange()
        super().set_bus_width(width, value)
        self._infer_dimensions()
        if self.graphic:
            self.graphic._reposition_ports()
            self.graphic.update()

    def set_dimensions(self, rows, columns):
        rows, columns = int(rows), int(columns)
        if not 1 <= rows <= 32 or not 1 <= columns <= 32 or not 2 <= rows * columns <= 32:
            raise ValueError(tr('La matriz debe tener entre 2 y 32 LED en total.'))
        if self.graphic:
            self.graphic.prepareGeometryChange()
        self.rows, self.columns = rows, columns
        self.width = rows * columns
        self.input_widths = [self.width]
        if isinstance(self.enter[0], (bool, int)):
            self.enter[0] = int(self.enter[0]) & ((1 << self.width) - 1)
        if self.graphic:
            self.graphic.rebuild_ports()
            self.graphic.update()

    def pixel(self, row, column):
        if not 0 <= row < self.rows or not 0 <= column < self.columns:
            raise IndexError('LED fuera de la matriz')
        value = self.enter[0]
        return value if value in (LOGIC_X, LOGIC_Z) else bool(int(value) & (1 << (row * self.columns + column)))


class RGBLED(Native):
    title = "LED RGB"
    configurable_width = False

    def __init__(self, id, **kwargs):
        super().__init__(id, width=1)

    def layout(self):
        return [(label, 8) for label in ("R", "G", "B")], []

    def logic(self):
        pass


class TrafficLight(Native):
    title = "Semáforo"
    configurable_width = False

    def __init__(self, id, **kwargs):
        super().__init__(id, width=1)

    def layout(self):
        return [(label, 1) for label in ("ROJO", "AMARILLO", "VERDE")], []

    def logic(self):
        pass


class Buzzer(Native):
    title = "Indicador sonoro"
    configurable_width = False

    def __init__(self, id, **kwargs):
        super().__init__(id, width=1)
        self.sound_enabled = False
        self.was_active = False

    def layout(self):
        return [("EN", 1)], []

    def logic(self):
        self.value = self.enter[0]

    def compute_and_propagate(self, board):
        self.logic()
        active = self.enter[0] == 1
        if active and not self.was_active and self.sound_enabled:
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        self.was_active = active
        if self.graphic:
            self.graphic.update_port_color(0, True)

    def export_native(self):
        return {**super().export_native(), 'sound_enabled': self.sound_enabled,
                'was_active': self.was_active}

    def restore_native(self, data):
        super().restore_native(data)
        self.sound_enabled = bool(data.get('sound_enabled', False))
        self.was_active = bool(data.get('was_active', False))


COMPONENTS = {
    "SUMADOR": Adder, "SUMA_RESTA": AddSubtract, "COMPARADOR": Comparator,
    "ALU": ALU, "MUX": Multiplexer, "DEMUX": Demultiplexer,
    "DECODIFICADOR": Decoder, "BCD7": BCDDecoder, "RAM": RAM, "ROM": ROM,
    "CONTADOR": Counter, "REG_DESPLAZAMIENTO": ShiftRegister,
    "DIP": DIPSwitch, "TECLADO_HEX": HexKeyboard, "CONSTANTE": Constant,
    "PULL_UP": PullUp, "PULL_DOWN": PullDown, "LED_BAR": LEDBar,
    "DISPLAY_NUMERICO": NumericDisplay, "LED_MATRIX": LEDMatrix,
    "LED_RGB": RGBLED, "SEMAFORO": TrafficLight, "SONIDO": Buzzer,
}
