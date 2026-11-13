"""User-defined instruction encodings for circuit memories."""

import re
from dataclasses import dataclass

from resources import translate_text as tr


IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
MAX_SOURCE = 262144
MAX_ISA = 65536


@dataclass(frozen=True)
class Encoding:
    mnemonic: str
    fields: tuple
    words: tuple


def source_lines(source):
    for line, raw in enumerate(source.splitlines(), 1):
        code = re.split(r"[;#]", raw, maxsplit=1)[0].strip()
        if code:
            yield line, code


def error(line, message, **values):
    return ValueError(tr("Línea {v0} · {v1}", v0=line, v1=tr(message, **values)))


def tokens(text):
    return text.replace(",", " ").split()


def literal(token):
    base = 0 if token.lstrip("+-").lower().startswith(("0x", "0b")) else 10
    return int(token, base)


def read_isa(source, width):
    if len(source) > MAX_ISA:
        raise ValueError(tr("La definición de instrucciones supera el tamaño admitido."))
    encodings = {}
    for line, text in source_lines(source):
        form, equals, pattern = text.partition("=")
        parts = tokens(form)
        if not equals or not parts or not IDENTIFIER.fullmatch(parts[0]):
            raise error(line, "Escribe una instrucción como NOMBRE a = 01aaaa.")
        mnemonic = parts[0].upper()
        fields = tuple(field.lower() for field in parts[1:])
        if len(set(fields)) != len(fields) or any(not re.fullmatch("[a-z]", field) for field in fields):
            raise error(line, "Cada operando debe ser una letra distinta.")
        words = tuple("".join(word.lower().split()).replace("_", "") for word in pattern.split("|"))
        flat = "".join(words)
        if (any(len(word) != width for word in words) or
                set(flat) - set("01") != set(fields)):
            raise error(line, "Cada palabra debe tener {v0} bits e incluir solo 0, 1 y los operandos definidos.",
                        v0=width)
        key = mnemonic, len(fields)
        if key in encodings:
            raise error(line, "Ya existe {v0} con esa cantidad de operandos.", v0=mnemonic)
        encodings[key] = Encoding(mnemonic, fields, words)
    return encodings


def _symbol(line, name, address, symbols):
    key = name.strip().upper()
    if not IDENTIFIER.fullmatch(key) or key in symbols:
        raise error(line, "Etiqueta inválida o repetida: {v0}", v0=key)
    symbols[key] = address


def _value(line, token, bits, symbols):
    try:
        value = symbols[token.upper()] if token.upper() in symbols else literal(token)
    except ValueError:
        raise error(line, "Operando desconocido: {v0}", v0=token) from None
    if not -(1 << (bits - 1)) <= value < 1 << bits:
        raise error(line, "Operando fuera de rango: {v0}", v0=token)
    return format(value & ((1 << bits) - 1), f"0{bits}b")


def assemble_custom(source, isa, width, capacity):
    if len(source) > MAX_SOURCE:
        raise ValueError(tr("El programa supera el tamaño de texto admitido."))
    encodings = read_isa(isa, width)
    symbols, plan = {}, []
    address = 0
    for line, text in source_lines(source):
        label, colon, instruction = text.partition(":")
        if colon:
            _symbol(line, label, address, symbols)
            text = instruction.strip()
        parts = tokens(text)
        if not parts:
            continue
        mnemonic, *operands = parts
        mnemonic = mnemonic.upper()
        if mnemonic == ".EQU" and len(operands) == 2:
            try:
                number = literal(operands[1])
            except ValueError:
                raise error(line, "La directiva .equ necesita un valor numérico.") from None
            _symbol(line, operands[0], number, symbols)
            continue
        if mnemonic == ".WORD" and operands:
            encoding = None
            count = len(operands)
        else:
            encoding = encodings.get((mnemonic, len(operands)))
            if encoding is None:
                raise error(line, "No hay una definición de {v0} para {v1} operandos.", v0=mnemonic, v1=len(operands))
            count = len(encoding.words)
        address += count
        if address > capacity:
            raise error(line, "El programa no cabe en {v0} palabras.", v0=capacity)
        plan.append((line, encoding, operands))

    image = []
    for line, encoding, operands in plan:
        if encoding is None:
            image.extend(int(_value(line, operand, width, symbols), 2) for operand in operands)
            continue
        pattern = "".join(encoding.words)
        fields = {field: iter(_value(line, operand, pattern.count(field), symbols))
                  for field, operand in zip(encoding.fields, operands)}
        for word in encoding.words:
            image.append(int("".join(next(fields[bit]) if bit in fields else bit for bit in word), 2))
    return image


def read_words(source, width, capacity):
    if len(source) > MAX_SOURCE:
        raise ValueError(tr("El programa supera el tamaño de texto admitido."))
    image = []
    for line, text in source_lines(source):
        bits = "".join(text.lower().split()).removeprefix("0b").replace("_", "")
        if len(bits) != width or set(bits) - set("01"):
            raise error(line, "Escribe exactamente {v0} bits por palabra.", v0=width)
        if len(image) == capacity:
            raise error(line, "El programa no cabe en {v0} palabras.", v0=capacity)
        image.append(int(bits, 2))
    return image
