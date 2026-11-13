"""DaLogic-8 instruction encoding and machine state."""

import re

from resources import translate_text as tr


# The list index is the high byte of each instruction.
INSTRUCTIONS = (
    ("NOP", None, "No hace nada"), ("LDI", "value", "Carga un literal en A"),
    ("LDA", "address", "Carga RAM[operando] en A"), ("STA", "address", "Guarda A en RAM[operando]"),
    ("ADD", "address", "Suma RAM[operando] a A"), ("SUB", "address", "Resta RAM[operando] de A"),
    ("AND", "address", "AND de A y RAM[operando]"), ("OR", "address", "OR de A y RAM[operando]"),
    ("XOR", "address", "XOR de A y RAM[operando]"), ("JMP", "address", "Salta a una dirección"),
    ("JZ", "address", "Salta si A vale cero"), ("JNZ", "address", "Salta si A es distinto de cero"),
    ("IN", None, "Lee el puerto IN en A"), ("OUT", "port", "Envía A al puerto indicado"),
    ("HLT", None, "Detiene la CPU hasta RESET"),
)
OPCODES = {instruction[0]: opcode for opcode, instruction in enumerate(INSTRUCTIONS)}
PORTS = ("X", "Y", "R", "G", "B", "PLOT")
PROGRAM_SIZE = 256
WORD_BITS = 16
LABEL = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _error(line, message, **values):
    return ValueError(tr("Línea {v0} · {v1}", v0=line, v1=tr(message, **values)))


def _program_lines(source):
    for number, line in enumerate(source.splitlines(), 1):
        code = re.split(r"[;#]", line, maxsplit=1)[0].strip()
        if code:
            yield number, code


def assemble(source):
    labels, program = {}, []
    for number, code in _program_lines(source):
        label, sep, body = code.partition(":")
        if sep:
            name = label.strip().upper()
            if not LABEL.fullmatch(name) or name in labels or len(program) == PROGRAM_SIZE:
                raise _error(number, "Etiqueta inválida o repetida: {v0}", v0=name)
            labels[name] = len(program)
            code = body.strip()
        if code:
            if len(program) == PROGRAM_SIZE:
                raise _error(number, "El programa supera las 256 instrucciones.")
            program.append((number, code.upper().split()))

    words = []
    for number, (mnemonic, *operands) in program:
        if mnemonic not in OPCODES:
            raise _error(number, "Instrucción desconocida: {v0}", v0=mnemonic)
        opcode = OPCODES[mnemonic]
        kind = INSTRUCTIONS[opcode][1]
        if len(operands) != int(kind is not None):
            raise _error(number, "Cantidad de operandos incorrecta para {v0}.", v0=mnemonic)
        operand = 0
        if kind:
            token = operands[0]
            if kind == "address" and token in labels:
                operand = labels[token]
            elif kind == "port" and token in PORTS:
                operand = PORTS.index(token)
            else:
                try:
                    operand = int(token, 0 if token.startswith(("0X", "0B")) else 10)
                except ValueError:
                    raise _error(number, "Operando desconocido: {v0}", v0=token) from None
            limit = len(PORTS) if kind == "port" else PROGRAM_SIZE
            if not 0 <= operand < limit:
                raise _error(number, "Operando fuera de rango: {v0}", v0=token)
        words.append((opcode << 8) | operand)
    return words


def read_binary(source):
    words = []
    for number, code in _program_lines(source):
        bits = "".join(code.split()).removeprefix("0b").removeprefix("0B").replace("_", "")
        if len(bits) != WORD_BITS or any(bit not in "01" for bit in bits):
            raise _error(number, "Escribe exactamente 16 bits por instrucción.")
        if len(words) == PROGRAM_SIZE:
            raise _error(number, "El programa supera las 256 instrucciones.")
        words.append(int(bits, 2))
    return words


def format_binary(words):
    return "\n".join(f"{word >> 8:08b} {word & 255:08b}" for word in words)


def decode(word):
    opcode, operand = word >> 8, word & 255
    if not 0 <= opcode < len(INSTRUCTIONS):
        raise ValueError(tr("Código de operación desconocido."))
    mnemonic, kind, _ = INSTRUCTIONS[opcode]
    if (kind is None and operand) or (kind == "port" and operand >= len(PORTS)):
        raise ValueError(tr("Operando inválido para {v0}.", v0=mnemonic))
    return mnemonic, operand


class Processor:
    def __init__(self):
        self.reset()

    def reset(self):
        self.pc = self.a = 0
        self.ram = bytearray(PROGRAM_SIZE)
        self.video = [0] * 5
        self.pending_plot = self.plot = self.halted = False
        self.fault = ""

    def step(self, word, input_value):
        self.plot = False
        if self.halted:
            return
        try:
            if type(word) not in (int, bool):
                raise ValueError(tr("Conecta la ROM de programa a INST."))
            mnemonic, operand = decode(word)
            if mnemonic == "IN" and type(input_value) not in (int, bool):
                raise ValueError(tr("IN necesita un bus de 8 bits definido."))
        except ValueError as error:
            self.fault, self.halted = str(error), True
            return
        self.pc = (self.pc + 1) & 255
        data = self.ram[operand]
        if mnemonic == "LDI":
            self.a = operand
        elif mnemonic == "LDA":
            self.a = data
        elif mnemonic == "STA":
            self.ram[operand] = self.a
        elif mnemonic == "ADD":
            self.a = (self.a + data) & 255
        elif mnemonic == "SUB":
            self.a = (self.a - data) & 255
        elif mnemonic == "AND":
            self.a &= data
        elif mnemonic == "OR":
            self.a |= data
        elif mnemonic == "XOR":
            self.a ^= data
        elif mnemonic == "JMP" or (mnemonic == "JZ" and not self.a) or (mnemonic == "JNZ" and self.a):
            self.pc = operand
        elif mnemonic == "IN":
            self.a = int(input_value) & 255
        elif mnemonic == "OUT":
            if operand == len(self.video):
                self.pending_plot = True
            else:
                self.video[operand] = self.a
        elif mnemonic == "HLT":
            self.halted = True

    def finish_cycle(self):
        self.plot, self.pending_plot = self.pending_plot, False

    def snapshot(self):
        return dict(pc=self.pc, a=self.a, ram=self.ram.hex(), video=list(self.video),
                    plot=self.plot, pending_plot=self.pending_plot, halted=self.halted, fault=self.fault)

    def restore(self, state):
        def is_byte(value):
            return type(value) is int and 0 <= value <= 255

        if not isinstance(state, dict):
            raise ValueError(tr("Estado de CPU no válido."))
        pc, a = state.get("pc"), state.get("a")
        ram, video = state.get("ram"), state.get("video")
        flags = tuple(state.get(key) for key in ("plot", "pending_plot", "halted"))
        fault = state.get("fault")
        if (not is_byte(pc) or not is_byte(a) or not isinstance(ram, str) or len(ram) != PROGRAM_SIZE * 2
                or not isinstance(video, list) or len(video) != 5 or not all(map(is_byte, video))
                or any(type(flag) is not bool for flag in flags) or not isinstance(fault, str)):
            raise ValueError(tr("Estado de CPU no válido."))
        memory = bytearray.fromhex(ram)
        if len(memory) != PROGRAM_SIZE:
            raise ValueError(tr("Estado de CPU no válido."))
        self.pc, self.a, self.ram, self.video = pc, a, memory, video.copy()
        self.plot, self.pending_plot, self.halted = flags
        self.fault = fault
