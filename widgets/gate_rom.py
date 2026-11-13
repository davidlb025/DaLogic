"""Build a small, editable memory image using only combinational gates."""

from resources import translate_text as tr


def gate_rom_project(words, address_bits, width):
    if not 1 <= address_bits <= 4 or not 1 <= width <= 16:
        raise ValueError(tr("La ROM cableada admite 1–4 bits de dirección y 1–16 bits de datos."))
    capacity = 1 << address_bits
    if len(words) > capacity or any(type(word) is not int or not 0 <= word < 1 << width for word in words):
        raise ValueError(tr("Programa no válido."))
    components, wires, annotations, positions = [], [], [], {}

    def component(kind, column, caption=None):
        ident = len(components)
        row = positions.get(column, 0)
        positions[column] = row + 1
        x, y = 210 * column, 112 * row
        components.append(dict(type=kind, id=ident, position=[x, y]))
        if caption is not None:
            annotations.append(dict(kind="text", text=caption, position=[x - 24, y - 50], font_size=13))
        return ident

    def connect(source, destination, pin):
        wires.append(dict(
            src=dict(kind="port", widget=source, side="out", index=0),
            dst=dict(kind="port", widget=destination, side="in", index=pin)))

    def gate(kind, column, *sources):
        ident = component(kind, column)
        for pin, source in enumerate(sources):
            connect(source, ident, pin)
        return ident

    switches = [component("INTERRUPTOR", 0, f"A{bit}") for bit in range(address_bits)]
    inverted = [gate("NOT", 1, source) for source in switches]
    active_rows = []
    for address in range(capacity):
        active_rows.append([switches[bit] if address >> bit & 1 else inverted[bit]
                            for bit in range(address_bits)])
    zero = None
    decoded = {}

    def combine(kind, operands, column):
        while len(operands) > 1:
            operands = [gate(kind, column, *operands[index:index + 2])
                        if index + 1 < len(operands) else operands[index]
                        for index in range(0, len(operands), 2)]
            column += 1
        return operands[0]

    for bit in range(width):
        branches = []
        for address, word in enumerate(words):
            if word >> bit & 1:
                if address not in decoded:
                    decoded[address] = combine("AND", active_rows[address], 2)
                branches.append(decoded[address])
        if branches:
            output = combine("OR", branches, 4)
        else:
            if zero is None:
                zero = gate("AND", 2, switches[0], inverted[0])
            output = zero
        connect(output, component("BOMBILLA", 8, f"D{bit}"), 0)

    return dict(format="DaLogic", version=1, name=tr("ROM de puertas"), components=components,
                wires=wires, visuals=annotations)
