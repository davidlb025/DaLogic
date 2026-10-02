"""Formato de proyecto portable de DaLogic (JSON, extensión .dalogic)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsTextItem

from widgets.graphics import Port, Wire, Junction, WireEndpoint
from widgets.widgets import Module, Switch, Button, Clock, Bulb, Display


FORMAT_VERSION = 1


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
    junctions = [item for item in scene.items() if isinstance(item, Junction)]
    endpoints = [item for item in scene.items() if isinstance(item, WireEndpoint)]
    junction_ids = {item: f"j{index}" for index, item in enumerate(junctions)}
    endpoint_ids = {item: f"e{index}" for index, item in enumerate(endpoints)}

    components = []
    for widget_id, graphic in window.all_graphics.items():
        widget = graphic.widg
        entry = {
            "id": widget_id,
            "type": window.type_for_widget(widget),
            "position": point(graphic.pos()),
            "inputs": len(widget.enter), "outputs": len(widget.exit),
            # Persist the live gate state so feedback circuits (for example an
            # SR latch) keep their memory when the project is reopened.
            "logic_inputs": list(widget.enter),
            "logic_outputs": list(widget.exit),
            "delay_ms": widget.delay_ms,
            "truth_table_number": getattr(widget, "truth_table_number", widget.id),
        }
        if isinstance(widget, (Switch, Button, Clock)):
            entry["state"] = widget.state
        if isinstance(widget, Clock):
            entry["interval_ms"] = widget.interval_ms
        if isinstance(widget, Bulb):
            entry["bulb_color"] = widget.bulb_color
        if isinstance(widget, Display):
            entry["segment_colors"] = widget.segment_colors
        if isinstance(widget, Module):
            entry["name"] = widget.name
            entry["truth_table"] = widget.truth_table
            entry["input_numbers"] = widget.input_numbers
            entry["output_numbers"] = widget.output_numbers
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
    for wire in scene.items():
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
        "junctions": [{"id": junction_ids[item], "position": point(item.pos()),
                       "bridge": bool(getattr(item, "bridge", False)),
                       "bridge_mode": int(getattr(item, "bridge_mode", 0))}
                      for item in junctions],
        "endpoints": [{"id": endpoint_ids[item], "position": point(item.pos())}
                      for item in endpoints],
        "sections": [{"text": item.toPlainText(), "position": point(item.pos())}
                     for item in scene.items() if isinstance(item, QGraphicsTextItem)],
        "wires": wires,
    }


def module_definition(name: str, inputs: int, outputs: int, truth_table: list,
                     delay_ms: int = 0, input_numbers: list[int] | None = None,
                     output_numbers: list[int] | None = None,
                     stateful_circuit: dict | None = None) -> dict:
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
        return {"format": "DaLogic module", "version": 1.1,
                "name": name, "inputs": inputs, "outputs": outputs,
                "delay_ms": max(0, int(delay_ms)),
                "input_numbers": [input_numbers[index] for index in input_order],
                "output_numbers": [output_numbers[index] for index in output_order],
                "stateful_circuit": circuit}
    input_numbers, output_numbers, truth_table, _input_order, _output_order = \
        Module.canonicalize_port_order(inputs, outputs, truth_table,
                                       input_numbers, output_numbers)
    return {"format": "DaLogic module", "version": 1,
            "name": name, "inputs": inputs, "outputs": outputs,
            "delay_ms": max(0, int(delay_ms)),
            "input_numbers": input_numbers,
            "output_numbers": output_numbers,
            "truth_table": truth_table}
