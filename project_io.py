"""Project/module persistence and captured probe data export (CSV/VCD)."""

from __future__ import annotations

from resources import translate_text as tr

import csv
import json
import math
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsTextItem

from widgets.graphics import Port, Wire, Junction, WireEndpoint
from widgets.native import Native, LEDMatrix
from widgets.widgets import Module, Switch, Clock, Bulb, Display, BusInput
from widgets.visual import VisualItem


FORMAT_VERSION = 1


def write_json_atomic(path, data):
    """Replace a JSON file only after its full contents have reached disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def rename_library_module(path, new_name, library):
    """Rename the file and its displayed name without overwriting another module."""
    import re
    source, library = Path(path).resolve(), Path(library).resolve()
    if not source.is_relative_to(library) or source.suffix.lower() != '.dmodule':
        raise ValueError(tr("El módulo debe estar dentro de la Biblioteca."))
    name = str(new_name).strip()
    if (not name or len(name) > 120 or name.endswith(('.', ' ')) or
            re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or
            re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name, re.I)):
        raise ValueError(tr("Introduce un nombre válido de hasta 120 caracteres, sin caracteres de ruta ni nombres reservados."))
    data = json.loads(source.read_text(encoding='utf-8'))
    if not supported_dmodule(data):
        raise ValueError(tr("El archivo no es un módulo DaLogic válido."))
    destination = source.with_name(name + '.dmodule')
    if not destination.resolve().is_relative_to(library):
        raise ValueError(tr("El módulo debe estar dentro de la Biblioteca."))
    data['name'] = name
    if destination == source:
        write_json_atomic(source, data)
        if destination.name != source.name:
            source.rename(destination)
        return destination, data
    # Exclusive creation prevents replacing another file, including a concurrent rename.
    with destination.open('x', encoding='utf-8'):
        pass
    try:
        write_json_atomic(destination, data)
        source.unlink()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination, data


def prepare_project(data, component_factory):
    """Validate and construct detached items before replacing the open circuit."""
    if (not isinstance(data, dict) or data.get("format") != "DaLogic"
            or data.get("version") not in (1, "1") or isinstance(data.get("version"), bool)):
        raise ValueError(tr("No es un proyecto DaLogic compatible."))
    collections = ("components", "visuals", "junctions", "endpoints", "sections", "wires")
    for name in collections:
        values = data.get(name, [])
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError(tr('La colección {v0} no es válida.', v0=name))
    if "components" not in data:
        raise ValueError(tr("El proyecto no contiene componentes válidos."))
    if not isinstance(data.get("name", ""), str):
        raise ValueError(tr("Nombre de proyecto no válido."))

    def position(value):
        if (not isinstance(value, (list, tuple)) or len(value) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
            raise ValueError(tr("Posición de elemento no válida."))

    components = {}
    for item in data["components"]:
        widget_id = item.get("id")
        if type(widget_id) is not int or widget_id < 0 or widget_id in components:
            raise ValueError(tr("Los identificadores de componentes deben ser enteros únicos."))
        position(item.get("position", [0, 0]))
        int(item.get("rotation", 0))
        if item.get("truth_table_number") is not None:
            int(item["truth_table_number"])
        if item.get("type") == "MODULO":
            if any(type(item.get(key, 1)) is not int or not minimum <= item.get(key, 1) <= 99
                   for key, minimum in (("inputs", 0), ("outputs", 1))):
                raise ValueError(tr("Cantidad de puertos de módulo no válida."))
            definition = {**item, "format": "DaLogic module"}
            if item.get("stateful_circuit"):
                definition["version"] = 1.3 if item["stateful_circuit"].get("version", 1) >= 2 else 1.1
                definition.pop("truth_table", None)
            else:
                definition["version"] = 1.2 if "input_widths" in item or "output_widths" in item else 1
            if not supported_dmodule(definition):
                raise ValueError(tr("El proyecto contiene un CI con una definición no válida."))
        components[widget_id] = component_factory(item.get("type"), item, widget_id)

    nodes = {}
    for kind in ("junctions", "endpoints"):
        ids = set()
        for item in data.get(kind, []):
            node_id = item.get("id")
            if not isinstance(node_id, str) or not node_id or node_id in ids:
                raise ValueError(tr("Identificador de nexo o extremo no válido."))
            ids.add(node_id)
            position(item.get("position"))
            if kind == "junctions":
                int(item.get("bridge_mode", 0))
        nodes["junction" if kind == "junctions" else "endpoint"] = ids

    def endpoint(ref):
        if not isinstance(ref, dict):
            raise ValueError(tr("Extremo de cable no válido."))
        kind = ref.get("kind")
        if kind in nodes:
            if ref.get("id") not in nodes[kind]:
                raise ValueError(tr("El cable referencia un nexo o extremo inexistente."))
        elif kind == "port":
            widget_id, index, side = ref.get("widget"), ref.get("index"), ref.get("side")
            if type(widget_id) is not int or widget_id not in components or side not in ("in", "out"):
                raise ValueError(tr("El cable referencia un componente inexistente o un lado inválido."))
            widget, _graphic = components[widget_id]
            count = len(widget.enter if side == "in" else widget.exit)
            if type(index) is not int or not 0 <= index < count:
                raise ValueError(tr("El cable referencia un puerto inexistente."))
        else:
            raise ValueError(tr("Tipo de extremo de cable desconocido."))

    for item in data.get("wires", []):
        endpoint(item.get("src"))
        endpoint(item.get("dst"))
        if (not isinstance(item.get("midpoints", []), list) or
                not isinstance(item.get("midpoint_bridges", []), list)):
            raise ValueError(tr("Puntos intermedios de cable no válidos."))
        for value in item.get("midpoints", []):
            position(value)
        for value in item.get("midpoint_bridges", []):
            int(value)
        if item.get("color") is not None:
            from PySide6.QtGui import QColor
            if not isinstance(item["color"], str) or not QColor(item["color"]).isValid():
                raise ValueError(tr("Color de cable inválido."))
    for item in data.get("sections", []):
        position(item.get("position"))
        if "text" not in item:
            raise ValueError(tr("Sección sin texto."))
    visuals = []
    for item in data.get("visuals", []):
        position(item.get("position", [0, 0]))
        visuals.append(VisualItem.from_data(item))
    names = [item.text.strip().casefold() for item in visuals if item.kind == "plane"]
    if any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError(tr("Los planos deben tener nombres únicos y no vacíos."))
    return components, visuals


def point(point: QPointF) -> list[float]:
    return [round(point.x(), 3), round(point.y(), 3)]


def endpoint_ref(endpoint, junction_ids, endpoint_ids):
    if isinstance(endpoint, Port):
        return {"kind": "port", "widget": endpoint.graphic.widg.id,
                "side": "in" if endpoint.is_input else "out", "index": endpoint.port_index}
    if isinstance(endpoint, Junction):
        return {"kind": "junction", "id": junction_ids[endpoint]}
    if isinstance(endpoint, WireEndpoint):
        return {"kind": "endpoint", "id": endpoint_ids[endpoint]}
    return None


def dump_project(window) -> dict:
    scene = window.ui.graphicsView.scene
    items = scene.items()
    junctions = [item for item in items if isinstance(item, Junction)]
    endpoints = [item for item in items if isinstance(item, WireEndpoint)]
    junction_ids = {item: f"j{index}" for index, item in enumerate(junctions)}
    endpoint_ids = {item: f"e{index}" for index, item in enumerate(endpoints)}

    components = []
    for widget_id, graphic in window.all_graphics.items():
        widget = graphic.widg
        entry = {
            "id": widget_id,
            "type": window.type_for_widget(widget),
            "position": point(graphic.pos()),
            "rotation": int(getattr(graphic, "rotation_degrees", 0)),
            "mirrored": bool(getattr(graphic, "mirrored", False)),
            "inputs": len(widget.enter), "outputs": len(widget.exit),
            # Persist the live gate state so feedback circuits (for example an
            # SR latch) keep their memory when the project is reopened.
            "logic_inputs": list(widget.enter),
            "logic_outputs": list(widget.exit),
            "delay_ms": widget.delay_ms,
            "delay_gates": widget.delay_gates,
            "truth_table_number": getattr(widget, "truth_table_number", widget.id),
        }
        if any(width > 1 for width in widget.input_widths + widget.output_widths):
            entry["input_widths"] = list(widget.input_widths)
            entry["output_widths"] = list(widget.output_widths)
        if hasattr(widget, "width"):
            entry["bus_width"] = widget.width
        if isinstance(widget, Native):
            entry.update(widget.export_native())
        if isinstance(widget, LEDMatrix):
            entry.update(matrix_rows=widget.rows, matrix_columns=widget.columns)
        if isinstance(widget, BusInput):
            entry["bus_value"] = widget.value
        if isinstance(widget, (Switch, Clock)):
            entry["state"] = widget.state
        if isinstance(widget, Clock):
            entry["interval_ms"] = widget.interval_ms
        if isinstance(widget, Bulb):
            entry["bulb_color"] = widget.bulb_color
        if isinstance(widget, Display):
            entry["segment_colors"] = widget.segment_colors
        if isinstance(widget, Module):
            if getattr(graphic, "appearance", None):
                entry["appearance"] = dict(graphic.appearance)
            entry["name"] = widget.name
            entry["truth_table"] = widget.truth_table
            entry["input_numbers"] = widget.input_numbers
            entry["output_numbers"] = widget.output_numbers
            if any(width > 1 for width in widget.input_widths + widget.output_widths):
                entry["input_widths"] = widget.input_widths
                entry["output_widths"] = widget.output_widths
            if any(widget.input_labels):
                entry["input_labels"] = widget.input_labels
            if any(widget.output_labels):
                entry["output_labels"] = widget.output_labels
            if getattr(widget, "module_path", None):
                entry["module_path"] = widget.module_path
            if widget.stateful_circuit:
                entry["stateful_circuit"] = widget.stateful_circuit
                entry["stateful_state"] = widget.export_stateful_state()
            source = getattr(widget, "module_source", "")
            if source in {"library", "uploaded"}:
                entry["source"] = source
        components.append(entry)

    wires = []
    for wire in items:
        if not isinstance(wire, Wire) or wire.dst_port is None:
            continue
        src = endpoint_ref(wire.src_port, junction_ids, endpoint_ids)
        dst = endpoint_ref(wire.dst_port, junction_ids, endpoint_ids)
        if src and dst:
            wires.append({"src": src, "dst": dst,
                          "midpoints": [point(mid.scenePos()) for mid in wire._mid_pts],
                          "midpoint_bridges": [int(mid.bridge_mode) for mid in wire._mid_pts],
                          "color": wire.custom_color.name() if wire.custom_color else None})

    return {
        "format": "DaLogic", "version": FORMAT_VERSION,
        "name": window.project_name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
        "visuals": [item.to_data() for item in items if isinstance(item, VisualItem)],
        "junctions": [{"id": junction_ids[item], "position": point(item.pos()),
                       "bridge": bool(getattr(item, "bridge", False)),
                       "bridge_mode": int(getattr(item, "bridge_mode", 0))}
                      for item in junctions],
        "endpoints": [{"id": endpoint_ids[item], "position": point(item.pos())}
                      for item in endpoints],
        "sections": [{"text": item.toPlainText(), "position": point(item.pos())}
                     for item in items if isinstance(item, QGraphicsTextItem)],
        "wires": wires,
    }


def module_definition(name: str, inputs: int, outputs: int, truth_table: list,
                     delay_ms: int = 0, input_numbers: list[int] | None = None,
                     output_numbers: list[int] | None = None,
                     stateful_circuit: dict | None = None,
                     input_labels: list[str] | None = None,
                     output_labels: list[str] | None = None,
                     input_widths: list[int] | None = None,
                     output_widths: list[int] | None = None,
                     format_version: str = "auto",
                     delay_gates: int = 0) -> dict:
    input_widths = Module._normalize_widths(input_widths, inputs)
    output_widths = Module._normalize_widths(output_widths, outputs)
    input_labels = Module._normalize_port_labels(input_labels, inputs)
    output_labels = Module._normalize_port_labels(output_labels, outputs)
    if stateful_circuit:
        input_numbers = Module._normalize_port_numbers(input_numbers, inputs)
        output_numbers = Module._normalize_port_numbers(output_numbers, outputs)
        input_order = sorted(range(inputs), key=lambda index: input_numbers[index])
        output_order = sorted(range(outputs), key=lambda index: output_numbers[index])
        input_remap = {old: new for new, old in enumerate(input_order)}
        output_remap = {old: new for new, old in enumerate(output_order)}
        circuit = json.loads(json.dumps(stateful_circuit))
        for binding in circuit.get("input_bindings", []):
            binding["input"] = input_remap.get(int(binding["input"]), int(binding["input"]))
        for binding in circuit.get("output_bindings", []):
            binding["output"] = output_remap.get(int(binding["output"]), int(binding["output"]))
            for source in binding.get("sources", []):
                if "input" in source:
                    source["input"] = input_remap.get(int(source["input"]), int(source["input"]))
        initial_state = circuit.get("initial_state", {})
        if isinstance(initial_state, dict) and isinstance(initial_state.get("inputs"), list):
            old_values = initial_state["inputs"]
            initial_state["inputs"] = [old_values[index] for index in input_order]
        extended = circuit.get("version", 1) >= 2
        definition = {"format": "DaLogic module", "version": 1.3 if extended else 1.1,
                      "name": name, "inputs": inputs, "outputs": outputs,
                      "delay_ms": max(0, int(delay_ms)),
                      "delay_gates": max(0, min(10000, int(delay_gates))),
                      "input_numbers": [input_numbers[index] for index in input_order],
                      "output_numbers": [output_numbers[index] for index in output_order],
                      "stateful_circuit": circuit}
        if extended:
            definition["input_widths"] = [input_widths[index] for index in input_order]
            definition["output_widths"] = [output_widths[index] for index in output_order]
        sorted_input_labels = [input_labels[index] for index in input_order]
        sorted_output_labels = [output_labels[index] for index in output_order]
        if any(sorted_input_labels):
            definition["input_labels"] = sorted_input_labels
        if any(sorted_output_labels):
            definition["output_labels"] = sorted_output_labels
        return definition
    input_numbers, output_numbers, truth_table, _input_order, _output_order = \
        Module.canonicalize_port_order(inputs, outputs, truth_table,
                                       input_numbers, output_numbers,
                                       input_widths, output_widths)
    definition = {"format": "DaLogic module", "version": 1,
                  "name": name, "inputs": inputs, "outputs": outputs,
                  "delay_ms": max(0, int(delay_ms)),
                  "delay_gates": max(0, min(10000, int(delay_gates))),
                  "input_numbers": input_numbers,
                  "output_numbers": output_numbers,
                  "truth_table": truth_table}
    if any(width > 1 for width in input_widths + output_widths):
        definition["version"] = 1.2
        definition["input_widths"] = [input_widths[index] for index in _input_order]
        definition["output_widths"] = [output_widths[index] for index in _output_order]
        definition["truth_table"] = truth_table
    elif str(format_version) == "1.2":
        definition["version"] = 1.2
        definition["input_widths"] = input_widths
        definition["output_widths"] = output_widths
    if any(input_labels):
        definition["input_labels"] = [input_labels[index] for index in _input_order]
    if any(output_labels):
        definition["output_labels"] = [output_labels[index] for index in _output_order]
    return definition


def supported_dmodule(data):
    """Accept public module formats 1/1.1/1.2 and reject pre-repository trials."""
    if not isinstance(data, dict) or data.get("format") != "DaLogic module":
        return False
    if isinstance(data.get("version"), bool):
        return False
    if not isinstance(data.get("name", "Módulo"), str):
        return False
    try:
        version = float(data.get("version", 0))
    except (TypeError, ValueError):
        return False
    if version in (1.1, 1.3):
        # 1.1 stores the literal sequential circuit; it is unreadable by DaLogic v1.0.
        if "truth_table" in data or not isinstance(data.get("stateful_circuit"), dict) or not data["stateful_circuit"]:
            return False
        if version == 1.1 and data["stateful_circuit"].get("version", 1) != 1:
            return False
        try:
            inputs, outputs = data["inputs"], data["outputs"]
            if type(inputs) is not int or type(outputs) is not int or not 0 <= inputs <= 99 or not 1 <= outputs <= 99:
                return False
            if version == 1.3:
                if data["stateful_circuit"].get("version") != 2:
                    return False
                for key, count in (("input_widths", inputs), ("output_widths", outputs)):
                    values = data.get(key)
                    if not isinstance(values, list) or len(values) != count or any(type(v) is not int or not 1 <= v <= 32 for v in values):
                        return False
            Module(0, data.get("name", "Módulo"), inputs, outputs,
                   stateful_circuit=data["stateful_circuit"],
                   input_widths=data.get("input_widths"), output_widths=data.get("output_widths"))
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, RecursionError, OverflowError):
            return False
        return True
    if version in (1.0, 1.2):
        table = data.get("truth_table")
        try:
            inputs, outputs = data.get("inputs", -1), data.get("outputs", -1)
            if (type(inputs) is not int or type(outputs) is not int
                    or not 0 <= inputs <= 32 or not 1 <= outputs <= 99):
                return False
            widths_in = data.get("input_widths") if version == 1.2 else [1] * inputs
            widths_out = data.get("output_widths") if version == 1.2 else [1] * outputs
            valid_widths = (isinstance(widths_in, list) and isinstance(widths_out, list)
                            and len(widths_in) == inputs and len(widths_out) == outputs
                            and all(type(width) is int and 1 <= width <= 32
                                    for width in widths_in + widths_out))
            expected_rows = 1 << sum(widths_in) if valid_widths and sum(widths_in) <= 16 else -1
        except (TypeError, ValueError):
            return False
        if ("stateful_circuit" in data or not valid_widths or
                sum(widths_in) > 16 or not isinstance(table, list) or
                len(table) != expected_rows):
            return False
        input_vectors = set()
        for row in table:
            if (not isinstance(row, dict) or
                    not isinstance(row.get("inputs"), list) or
                    not isinstance(row.get("outputs"), list) or
                    len(row["inputs"]) != inputs or len(row["outputs"]) != outputs):
                return False
            for index, value in enumerate(row["inputs"]):
                if type(value) not in (int, bool) or not 0 <= value < (1 << widths_in[index]):
                    return False
            vector = tuple(int(value) for value in row["inputs"])
            if vector in input_vectors:
                return False
            input_vectors.add(vector)
            for index, value in enumerate(row["outputs"]):
                if value == "X" or value == "Z":
                    continue
                if type(value) not in (int, bool) or not 0 <= value < (1 << widths_out[index]):
                    return False
            if type(row.get("time_ms")) is not int or row["time_ms"] < 0:
                return False
        return len(input_vectors) == expected_rows
    return False


# Export the bounded probe history, preserving bus widths and X/Z values.
def probe_width(probe):
    target = probe["target"]
    if isinstance(target, Wire):
        return target._bus_endpoint()[1]
    if isinstance(target, Port):
        widget = target.graphic.widg
        widths = widget.input_widths if target.is_input else widget.output_widths
        return widths[target.port_index]
    values = [v for _t, v in probe["history"] if type(v) in (int, bool)]
    return max((int(v).bit_length() for v in values), default=1) or 1


def write_probe_history(path, probes, *, vcd=False):
    if not probes or not any(p["history"] for p in probes):
        raise ValueError(tr("No hay muestras de sondas para exportar."))
    widths = [probe_width(p) for p in probes]
    histories = [list(p["history"]) for p in probes]
    if not vcd:
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["Tiempo (s)", "Sonda", "Nombre", "Ancho (bits)", "Valor"])
            rows = [(stamp, i, value) for i, history in enumerate(histories) for stamp, value in history]
            for stamp, i, value in sorted(rows):
                writer.writerow([f"{stamp:.9f}", i + 1, probes[i]["label"], widths[i],
                                 value if value in ("X", "Z") else int(value)])
        return
    origin = min(stamp for history in histories for stamp, _value in history)
    events = {}
    for i, history in enumerate(histories):
        for stamp, value in history:
            tick = max(0, round((stamp - origin) * 1_000_000))
            events.setdefault(tick, {})[i] = value
    with Path(path).open("w", encoding="ascii", newline="\n") as stream:
        stream.write("$version DaLogic $end\n$timescale 1 us $end\n$scope module DaLogic $end\n")
        for i, width in enumerate(widths):
            stream.write(f"$var wire {width} s{i} probe_{i + 1} $end\n")
        stream.write("$upscope $end\n$enddefinitions $end\n#0\n$dumpvars\n")
        for i, width in enumerate(widths):
            stream.write(f"b{'x' * width} s{i}\n")
        stream.write("$end\n")
        for tick, changes in sorted(events.items()):
            stream.write(f"#{tick}\n")
            for i, value in sorted(changes.items()):
                bits = value.lower() * widths[i] if value in ("X", "Z") else format(int(value), f"0{widths[i]}b")
                stream.write(f"b{bits} s{i}\n")
