from resources import translate_text as tr, load_catalogs, source_text, language_code, library_module_name
# This Python file uses the following encoding: utf-8
import sys
import ast
from pathlib import Path, PurePosixPath
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QTextBrowser,
    QPushButton, QFileDialog, QInputDialog, QMessageBox, QToolBar,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QWidget, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QGroupBox, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QTabWidget, QDockWidget, QMenu,
    QTreeWidgetItem, QStyle, QToolButton
)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap,
    QPageLayout, QPageSize, QPdfWriter, QDrag, QPalette, QHoverEvent
)
from PySide6.QtCore import QRect, QRectF, QPointF, QSize, Qt, QEvent, QTimer, QMimeData
import csv
import re
import importlib
import json
import time
import zipfile
from xml.sax.saxutils import escape as xml_escape

from resources import get_app_icon, APP_VERSION

import widgets.widgets as wdg
import widgets.graphics as gra
from widgets.native import COMPONENTS, Native, LEDMatrix
from widgets.native_graphics import NativeGraphic
from widgets.graphics import Port, Wire, Junction, WireEndpoint
from project_io import (dump_project, module_definition, prepare_project, write_json_atomic,
                        write_probe_history, probe_width,
                        supported_dmodule as _supported_dmodule)
from widgets.visual import VisualItem, VisualDock, ActionBar, ComponentPalette, ShortcutMenu, LibraryTree
from app_runtime import (BASE_DIR, USER_DIR, CI_LIBRARY_DIR, LEGACY_CI_LIBRARY_DIR,
                         LANGUAGE_DIR, PROJECTS_DIR, EXPORTS_DIR, initialize_user_data,
                         comprobar_actualizaciones, run)
from board_view import CalculationProgress, cancellable, inspect_circuit

def _default_ci_labels(widgets, is_input):
    """Give newly encapsulated source/sink ports concise schematic names."""
    if is_input:
        from widgets.widgets import Switch, Button, Clock, BusInput
        bases = ["CLK" if isinstance(widget, Clock) else
                 "BUS" if isinstance(widget, BusInput) else
                 "BTN" if isinstance(widget, Button) else
                 "IN" if isinstance(widget, Switch) else "IN"
                 for widget in widgets]
    else:
        from widgets.widgets import Bulb, BusLamp
        bases = ["BUS" if isinstance(widget, BusLamp) else
                 "Q" if isinstance(widget, Bulb) else "OUT"
                 for widget in widgets]
    totals = {base: bases.count(base) for base in set(bases)}
    seen = {}
    labels = []
    for base in bases:
        seen[base] = seen.get(base, 0) + 1
        labels.append(f"{base}{seen[base]}" if totals[base] > 1 else base)
    return labels


# La interfaz generada se incluye en el repositorio. Compilarla en cada arranque
# hacía que la aplicación se bloqueara cuando Qt Creator no estaba instalado.


# ── Diálogos auxiliares ──────────────────────────────────────────────────────

from resources import LocalizedInputDialog as QInputDialog, LocalizedFileDialog as QFileDialog

class VentanaConfig(QDialog):
    def __init__(self, ui_config, parent=None):
        super().__init__(parent)
        self.ui = ui_config
        self.ui.setupUi(self)


class VentanaCreditos(QDialog):

    def __init__(self, ui_form, parent=None):
        super().__init__(parent)
        self.ui = ui_form
        self.ui.setupUi(self)
        self.setWindowTitle(tr('Créditos — DaLogic {v0}', v0=APP_VERSION))
        self.cargar_creditos()

    def convertir_links(self, texto):
        return re.sub(r"(https?://[^\s]+)", r'<a href="\1">\1</a>', texto)

    def format_notice(self, texto):
        lineas = texto.splitlines()
        html   = []
        for i, linea in enumerate(lineas):
            linea = self.convertir_links(linea)
            linea = linea.replace("David Lopez Borrego", "<b>David Lopez Borrego</b>")
            if not linea:
                html.append("<p></p>")
            elif i == 0:
                html.append(f"<h1 style='text-align:center;'>{linea}</h1>")
            elif i == 1:
                html.append(f"<h3 style='text-align:center;'>{linea}</h3>")
            else:
                html.append(f"<p>{linea}</p>")
        return "".join(html)

    def cargar_creditos(self):
        try:
            with (BASE_DIR / "NOTICE").open("r", encoding="utf-8") as f:
                texto = f.read()
        except FileNotFoundError:
            texto = ("DaLogic\n\nCopyright 2026 David Lopez Borrego\n\n"
                     "https://github.com/davidlb025/DaLogic")
        label = self.findChild(QTextBrowser, "Creditos")
        if label:
            label.setHtml(self.format_notice(tr(texto)))


class TruthTableDialog(QDialog):
    def __init__(self, rows, input_labels, output_labels, calculation_ms,
                 ignored_summary="", parent=None, input_widths=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Tabla de verdad del circuito"))
        self.resize(980, 620)

        layout = QVBoxLayout(self)
        summary = QLabel(
            tr('{v0} entradas · {v1} combinaciones · Cálculo: {v2:.2f} ms', v0=len(input_labels), v1=len(rows), v2=calculation_ms), self)
        summary.setStyleSheet("font-weight: 600; padding: 4px 0;")
        layout.addWidget(summary)
        notation = QLabel(
            tr("Bombillas: 0/1 · Displays: índices de segmentos (p. ej. 012) · "
            "Buses: hexadecimal · X: indeterminado · Z: alta impedancia"),
            self)
        notation.setWordWrap(True)
        layout.addWidget(notation)
        if ignored_summary:
            ignored = QLabel(tr(ignored_summary), self)
            ignored.setWordWrap(True)
            ignored.setStyleSheet("padding: 4px 0;")
            layout.addWidget(ignored)

        table_tools = QHBoxLayout()
        search = QLineEdit(self)
        search.setClearButtonEnabled(True)
        search.setPlaceholderText(tr("Filtrar filas por valor (p. ej. 012 o 1)…"))
        table_tools.addWidget(search, 1)
        fit_columns = QPushButton(tr("Ajustar columnas"), self)
        fit_columns.setToolTip(tr("Ajusta el ancho al contenido; también puedes arrastrar los bordes de las cabeceras"))
        table_tools.addWidget(fit_columns)
        layout.addLayout(table_tools)

        headers = [*input_labels, *output_labels, "Respuesta (ms)"]
        self.headers = headers
        table = QTableWidget(len(rows), len(headers), self)
        self.table = table
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setMinimumSectionSize(72)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setToolTip(tr("Arrastra el borde entre cabeceras para cambiar el ancho"))
        for row_index, row in enumerate(rows):
            widths = input_widths or [1] * len(row["inputs"])
            values = [(f"0x{int(value):X}" if widths[column] > 1 else
                       "1" if value else "0")
                      for column, value in enumerate(row["inputs"])]
            values += list(row["outputs"]) + [str(row["time_ms"])]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(tr(value))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, column, cell)
        table.resizeColumnsToContents()
        fit_columns.clicked.connect(table.resizeColumnsToContents)
        search.textChanged.connect(self._filter_rows)
        layout.addWidget(table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        export = QPushButton(tr("Exportar tabla…"), self)
        export.clicked.connect(self._export_table)
        buttons.addWidget(export)
        close = QPushButton(tr("Cerrar"), self)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _export_table(self):
        formats = (tr("Imagen PNG (*.png);;Documento PDF (*.pdf);;Gráfico SVG (*.svg);;"
                   "Libro de Excel (*.xlsx);;CSV para Excel (*.csv)"))
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path, selected_filter = QFileDialog.getSaveFileName(self, tr("Exportar tabla de verdad"), str(EXPORTS_DIR / "tabla_verdad.png"),
            formats, "Imagen PNG (*.png)")
        if not path:
            return
        extensions = {"Imagen PNG": ".png", "Documento PDF": ".pdf",
                      "Gráfico SVG": ".svg", "Libro de Excel": ".xlsx",
                      "CSV para Excel": ".csv"}
        ext = next((value for label, value in extensions.items()
                    if selected_filter.startswith(label)), Path(path).suffix.lower())
        if ext not in extensions.values():
            ext = ".png"
        if Path(path).suffix.lower() != ext:
            path = str(Path(path).with_suffix(ext))
        rows = [[self.table.item(r, c).text() if self.table.item(r, c) else ""
                 for c in range(self.table.columnCount())]
                for r in range(self.table.rowCount())]
        try:
            if ext == ".csv":
                with open(path, "w", newline="", encoding="utf-8-sig") as file:
                    writer = csv.writer(file, delimiter=";")
                    writer.writerow(self.headers)
                    writer.writerows(rows)
            elif ext == ".xlsx":
                self._write_xlsx(path, self.headers, rows)
            else:
                self._export_table_graphic(path, ext, self.headers, rows)
        except (OSError, ImportError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, tr("No se pudo exportar la tabla"), tr(str(exc)))

    @staticmethod
    def _write_xlsx(path, headers, rows):
        def col_name(number):
            result = ""
            while number:
                number, rest = divmod(number - 1, 26)
                result = chr(65 + rest) + result
            return result

        xml_rows = []
        for row_no, values in enumerate([headers, *rows], 1):
            cells = []
            for col_no, value in enumerate(values, 1):
                ref = f"{col_name(col_no)}{row_no}"
                if col_no == len(headers) and headers[-1] == "Respuesta (ms)":
                    try:
                        numeric = float(value)
                    except (TypeError, ValueError):
                        numeric = None
                    if numeric is not None:
                        cells.append(f'<c r="{ref}" t="n"><v>{numeric:g}</v></c>')
                        continue
                text = xml_escape(str(value), {'"': "&quot;"})
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>')
            xml_rows.append(f'<row r="{row_no}">{"".join(cells)}</row>')
        sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
        parts = {
            "[Content_Types].xml": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '</Types>'),
            "_rels/.rels": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>'),
            "xl/workbook.xml": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Tabla de verdad" sheetId="1" r:id="rId1"/></sheets></workbook>'),
            "xl/_rels/workbook.xml.rels": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                '</Relationships>'),
            "xl/worksheets/sheet1.xml": sheet,
        }
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in parts.items():
                archive.writestr(name, content)

    @staticmethod
    def _paint_table_rows(painter, headers, rows, widths, x, y,
                          header_height=42, row_height=22):
        total_width = sum(widths)
        painter.setFont(QFont("Arial", 8))
        painter.fillRect(QRectF(x, y, total_width, header_height), QColor("#315f91"))
        cursor = x
        for col, header in enumerate(headers):
            rect = QRectF(cursor, y, widths[col], header_height)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(rect.adjusted(4, 2, -4, -2),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             tr(str(header)))
            painter.setPen(QColor("#9aaec3"))
            painter.drawRect(rect)
            cursor += widths[col]
        for row_no, values in enumerate(rows):
            cursor = x
            top = y + header_height + row_no * row_height
            fill = QColor("#ffffff" if row_no % 2 == 0 else "#eef3f8")
            for col, value in enumerate(values):
                rect = QRectF(cursor, top, widths[col], row_height)
                painter.fillRect(rect, fill)
                painter.setPen(QColor("#c7d0da"))
                painter.drawRect(rect)
                painter.setPen(QColor("#17212b"))
                painter.drawText(rect.adjusted(5, 1, -5, -1),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 tr(str(value)))
                cursor += widths[col]

    def _export_table_graphic(self, path, ext, headers, rows):
        widths = [max(88, self.table.columnWidth(c))
                  for c in range(self.table.columnCount())]
        width = sum(widths)
        head_h, row_h = 42, 22
        height = head_h + len(rows) * row_h
        if ext == ".pdf":
            writer = QPdfWriter(path)
            writer.setResolution(120)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageOrientation(QPageLayout.Orientation.Landscape)
            painter = QPainter(writer)
            if not painter.isActive():
                raise RuntimeError(tr("No se pudo crear el PDF."))
            margin = 38
            scale = min(1.0, (writer.width() - 2 * margin) / width)
            page_w = (writer.width() - 2 * margin) / scale
            page_h = (writer.height() - 2 * margin) / scale
            per_page = max(1, int((page_h - head_h) / row_h))
            for start in range(0, len(rows), per_page):
                if start:
                    writer.newPage()
                painter.save()
                painter.scale(scale, scale)
                painter.fillRect(QRectF(0, 0, page_w, page_h), QColor("#ffffff"))
                self._paint_table_rows(painter, headers, rows[start:start + per_page],
                                       widths, margin / scale, margin / scale, head_h, row_h)
                painter.restore()
            painter.end()
        elif ext == ".svg":
            from PySide6.QtSvg import QSvgGenerator
            generator = QSvgGenerator()
            generator.setFileName(path)
            generator.setSize(QSize(width, height))
            generator.setViewBox(QRect(0, 0, width, height))
            generator.setTitle(tr("Tabla de verdad del circuito"))
            painter = QPainter(generator)
            if not painter.isActive():
                raise RuntimeError(tr("No se pudo crear el SVG."))
            painter.fillRect(QRectF(0, 0, width, height), QColor("#ffffff"))
            self._paint_table_rows(painter, headers, rows, widths, 0, 0, head_h, row_h)
            painter.end()
        else:
            scale = min(1.0, (50_000_000 / max(1, width * height)) ** 0.5,
                        32767 / max(1, width, height))
            image = QImage(max(1, int(width * scale)), max(1, int(height * scale)),
                           QImage.Format.Format_ARGB32)
            if image.isNull():
                raise RuntimeError(tr("La imagen es demasiado grande para PNG."))
            image.fill(QColor("#ffffff"))
            painter = QPainter(image)
            painter.scale(scale, scale)
            self._paint_table_rows(painter, headers, rows, widths, 0, 0, head_h, row_h)
            painter.end()
            if not image.save(path, "PNG"):
                raise RuntimeError(tr("No se pudo guardar el PNG."))


    def _filter_rows(self, query):
        query = query.casefold().strip()
        for row in range(self.table.rowCount()):
            matches = not query or any(
                query in (self.table.item(row, column).text().casefold()
                          if self.table.item(row, column) else "")
                for column in range(self.table.columnCount()))
            self.table.setRowHidden(row, not matches)


class FocusLabel(QLabel):
    def __init__(self, text, on_double_click, parent=None):
        super().__init__(text, parent)
        self._on_double_click = on_double_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("Doble clic para localizar este componente en el circuito"))

    def mouseDoubleClickEvent(self, event):
        self._on_double_click()
        event.accept()


class TruthTableOrderDialog(QDialog):
    def __init__(self, inputs, outputs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Orden de la tabla de verdad"))
        self.resize(560, 500)
        self.input_fields = []
        self.output_fields = []

        layout = QVBoxLayout(self)
        instructions = QLabel(
            tr("Asigna un número único a cada columna; el número menor aparece primero.\n"
            "Haz doble clic en el nombre de una entrada o salida para localizarla en el circuito."), self)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        columns = QHBoxLayout(content)
        for title, widgets, fields in (("Entradas", inputs, self.input_fields),
                                       ("Salidas", outputs, self.output_fields)):
            group = QGroupBox(tr(title), content)
            group_layout = QVBoxLayout(group)
            for index, widget in enumerate(widgets):
                if isinstance(widget, (wdg.Switch, wdg.Button, wdg.Clock, wdg.BusInput)):
                    kind = ("Botón" if isinstance(widget, wdg.Button) else
                            "Reloj" if isinstance(widget, wdg.Clock) else
                            "Entrada bus" if isinstance(widget, wdg.BusInput) else "Interruptor")
                else:
                    kind = ("Bombilla" if isinstance(widget, wdg.Bulb) else
                            "Salida bus" if isinstance(widget, wdg.BusLamp) else "Display")
                width = getattr(widget, "width", 1)
                if width > 1:
                    kind += f" · {width} bits"
                row = QHBoxLayout()
                label_text = f"{kind} {widget.id}"
                if parent is not None:
                    label = FocusLabel(label_text,
                        lambda target=widget: parent.localizar_elemento_tabla(target), group)
                else:
                    label = QLabel(tr(label_text), group)
                row.addWidget(label)
                number = QSpinBox(group)
                number.setRange(0, 999)
                number.setPrefix(tr("N.º "))
                number.setToolTip(tr("Orden de esta columna en la tabla de verdad"))
                number.setValue(int(getattr(widget, "truth_table_number", index)))
                number.setFixedWidth(76)
                row.addWidget(number)
                group_layout.addLayout(row)
                fields.append((widget, number))
            group_layout.addStretch(1)
            columns.addWidget(group)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self._make_unique(self.input_fields)
        self._make_unique(self.output_fields)
        self._connect_unique(self.input_fields)
        self._connect_unique(self.output_fields)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        calculate = QPushButton(tr("Calcular tabla"), self)
        calculate.clicked.connect(self.accept)
        cancel = QPushButton(tr("Cancelar"), self)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(calculate)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    @staticmethod
    def _make_unique(fields):
        used = set()
        for _widget, field in fields:
            value = field.value()
            if value in used:
                value = next(number for number in range(1000) if number not in used)
                field.setValue(value)
            used.add(value)

    @staticmethod
    def _connect_unique(fields):
        previous = [field.value() for _widget, field in fields]
        for index, (_widget, field) in enumerate(fields):
            def keep_unique(value, edited=index, entries=fields, old=previous):
                duplicate = next((other for other, (_candidate, spin) in enumerate(entries)
                                  if other != edited and spin.value() == value), None)
                if duplicate is not None:
                    other_field = entries[duplicate][1]
                    other_field.blockSignals(True)
                    other_field.setValue(old[edited])
                    other_field.blockSignals(False)
                old[:] = [spin.value() for _candidate, spin in entries]
            field.valueChanged.connect(keep_unique)

# ── Ventana principal ────────────────────────────────────────────────────────

class ProbePlot(QWidget):
    """Compact digital timeline for the active signal probes."""

    def __init__(self, board, parent=None):
        super().__init__(parent)
        self.board = board
        self.span_seconds = 10.0
        self.offset_seconds = 0.0
        self.setMinimumHeight(118)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.update)
        self.refresh_timer.start(250)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = QColor("#17212d" if getattr(self.board, "theme_mode", "light") == "dark" else "#f5f7fa")
        fg = QColor("#92a2b4" if bg.red() < 100 else "#758398")
        painter.fillRect(self.rect(), bg)
        probes = self.board._probes
        if not probes:
            painter.setPen(fg)
            painter.drawText(self.rect(), Qt.AlignCenter, tr("Ctrl+clic en un cable o puerto para añadir una sonda"))
            return
        left, right = 54.0, max(55.0, float(self.width() - 16))
        top, bottom = 15.0, float(self.height() - 20)
        rows = len(probes)
        row_h = (bottom - top) / max(1, rows)
        now = max(0.0, self.board.probe_time() - self.offset_seconds)
        span = self.span_seconds
        start = max(0.0, now - span)
        painter.setPen(QPen(fg, 1))
        for tick in range(6):
            x = left + (right - left) * tick / 5
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            painter.drawText(QRectF(x - 25, bottom + 2, 50, 16), Qt.AlignHCenter,
                             tr('{v0:.1f}s', v0=start + span * tick / 5))
        for row, probe in enumerate(probes):
            y0 = top + row * row_h
            y_low, y_high = y0 + row_h * .72, y0 + row_h * .28
            painter.setPen(QPen(QColor(probe["color"]), 2))
            history = probe["history"]
            visible_values = [value for stamp, value in history if stamp <= now]
            current = visible_values[-1] if visible_values else "X"
            if probe_width(probe) > 1:
                painter.drawText(QRectF(4, y0, 46, row_h), Qt.AlignVCenter,
                                 (tr(str(current)) if current in ("X", "Z") else tr('0x{v0:X}', v0=int(current))))
                previous_x = left - 36
                for stamp, value in history:
                    if stamp > now:
                        continue
                    x = left + (stamp - start) / span * (right - left)
                    if x < left or x - previous_x < 38:
                        continue
                    label = value if value in ("X", "Z") else f"{int(value):X}"
                    painter.drawText(QRectF(x - 18, y0, 36, row_h), Qt.AlignCenter,
                                     tr(str(label)))
                    previous_x = x
                continue
            current_label = (current if current in ("X", "Z") else
                             "1 / H" if current else "0 / L")
            painter.drawText(QRectF(4, y0, 46, row_h), Qt.AlignVCenter, tr(str(current_label)))
            if not history:
                continue
            points = [(max(start, stamp), value) for stamp, value in history if start <= stamp <= now]
            past = [value for stamp, value in history if stamp < start]
            if past:
                points.insert(0, (start, past[-1]))
            if not points:
                points = [(now, current)]
            path = QPainterPath()
            x = left + (points[0][0] - start) / span * (right - left)
            level = lambda value: (y_high + y_low) / 2 if value in ("X", "Z") else y_high if value else y_low
            path.moveTo(x, level(points[0][1]))
            previous = points[0][1]
            for stamp, value in points[1:]:
                x = left + (stamp - start) / span * (right - left)
                path.lineTo(x, level(previous))
                path.lineTo(x, level(value))
                previous = value
            end_x = left + (now - start) / span * (right - left)
            path.lineTo(end_x, level(previous))
            painter.drawPath(path)


class ProbePanel(QWidget):
    def __init__(self, board, parent=None):
        super().__init__(parent)
        self.board = board
        self.panel_layout = QVBoxLayout(self)
        self.panel_layout.setContentsMargins(8, 6, 8, 6)
        self.panel_layout.setSpacing(3)
        tools = QHBoxLayout()
        export = QPushButton(tr("Exportar sondas…"), self)
        export.clicked.connect(self.export_history)
        clear = QPushButton(tr("Limpiar historial"), self)
        clear.clicked.connect(self.clear_history)
        tools.addWidget(export)
        tools.addWidget(clear)
        tools.addStretch(1)
        self.panel_layout.addLayout(tools)
        self.plot = ProbePlot(board, self)
        self.panel_layout.addWidget(self.plot)
        navigation = QHBoxLayout()
        self.span = QDoubleSpinBox(self)
        self.span.setRange(.5, 600)
        self.span.setValue(10)
        self.span.setSuffix(tr(" s"))
        self.offset = QDoubleSpinBox(self)
        self.offset.setRange(0, 86400)
        self.offset.setSuffix(tr(" s"))
        self.capacity = QSpinBox(self)
        self.capacity.setRange(256, 100000)
        self.capacity.setValue(board.probe_history_limit)
        for label, field in (("Ventana", self.span), ("Retroceder", self.offset), ("Cambios por sonda", self.capacity)):
            navigation.addWidget(QLabel(tr(label), self))
            navigation.addWidget(field)
        navigation.addStretch(1)
        self.panel_layout.addLayout(navigation)
        self.span.valueChanged.connect(self.change_view)
        self.offset.valueChanged.connect(self.change_view)
        self.capacity.valueChanged.connect(self.change_capacity)

    def change_view(self):
        self.plot.span_seconds = self.span.value()
        self.plot.offset_seconds = self.offset.value()
        self.plot.update()

    def change_capacity(self, value):
        self.board.probe_history_limit = value
        for probe in self.board._probes:
            del probe["history"][:-value]
        owner = self.board.owner
        owner.config["probe_history_limit"] = value
        owner._save_editor_preferences()
        self.plot.update()

    def clear_history(self):
        for probe in self.board._probes:
            probe["history"].clear()
        self.board._probe_started = time.monotonic()
        self.board._probe_pause_total = 0.0
        self.board._probe_paused_at = self.board._probe_started if self.board._clocks_paused else None
        self.offset.setValue(0)
        self.board._record_probe_values(force=True)
        self.plot.update()

    def export_history(self):
        if not any(probe["history"] for probe in self.board._probes):
            QMessageBox.information(self, tr("Exportar sondas"), tr("Añade una sonda con Ctrl+clic antes de exportar."))
            return
        try:
            EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path, selected = QFileDialog.getSaveFileName(self, "Exportar sondas",
                str(EXPORTS_DIR / "sondas.csv"), tr("CSV (*.csv);;Ondas VCD (*.vcd)"))
            if not path:
                return
            vcd = selected.startswith("Ondas")
            path = Path(path).with_suffix(".vcd" if vcd else ".csv")
            write_probe_history(path, self.board._probes, vcd=vcd)
            self.window().statusBar().showMessage(tr('Sondas exportadas: {v0}', v0=path.name), 5000)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, tr("No se pudieron exportar las sondas"), tr(str(exc)))

    def refresh(self):
        while self.panel_layout.count() > 3:
            item = self.panel_layout.takeAt(3)
            if item.widget():
                item.widget().deleteLater()
        for probe in self.board._probes:
            row = QWidget(self)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(3, 0, 3, 0)
            swatch = QFrame(row)
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(f"background: {probe['color']}; border-radius: 5px;")
            label = QLabel(probe["label"], row)
            label.setToolTip(probe["label"])
            remove = QPushButton("×", row)
            remove.setFixedSize(26, 23)
            remove.setToolTip(tr("Quitar sonda"))
            remove.clicked.connect(lambda checked=False, p=probe: self.board.remove_probe(p))
            row_layout.addWidget(swatch)
            row_layout.addWidget(label, 1)
            row_layout.addWidget(remove)
            self.panel_layout.addWidget(row)
        self.plot.update()


class ProbeDock(QDockWidget):
    def __init__(self, board, parent=None):
        super().__init__(tr("Sondas"), parent)
        self.panel = ProbePanel(board, self)
        self.setWidget(self.panel)
        self.setMinimumHeight(185)


class VentanaInicial(QMainWindow):

    # Mapa tipo_widget → (clase Widget, clase Graphic o None, ruta SVG o None, escala)
    # None en clase Graphic significa usar la clase Graphic SVG estándar
    WIDGET_DEFS = {
        "AND":         (wdg.AND,     gra.LogicGateGraphic, None, 1.0),
        "OR":          (wdg.OR,      gra.LogicGateGraphic, None, 1.0),
        "XOR":         (wdg.XOR,     gra.LogicGateGraphic, None, 1.0),
        "NOT":         (wdg.NOT,     gra.LogicGateGraphic, None, 1.0),
        "NAND":        (wdg.NAND,    gra.LogicGateGraphic, None, 1.0),
        "NOR":         (wdg.NOR,     gra.LogicGateGraphic, None, 1.0),
        "INTERRUPTOR": (wdg.Switch,  gra.LogicGateGraphic, None, 1.0),
        "RELOJ":       (wdg.Clock,   gra.LogicGateGraphic, None, 1.0),
        "BOTON":       (wdg.Button,  gra.LogicGateGraphic, None, 1.0),
        "RETARDO":     (wdg.Delay,   gra.LogicGateGraphic, None, 1.0),
        "BOMBILLA":    (wdg.Bulb,    gra.BulbGraphic,    None,                          1.0),
        "DISPLAY":     (wdg.Display, gra.DisplayGraphic, None,                          1.0),
        "BUS_ENTRADA": (wdg.BusInput, gra.LogicGateGraphic, None, 1.0),
        "BUS_LAMP":    (wdg.BusLamp, gra.LogicGateGraphic, None, 1.0),
        "BUS_VISOR":   (wdg.BusViewer, gra.LogicGateGraphic, None, 1.0),
        "SPLITTER":    (wdg.Splitter, gra.LogicGateGraphic, None, 1.0),
        "COMBINER":    (wdg.Combiner, gra.LogicGateGraphic, None, 1.0),
        "TRIESTADO":   (wdg.TriState, gra.LogicGateGraphic, None, 1.0),
        **{kind: (klass, NativeGraphic, None, 1.0) for kind, klass in COMPONENTS.items()},
    }

    def __init__(self, app, *, recover=True):
        super().__init__()
        self.app = app
        self._allow_recovery = recover
        initialize_user_data()
        self.load_settings()
        catalogs = load_catalogs(LANGUAGE_DIR)
        initial = catalogs.get(str(self.config.get("lang", "es")), catalogs["es"])
        gra.set_language_translations(initial["translations"], initial["code"])
        self.iniciarUI()
        self.def_actions()
        self._prepare_language_selector()
        self._apply_saved_language()
        self._setup_history()
        self._setup_autosave()

    def iniciarUI(self):
        self.all_widgets: dict[int, wdg.Widget]   = {}
        self.all_graphics: dict[int, gra.Graphic] = {}
        self.next_id = 0
        self.project_path: Path | None = None
        self.project_name = "Sin título"
        self._clipboard: list[dict] = []
        self._visual_clipboard: list[dict] = []
        self._connection_clipboard = {"wires": [], "junctions": [], "endpoints": []}
        self.imported_modules: list[dict] = []
        self._undo_history = []
        self._redo_history = []
        self._history_restoring = False
        self._history_snapshot_json = None
        self._document_saved_key = None
        self._recovery_pending = False

        self.ui = self.MainWindow
        self.setFont(QFont("Segoe UI", 9))
        self.ui.setupUi(self)
        self._original_icons = {}
        self._capturar_iconos()
        self.ui.tabWidget.setTabText(self.ui.tabWidget.indexOf(self.ui.Puertas), tr("Básico"))
        self.ui.tabWidget.setTabText(self.ui.tabWidget.indexOf(self.ui.tab_2), tr("CI"))
        self.app.setStyle("Fusion")
        self.theme_mode = "dark" if "dark" in self.config.get("theme", "") else "light"
        self.aplicar_tema(self.theme_mode, persist=False)

        self.ui.Show.hide()
        self.ui.Show.clicked.connect(self.devolver_widg_panel)

        close_button = QPushButton(tr("X"), self.ui.scrollAreaWidgetContents)
        self.ui.close = close_button
        self.ui.close.setFlat(True)
        self.ui.close.clicked.connect(self.cerrar_widg_panel)
        self.ui.close.setFixedSize(30, 26)
        self.ui.gridLayout.removeWidget(self.ui.tabWidget)
        self.ui.gridLayout.addWidget(QLabel(tr("Componentes"), self.ui.scrollAreaWidgetContents), 0, 0, Qt.AlignLeft)
        self.ui.gridLayout.addWidget(self.ui.close, 0, 0, Qt.AlignRight)
        self.ui.gridLayout.addWidget(self.ui.tabWidget, 1, 0)
        self.ui.splitter.splitterMoved.connect(self.check_widg_panel)

        self.ui.graphicsView.board_ref = self.ui.graphicsView
        self.ui.graphicsView.owner = self
        self.ui.graphicsView.centerOn(0, 0)

        self.def_buttons()
        self._prepare_component_palettes()
        self._preparar_biblioteca_ci()
        self._preparar_interfaz_profesional()
        self.setWindowTitle(tr("DaLogic — Sin título"))
        self.show()
        QTimer.singleShot(0, self._set_compact_tool_panel)

    def _set_compact_tool_panel(self):
        total = self.ui.splitter.width()
        self.ui.tabWidget.tabBar().setUsesScrollButtons(True)
        for button in self.ui.tabWidget.tabBar().findChildren(QToolButton):
            button.setAttribute(Qt.WA_NoMousePropagation, True)
            button.setProperty("componentScrollButton", True)
        self.ui.splitter.setStretchFactor(0, 0)
        self.ui.splitter.setStretchFactor(1, 1)
        panel_width = max(self.ui.menu.minimumWidth(), min(330, int(total * .25)))
        self.ui.splitter.setSizes([panel_width, total - panel_width])

    def _style_component_button(self, button):
        button.setObjectName("componentButton")
        button.setMinimumHeight(32)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _prepare_component_palettes(self):
        self.ui.menu.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.tabWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.component_palettes = []
        for page in [self.ui.Puertas, *self.component_tabs.values()]:
            layout = page.layout()
            buttons = []
            while layout.count():
                item = layout.takeAt(0)
                if isinstance(item.widget(), QPushButton):
                    buttons.append(item.widget())
            layout.setContentsMargins(0, 0, 0, 0)
            scroll = QScrollArea(page)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            palette = ComponentPalette(buttons, scroll)
            scroll.setWidget(palette)
            layout.addWidget(scroll)
            self.component_palettes.append(palette)

    def _bind_component_button(self, button, kind):
        button.setProperty("component_kind", kind)
        button.setCheckable(True)
        button.installEventFilter(self)
        button.clicked.connect(lambda checked=False: self.ui.graphicsView.begin_component_placement(kind))
        self.ui.graphicsView.componentPlacementChanged.connect(
            lambda active: button.setChecked(active == kind))

    def def_buttons(self):
        for tipo, btn_name in [
            ("AND",         "AND"),
            ("OR",          "OR"),
            ("XOR",         "XOR"),
            ("NOT",         "NOT"),
            ("NAND",        "NAND"),
            ("NOR",         "NOR"),
            ("INTERRUPTOR", "INTERRUPTOR"),
            ("BOTON",       "BOTON"),
            ("BOMBILLA",    "BOMBILLA"),
            ("DISPLAY",     "DISPLAY"),
        ]:
            btn = getattr(self.ui, btn_name, None)
            if btn:
                self._style_component_button(btn)
                self._bind_component_button(btn, tipo)
        self.ui.RETARDO = QPushButton(tr("RETARDO"), self.ui.Puertas)
        self._style_component_button(self.ui.RETARDO)
        self.ui.RETARDO.setToolTip(tr("Retrasa una señal; usa Editar para configurar el tiempo y el retraso de cálculo."))
        self.ui.verticalLayout_2.insertWidget(self.ui.verticalLayout_2.count() - 1, self.ui.RETARDO)
        self._bind_component_button(self.ui.RETARDO, "RETARDO")
        self.ui.RELOJ = QPushButton(tr("RELOJ"), self.ui.Puertas)
        self._style_component_button(self.ui.RELOJ)
        self.ui.RELOJ.setToolTip(tr("Genera una señal cuadrada periódica; clic derecho para ajustar el intervalo."))
        self.ui.verticalLayout_2.insertWidget(self.ui.verticalLayout_2.count() - 1, self.ui.RELOJ)
        self._bind_component_button(self.ui.RELOJ, "RELOJ")
        self.ui.BOTON = QPushButton(tr("BOTÓN"), self.ui.Puertas)
        self._style_component_button(self.ui.BOTON)
        self.ui.BOTON.setToolTip(tr("Activa la salida solo mientras mantienes pulsado el componente."))
        self.ui.verticalLayout_2.insertWidget(self.ui.verticalLayout_2.count() - 1, self.ui.BOTON)
        self._bind_component_button(self.ui.BOTON, "BOTON")
        for kind, title, tooltip in (
                ("BUS_ENTRADA", "ENTRADA BUS", tr("Introduce un valor entero de 2 a 32 bits.")),
                ("BUS_LAMP", "SALIDA BUS", tr("Muestra el valor decimal y hexadecimal de un bus.")),
                ("BUS_VISOR", "VISOR DE BUS", tr("Se adapta a un bit o un bus y muestra la señal sin cambiarla.")),
                ("SPLITTER", "SPLITTER", tr("Separa un bus en bits; el bit 0 aparece arriba.")),
                ("COMBINER", "COMBINER", tr("Combina entradas escalares en un bus; el bit 0 aparece arriba.")),
                ("TRIESTADO", "TRI-STATE", tr("Con enable activo conduce el bus; desactivado deja la salida en Z."))):
            button = QPushButton(tr(title), self.ui.Puertas)
            self._style_component_button(button)
            button.setToolTip(tr(tooltip))
            self.ui.verticalLayout_2.insertWidget(self.ui.verticalLayout_2.count() - 1, button)
            self._bind_component_button(button, kind)

        self.component_tabs = {}
        for title, label, kinds in (
                ("Aritmética y selección", "Aritmética",
                 ("SUMADOR", "SUMA_RESTA", "COMPARADOR", "ALU", "MUX", "DEMUX", "DECODIFICADOR", "BCD7")),
                ("Memoria y registros", "Memoria", ("RAM", "ROM", "CONTADOR", "REG_DESPLAZAMIENTO")),
                ("Entradas y salidas", "E/S",
                 ("DIP", "TECLADO_HEX", "CONSTANTE", "PULL_UP", "PULL_DOWN", "LED_BAR", "DISPLAY_NUMERICO", "LED_MATRIX", "LED_RGB", "SEMAFORO", "SONIDO"))):
            page = QWidget(self.ui.tabWidget)
            layout = QVBoxLayout(page)
            layout.setContentsMargins(10, 10, 10, 10)
            self.component_tabs[label] = page
            for kind in kinds:
                button = QPushButton(tr(COMPONENTS[kind].title), page)
                button.setProperty("component_kind", kind)
                self._style_component_button(button)
                self._bind_component_button(button, kind)
                layout.addWidget(button)
            layout.addStretch()
            index = self.ui.tabWidget.insertTab(self.ui.tabWidget.indexOf(self.ui.tab_2), page, tr(label))
            self.ui.tabWidget.setTabToolTip(index, tr(title))

    # ── Creación de widgets ──────────────────────────────────────────────────

    def _create_component(self, tipo, data, widget_id):
        """Construct a component without touching the active scene or timers."""
        if tipo == "MODULO":
            new_widg = wdg.Module(widget_id, data.get("name", "Módulo"),
                                   int(data.get("inputs", 1)), int(data.get("outputs", 1)),
                                   data.get("truth_table", []),
                                   data.get("input_numbers"), data.get("output_numbers"),
                                   data.get("stateful_circuit"), data.get("stateful_state"),
                                   data.get("input_labels"), data.get("output_labels"),
                                   data.get("input_widths"), data.get("output_widths"))
            new_widg.set_delay(data.get("delay_ms", new_widg.delay_ms))
            new_widg.set_delay_gates(data.get("delay_gates", 0))
            new_widg.module_source = data.get("source", "")
            module_path = data.get("module_path")
            if module_path and Path(module_path).parent.name.casefold() == LEGACY_CI_LIBRARY_DIR.name.casefold():
                migrated_path = CI_LIBRARY_DIR / Path(module_path).name
                if migrated_path.exists():
                    module_path = str(migrated_path)
            if module_path and not Path(module_path).exists():
                filename = Path(module_path).name
                relocated = next(
                    (candidate for candidate in CI_LIBRARY_DIR.rglob(filename)
                     if candidate.is_file()),
                    None,
                )
                if relocated is not None:
                    module_path = str(relocated)
            new_widg.module_path = module_path
            new_graph = gra.ModuleGraphic(new_widg)
            new_graph.set_appearance(data.get("appearance", {}))
        else:
            if tipo not in self.WIDGET_DEFS:
                raise ValueError(tr('Componente desconocido: {v0}', v0=tipo))
            cls_widg, cls_graph, svg_path, scale = self.WIDGET_DEFS[tipo]
            if issubclass(cls_widg, Native):
                new_widg = cls_widg(widget_id, width=int(data.get("bus_width", 8)),
                                    address_bits=int(data.get("address_bits", 4)),
                                    channels=int(data.get("channels", 4)))
                new_widg.restore_native(data)
                # Set visible outputs without sampling a synthetic clock edge.
                new_widg.enter = new_widg.default_input_values()
                if not new_widg.sequential:
                    new_widg.logic()
                else:
                    new_widg.exit[0] = new_widg.value if not new_widg.configurable_address else 0
            elif issubclass(cls_widg, (wdg.BusInput, wdg.BusLamp, wdg.BusViewer, wdg.Splitter,
                                     wdg.Combiner, wdg.TriState)):
                new_widg = cls_widg(widget_id, int(data.get("bus_width", 8)),
                                    int(data.get("bus_value", 0))) if issubclass(cls_widg, wdg.BusInput) else \
                           cls_widg(widget_id, int(data.get("bus_width", 1 if cls_widg is wdg.BusViewer else 8)))
            else:
                new_widg = cls_widg(widget_id)
            if isinstance(new_widg, LEDMatrix) and "matrix_rows" in data:
                new_widg.set_dimensions(data["matrix_rows"], data.get("matrix_columns", new_widg.columns))
            if new_widg.can_set_enter() and "inputs" in data:
                new_widg.set_enter(int(data["inputs"]))
            if new_widg.can_set_exit() and "outputs" in data:
                new_widg.set_exit(int(data["outputs"]))
            new_widg.set_delay(data.get("delay_ms", new_widg.delay_ms))
            new_widg.set_delay_gates(data.get("delay_gates", 0))
            if isinstance(new_widg, wdg.BusViewer):
                new_widg.delay_ms = 0
            if isinstance(new_widg, wdg.Bulb):
                new_widg.bulb_color = data.get("bulb_color")
            elif isinstance(new_widg, wdg.Display):
                colors = data.get("segment_colors", [None] * 7)
                new_widg.segment_colors = (list(colors) + [None] * 7)[:7]
            if isinstance(new_widg, wdg.Clock):
                new_widg.set_interval(int(data.get("interval_ms", new_widg.interval_ms)))
            if isinstance(new_widg, wdg.BusInput):
                new_widg.set_bus(int(data.get("bus_width", new_widg.width)),
                                 int(data.get("bus_value", new_widg.value)))
            if isinstance(new_widg, wdg.Button):
                # Buttons are momentary inputs. A stale pressed state must
                # never be restored when a saved project is reopened.
                new_widg.state = False
                new_widg.exit[0] = False
            elif isinstance(new_widg, (wdg.Switch, wdg.Clock)):
                new_widg.state = bool(data.get("state", False))
                new_widg.exit[0] = new_widg.state
            new_graph = cls_graph(new_widg) if cls_graph else gra.Graphic(new_widg, svg_path, scale)

        has_saved_logic_state = "logic_inputs" in data or "logic_outputs" in data
        if has_saved_logic_state:
            saved_inputs = data.get("logic_inputs", [])
            saved_outputs = data.get("logic_outputs", [])
            if isinstance(saved_inputs, list):
                values = (saved_inputs + [0] * len(new_widg.enter))[:len(new_widg.enter)]
                new_widg.enter = [wdg.normalize_logic_value(value, new_widg.input_widths[index])
                                  for index, value in enumerate(values)]
            if isinstance(saved_outputs, list):
                values = (saved_outputs + [0] * len(new_widg.exit))[:len(new_widg.exit)]
                if isinstance(new_widg, wdg.Button):
                    # Ignore legacy project files that serialized a held
                    # mouse button as live simulation state.
                    values = [False] * len(new_widg.exit)
                new_widg.exit = [wdg.normalize_logic_value(value, new_widg.output_widths[index])
                                 for index, value in enumerate(values)]
        new_widg._has_saved_logic_state = has_saved_logic_state
        return new_widg, new_graph

    def crear_widget(self, tipo: str, position=None, data: dict | None = None, *, _prepared=None):
        """Crea un componente y devuelve su representación gráfica."""
        data = data or {}
        widget_id = int(data.get("id", self.next_id))
        new_widg, new_graph = _prepared or self._create_component(tipo, data, widget_id)

        if "truth_table_number" in data and data["truth_table_number"] is not None:
            new_widg.truth_table_number = int(data["truth_table_number"])
        elif isinstance(new_widg, (wdg.Switch, wdg.Button, wdg.Clock)):
            existing = [getattr(widget, "truth_table_number", -1)
                        for widget in self.all_widgets.values()
                        if isinstance(widget, (wdg.Switch, wdg.Button, wdg.Clock))]
            new_widg.truth_table_number = max(existing, default=-1) + 1
        elif isinstance(new_widg, (wdg.Bulb, wdg.Display)):
            existing = [getattr(widget, "truth_table_number", -1)
                        for widget in self.all_widgets.values()
                        if isinstance(widget, (wdg.Bulb, wdg.Display))]
            new_widg.truth_table_number = max(existing, default=-1) + 1
        else:
            new_widg.truth_table_number = widget_id

        self.ui.graphicsView.scene.addItem(new_graph)
        if position is None:
            position = self.ui.graphicsView.mapToScene(self.ui.graphicsView.viewport().rect().center())
        new_graph.setPos(position)
        new_graph.set_orientation(data.get("rotation", 0), data.get("mirrored", False))
        self.all_widgets[widget_id] = new_widg
        self.all_graphics[widget_id] = new_graph
        self.next_id = max(self.next_id, widget_id + 1)
        if isinstance(new_widg, wdg.Clock):
            self.ui.graphicsView.sync_clock_timers()
        return new_graph

    def type_for_widget(self, widget) -> str:
        if isinstance(widget, wdg.Module):
            return "MODULO"
        for name, (klass, *_rest) in self.WIDGET_DEFS.items():
            if type(widget) is klass:
                return name
        raise ValueError(tr('Tipo no serializable: {v0}', v0=type(widget).__name__))

    # ── Panel lateral ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updt_button()

    def updt_button(self):
        self.ui.close.raise_()

    def check_widg_panel(self, pos, index):
        self.updt_button()

    def cerrar_widg_panel(self):
        self.ui.menu.hide()
        self.ui.splitter.setSizes([0, self.ui.splitter.width()])
        self.ui.Show.show()

    def devolver_widg_panel(self):
        total    = self.ui.splitter.width()
        left_min = self.ui.menu.minimumWidth()
        self.ui.splitter.setSizes([left_min, total - left_min])
        self.ui.menu.show()
        self.ui.Show.hide()
        self.ui.close.show()

    # ── Acciones de menú ─────────────────────────────────────────────────────

    def def_actions(self):
        self.ui.actionAbrir.triggered.connect(self.abrir_archivo)
        self.ui.actionCerrar.triggered.connect(self.cerrar_proj)
        self.ui.actionConfiguracion.triggered.connect(self.configure)
        self.ui.actionExportar.triggered.connect(self.exportar)
        self.ui.actionImprimir.setShortcut("")
        self.ui.actionExportar.setShortcut("Ctrl+P")
        self.ui.actionGuardar.setShortcuts(["Ctrl+S", "Ctrl+G"])
        self.ui.actionGuardar.triggered.connect(self.guardar)
        self.ui.actionGuardar_Como.triggered.connect(self.guardarcomo)
        self.ui.actionImprimir.triggered.connect(self.imprimir)
        self.ui.actionNuevo.triggered.connect(self.nuevo)
        self.ui.actionRecientes.triggered.connect(self.recientes)
        self.ui.actionSalir.triggered.connect(self.salir_app)
        self.ui.actionCopiar.triggered.connect(self.copiar)
        self.ui.actionCortar.triggered.connect(self.cortar)
        self.ui.actionPegar.triggered.connect(self.pegar)
        self.actionDuplicar = QAction(tr("Duplicar"), self.ui.graphicsView)
        self.actionDuplicar.setShortcut("Ctrl+D")
        self.actionDuplicar.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.ui.graphicsView.addAction(self.actionDuplicar)
        self.ui.menuEditar.addAction(self.actionDuplicar)
        self.actionDuplicar.triggered.connect(self.duplicar)
        self.ui.actionSobre_Nosotros.triggered.connect(self.about)
        self.ui.actionSobre_Nosotros_2.triggered.connect(self.about)
        self.ui.actionTutorial.triggered.connect(self.tutorial)
        self.ui.actionGuardar_CI.triggered.connect(self.crear_modulo)
        self.ui.actionCargar_CI.triggered.connect(self.cargar_modulo)
        self.ui.menuWidgets.removeAction(self.ui.actionCrear_Seccion)
        self.actionCalcularTabla = QAction(tr("Calcular tabla de verdad"), self)
        self.actionCalcularTabla.setShortcut("Ctrl+Shift+F")
        self.actionCalcularTabla.triggered.connect(self.calcular_tabla_verdad)
        self.ui.menuWidgets.addSeparator()
        self.ui.menuWidgets.addAction(self.actionCalcularTabla)
        self.actionDiagnosticar = QAction(tr("Comprobar circuito…"), self)
        self.actionDiagnosticar.setShortcut("F7")
        self.actionDiagnosticar.triggered.connect(self.comprobar_circuito)
        self.ui.menuWidgets.addAction(self.actionDiagnosticar)
        self.actionManual = QAction(tr("Manual de DaLogic…"), self)
        self.actionManual.setShortcut("F1")
        self.actionManual.triggered.connect(self.mostrar_manual)
        self.ui.menuAyuda.addAction(self.actionManual)
        self.actionUpdateNotifications = QAction(tr("Avisar de actualizaciones"), self)
        self.actionUpdateNotifications.setCheckable(True)
        self.actionUpdateNotifications.setChecked(self.config.get("update_notifications", True))
        self.actionUpdateNotifications.setToolTip(tr("Activa o desactiva la consulta y los avisos de nuevas versiones al iniciar."))
        self.actionUpdateNotifications.toggled.connect(self._set_update_notifications)
        self.ui.menuAyuda.addSeparator()
        self.ui.menuAyuda.addAction(self.actionUpdateNotifications)
        self.actionDeshacer = QAction(tr("Deshacer"), self)
        self.actionDeshacer.setShortcut("Ctrl+Z")
        self.actionDeshacer.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.actionDeshacer.triggered.connect(self.deshacer)
        self.actionRehacer = QAction(tr("Rehacer"), self)
        self.actionRehacer.setShortcut("Ctrl+Y")
        self.actionRehacer.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.actionRehacer.triggered.connect(self.rehacer)
        self.ui.menuEditar.insertAction(self.ui.menuEditar.actions()[0]
                                        if self.ui.menuEditar.actions() else None,
                                        self.actionDeshacer)
        self.ui.menuEditar.insertAction(self.ui.menuEditar.actions()[1]
                                        if len(self.ui.menuEditar.actions()) > 1 else None,
                                        self.actionRehacer)

    def _set_update_notifications(self, enabled):
        previous = self.config.get("update_notifications", True)
        self.config["update_notifications"] = bool(enabled)
        try:
            write_json_atomic(USER_DIR / "config.json", self.config)
        except OSError as error:
            self.config["update_notifications"] = previous
            self.actionUpdateNotifications.blockSignals(True)
            self.actionUpdateNotifications.setChecked(previous)
            self.actionUpdateNotifications.blockSignals(False)
            self.statusBar().showMessage(tr("No se pudieron guardar las preferencias: {v0}", v0=error), 6000)
            return
        self.statusBar().showMessage(tr("Avisos de actualización activados." if enabled else "Avisos de actualización desactivados."), 4000)
        if enabled:
            QTimer.singleShot(0, lambda: comprobar_actualizaciones(self))

    def _preparar_interfaz_profesional(self):
        """Mantiene solo acciones útiles y ofrece los atajos visibles de uso diario."""
        # Configuración e impresión no tenían efecto real; se eliminan en vez de
        # presentar promesas vacías al usuario.
        self.ui.menuArchivo.removeAction(self.ui.actionConfiguracion)
        self.ui.menuArchivo.removeAction(self.ui.actionImprimir)
        self.ui.menuArchivo.removeAction(self.ui.actionSobre_Nosotros)

        self.actionTema = QAction(tr("Tema oscuro"), self)
        self.actionTema.setCheckable(True)
        self.actionTema.setShortcut("Ctrl+Shift+T")
        self.actionTema.setChecked(self.theme_mode == "dark")
        self.actionTema.toggled.connect(lambda dark: self.aplicar_tema("dark" if dark else "light"))
        self.actionAjustarVista = QAction(tr("Ajustar"), self)
        self.actionAjustarVista.setShortcut("Ctrl+0")
        self.actionAjustarVista.triggered.connect(self.ajustar_vista)
        self.actionZoomIn = QAction(tr("Acercar"), self.ui.graphicsView)
        self.actionZoomIn.setShortcut("Ctrl++")
        self.actionZoomIn.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.actionZoomIn.triggered.connect(lambda: self.ui.graphicsView.zoom_by_factor(1.25))
        self.ui.graphicsView.addAction(self.actionZoomIn)
        self.actionZoomOut = QAction(tr("Alejar"), self.ui.graphicsView)
        self.actionZoomOut.setShortcut("Ctrl+-")
        self.actionZoomOut.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.actionZoomOut.triggered.connect(lambda: self.ui.graphicsView.zoom_by_factor(1 / 1.25))
        self.ui.graphicsView.addAction(self.actionZoomOut)
        self.actionPausarRelojes = QAction(tr("Pausar relojes"), self)
        self.actionPausarRelojes.setCheckable(True)
        self.actionPausarRelojes.setShortcut("F6")
        self.actionPausarRelojes.setToolTip(
            tr("Pausa o reanuda todos los relojes del circuito (F6)."))
        self.actionPausarRelojes.toggled.connect(
            self.ui.graphicsView.set_clocks_paused)
        self.actionEliminar = QAction(tr("Eliminar selección"), self)
        self.actionEliminar.setShortcuts(["Delete", "Backspace"])
        self.actionEliminar.triggered.connect(self.eliminar_seleccion)
        self.ui.menuEditar.addAction(self.actionEliminar)

        self.menuVer = ShortcutMenu(tr("Ver"), self)
        self.menuBar().addMenu(self.menuVer)
        self.menuTema = self.menuVer.addMenu(tr("Tema"))
        self.menuTema.menuAction().shortcut_hint_source = self.actionTema
        self.theme_group = QActionGroup(self)
        self.theme_actions = {}
        for mode, title in (("light", "Claro"), ("dark", "Oscuro")):
            action = self.menuTema.addAction(tr(title))
            action.setCheckable(True)
            action.setChecked(self.theme_mode == mode)
            self.theme_group.addAction(action)
            action.triggered.connect(lambda checked=False, mode=mode: self.aplicar_tema(mode))
            self.theme_actions[mode] = action
        self.addAction(self.actionTema)
        self.menuIdioma = self.menuVer.addMenu(tr("Idioma"))
        self.menuVer.addAction(self.actionZoomIn)
        self.menuVer.addAction(self.actionZoomOut)
        self.menuVer.addAction(self.actionAjustarVista)
        self.menuSimulacion = ShortcutMenu(tr("Simulación"), self)
        self.menuBar().addMenu(self.menuSimulacion)
        self.menuBar().insertMenu(self.ui.menuWidgets.menuAction(), self.menuVer)
        self.menuBar().insertMenu(self.ui.menuWidgets.menuAction(), self.menuSimulacion)
        self.menuSimulacion.addAction(self.actionPausarRelojes)
        self.actionPausarSimulacion = QAction(tr("Pausar simulación"), self)
        self.actionPausarSimulacion.setCheckable(True)
        self.actionPausarSimulacion.setShortcut("F8")
        self.actionPausarSimulacion.toggled.connect(self.ui.graphicsView.set_simulation_paused)
        self.actionPaso = QAction(tr("Avanzar un paso"), self)
        self.actionPaso.setShortcut("F10")
        self.actionPaso.triggered.connect(self.ui.graphicsView.step_simulation)
        self.actionBreakpoint = QAction(tr("Alternar punto de parada"), self)
        self.actionBreakpoint.setCheckable(True)
        self.actionBreakpoint.setShortcut("F9")
        self.actionBreakpoint.setToolTip(tr(
            "Selecciona componentes con entradas y pulsa F9 para añadir o quitar su marca roja. "
            "La simulación se pausa cuando cambia una entrada. F10 avanza un paso; F8 continúa."))
        self.actionBreakpoint.triggered.connect(self.alternar_puntos_parada)
        self.ui.graphicsView.scene.selectionChanged.connect(self._update_breakpoint_action)
        self.menuSimulacion.setToolTipsVisible(True)
        for action in (self.actionPausarSimulacion, self.actionPaso, self.actionBreakpoint):
            self.menuSimulacion.addAction(action)
        try:
            self.ui.graphicsView.probe_history_limit = max(256, min(100000, int(self.config.get("probe_history_limit", 10000))))
        except (ValueError, TypeError):
            self.ui.graphicsView.probe_history_limit = 10000
        self.probesDock = ProbeDock(self.ui.graphicsView, self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.probesDock)
        self.probesDock.hide()
        self.menuSimulacion.addAction(self.probesDock.toggleViewAction())
        self.visualDock = VisualDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.visualDock)
        self.visualDock.hide()
        self.fitMenu = QMenu(self)
        self.fitMenu.aboutToShow.connect(self._refresh_fit_menu)
        self.ui.graphicsView.scene.changed.connect(self._refresh_fit_menu)
        self.actionGridVisible = QAction(tr("Mostrar rejilla"), self)
        self.actionGridVisible.setCheckable(True)
        self.actionGridVisible.setChecked(bool(self.config.get("show_grid", True)))
        self.actionGridVisible.toggled.connect(self._toggle_grid)
        self.actionSnapGrid = QAction(tr("Ajustar a rejilla"), self)
        self.actionSnapGrid.setCheckable(True)
        self.actionSnapGrid.setChecked(bool(self.config.get("snap_to_grid", False)))
        self.actionSnapGrid.toggled.connect(self._toggle_snap_grid)
        self.actionOrthogonalWires = QAction(tr("Cables en ángulo recto"), self)
        self.actionOrthogonalWires.setCheckable(True)
        self.actionOrthogonalWires.setChecked(bool(self.config.get("orthogonal_wires", False)))
        self.actionOrthogonalWires.toggled.connect(self._toggle_orthogonal_wires)
        self.menuVer.addSeparator()
        self.menuVer.addAction(self.actionGridVisible)
        self.menuVer.addAction(self.actionSnapGrid)
        self.menuVer.addAction(self.actionOrthogonalWires)
        board = self.ui.graphicsView
        board.grid_visible = self.actionGridVisible.isChecked()
        board.snap_to_grid = self.actionSnapGrid.isChecked()
        board.orthogonal_wires = self.actionOrthogonalWires.isChecked()
        board.viewport().update()

        self.actionRotate = QAction(tr("Rotar 90°"), self.ui.graphicsView)
        self.actionRotate.setShortcut("R")
        self.actionRotate.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.ui.graphicsView.addAction(self.actionRotate)
        self.actionRotate.triggered.connect(lambda: self._transform_selection("rotate"))
        self.actionMirror = QAction(tr("Espejo horizontal"), self.ui.graphicsView)
        self.actionMirror.setShortcut("H")
        self.actionMirror.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.ui.graphicsView.addAction(self.actionMirror)
        self.actionMirror.triggered.connect(lambda: self._transform_selection("mirror"))
        self.actionAlign = QAction(tr("Alinear selección…"), self)
        self.actionAlign.setShortcut("Ctrl+Shift+A")
        self.actionAlign.triggered.connect(self._align_selection)
        self.actionDistribute = QAction(tr("Distribuir selección…"), self)
        self.actionDistribute.setShortcut("Ctrl+Shift+D")
        self.actionDistribute.triggered.connect(self._distribute_selection)
        self.actionHistoryLimit = QAction(tr("Límite de deshacer…"), self)
        self.actionHistoryLimit.triggered.connect(self._configure_history_limit)
        self.ui.menuEditar.addSeparator()
        for action in (self.actionRotate, self.actionMirror, self.actionAlign,
                       self.actionDistribute, self.actionHistoryLimit):
            self.ui.menuEditar.addAction(action)

        self.action_bar = ActionBar(self.ui.centralwidget)
        actions_layout = self.action_bar.layout()
        self.action_buttons = []
        for action in (self.ui.actionNuevo, self.ui.actionAbrir, self.ui.actionGuardar,
                       self.ui.actionCopiar, self.ui.actionPegar, self.actionEliminar):
            button = QToolButton(self.action_bar)
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            actions_layout.addWidget(button)
            self.action_buttons.append(button)
        self.fitButton = QToolButton(self)
        self.fitButton.setText(tr("Ajustar a circuito"))
        self.fitButton.setToolTip(tr("Ajustar a circuito · Ctrl+0 encuadra todo"))
        self.fitButton.clicked.connect(lambda: self.ajustar_vista() if not self.visual_planes() else None)
        actions_layout.addWidget(self.fitButton)
        for action in (self.visualDock.toggleViewAction(),):
            button = QToolButton(self.action_bar)
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            actions_layout.addWidget(button)
            self.action_buttons.append(button)
        self._refresh_fit_menu()
        self.ui.centralwidget.layout().insertWidget(0, self.action_bar)
        self.language_combo = QComboBox(self)
        self.language_combo.setObjectName("languageSelector")
        self.language_combo.setToolTip(tr("Seleccionar idioma"))
        self.language_combo.hide()
        self.statusBar().showMessage(tr("Listo · rueda: zoom · botón central: desplazar"), 5000)

    def _save_editor_preferences(self):
        self.config.update({
            "show_grid": self.ui.graphicsView.grid_visible,
            "snap_to_grid": self.ui.graphicsView.snap_to_grid,
            "orthogonal_wires": self.ui.graphicsView.orthogonal_wires,
            "history_limit": self.history_limit,
        })
        try:
            write_json_atomic(USER_DIR / "config.json", self.config)
        except OSError as exc:
            self.statusBar().showMessage(tr('No se pudieron guardar las preferencias: {v0}', v0=exc), 6000)

    def alternar_puntos_parada(self):
        board = self.ui.graphicsView
        identifiers = {graphic.widg.id for graphic in self._selected_graphics()
                       if graphic.widg.enter}
        if not identifiers:
            self._update_breakpoint_action()
            self.statusBar().showMessage(tr(
                "Selecciona una puerta, un módulo o una salida con entradas y pulsa F9. "
                "Los interruptores y relojes no reciben señales de entrada."), 8000)
            return
        if identifiers.issubset(board._breakpoints):
            board._breakpoints.difference_update(identifiers)
            board._breakpoint_hits.difference_update(identifiers)
        else:
            board._breakpoints.update(identifiers)
        board.refresh_breakpoint_markers()
        self.statusBar().showMessage(tr(
            "{v0} puntos de parada activos (marca roja). Se pausará al cambiar una entrada. "
            "F9 quita la marca; F10 avanza; F8 continúa.", v0=len(board._breakpoints)), 8000)

    def _update_breakpoint_action(self):
        action = getattr(self, "actionBreakpoint", None)
        if action is None:
            return
        identifiers = {graphic.widg.id for graphic in self._selected_graphics()
                       if graphic.widg.enter}
        marked = bool(identifiers) and identifiers.issubset(self.ui.graphicsView._breakpoints)
        action.setChecked(marked)
        action.setText(tr("Quitar punto de parada" if marked else
                          "Añadir punto de parada" if identifiers else "Alternar punto de parada"))

    def mostrar_punto_parada(self, identifiers):
        board = self.ui.graphicsView
        board.refresh_breakpoint_markers()
        graphic = self.all_graphics.get(min(identifiers))
        if graphic is not None:
            board.ensureVisible(graphic, 48, 48)
        self.statusBar().showMessage(tr(
            "Pausa en componentes {v0}: cambió una entrada. Marca naranja. "
            "F10 avanza un paso; F8 continúa; F9 quita la marca de la selección.",
            v0=", ".join(map(str, sorted(identifiers)))))

    def _toggle_grid(self, visible):
        self.ui.graphicsView.grid_visible = bool(visible)
        self.ui.graphicsView.viewport().update()
        self._save_editor_preferences()

    def _toggle_snap_grid(self, enabled):
        self.ui.graphicsView.snap_to_grid = bool(enabled)
        self._save_editor_preferences()

    def _toggle_orthogonal_wires(self, enabled):
        self.ui.graphicsView.orthogonal_wires = bool(enabled)
        for item in self.ui.graphicsView.scene.items():
            if isinstance(item, Wire):
                item.update_path()
        self._save_editor_preferences()

    def _transform_selection(self, operation):
        selected = self._selected_graphics()
        if not selected:
            self.statusBar().showMessage(tr("Selecciona uno o varios componentes primero."), 3500)
            return
        for graphic in selected:
            rotation = graphic.rotation_degrees
            mirrored = graphic.mirrored
            if operation == "rotate":
                rotation = (rotation + 90) % 360
            else:
                mirrored = not mirrored
            graphic.set_orientation(rotation, mirrored)

    def _align_selection(self):
        selected = self._selected_graphics()
        if len(selected) < 2:
            self.statusBar().showMessage(tr("Selecciona al menos dos componentes para alinear."), 3500)
            return
        options = ["Izquierda", "Centro horizontal", "Derecha", "Arriba",
                   "Centro vertical", "Abajo"]
        choice, accepted = QInputDialog.getItem(self, "Alinear selección",
                                                 "Alinear por:", options, 0, False)
        if not accepted:
            return
        rects = [item.sceneBoundingRect() for item in selected]
        left, right = min(r.left() for r in rects), max(r.right() for r in rects)
        top, bottom = min(r.top() for r in rects), max(r.bottom() for r in rects)
        center_x, center_y = (left + right) / 2, (top + bottom) / 2
        for item, rect in zip(selected, rects):
            if choice == "Izquierda": dx, dy = left - rect.left(), 0
            elif choice == "Centro horizontal": dx, dy = center_x - rect.center().x(), 0
            elif choice == "Derecha": dx, dy = right - rect.right(), 0
            elif choice == "Arriba": dx, dy = 0, top - rect.top()
            elif choice == "Centro vertical": dx, dy = 0, center_y - rect.center().y()
            else: dx, dy = 0, bottom - rect.bottom()
            item.setPos(item.pos().x() + dx, item.pos().y() + dy)

    def _distribute_selection(self):
        selected = self._selected_graphics()
        if len(selected) < 3:
            self.statusBar().showMessage(tr("Selecciona al menos tres componentes para distribuir."), 3500)
            return
        options = ["Horizontal", "Vertical"]
        choice, accepted = QInputDialog.getItem(self, "Distribuir selección",
                                                 "Dirección:", options, 0, False)
        if not accepted:
            return
        horizontal = choice == "Horizontal"
        ordered = sorted(selected, key=lambda item: item.sceneBoundingRect().center().x()
                         if horizontal else item.sceneBoundingRect().center().y())
        rects = [item.sceneBoundingRect() for item in ordered]
        if horizontal:
            start = rects[0].center().x()
            end = rects[-1].center().x()
            step = (end - start) / (len(ordered) - 1)
            for index, (item, rect) in enumerate(zip(ordered, rects)):
                item.setX(item.x() + (start + step * index - rect.center().x()))
        else:
            start = rects[0].center().y()
            end = rects[-1].center().y()
            step = (end - start) / (len(ordered) - 1)
            for index, (item, rect) in enumerate(zip(ordered, rects)):
                item.setY(item.y() + (start + step * index - rect.center().y()))

    def _configure_history_limit(self):
        value, accepted = QInputDialog.getInt(self, "Historial de edición",
            tr("Número máximo de pasos para deshacer:"), self.history_limit, 10, 1000, 10)
        if accepted:
            self.history_limit = value
            del self._undo_history[:-self.history_limit]
            self._update_history_actions()
            self._save_editor_preferences()
            self.statusBar().showMessage(tr('Historial limitado a {v0} pasos.', v0=value), 3000)

    def refresh_probes(self):
        if hasattr(self, "probesDock"):
            self.probesDock.panel.refresh()

    def update_probe_plot(self):
        if hasattr(self, "probesDock"):
            timer = self.probesDock.panel.plot.refresh_timer
            if self.ui.graphicsView._clocks_paused:
                timer.stop()
            elif not timer.isActive():
                timer.start(250)
            self.probesDock.panel.plot.update()

    def _save_language_catalog(self, path, catalog):
        try:
            write_json_atomic(path, catalog)
        except OSError as exc:
            self.statusBar().showMessage(tr('No se pudo actualizar el catálogo de idioma: {v0}', v0=exc), 6000)

    def _language_catalogs(self):
        return load_catalogs(LANGUAGE_DIR)

    def _language_objects(self, root=None):
        root = root or self
        objects = [root]
        if isinstance(root, QWidget):
            objects.extend(root.findChildren(QWidget))
            objects.extend(root.findChildren(QAction))
        seen = set()
        for obj in objects:
            if obj is self.language_combo or id(obj) in seen:
                continue
            seen.add(id(obj))
            yield obj

    def _original_text(self, obj, prop):
        # Editable fields and document bodies belong to the user.
        if prop == "text" and isinstance(obj, QLineEdit):
            return None
        getter = getattr(obj, prop, None)
        if not callable(getter):
            return None
        try:
            value = getter()
        except (RuntimeError, TypeError):
            return None
        if not isinstance(value, str) or not value:
            return None
        if ((isinstance(obj, QAction) and prop == "text") or
                (isinstance(obj, QMenu) and prop == "title")):
            value = value.split("\t", 1)[0]
        saved_name = "_dalogic_original_" + prop
        last_name = "_dalogic_last_" + prop
        if value == getattr(obj, last_name, None):
            return getattr(obj, saved_name, value)
        source = source_text(value)
        setattr(obj, saved_name, source)
        return source

    def _collect_language_defaults(self):
        return dict(self._language_catalogs()["es"]["translations"])

    def _prepare_language_selector(self):
        catalogs = self._language_catalogs()
        self.language_group = QActionGroup(self)
        self.language_actions = {}
        for catalog in sorted(catalogs.values(), key=lambda item: item["code"]):
            self.language_combo.addItem(catalog["name"], catalog["code"])
            action = self.menuIdioma.addAction(catalog["name"])
            action.setCheckable(True)
            self.language_group.addAction(action)
            self.language_actions[catalog["code"]] = action
            action.triggered.connect(lambda checked=False, code=catalog["code"]:
                self.language_combo.setCurrentIndex(self.language_combo.findData(code)))
        selected = str(self.config.get("lang", "es"))
        index = self.language_combo.findData(selected)
        if index < 0:
            index = self.language_combo.findData("es")
        self.language_combo.setCurrentIndex(max(0, index))
        self.language_combo.currentIndexChanged.connect(self._select_language)
        self.language_catalogs = catalogs
        self.app.installEventFilter(self)

    def _localized_window_title(self):
        translations = getattr(self, "language_translations", {})
        translated = translations.get(
            "DaLogic — Sin título", "DaLogic — Sin título")
        if self.project_path is None:
            return translated
        prefix = translations.get("DaLogic — ", "DaLogic — ")
        return f"{prefix}{self.project_name}"

    def _apply_saved_language(self):
        code = self.language_combo.currentData() or "es"
        self._apply_language(str(code), persist=False)

    def _select_language(self, index):
        code = self.language_combo.itemData(index)
        if code:
            self._apply_language(str(code), persist=True)

    def _apply_language(self, code, persist=True):
        # Capture current sources before replacing the active language.
        self._apply_language_tree(self)
        catalogs = self._language_catalogs()
        catalog = catalogs.get(code) or catalogs.get("es", {})
        self.language_code = catalog.get("code", "es")
        for language, action in self.language_actions.items():
            action.setChecked(language == self.language_code)
        self.language_translations = catalog.get("translations", {})
        self.language_catalogs = catalogs
        gra.set_language_translations(self.language_translations, self.language_code)
        self._apply_language_tree(self)
        self.actualizar_biblioteca_ci()
        for palette in [*self.component_palettes, self.visualDock.palette]:
            palette._reflow()
        self.probesDock.panel.refresh()
        self._refresh_fit_menu()
        self.ui.graphicsView.refresh_breakpoint_markers()
        self.ui.graphicsView.viewport().update()
        self.statusBar().showMessage(tr("Listo · rueda: zoom · botón central: desplazar"), 4000)
        for item in self.ui.graphicsView.scene.items():
            if isinstance(item, Port):
                item.update_tooltip()
            elif hasattr(item, "_update_bridge_tooltip"):
                item._update_bridge_tooltip()
            elif isinstance(item, Wire):
                item.setToolTip(tr(gra.translate_text("Clic derecho para ver las opciones del cable")))
            if isinstance(item, gra.Graphic):
                item.update()
            if isinstance(item, gra.BulbGraphic):
                item.setToolTip(((tr(gra.translate_text("Bombilla")) + tr(' {v0}', v0=item.widg.id)) + tr(gra.translate_text(" · clic derecho → Editar para ajustar el retardo"))))
        if persist:
            self.config["lang"] = self.language_code
            try:
                write_json_atomic(USER_DIR / "config.json", self.config)
            except OSError:
                pass

    def _apply_language_tree(self, root):
        props = ("text", "windowTitle", "title", "toolTip", "statusTip",
                 "whatsThis", "placeholderText", "accessibleName")
        translations = getattr(self, "language_translations", {})
        for obj in self._language_objects(root):
            for prop in props:
                if obj is self and prop == "windowTitle":
                    obj.setWindowTitle(tr(self._localized_window_title()))
                    continue
                source = self._original_text(obj, prop)
                if source is None:
                    continue
                setter = getattr(obj, "set" + prop[0].upper() + prop[1:], None)
                if callable(setter):
                    try:
                        localized = tr(source)
                        setter(localized)
                        setattr(obj, "_dalogic_last_" + prop, localized)
                    except RuntimeError:
                        pass
            if isinstance(obj, QTabWidget):
                original = getattr(obj, "_dalogic_original_tabs", None)
                if original is None:
                    original = [source_text(obj.tabText(i)) for i in range(obj.count())]
                    obj._dalogic_original_tabs = original
                for i, source in enumerate(original):
                    if i < obj.count():
                        obj.setTabText(i, tr(translations.get(source, source)))
            if isinstance(obj, QComboBox):
                original = getattr(obj, "_dalogic_original_items", None)
                if original is None:
                    original = [source_text(obj.itemText(i)) for i in range(obj.count())]
                    obj._dalogic_original_items = original
                for i, source in enumerate(original):
                    if i < obj.count():
                        obj.setItemText(i, tr(translations.get(source, source)))

    def eventFilter(self, watched, event):
        if (watched is self.ui.tabWidget.tabBar()
                and event.type() in (QEvent.HoverEnter, QEvent.HoverMove)
                and any(button.isVisible() and button.geometry().contains(event.position().toPoint())
                        for button in watched.findChildren(QToolButton))):
            # Windows can deliver a parent hover after the child arrow's Enter
            # (including disabled arrows). Keep that area out of tab hovering.
            hover_leave = QHoverEvent(QEvent.HoverLeave, QPointF(-1, -1),
                                      QPointF(-1, -1), QPointF(-1, -1), Qt.NoModifier)
            self.app.sendEvent(watched, hover_leave)
            return True
        if (isinstance(watched, QToolButton) and watched.property("componentScrollButton")
                and event.type() in (QEvent.Enter, QEvent.HoverEnter, QEvent.HoverMove, QEvent.MouseMove)):
            # Stopping propagation alone leaves QTabBar's previous hoverIndex
            # intact. Explicitly end that hover when entering either arrow.
            hover_leave = QHoverEvent(QEvent.HoverLeave, QPointF(-1, -1),
                                      QPointF(-1, -1), QPointF(-1, -1), Qt.NoModifier)
            self.app.sendEvent(watched.parentWidget(), hover_leave)
        if isinstance(watched, QPushButton) and watched.property("component_kind"):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                watched._placement_drag_start = event.position().toPoint()
            elif (event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.LeftButton and
                  getattr(watched, "_placement_drag_start", None) is not None and
                  (event.position().toPoint() - watched._placement_drag_start).manhattanLength()
                  >= QApplication.startDragDistance()):
                watched._placement_drag_start = None
                watched.setDown(False)
                self.ui.graphicsView.cancel_visual_placement()
                drag = QDrag(watched)
                mime = QMimeData()
                mime.setData("application/x-dalogic-component", watched.property("component_kind").encode())
                drag.setMimeData(mime)
                drag.exec(Qt.CopyAction)
                self.ui.graphicsView.cancel_visual_placement()
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                watched._placement_drag_start = None
        if (event.type() == QEvent.Type.Show and
                hasattr(self, "language_translations") and
                isinstance(watched, QWidget)):
            self._apply_language_tree(watched)
        return super().eventFilter(watched, event)

    def _setup_history(self):
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(300)
        self._history_timer.timeout.connect(self._capture_history_change)
        self.ui.graphicsView.scene.changed.connect(self._schedule_history_capture)
        self._reset_history()

    def _history_state(self):
        project = dump_project(self)
        project.pop("saved_at", None)
        return {
            "data": project,
            "project_path": str(self.project_path) if self.project_path else None,
            "project_name": self.project_name,
            "imported_modules": self.imported_modules,
        }

    @staticmethod
    def _history_key(state):
        # Saving/renaming is not an edit of the circuit and must not become an
        # undo step or make an older step change the document's destination.
        content = {"data": {k: v for k, v in state["data"].items() if k != "name"},
                   "imported_modules": state.get("imported_modules", [])}
        return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _project_content_key(self):
        project = dump_project(self)
        project.pop("saved_at", None)
        return json.dumps(project, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _reset_history(self):
        if hasattr(self, "_history_timer"):
            self._history_timer.stop()
        self._undo_history = []
        self._redo_history = []
        self._history_snapshot_json = self._history_key(self._history_state())
        self.history_limit = max(10, min(1000, int(self.config.get("history_limit", 100))))
        self._document_saved_key = self._project_content_key()
        self._update_document_state()
        self._update_history_actions()

    def _schedule_history_capture(self, *_args):
        if not self._history_restoring and hasattr(self, "_history_timer"):
            self._history_timer.start()
            if hasattr(self, "_document_state_timer"):
                self._document_state_timer.start()

    def _capture_history_change(self):
        if self._history_restoring:
            return
        state = self._history_state()
        key = self._history_key(state)
        if key == self._history_snapshot_json:
            return
        previous = json.loads(self._history_snapshot_json)
        self._undo_history.append(previous)
        del self._undo_history[:-self.history_limit]
        self._redo_history.clear()
        self._history_snapshot_json = key
        self._update_document_state()
        self._update_history_actions()

    def _is_document_dirty(self):
        if self._document_saved_key is None:
            return False
        return self._project_content_key() != self._document_saved_key

    def _update_document_state(self):
        if not hasattr(self, "ui"):
            return
        dirty = self._is_document_dirty()
        base = self._localized_window_title()
        self.setWindowTitle((("● " if dirty else "") + tr(base)))
        if dirty:
            self.statusBar().showMessage(tr("Cambios sin guardar · Ctrl+S para guardar"))
        elif not self._recovery_pending:
            self.statusBar().showMessage(tr("Todos los cambios están guardados"), 2500)

    def _setup_autosave(self):
        self.autosave_path = USER_DIR / "autosave" / "recovery.dalogic"
        self._document_state_timer = QTimer(self)
        self._document_state_timer.setSingleShot(True)
        self._document_state_timer.setInterval(350)
        self._document_state_timer.timeout.connect(self._update_document_state)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(60_000)
        self._autosave_timer.timeout.connect(self._write_autosave)
        self._autosave_timer.start()
        if self._allow_recovery:
            QTimer.singleShot(0, self._offer_autosave_recovery)

    def _discard_autosave(self):
        try:
            self.autosave_path.unlink(missing_ok=True)
        except OSError as exc:
            self.statusBar().showMessage(tr('No se pudo eliminar la copia de recuperación: {v0}', v0=exc), 6000)

    def _write_autosave(self):
        if not self._is_document_dirty():
            return
        try:
            self.autosave_path.parent.mkdir(parents=True, exist_ok=True)
            data = dump_project(self)
            data["_autosave_origin"] = {
                "project_path": str(self.project_path) if self.project_path else None,
                "project_name": self.project_name,
                "saved_at": time.time(),
            }
            write_json_atomic(self.autosave_path, data)
        except (OSError, TypeError, ValueError) as exc:
            self.statusBar().showMessage(tr('No se pudo guardar la recuperación automática: {v0}', v0=exc), 6000)

    def _offer_autosave_recovery(self):
        try:
            if not self.autosave_path.is_file():
                return
            data = json.loads(self.autosave_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != "DaLogic" or not isinstance(data.get("components"), list):
                return
            origin = data.get("_autosave_origin", {})
            if not isinstance(origin, dict):
                return
            original = Path(origin["project_path"]) if origin.get("project_path") else None
            if original and original.exists() and original.stat().st_mtime > self.autosave_path.stat().st_mtime:
                self._discard_autosave()
                return
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        answer = QMessageBox.question(self, tr("Recuperar cambios"),
            tr("DaLogic encontró cambios recuperables de un cierre inesperado. ¿Quieres restaurarlos?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if answer == QMessageBox.StandardButton.Yes:
            self._recovery_pending = True
            if self.cargar_proyecto(self.autosave_path):
                origin = data.get("_autosave_origin", {})
                self.project_path = Path(origin["project_path"]) if origin.get("project_path") else None
                self.project_name = origin.get("project_name") or data.get("name") or "Recuperado"
                self._document_saved_key = ""
                self.statusBar().showMessage(tr("Proyecto recuperado · guarda los cambios para conservarlos"), 8000)
                self._update_document_state()
            self._recovery_pending = False
        else:
            self._discard_autosave()

    def _update_history_actions(self):
        if hasattr(self, "actionDeshacer"):
            self.actionDeshacer.setEnabled(bool(self._undo_history))
            self.actionRehacer.setEnabled(bool(self._redo_history))

    def _restore_history_state(self, state):
        self._history_restoring = True
        try:
            self.cargar_proyecto(_history_state=state)
            self.imported_modules = state.get("imported_modules", [])
            self._history_snapshot_json = self._history_key(self._history_state())
        finally:
            self._history_restoring = False
        self._update_document_state()
        self._update_history_actions()

    def deshacer(self):
        self._history_timer.stop()
        self._capture_history_change()
        if not self._undo_history:
            return
        current = self._history_state()
        target = self._undo_history.pop()
        self._redo_history.append(current)
        self._restore_history_state(target)

    def rehacer(self):
        self._history_timer.stop()
        self._capture_history_change()
        if not self._redo_history:
            return
        current = self._history_state()
        target = self._redo_history.pop()
        self._undo_history.append(current)
        self._restore_history_state(target)

    def _module_definition(self, data):
        definition = module_definition(str(data.get("name", "Módulo")),
            int(data.get("inputs", 1)), int(data.get("outputs", 1)),
            data.get("truth_table", []), int(data.get("delay_ms", 0)),
            data.get("input_numbers"), data.get("output_numbers"),
            data.get("stateful_circuit"), data.get("input_labels"),
            data.get("output_labels"), data.get("input_widths"),
            data.get("output_widths"),
            "1.2" if str(data.get("version", "")) == "1.2" else "auto",
            int(data.get("delay_gates", 0)))
        if "appearance" in data:
            definition["appearance"] = gra.ModuleGraphic.normalize_appearance(data["appearance"])
        return definition

    def _module_signature(self, data):
        definition = self._module_definition(data)
        if definition.get("stateful_circuit"):
            return (definition["name"].casefold(), definition["inputs"],
                    definition["outputs"], tuple(definition["input_numbers"]),
                    tuple(definition["output_numbers"]),
                    tuple(definition.get("input_labels", [])),
                    tuple(definition.get("output_labels", [])),
                    tuple(definition.get("input_widths", [])),
                    tuple(definition.get("output_widths", [])),
                    json.dumps(definition["stateful_circuit"], sort_keys=True,
                               ensure_ascii=False, separators=(",", ":")))
        rows = tuple((tuple(row["inputs"]), tuple(row["outputs"]), row["time_ms"])
                     for row in definition["truth_table"])
        return (definition["name"].casefold(), definition["inputs"],
                definition["outputs"], tuple(definition["input_numbers"]),
                tuple(definition["output_numbers"]),
                tuple(definition.get("input_labels", [])),
                tuple(definition.get("output_labels", [])),
                tuple(definition.get("input_widths", [])),
                tuple(definition.get("output_widths", [])), rows)

    def _read_ci_library(self):
        modules = []
        CI_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        if LEGACY_CI_LIBRARY_DIR.is_dir():
            for old_file in LEGACY_CI_LIBRARY_DIR.iterdir():
                if not old_file.is_file():
                    continue
                destination = CI_LIBRARY_DIR / old_file.name
                suffix = 2
                while destination.exists():
                    destination = CI_LIBRARY_DIR / f"{old_file.stem} (anterior {suffix}){old_file.suffix}"
                    suffix += 1
                old_file.replace(destination)
            if not any(LEGACY_CI_LIBRARY_DIR.iterdir()):
                LEGACY_CI_LIBRARY_DIR.rmdir()
        cache = getattr(self, "_ci_library_cache", {})
        refreshed = {}
        for path in sorted(CI_LIBRARY_DIR.rglob("*.dmodule"), key=lambda item: item.as_posix().casefold()):
            try:
                stat = path.stat()
                signature = (stat.st_mtime_ns, stat.st_size)
                cached = cache.get(path)
                if cached and cached[0] == signature:
                    definition = cached[1]
                else:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    definition = self._module_definition(data) if _supported_dmodule(data) else None
                refreshed[path] = (signature, definition)
                if definition is not None:
                    modules.append((path, definition))
            except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
                continue
        self._ci_library_cache = refreshed
        return modules

    def _preparar_biblioteca_ci(self):
        self._ci_layout = QVBoxLayout(self.ui.tab_2)
        self._ci_layout.setContentsMargins(10, 10, 10, 10)
        self._ci_layout.setSpacing(8)

        self.ci_search = QLineEdit(self.ui.tab_2)
        self.ci_search.setObjectName("ciSearch")
        self.ci_search.setPlaceholderText(tr("Buscar por nombre…"))
        self.ci_search.setClearButtonEnabled(True)
        self.ci_search.setAccessibleName(tr("Buscar circuitos integrados por nombre"))
        self._ci_layout.addWidget(self.ci_search)

        self.ci_new_folder = QPushButton(tr("＋  Nueva carpeta"), self.ui.tab_2)
        self.ci_new_folder.setObjectName("ciNewFolder")
        self.ci_new_folder.setToolTip(tr("Crear una carpeta para organizar los CI"))
        self._ci_layout.addWidget(self.ci_new_folder)

        self.ci_tree = LibraryTree(self.ui.tab_2)
        self.ci_tree.setObjectName("ciLibraryTree")
        self.ci_tree.setHeaderHidden(True)
        self.ci_tree.setIndentation(18)
        self.ci_tree.setAnimated(True)
        self.ci_tree.setUniformRowHeights(True)
        self.ci_tree.setExpandsOnDoubleClick(True)
        self.ci_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ci_tree.setToolTip(tr("Abre las carpetas y pulsa un CI para colocarlo en el tablero"))
        self.ci_tree.itemClicked.connect(self._activate_ci_tree_item)
        self.ci_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ci_tree.customContextMenuRequested.connect(self._show_ci_context_menu)
        self._ci_layout.addWidget(self.ci_tree, 1)
        self._ci_tree_ready = False
        self.ci_search.textChanged.connect(self.actualizar_biblioteca_ci)
        self.ci_new_folder.clicked.connect(self._crear_carpeta_ci)
        self.actualizar_biblioteca_ci()
    def _library_folders(self):
        CI_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        return sorted((path.relative_to(CI_LIBRARY_DIR).as_posix()
                       for path in CI_LIBRARY_DIR.rglob("*") if path.is_dir()),
                      key=str.casefold)

    def _crear_carpeta_ci(self):
        folder, accepted = QInputDialog.getText(
            self, "Nueva carpeta", tr("Nombre o ruta dentro de la Biblioteca:"))
        if not accepted or not folder.strip():
            return
        destination = (CI_LIBRARY_DIR / folder.strip()).resolve()
        if destination == CI_LIBRARY_DIR.resolve() or CI_LIBRARY_DIR.resolve() not in destination.parents:
            QMessageBox.information(self, tr("Ruta no válida"), tr("La carpeta debe estar dentro de la Biblioteca."))
            return
        try:
            destination.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            QMessageBox.information(self, tr("Carpeta existente"), tr("Ya hay una carpeta con ese nombre."))
            return
        except OSError as exc:
            QMessageBox.warning(self, tr("No se pudo crear la carpeta"), tr(str(exc)))
            return
        self.actualizar_biblioteca_ci()
        self.statusBar().showMessage(tr("Carpeta creada en la biblioteca"), 3000)

    def _activate_ci_tree_item(self, item, _column=0):
        metadata = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(metadata, dict) or metadata.get("kind") != "module":
            return
        self._use_ci_module(metadata["module"])

    def _show_ci_context_menu(self, position):
        item = self.ci_tree.itemAt(position)
        metadata = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(metadata, dict) or metadata.get("kind") != "module":
            return
        module_path = metadata.get("path")
        if not module_path:
            return
        menu = QMenu(self.ci_tree)
        rename = menu.addAction(tr("Cambiar nombre…"))
        move_to = menu.addAction(tr("Mover a carpeta…"))
        chosen = menu.exec(self.ci_tree.viewport().mapToGlobal(position))
        if chosen is rename:
            self._rename_ci_module(module_path)
        elif chosen is move_to:
            self._move_ci_to_folder(module_path)

    def _rename_ci_module(self, module_path, new_name=None):
        from project_io import rename_library_module
        try:
            source = Path(module_path).resolve()
            data = json.loads(source.read_text(encoding="utf-8"))
            if new_name is None:
                new_name, accepted = QInputDialog.getText(
                    self, tr("Cambiar nombre del módulo"), "Nuevo nombre:",
                    text=str(data.get("name", source.stem)))
                if not accepted:
                    return False
            destination, definition = rename_library_module(source, new_name, CI_LIBRARY_DIR)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(self, tr("No se pudo cambiar el nombre"), str(error))
            return False
        for widget in self.all_widgets.values():
            if not isinstance(widget, wdg.Module) or not getattr(widget, "module_path", None):
                continue
            if Path(widget.module_path).resolve() == source:
                widget.module_path = str(destination)
                widget.name = definition["name"]
                graphic = self.all_graphics.get(widget.id)
                if graphic:
                    graphic.update()
                    for port in graphic._ports_in + graphic._ports_out:
                        port.update_tooltip()
        self._ci_library_cache = {}
        self.actualizar_biblioteca_ci()
        self._capture_history_change()
        self.statusBar().showMessage(tr("Módulo renombrado: {name}", name=definition["name"]), 4000)
        return True

    def _move_ci_to_folder(self, module_path):
        try:
            source = Path(module_path).resolve()
            relative = source.relative_to(CI_LIBRARY_DIR.resolve())
        except (ValueError, OSError):
            return
        folders = ["Biblioteca (raíz)"] + self._library_folders()
        choices = [folder for folder in folders
                   if folder == "Biblioteca (raíz)" or folder != relative.parent.as_posix()]
        destination_folder, accepted = QInputDialog.getItem(
            self, "Mover CI", "Carpeta de destino:", choices, 0, False,
            literal_items=choices)
        if not accepted:
            return
        parent = (CI_LIBRARY_DIR if destination_folder == "Biblioteca (raíz)"
                  else CI_LIBRARY_DIR / destination_folder)
        destination = parent / source.name
        suffix = 2
        while destination.exists():
            destination = parent / f"{source.stem} ({suffix}){source.suffix}"
            suffix += 1
        try:
            parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
        except OSError as exc:
            QMessageBox.warning(self, tr("No se pudo mover el CI"), tr(str(exc)))
            return
        for widget in self.all_widgets.values():
            if isinstance(widget, wdg.Module) and getattr(widget, "module_path", None):
                try:
                    if Path(widget.module_path).resolve() == source:
                        widget.module_path = str(destination.resolve())
                except OSError:
                    pass
        self.actualizar_biblioteca_ci()

    def _use_ci_module(self, module_data):
        # Insertar un CI no reconstruye el árbol: conserva selección y expansión tal cual.
        self.ui.graphicsView.begin_component_placement("MODULO", module_data)

    @staticmethod
    def _clean_ci_name(name):
        cleaned = re.sub(r"\s*\(\s*(?:[A-Z]{1,4}\s*,\s*)+[A-Z]{1,4}\s*\)\s*$",
                         "", str(name), flags=re.IGNORECASE)
        return cleaned.strip()


    def _ensure_ci_folder_item(self, root, folder_path, folders):
        current = root
        parent_path = ""
        for part in PurePosixPath(folder_path).parts:
            if part in {"", "."}:
                continue
            parent_path = f"{parent_path}/{part}".strip("/")
            if parent_path not in folders:
                node = QTreeWidgetItem(current, [part])
                node.setData(0, Qt.ItemDataRole.UserRole,
                             {"kind": "folder", "path": parent_path})
                node.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                folder_font = node.font(0)
                folder_font.setBold(True)
                node.setFont(0, folder_font)
                node.setToolTip(0, part)
                folders[parent_path] = node
            current = folders[parent_path]
        return current

    def _append_ci_module(self, parent, label, definition, source, path=None):
        name = self._clean_ci_name(label)
        display_name = library_module_name(name, path, CI_LIBRARY_DIR)
        item = QTreeWidgetItem(parent, [display_name])
        item.setIcon(0, get_app_icon())
        module_data = {**definition, "name": name, "source": source}
        if path:
            module_data["module_path"] = str(path)
        item.setData(0, Qt.ItemDataRole.UserRole,
                     {"kind": "module", "module": module_data,
                      "path": str(path) if path else None})
        item.setToolTip(0, tr('{v0} · pulsa para colocar en el tablero', v0=display_name))
        return item

    def actualizar_biblioteca_ci(self):
        if not hasattr(self, "ci_tree"):
            return
        previous_expansion = {}
        preserve_expansion = getattr(self, "_ci_tree_ready", False)
        if preserve_expansion:
            pending = [self.ci_tree.topLevelItem(i)
                       for i in range(self.ci_tree.topLevelItemCount())]
            while pending:
                node = pending.pop()
                metadata = node.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(metadata, dict):
                    key = (metadata.get("kind"), metadata.get("source", metadata.get("path", "")))
                    previous_expansion[key] = node.isExpanded()
                pending.extend(node.child(i) for i in range(node.childCount()))

        self.ci_tree.clear()
        search = self.ci_search.text().strip().casefold()
        library = self._read_ci_library()
        library.sort(key=lambda entry: (
            entry[0].parent.as_posix().casefold(),
            self._clean_ci_name(entry[1].get("name", "")).casefold()))

        library_root = QTreeWidgetItem(self.ci_tree, ["Biblioteca"])
        library_root.setData(0, Qt.ItemDataRole.UserRole,
                             {"kind": "root", "source": "library"})
        library_root.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        root_font = library_root.font(0)
        root_font.setBold(True)
        library_root.setFont(0, root_font)
        folder_nodes = {"": library_root}
        for folder in self._library_folders():
            folder_item = self._ensure_ci_folder_item(library_root, folder, folder_nodes)
            folder_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        visible_library_count = 0
        for path, definition in library:
            name = self._clean_ci_name(definition.get("name", path.stem))
            if search and search not in name.casefold() and search not in library_module_name(name, path, CI_LIBRARY_DIR).casefold():
                continue
            relative = path.relative_to(CI_LIBRARY_DIR)
            parent = self._ensure_ci_folder_item(
                library_root, relative.parent.as_posix(), folder_nodes)
            self._append_ci_module(parent, name, definition, "library", path)
            visible_library_count += 1
        if not visible_library_count and (search or not folder_nodes.keys() - {""}):
            empty_text = tr("No hay CI que coincidan.") if search else tr("La biblioteca está vacía.")
            empty_item = QTreeWidgetItem(library_root, [tr(empty_text)])
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)

        library_root.setExpanded(previous_expansion.get(("root", "library"), False)
                                 if preserve_expansion else False)
        for folder_path, folder_item in folder_nodes.items():
            if folder_path:
                folder_item.setExpanded(previous_expansion.get(("folder", folder_path), False)
                                        if preserve_expansion else False)

        library_signatures = {self._module_signature(definition)
                              for _, definition in library}
        imported = []
        imported_signatures = set()
        imported_definitions = list(self.imported_modules)
        imported_definitions.extend(
            self._module_definition({"name": widget.name,
                "inputs": len(widget.enter), "outputs": len(widget.exit),
                "truth_table": widget.truth_table,
                "input_numbers": widget.input_numbers,
                "output_numbers": widget.output_numbers,
                "input_labels": widget.input_labels,
                "output_labels": widget.output_labels,
                "input_widths": widget.input_widths,
                "output_widths": widget.output_widths,
                "stateful_circuit": widget.stateful_circuit})
            for widget in self.all_widgets.values()
            if isinstance(widget, wdg.Module)
            and getattr(widget, "module_source", "") == "uploaded")
        for definition in imported_definitions:
            signature = self._module_signature(definition)
            if signature not in imported_signatures:
                imported.append(definition)
                imported_signatures.add(signature)
        if imported:
            uploaded_root = QTreeWidgetItem(self.ci_tree, ["Subido"])
            uploaded_root.setData(0, Qt.ItemDataRole.UserRole,
                                 {"kind": "root", "source": "uploaded"})
            uploaded_root.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            for definition in sorted(imported, key=lambda item: str(item.get("name", "")).casefold()):
                name = self._clean_ci_name(definition.get("name", "Módulo"))
                if not search or search in name.casefold():
                    self._append_ci_module(uploaded_root, name, definition, "uploaded")
            if not uploaded_root.childCount():
                self.ci_tree.takeTopLevelItem(self.ci_tree.indexOfTopLevelItem(uploaded_root))
            else:
                uploaded_root.setExpanded(previous_expansion.get(("root", "uploaded"), False)
                                          if preserve_expansion else False)

        library_sigs = library_signatures | imported_signatures
        loaded = []
        for widget in self.all_widgets.values():
            if not isinstance(widget, wdg.Module) or getattr(widget, "module_source", "") == "uploaded":
                continue
            definition = self._module_definition({"name": widget.name,
                "inputs": len(widget.enter), "outputs": len(widget.exit),
                "truth_table": widget.truth_table,
                "input_numbers": widget.input_numbers,
                "output_numbers": widget.output_numbers,
                "input_labels": widget.input_labels,
                "output_labels": widget.output_labels,
                "input_widths": widget.input_widths,
                "output_widths": widget.output_widths,
                "stateful_circuit": widget.stateful_circuit})
            signature = self._module_signature(definition)
            if signature not in library_sigs and not any(
                    self._module_signature(existing) == signature for existing in loaded):
                loaded.append(definition)
        if loaded:
            loaded_root = QTreeWidgetItem(self.ci_tree, ["Cargado"])
            loaded_root.setData(0, Qt.ItemDataRole.UserRole,
                                {"kind": "root", "source": "loaded"})
            loaded_root.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            for definition in sorted(loaded, key=lambda item: str(item.get("name", "")).casefold()):
                name = self._clean_ci_name(definition.get("name", "Módulo"))
                if not search or search in name.casefold():
                    self._append_ci_module(loaded_root, name, definition, "project")
            if not loaded_root.childCount():
                self.ci_tree.takeTopLevelItem(self.ci_tree.indexOfTopLevelItem(loaded_root))
            else:
                loaded_root.setExpanded(previous_expansion.get(("root", "loaded"), False)
                                        if preserve_expansion else False)
        self._ci_tree_ready = True
    def _choose_ci_destination(self):
        folders = self._library_folders()
        choices = ["Biblioteca (raíz)", *folders, "Crear una carpeta nueva…"]
        preferred = self.config.get("ci_last_folder", "")
        preferred_label = preferred or "Biblioteca (raíz)"
        initial = choices.index(preferred_label) if preferred_label in choices else 0
        selected, accepted = QInputDialog.getItem(
            self, tr("Guardar CI en la Biblioteca"), "Carpeta de destino:", choices, initial, False,
            literal_items=choices[:-1])
        if not accepted:
            return None
        if selected == "Crear una carpeta nueva…":
            name, accepted = QInputDialog.getText(
                self, "Nueva carpeta", tr("Nombre o ruta dentro de la Biblioteca:"))
            if not accepted or not name.strip():
                return None
            folder = name.strip().replace("\\", "/")
            destination = (CI_LIBRARY_DIR / folder).resolve()
            if destination == CI_LIBRARY_DIR.resolve() or CI_LIBRARY_DIR.resolve() not in destination.parents:
                QMessageBox.information(self, tr("Ruta no válida"), tr("La carpeta debe estar dentro de la Biblioteca."))
                return None
            try:
                destination.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.warning(self, tr("No se pudo crear la carpeta"), tr(str(exc)))
                return None
            relative = destination.relative_to(CI_LIBRARY_DIR.resolve()).as_posix()
        else:
            relative = "" if selected == "Biblioteca (raíz)" else selected
            destination = CI_LIBRARY_DIR / relative
        self.config["ci_last_folder"] = relative
        try:
            write_json_atomic(USER_DIR / "config.json", self.config)
        except OSError:
            pass
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, tr("No se pudo abrir la carpeta"), tr(str(exc)))
            return None
        return destination

    def _save_ci_definition(self, name, inputs, outputs, table,
                            stateful_circuit=None, input_widths=None,
                            output_widths=None, input_labels=None,
                            output_labels=None):
        file_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip(" .") or "Módulo"
        if file_stem.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                                 *(f"LPT{i}" for i in range(1, 10))}:
            file_stem = f"_{file_stem}"
        destination_dir = self._choose_ci_destination()
        if destination_dir is None:
            return None
        path = destination_dir / f"{file_stem}.dmodule"
        suffix = 2
        while path.exists():
            path = destination_dir / f"{file_stem} ({suffix}).dmodule"
            suffix += 1
        try:
            CI_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
            write_json_atomic(path, module_definition(name, inputs, outputs, table,
                                                        stateful_circuit=stateful_circuit,
                                                        input_labels=input_labels,
                                                        output_labels=output_labels,
                                                        input_widths=input_widths,
                                                        output_widths=output_widths,
                                                        format_version="auto"))
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, tr("No se pudo guardar el CI"), tr(str(exc)))
            return None
        self._mark_module_source(name, inputs, outputs, table, "library", stateful_circuit,
                                 input_widths, output_widths)
        self.actualizar_biblioteca_ci()
        return path.resolve()

    def _mark_module_source(self, name, inputs, outputs, table, source,
                            stateful_circuit=None, input_widths=None,
                            output_widths=None):
        target = self._module_signature({"name": name, "inputs": inputs,
                                         "outputs": outputs, "truth_table": table,
                                         "stateful_circuit": stateful_circuit,
                                         "input_widths": input_widths,
                                         "output_widths": output_widths})
        for widget in self.all_widgets.values():
            if isinstance(widget, wdg.Module) and self._module_signature({
                    "name": widget.name, "inputs": len(widget.enter),
                    "outputs": len(widget.exit), "truth_table": widget.truth_table,
                    "input_numbers": widget.input_numbers,
                    "output_numbers": widget.output_numbers,
                    "input_labels": widget.input_labels,
                    "output_labels": widget.output_labels,
                    "input_widths": widget.input_widths,
                    "output_widths": widget.output_widths,
                    "stateful_circuit": widget.stateful_circuit}) == target:
                widget.module_source = source

    def _capturar_iconos(self):
        self._original_icons = {action: action.icon() for action in self.findChildren(QAction)
                                if not action.icon().isNull()}

    def _actualizar_tinta_iconos(self):
        color = QColor(205, 220, 239) if self.theme_mode == "dark" else QColor(69, 87, 111)
        for action, icon in self._original_icons.items():
            pixmap = icon.pixmap(24, 24)
            if pixmap.isNull():
                continue
            tinted = QPixmap(pixmap.size())
            tinted.fill(Qt.GlobalColor.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(tinted.rect(), color)
            painter.end()
            action.setIcon(QIcon(tinted))

    def aplicar_tema(self, mode: str, persist=True):
        self.theme_mode = "dark" if mode == "dark" else "light"
        # Native subcontrols (arrows, table corners and tab scroll buttons)
        # also need a palette; QSS alone leaves them in the Windows light theme.
        palette = self.app.style().standardPalette()
        if self.theme_mode == "dark":
            for role, color in (
                    (QPalette.Window, "#171e28"), (QPalette.WindowText, "#e7edf6"),
                    (QPalette.Base, "#131b25"), (QPalette.AlternateBase, "#202a37"),
                    (QPalette.Text, "#e7edf6"), (QPalette.Button, "#263342"),
                    (QPalette.ButtonText, "#e7edf6"), (QPalette.Light, "#405064"),
                    (QPalette.Midlight, "#35465a"), (QPalette.Mid, "#303d4e"),
                    (QPalette.Dark, "#101722"), (QPalette.Shadow, "#101722"),
                    (QPalette.Highlight, "#356ba8"), (QPalette.HighlightedText, "#ffffff"),
                    (QPalette.ToolTipBase, "#273546"), (QPalette.ToolTipText, "#f2f6fc"),
                    (QPalette.PlaceholderText, "#aebbc9")):
                palette.setColor(role, QColor(color))
            for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
                palette.setColor(QPalette.Disabled, role, QColor("#758396"))
        self.app.setPalette(palette)
        path = BASE_DIR / "resources" / "styles" / f"{self.theme_mode}.qss"
        self.app.setStyleSheet(self.cargar_tema(str(path)))
        if hasattr(self, "ui"):
            self.ui.graphicsView.set_theme(self.theme_mode)
            self._actualizar_tinta_iconos()
            self.update_probe_plot()
        if persist:
            self.config["theme"] = str(path.relative_to(BASE_DIR)).replace("\\", "/")
            self._save_editor_preferences()
        if hasattr(self, "actionTema"):
            self.actionTema.blockSignals(True)
            self.actionTema.setChecked(self.theme_mode == "dark")
            self.actionTema.setText((tr("Tema claro") if self.theme_mode == "dark" else tr("Tema oscuro")))
            self.actionTema.blockSignals(False)
        for theme, action in getattr(self, "theme_actions", {}).items():
            action.setChecked(theme == self.theme_mode)

    def visual_planes(self):
        return sorted((item for item in self.ui.graphicsView.scene.items()
                       if isinstance(item, VisualItem) and item.kind == "plane"),
                      key=lambda item: item.text.casefold())

    def _unique_plane_name(self, base="Plano"):
        names = {item.text.casefold() for item in self.visual_planes()}
        base = base.strip() or "Plano"
        if base.casefold() not in names:
            return base
        index = 2
        while f"{base} {index}".casefold() in names:
            index += 1
        return f"{base} {index}"

    def add_visual(self, kind, position, data=None):
        self._capture_history_change()
        if data is None:
            data = {"kind": kind, "text": "Texto" if kind == "text" else "",
                    "width": 500 if kind == "plane" else 160,
                    "height": 350 if kind == "plane" else 160}
        else:
            data = dict(data)
        if kind == "plane":
            data["text"] = self._unique_plane_name(data.get("text") or "Plano")
        item = VisualItem.from_data(data)
        self.ui.graphicsView.scene.clearSelection()
        self.ui.graphicsView.scene.addItem(item)
        item.setPos(position)
        item.setSelected(True)
        self.visualDock.show()
        self._refresh_fit_menu()
        self._capture_history_change()
        return item

    def _refresh_fit_menu(self, *_args):
        if not hasattr(self, "fitButton"):
            return
        planes = self.visual_planes()
        signature = tuple(item.text for item in planes)
        if signature == getattr(self, "_fit_menu_signature", None):
            return
        self._fit_menu_signature = signature
        self.fitMenu.clear()
        if planes:
            self.fitMenu.addAction(tr("(Todo)"), lambda: self.ajustar_vista())
            self.fitMenu.addSeparator()
            for plane in planes:
                name = plane.text
                self.fitMenu.addAction(name, lambda checked=False, name=name: self.ajustar_vista(plane_name=name))
        self.actionAjustarVista.setMenu(self.fitMenu if planes else None)
        self.fitButton.setMenu(self.fitMenu if planes else None)
        self.fitButton.setPopupMode(QToolButton.InstantPopup if planes else QToolButton.DelayedPopup)

    def ajustar_vista(self, checked=False, plane_name=None):
        if plane_name is not None:
            plane = next((item for item in self.visual_planes() if item.text == plane_name), None)
            if plane is None:
                return
            rect = plane.sceneBoundingRect().adjusted(-40, -40, 40, 40)
            self.ui.graphicsView.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.ui.graphicsView.zoom_act = self.ui.graphicsView.transform().m11()
            return
        items = [item for item in self.ui.graphicsView.scene.items()
                 if not (hasattr(item, "zValue") and item.zValue() == -1)]
        if items:
            rect = QRectF()
            for item in items:
                rect = rect.united(item.sceneBoundingRect())
            rect = rect.adjusted(-60, -60, 60, 60)
            self.ui.graphicsView.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.ui.graphicsView.zoom_act = self.ui.graphicsView.transform().m11()
        else:
            self.ui.graphicsView.centerOn(0, 0)

    def eliminar_seleccion(self):
        board = self.ui.graphicsView
        with board.topology_edit():
            for item in list(board.scene.selectedItems()):
                if isinstance(item, Wire):
                    board._remove_wire(item)
                elif isinstance(item, gra.Graphic):
                    board._remove_graphic(item)
                elif isinstance(item, Junction):
                    board._remove_junction(item)
                elif isinstance(item, VisualItem):
                    board.scene.removeItem(item)
        self._refresh_fit_menu()

    # ── Config ───────────────────────────────────────────────────────────────

    def create_config(self, file_path=None):
        config = {
            "theme":      "resources/styles/light.qss",
            "lang":       "es",
            "main_UI":    "resources.compiled.ui_ventana1",
            "credits_UI": "resources.compiled.ui_credits",
            "config_UI":  "resources.compiled.ui_config",
            "update_notifications": True,
        }
        write_json_atomic(file_path or USER_DIR / "config.json", config)

    def load_UI(self, ui, default, type_name):
        try:
            if ui in {"resources.ui.ui_ventana1", "resources.ui.ui_credits", "resources.ui.ui_config"}:
                ui = "resources.compiled." + ui.rsplit(".", 1)[-1]
            module = importlib.import_module(ui)
            ui_class = getattr(module, type_name)
        except (ModuleNotFoundError, AttributeError):
            module = importlib.import_module("resources.compiled." + default)
            ui_class = getattr(module, type_name)
        return ui_class

    def get_settings(self, file_path=None):
        path = Path(file_path) if file_path is not None else USER_DIR / "config.json"
        defaults = {"theme": "resources/styles/light.qss", "lang": "es",
                    "main_UI": "resources.compiled.ui_ventana1",
                    "credits_UI": "resources.compiled.ui_credits",
                    "config_UI": "resources.compiled.ui_config"}
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            saved = {}
        self.config = {**defaults, **saved} if isinstance(saved, dict) else defaults.copy()
        for key, value in defaults.items():
            if not isinstance(self.config.get(key), str):
                self.config[key] = value
        if not isinstance(self.config.get("update_notifications"), bool):
            self.config["update_notifications"] = True
        try:
            self.config["history_limit"] = max(10, min(1000, int(self.config.get("history_limit", 100))))
        except (TypeError, ValueError, OverflowError):
            self.config["history_limit"] = 100
        if self.config != saved:
            try:
                write_json_atomic(path, self.config)
            except OSError:
                pass

    def load_settings(self):
        self.get_settings()
        self.MainWindow  = self.load_UI(self.config["main_UI"],    "ui_ventana1", "Ui_MainWindow")()
        self.Credit_Form = self.load_UI(self.config["credits_UI"], "ui_credits",  "Ui_Form")()
        self.Config_Form = self.load_UI(self.config["config_UI"],  "ui_config",   "Ui_Form")()

    def cargar_tema(self, path="resources/styles/light.qss"):
        try:
            with (BASE_DIR / path).open("r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # ── Proyectos ───────────────────────────────────────────────────────────

    def _confirm_discard(self, message=tr("¿Quieres guardar los cambios antes de continuar?")):
        if not self._is_document_dirty():
            return True
        answer = QMessageBox.warning(self, tr("Cambios sin guardar"), tr(message),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save)
        if answer == QMessageBox.Save:
            self.guardar()
            return not self._is_document_dirty()
        if answer == QMessageBox.Discard:
            if hasattr(self, "autosave_path"):
                self._discard_autosave()
            return True
        return False

    def closeEvent(self, event):
        if not self._confirm_discard():
            event.ignore()
            return
        if hasattr(self, "_autosave_timer"):
            self._autosave_timer.stop()
        if self._allow_recovery and hasattr(self, "autosave_path"):
            self._discard_autosave()
        event.accept()

    def _clear_project(self):
        board = self.ui.graphicsView
        board.cancel_visual_placement()
        board._cancel_drawing()
        board._prop_timer.stop()
        board._signal_queue.clear()
        board._waiting_batch = None
        board._processing_signals = False
        board._signal_steps = 0
        board._input_drivers.clear()
        board._network_cache = None
        board._probes.clear()
        board._breakpoints.clear()
        board._breakpoint_hits.clear()
        board._step_time_ms = 0
        board._signal_visits.clear()
        board._signal_halted = False
        self.refresh_probes()
        board.scene.clear()
        board._draw_center()
        self.all_widgets.clear()
        self.all_graphics.clear()
        board.sync_clock_timers()
        self.next_id = 0
        self.actualizar_biblioteca_ci()
        self._refresh_fit_menu()

    def nuevo(self):
        if not self._confirm_discard():
            return
        if hasattr(self, "autosave_path"):
            self._discard_autosave()
        self._clear_project()
        self.project_path, self.project_name = None, "Sin título"
        self.setWindowTitle(tr(self._localized_window_title()))
        self._reset_history()

    def cerrar_proj(self):
        self.nuevo()

    def _remember_recent(self, path: Path):
        recent_file = USER_DIR / "recent.json"
        try:
            recent = json.loads(recent_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            recent = []
        normalized = str(path.resolve())
        recent = [p for p in recent if isinstance(p, str) and p != normalized] if isinstance(recent, list) else []
        try:
            write_json_atomic(recent_file, [normalized, *recent][:10])
        except OSError as exc:
            self.statusBar().showMessage(tr('No se pudo actualizar la lista de recientes: {v0}', v0=exc), 5000)

    def guardar(self):
        if self.project_path is None:
            return self.guardarcomo()
        self._history_timer.stop()
        self._capture_history_change()
        try:
            write_json_atomic(self.project_path, dump_project(self))
            self._remember_recent(self.project_path)
            self._document_saved_key = self._project_content_key()
            if hasattr(self, "autosave_path"):
                self._discard_autosave()
            self._update_document_state()
            self.statusBar().showMessage(tr("Proyecto guardado"), 3000)
            return True
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, tr("No se pudo guardar"), tr(str(exc)))
            return False

    def guardarcomo(self):
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", str(PROJECTS_DIR / "proyecto.dalogic"), tr("Proyecto DaLogic (*.dalogic)"))
        if not path:
            return
        self._history_timer.stop()
        self._capture_history_change()
        previous_path, previous_name = self.project_path, self.project_name
        self.project_path = Path(path).with_suffix(".dalogic")
        self.project_name = self.project_path.stem
        if not self.guardar():
            self.project_path, self.project_name = previous_path, previous_name
            self._update_document_state()
            return False
        # Naming a document does not erase its undo history.
        self._history_snapshot_json = self._history_key(self._history_state())
        return True

    def abrir_archivo(self):
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", str(PROJECTS_DIR), tr("Proyecto DaLogic (*.dalogic);;JSON (*.json)"))
        if path:
            self.cargar_proyecto(Path(path))

    def _resolve_endpoint(self, ref, junctions, endpoints):
        if ref["kind"] == "junction":
            return junctions.get(ref["id"])
        if ref["kind"] == "endpoint":
            return endpoints.get(ref["id"])
        graphic = self.all_graphics.get(int(ref["widget"]))
        if not graphic:
            return None
        ports = graphic._ports_in if ref.get("side") == "in" else graphic._ports_out
        index = int(ref.get("index", -1))
        return ports[index] if 0 <= index < len(ports) else None

    def cargar_proyecto(self, path: Path | None = None, _history_state=None, *, _report_errors=True):
        try:
            path = Path(path) if path is not None else None
            data = (_history_state["data"] if _history_state is not None else
                    json.loads(path.read_text(encoding="utf-8")))
            prepared, visual_items = prepare_project(data, self._create_component)
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, RecursionError) as exc:
            if _report_errors:
                QMessageBox.critical(self, tr("No se pudo abrir"), tr(str(exc)))
            return False

        if _history_state is None and not self._confirm_discard(
                tr("¿Guardar los cambios del proyecto actual antes de abrir otro?")):
            return False

        self._clear_project()
        try:
            module_port_maps = {}
            for item in data["components"]:
                if item.get("type") != "MODULO":
                    continue
                widget_id = int(item["id"])
                module_port_maps[widget_id] = {}
                for side, key, count_key in (("in", "input_numbers", "inputs"),
                                             ("out", "output_numbers", "outputs")):
                    numbers = wdg.Module._normalize_port_numbers(
                        item.get(key), int(item.get(count_key, 1)))
                    order = sorted(range(len(numbers)), key=lambda index: numbers[index])
                    module_port_maps[widget_id][side] = {
                        old_index: new_index for new_index, old_index in enumerate(order)}
            for item in data["components"]:
                x, y = item.get("position", [0, 0])
                component_data = item
                if item.get("type") == "MODULO":
                    component_data = {**item, "source": item.get("source") or "project"}
                graphic = self.crear_widget(item["type"], position=QPointF(x, y), data=component_data,
                                            _prepared=prepared[item["id"]])
                if isinstance(graphic.widg, wdg.Module):
                    graphic.widg.module_source = component_data.get("source", "project")
            junctions, endpoints = {}, {}
            for item in data.get("junctions", []):
                x, y = item["position"]
                bridge_mode = item.get("bridge_mode", 1 if item.get("bridge", False) else 0)
                node = Junction(QPointF(x, y), bridge_mode=bridge_mode)
                self.ui.graphicsView.scene.addItem(node)
                junctions[item["id"]] = node
            for item in data.get("endpoints", []):
                x, y = item["position"]
                node = WireEndpoint(QPointF(x, y))
                self.ui.graphicsView.scene.addItem(node)
                endpoints[item["id"]] = node
            for item in data.get("sections", []):
                x, y = item["position"]
                from PySide6.QtWidgets import QGraphicsTextItem
                label = QGraphicsTextItem(str(item["text"]))
                label.setDefaultTextColor(QColor(150, 195, 245))
                label.setFont(QFont("Sans Serif", 14, QFont.Weight.Bold))
                label.setPos(QPointF(x, y))
                self.ui.graphicsView.scene.addItem(label)
            for item in reversed(visual_items):
                self.ui.graphicsView.scene.addItem(item)
            for item in data.get("wires", []):
                src_ref, dst_ref = dict(item["src"]), dict(item["dst"])
                for ref in (src_ref, dst_ref):
                    if ref.get("kind") == "port" and int(ref.get("widget", -1)) in module_port_maps:
                        side = ref.get("side", "out")
                        ref["index"] = module_port_maps[int(ref["widget"])][side].get(
                            int(ref.get("index", -1)), int(ref.get("index", -1)))
                src = self._resolve_endpoint(src_ref, junctions, endpoints)
                dst = self._resolve_endpoint(dst_ref, junctions, endpoints)
                if src is None or dst is None:
                    continue
                mids = [QPointF(*p) for p in item.get("midpoints", [])]
                midpoint_bridges = item.get("midpoint_bridges", [])
                wire = Wire(src, dst, mids, midpoint_bridges=midpoint_bridges,
                            custom_color=item.get("color"))
                self.ui.graphicsView.scene.addItem(wire)
                wire.update_path()
        except (KeyError, TypeError, ValueError) as exc:
            self._clear_project()
            if _report_errors:
                QMessageBox.critical(self, tr("Proyecto inválido"), tr('No se pudo reconstruir el circuito: {v0}', v0=exc))
            return
        button_was_held = any(
            item.get("type") == "BOTON" and (
                bool(item.get("state", False)) or
                any(value is True or value == 1
                    for value in item.get("logic_outputs", [])))
            for item in data["components"])
        self.ui.graphicsView.rebuild_connections(
            # Undo/redo snapshots already contain the outputs that define a
            # flip-flop or latch state. Re-evaluating every gate at once can
            # momentarily invalidate that state and create a false oscillation.
            recalculate=button_was_held and _history_state is None,
            restore_state=True)
        if (self._allow_recovery and hasattr(self, "autosave_path") and path is not None and
                Path(path).resolve() != self.autosave_path.resolve()):
            self._discard_autosave()
        if _history_state is None:
            self.project_path = path
            self.project_name = data.get("name") or path.stem
            if path != getattr(self, "autosave_path", None):
                self._remember_recent(path)
        else:
            self.imported_modules = _history_state.get("imported_modules", [])
        self.setWindowTitle(tr(self._localized_window_title()))
        self.statusBar().showMessage(tr("Proyecto cargado"), 3000)
        self.actualizar_biblioteca_ci()
        self._refresh_fit_menu()
        if _history_state is None and not self._history_restoring:
            self._reset_history()
        return True

    def configure(self):
        self.config_window = VentanaConfig(self.Config_Form, self)
        self.config_window.exec()
    def exportar(self):
        filters = (tr("Imagen PNG (*.png);;Documento PDF (*.pdf);;"
                   "Gráfico vectorial SVG (*.svg)"))
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path, selected_filter = QFileDialog.getSaveFileName(self, "Exportar circuito", str(EXPORTS_DIR / "circuito.png"),
            filters, "Imagen PNG (*.png)")
        if not path:
            return
        extension = (".svg" if selected_filter.startswith("Gráfico vectorial SVG")
                     else ".pdf" if selected_filter.startswith("Documento PDF")
                     else ".png")
        if Path(path).suffix.lower() != extension:
            path = str(Path(path).with_suffix(extension))
        rect = self.ui.graphicsView.scene.itemsBoundingRect().adjusted(-30, -30, 30, 30)
        if rect.isEmpty():
            QMessageBox.information(self, tr("Exportar"), tr("No hay ningún circuito que exportar."))
            return
        if extension == ".svg":
            try:
                from PySide6.QtSvg import QSvgGenerator
            except ImportError as exc:
                QMessageBox.critical(self, tr("Exportar"), tr('No está disponible el exportador SVG: {v0}', v0=exc))
                return
            size = QSize(max(1, int(rect.width())), max(1, int(rect.height())))
            generator = QSvgGenerator()
            generator.setFileName(path)
            generator.setSize(size)
            generator.setViewBox(QRect(0, 0, size.width(), size.height()))
            generator.setTitle(tr("DaLogic · circuito"))
            painter = QPainter(generator)
            if not painter.isActive():
                QMessageBox.critical(self, tr("Exportar"), tr("No se pudo crear el archivo SVG."))
                return
            self.ui.graphicsView.scene.render(
                painter, QRectF(0, 0, size.width(), size.height()), rect)
            painter.end()
            return
        if extension == ".pdf":
            writer = QPdfWriter(path)
            writer.setResolution(144)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageOrientation(QPageLayout.Orientation.Landscape)
            painter = QPainter(writer)
            if not painter.isActive():
                QMessageBox.critical(self, tr("Exportar"), tr("No se pudo crear el documento PDF."))
                return
            target = QRectF(0, 0, writer.width(), writer.height())
            self.ui.graphicsView.scene.render(painter, target.adjusted(36, 36, -36, -36), rect)
            painter.end()
            return
        # Bound raster memory for circuits spread over a very large canvas.
        scale = min(1.0, (50_000_000 / max(1, rect.width() * rect.height())) ** 0.5,
                    32767 / max(1, rect.width(), rect.height()))
        image = QImage(max(1, int(rect.width() * scale)), max(1, int(rect.height() * scale)), QImage.Format.Format_ARGB32)
        if image.isNull():
            QMessageBox.critical(self, tr("Exportar"), tr("No hay memoria suficiente para crear la imagen PNG."))
            return
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.ui.graphicsView.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        if not image.save(path, "PNG"):
            QMessageBox.critical(self, tr("Exportar"), tr("No se pudo guardar la imagen PNG."))

    def imprimir(self):
        self.exportar()

    def recientes(self):
        try:
            recent = json.loads((USER_DIR / "recent.json").read_text(encoding="utf-8"))
            recent = [p for p in recent if isinstance(p, str) and Path(p).is_file()] if isinstance(recent, list) else []
        except (OSError, ValueError, UnicodeError):
            recent = []
        if not recent:
            QMessageBox.information(self, tr("Recientes"), tr("No hay proyectos recientes."))
            return
        choice, accepted = QInputDialog.getItem(self, "Proyectos recientes", "Abrir:", recent, 0, False)
        if accepted:
            self.cargar_proyecto(Path(choice))

    def salir_app(self):
        self.close()

    def copiar(self):
        selected = [g for g in self.ui.graphicsView.scene.selectedItems() if isinstance(g, gra.Graphic)]
        selected_ids = {graphic.widg.id for graphic in selected}
        import copy
        self._visual_clipboard = [copy.deepcopy(item.to_data())
                                  for item in self.ui.graphicsView.scene.selectedItems()
                                  if isinstance(item, VisualItem)]
        project = dump_project(self)
        self._clipboard = [copy.deepcopy(item) for item in project["components"]
                           if item["id"] in selected_ids]
        self._connection_clipboard = copy.deepcopy(
            self._internal_clipboard_connections(project, selected_ids))

    @staticmethod
    def _internal_clipboard_connections(project, selected_ids):
        """Keep complete internal paths, pruning branches to outside components."""
        from collections import deque

        def key(ref):
            return (("port", ref["widget"], ref["side"], ref["index"])
                    if ref["kind"] == "port" else (ref["kind"], ref["id"]))

        wires = [wire for wire in project["wires"]
                 if all(ref["kind"] != "port" or ref["widget"] in selected_ids
                        for ref in (wire["src"], wire["dst"]))]
        nodes, ends = {}, []
        for index, wire in enumerate(wires):
            pair = key(wire["src"]), key(wire["dst"])
            ends.append(pair)
            for node in pair:
                nodes.setdefault(node, set()).add(index)
        leaves = deque(node for node, edges in nodes.items()
                       if node[0] != "port" and len(edges) < 2)
        while leaves:
            node = leaves.popleft()
            for index in list(nodes[node]):
                for endpoint in ends[index]:
                    nodes[endpoint].discard(index)
                    if endpoint[0] != "port" and len(nodes[endpoint]) == 1:
                        leaves.append(endpoint)
        visited, retained = set(), set()
        for start in nodes:
            if start in visited:
                continue
            stack, component_nodes, edges = [start], set(), set()
            while stack:
                node = stack.pop()
                if node in component_nodes:
                    continue
                component_nodes.add(node)
                edges.update(nodes[node])
                for index in nodes[node]:
                    stack.extend(ends[index])
            visited.update(component_nodes)
            if sum(node[0] == "port" for node in component_nodes) >= 2:
                retained.update(edges)
        used_nodes = {node for index in retained for node in ends[index]}
        return {"wires": [wire for index, wire in enumerate(wires) if index in retained],
                "junctions": [node for node in project["junctions"]
                              if ("junction", node["id"]) in used_nodes],
                "endpoints": [node for node in project["endpoints"]
                              if ("endpoint", node["id"]) in used_nodes]}

    def cortar(self):
        self.copiar()
        board = self.ui.graphicsView
        selected = list(board.scene.selectedItems())
        with board.topology_edit():
            for item in selected:
                if isinstance(item, Wire):
                    board._remove_wire(item)
            for item in selected:
                if isinstance(item, gra.Graphic):
                    board._remove_graphic(item)
                elif isinstance(item, VisualItem):
                    board.scene.removeItem(item)
                elif isinstance(item, Junction):
                    board._remove_junction(item)
        self._refresh_fit_menu()

    def pegar(self):
        if not self._clipboard and not self._visual_clipboard:
            return
        import copy
        self._capture_history_change()
        restoring = self._history_restoring
        self._history_restoring = True
        board = self.ui.graphicsView
        board.scene.clearSelection()
        copies, widget_ids = [], {}
        try:
            for item in self._clipboard:
                data = copy.deepcopy(item)
                old_id = data.pop("id")
                x, y = data.pop("position")
                graphic = self.crear_widget(data.pop("type"), QPointF(x + 30, y + 30), data)
                widget_ids[old_id] = graphic.widg.id
                copies.append(graphic)
            for item in self._visual_clipboard:
                x, y = item["position"]
                copies.append(self.add_visual(item["kind"], QPointF(x + 30, y + 30), item))
            junctions, endpoints = {}, {}
            for data in self._connection_clipboard["junctions"]:
                x, y = data["position"]
                node = Junction(QPointF(x + 30, y + 30), bridge_mode=data.get("bridge_mode", 0))
                board.scene.addItem(node)
                junctions[data["id"]] = node
                copies.append(node)
            for data in self._connection_clipboard["endpoints"]:
                x, y = data["position"]
                node = WireEndpoint(QPointF(x + 30, y + 30))
                board.scene.addItem(node)
                endpoints[data["id"]] = node
                copies.append(node)
            for data in self._connection_clipboard["wires"]:
                refs = [dict(data["src"]), dict(data["dst"])]
                for ref in refs:
                    if ref["kind"] == "port":
                        ref["widget"] = widget_ids[ref["widget"]]
                src, dst = [self._resolve_endpoint(ref, junctions, endpoints) for ref in refs]
                wire = Wire(src, dst, [QPointF(x + 30, y + 30) for x, y in data["midpoints"]],
                            midpoint_bridges=data.get("midpoint_bridges", []),
                            custom_color=data.get("color"))
                board.scene.addItem(wire)
                copies.append(wire)
            # Adding visual items changes selection, so select the entire copy last.
            board.scene.clearSelection()
            for item in copies:
                item.setSelected(True)
            board.rebuild_connections()
        finally:
            self._history_restoring = restoring
        self._schedule_history_capture()

    def duplicar(self):
        clipboard = self._clipboard, self._visual_clipboard, self._connection_clipboard
        try:
            self.copiar()
            self.pegar()
        finally:
            self._clipboard, self._visual_clipboard, self._connection_clipboard = clipboard

    # ── Módulos reutilizables ───────────────────────────────────────────────

    def _selected_graphics(self):
        return [item for item in self.ui.graphicsView.scene.selectedItems()
                if isinstance(item, gra.Graphic)]

    def _module_interface(self, selected):
        """Obtiene conexiones que cruzan el límite de la selección."""
        chosen = {graphic.widg for graphic in selected}
        incoming, outgoing, internal = [], [], []
        for widget in self.all_widgets.values():
            for out_index, destinations in widget.connections.items():
                for destination, in_index in destinations:
                    edge = (widget, out_index, destination, in_index)
                    if widget in chosen and destination in chosen:
                        internal.append(edge)
                    elif widget not in chosen and destination in chosen:
                        incoming.append(edge)
                    elif widget in chosen and destination not in chosen:
                        outgoing.append(edge)
        # Un puerto es una sola entrada/salida del módulo, aunque tenga varios
        # cables conectados al exterior.
        unique_in, unique_out = [], []
        seen_in, seen_out = set(), set()
        for edge in incoming:
            key = (edge[2].id, edge[3])
            if key not in seen_in:
                seen_in.add(key); unique_in.append(edge)
        for edge in outgoing:
            key = (edge[0].id, edge[1])
            if key not in seen_out:
                seen_out.add(key); unique_out.append(edge)
        return unique_in, unique_out, internal, incoming, outgoing

    def _build_truth_table(self, selected, inputs, outputs, internal):
        chosen = {graphic.widg for graphic in selected}
        widths = [dst.input_widths[index] for _src, _out, dst, index in inputs]
        if sum(widths) > 16:
            raise ValueError(tr("Una tabla combinacional admite como máximo 16 bits de entrada."))
        plan = wdg.combinational_plan(chosen, internal)
        backups = {widget: (widget.enter.copy(), widget.exit.copy(),
                            getattr(widget, "response_ms", None)) for widget in chosen}
        table = []
        progress = CalculationProgress(self, 1 << sum(widths))
        try:
            for combination in range(1 << sum(widths)):
                progress.advance(combination)
                base_inputs = {}
                input_row, offset = [], 0
                for width in widths:
                    value = (combination >> offset) & ((1 << width) - 1)
                    input_row.append(bool(value) if width == 1 else value)
                    offset += width
                for index, (_src, _out, dst, in_index) in enumerate(inputs):
                    values = base_inputs.setdefault(dst, {})
                    values[in_index] = input_row[index]
                wdg.evaluate_combinational(plan, base_inputs)
                output_row = [src.exit[out_index] for src, out_index, _dst, _in in outputs]
                response_ms = self._estimate_response_ms(
                    chosen, [(dst, in_index) for _src, _out, dst, in_index in inputs],
                    internal, [(src, "out", out_index) for src, out_index, _dst, _in in outputs],
                    plan=plan)
                table.append({"inputs": input_row, "outputs": output_row, "time_ms": response_ms})
        finally:
            for widget, (enter, exit_, response_ms) in backups.items():
                widget.enter, widget.exit = enter, exit_
                if response_ms is not None:
                    widget.response_ms = response_ms
            progress.close()
        return table

    def _estimate_response_ms(self, chosen, input_bindings, internal, output_bindings,
                              source_outputs=(), *, plan=None):
        """Longest combinational path, including row-specific module response."""
        order, incoming = plan or wdg.combinational_plan(chosen, internal)
        arrivals = {widget: [None] * len(widget.enter) for widget in order}
        output_times = {(widget, index): 0 for widget, index in source_outputs}
        for widget, index in input_bindings:
            arrivals[widget][index] = 0
        for widget in order:
            for src, out_index, in_index in incoming[widget]:
                value = output_times.get((src, out_index))
                if value is not None:
                    old = arrivals[widget][in_index]
                    arrivals[widget][in_index] = value if old is None else max(old, value)
            known = [value for value in arrivals[widget] if value is not None]
            if known or not widget.enter:
                response = max(known, default=0) + widget.propagation_delay + max(
                    0, int(getattr(widget, "response_ms", 0)))
                for index in range(len(widget.exit)):
                    output_times.setdefault((widget, index), response)
        times = []
        for widget, side, index in output_bindings:
            value = (arrivals[widget][index] if side == "in" else output_times.get((widget, index)))
            if value is not None:
                times.append(value + widget.propagation_delay if side == "in" else value)
        return max(times, default=0)

    def _build_truth_table_from_io(self, selected, input_widgets, output_widgets):
        """Evaluate scalar and bus components as a reusable combinational module."""
        chosen = {graphic.widg for graphic in selected}
        edges = [(src, out_index, dst, in_index)
                 for src in chosen for out_index, destinations in src.connections.items()
                 for dst, in_index in destinations if dst in chosen]
        plan = wdg.combinational_plan(chosen, edges)
        backups = {widget: (widget.enter.copy(), widget.exit.copy(),
                            getattr(widget, "state", None),
                            getattr(widget, "response_ms", None)) for widget in chosen}
        bus_values = {widget: widget.value for widget in chosen
                      if isinstance(widget, wdg.BusInput)}
        table = []
        widths = [getattr(widget, "width", 1) for widget in input_widgets]
        if sum(widths) > 16:
            raise ValueError(tr("Una tabla combinacional admite como máximo 16 bits de entrada."))
        progress = CalculationProgress(self, 1 << sum(widths))
        try:
            for combination in range(1 << sum(widths)):
                progress.advance(combination)
                for widget in chosen:
                    widget.enter = widget.default_input_values()
                    widget.exit = [False] * len(widget.exit)
                input_row = []
                bit_offset = 0
                for source, width in zip(input_widgets, widths):
                    value = (combination >> bit_offset) & ((1 << width) - 1)
                    bit_offset += width
                    value = value if width > 1 else bool(value)
                    input_row.append(value)
                    if isinstance(source, wdg.BusInput):
                        source.value = int(value)
                        source.exit[0] = int(value)
                    else:
                        source.state = bool(value)
                        source.exit[0] = source.state

                wdg.evaluate_combinational(plan)

                output_row = [widget.enter[0] if isinstance(widget, wdg.BusLamp)
                              else widget.enter[0] if widget.enter else False
                              for widget in output_widgets]
                response_ms = self._estimate_response_ms(
                    chosen, [], edges, [(bulb, "in", 0) for bulb in output_widgets],
                    [(source, 0) for source in input_widgets], plan=plan)
                table.append({"inputs": input_row, "outputs": output_row,
                              "time_ms": response_ms})
        finally:
            for widget, (enter, exit_, state, response_ms) in backups.items():
                widget.enter, widget.exit = enter, exit_
                if widget in bus_values:
                    widget.value = bus_values[widget]
                if state is not None:
                    widget.state = state
                if response_ms is not None:
                    widget.response_ms = response_ms
            progress.close()
        return table

    @staticmethod
    def _has_recursive_connections(edges):
        """Return whether the directed component graph contains a feedback loop."""
        adjacency = {}
        indegree = {}
        for source, _out_index, destination, _in_index in edges:
            adjacency.setdefault(source, []).append(destination)
            indegree.setdefault(source, 0)
            indegree[destination] = indegree.get(destination, 0) + 1
        pending = [widget for widget, degree in indegree.items() if degree == 0]
        visited = 0
        while pending:
            widget = pending.pop()
            visited += 1
            for destination in adjacency.get(widget, ()):
                indegree[destination] -= 1
                if indegree[destination] == 0:
                    pending.append(destination)
        return visited != len(indegree)

    def localizar_elemento_tabla(self, widget):
        graphic = self.all_graphics.get(widget.id)
        if not graphic or not graphic.scene():
            return
        self.ui.graphicsView.scene.clearSelection()
        graphic.setSelected(True)
        self.ui.graphicsView.centerOn(graphic)
        self.ui.graphicsView.setFocus()
        self.ui.graphicsView.viewport().update()
    @cancellable
    def calcular_tabla_verdad(self):
        """Calcula la tabla del circuito completo con entradas escalares y buses."""
        widgets = list(self.all_widgets.values())
        sources = sorted((widget for widget in widgets
                          if isinstance(widget, (wdg.Switch, wdg.Button, wdg.Clock, wdg.BusInput))),
                         key=lambda widget: widget.id)
        edges = [(src, out_index, dst, in_index)
                 for src in widgets for out_index, destinations in src.connections.items()
                 for dst, in_index in destinations]
        if (self._has_recursive_connections(edges) or
                any(getattr(widget, "sequential", False) or
                    (isinstance(widget, wdg.Module) and widget.stateful_circuit)
                    for widget in widgets)):
            QMessageBox.warning(
                self, tr("Tabla de verdad no disponible"),
                tr("El circuito contiene conexiones recursivas (realimentación) y su resultado "
                "depende de estados anteriores. La tabla de verdad combinacional no puede "
                "representar ese comportamiento."))
            return
        incoming = {(dst, in_index) for _src, _out, dst, in_index in edges}
        connected_sources = [source for source in sources
                             if any(source.connections.values())]
        input_bits = sum(getattr(source, "width", 1) for source in connected_sources)
        if input_bits > 16:
            QMessageBox.warning(
                self, tr("Tabla demasiado grande"),
                tr("La tabla de verdad admite como máximo 16 bits de entrada (65.536 combinaciones). "
                "Reduce el ancho de entrada o usa una sonda para observar el circuito."))
            return
        if input_bits > 12:
            combinations = 1 << input_bits
            combination_count = f"{combinations:,}".replace(",", ".")
            choice = QMessageBox.warning(
                self, tr("Muchas entradas"),
                tr('La tabla tendrá {v0} bits de entrada en {v1} columnas y {v2} combinaciones. El cálculo puede tardar mucho y consumir bastante memoria. ¿Quieres continuar?', v0=input_bits, v1=len(connected_sources), v2=combination_count),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                return

        ignored_inputs = []
        ignored_outputs = []
        bus_lamps = []
        for source in sources:
            if not any(source.connections.values()):
                kind = ("Botón" if isinstance(source, wdg.Button) else
                        "Reloj" if isinstance(source, wdg.Clock) else
                        "Bus de entrada" if isinstance(source, wdg.BusInput) else "Interruptor")
                ignored_inputs.append(tr('{v0} {v1}: sin conexión; se excluye como entrada', v0=tr(kind), v1=source.id))

        bulbs, displays = [], []
        for widget in widgets:
            if isinstance(widget, (wdg.Switch, wdg.Button, wdg.Clock, wdg.BusInput)):
                continue
            if isinstance(widget, wdg.Bulb):
                if (widget, 0) in incoming:
                    bulbs.append(widget)
                else:
                    ignored_outputs.append(tr('Bombilla {v0}: sin conexión; se excluye como salida', v0=widget.id))
                continue
            if isinstance(widget, wdg.Display):
                connected_segments = [index for index in range(len(widget.enter))
                                      if (widget, index) in incoming]
                disconnected = [index for index in range(len(widget.enter))
                                if (widget, index) not in incoming]
                if connected_segments:
                    displays.append(widget)
                    if disconnected:
                        ignored_inputs.append(
                            tr('Display {v0}: segmentos sin conexión {v1}; se tomarán apagados', v0=widget.id, v1=', '.join(map(str, disconnected))))
                else:
                    ignored_outputs.append(tr('Display {v0}: sin segmentos conectados; se excluye como salida', v0=widget.id))
                continue
            if isinstance(widget, wdg.BusLamp):
                if (widget, 0) in incoming:
                    bus_lamps.append(widget)
                else:
                    ignored_outputs.append(tr('Salida bus {v0}: sin conexión; se excluye como salida', v0=widget.id))
                continue

            for index in range(len(widget.enter)):
                if (widget, index) not in incoming:
                    ignored_inputs.append(
                        tr('{v0} {v1}: entrada {v2} sin conexión; se tomará apagada', v0=type(widget).__name__, v1=widget.id, v2=index))
            for index, destinations in widget.connections.items():
                if not destinations:
                    ignored_outputs.append(
                        tr('{v0} {v1}: salida {v2} sin conexión; se ignora', v0=type(widget).__name__, v1=widget.id, v2=index))

        outputs = sorted([*bulbs, *displays, *bus_lamps], key=lambda widget: widget.id)
        if not outputs:
            details = []
            if ignored_inputs:
                details.append(tr('Entradas ignoradas: {v0}', v0=len(ignored_inputs)))
            if ignored_outputs:
                details.append(tr('Salidas ignoradas: {v0}', v0=len(ignored_outputs)))
            message = tr("No hay bombillas ni displays conectados que puedan usarse como salida.")
            if details:
                message += "\n" + "\n".join(details)
            QMessageBox.warning(self, tr("Tabla de verdad"), tr(message))
            return

        warning_lines = []
        if ignored_inputs:
            warning_lines.append("Entradas sin conexión: " + "; ".join(ignored_inputs[:6]) +
                                 (tr('; y {v0} más', v0=len(ignored_inputs) - 6) if len(ignored_inputs) > 6 else ""))
        if ignored_outputs:
            warning_lines.append("Salidas sin conexión: " + "; ".join(ignored_outputs[:6]) +
                                 (tr('; y {v0} más', v0=len(ignored_outputs) - 6) if len(ignored_outputs) > 6 else ""))
        ignored_summary = "\n".join(warning_lines)
        if ignored_summary:
            choice = QMessageBox.warning(
                self, tr("Puertos sin conexión"),
                (tr(ignored_summary) + tr("\n\nSe ignorarán al calcular la tabla. ¿Continuar?")),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Ok)
            if choice != QMessageBox.StandardButton.Ok:
                return

        order_dialog = TruthTableOrderDialog(connected_sources, outputs, self)
        if order_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        for widget, field in order_dialog.input_fields + order_dialog.output_fields:
            widget.truth_table_number = field.value()
        self._schedule_history_capture()
        connected_sources.sort(key=lambda widget: widget.truth_table_number)
        outputs.sort(key=lambda widget: widget.truth_table_number)

        chosen = set(widgets)
        plan = wdg.combinational_plan(chosen, edges)
        backups = {widget: (widget.enter.copy(), widget.exit.copy(),
                            getattr(widget, "state", None),
                            getattr(widget, "response_ms", None)) for widget in widgets}
        bus_values = {widget: widget.value for widget in widgets
                      if isinstance(widget, wdg.BusInput)}
        row_count = 1 << input_bits
        rows = []
        started = time.perf_counter()
        progress = CalculationProgress(self, row_count)
        try:
            for combination in range(row_count):
                progress.advance(combination)
                for widget in widgets:
                    widget.enter = widget.default_input_values()
                    widget.exit = [False] * len(widget.exit)
                input_values = []
                bit_offset = 0
                for index, source in enumerate(connected_sources):
                    width = getattr(source, "width", 1)
                    value = (combination >> bit_offset) & ((1 << width) - 1)
                    bit_offset += width
                    value = value if width > 1 else bool(value)
                    input_values.append(value)
                    if isinstance(source, wdg.BusInput):
                        source.value = int(value)
                        source.exit[0] = int(value)
                    else:
                        source.state = bool(value)
                        source.exit[0] = source.state

                wdg.evaluate_combinational(plan)

                row_outputs = []
                for widget in outputs:
                    if isinstance(widget, wdg.Bulb):
                        value = widget.enter[0]
                        row_outputs.append(value if value in (wdg.LOGIC_X, wdg.LOGIC_Z) else "1" if value else "0")
                    elif isinstance(widget, wdg.BusLamp):
                        value = widget.enter[0]
                        row_outputs.append(value if value in (wdg.LOGIC_X, wdg.LOGIC_Z)
                                           else f"0x{int(value):X}")
                    else:
                        if any(value in (wdg.LOGIC_X, wdg.LOGIC_Z) for value in widget.enter):
                            row_outputs.append(wdg.LOGIC_X if wdg.LOGIC_X in widget.enter else wdg.LOGIC_Z)
                            continue
                        active_segments = [str(index) for index, value in enumerate(widget.enter)
                                           if value]
                        row_outputs.append("".join(active_segments) if active_segments else "—")
                response_ms = self._estimate_response_ms(
                    chosen, [], edges,
                    [(bulb, "in", 0) for bulb in [*bulbs, *bus_lamps]] +
                    [(display, "in", index) for display in displays
                     for index in range(len(display.enter)) if (display, index) in incoming],
                    [(source, 0) for source in connected_sources], plan=plan)
                rows.append({
                    "inputs": input_values,
                    "outputs": row_outputs,
                    "time_ms": response_ms,
                })
        finally:
            for widget, (enter, exit_, state, response_ms) in backups.items():
                widget.enter, widget.exit = enter, exit_
                if widget in bus_values:
                    widget.value = bus_values[widget]
                if state is not None:
                    widget.state = state
                if response_ms is not None:
                    widget.response_ms = response_ms
                if widget.graphic:
                    for index in range(len(widget.enter)):
                        widget.graphic.update_port_color(index, is_input=True)
                    for index in range(len(widget.exit)):
                        widget.graphic.update_port_color(index, is_input=False)
                    widget.graphic.update_all_output_wires()
                    if isinstance(widget, (wdg.Switch, wdg.Button, wdg.Clock)):
                        widget.graphic.update_switch_look()
            progress.close()

        calculation_ms = (time.perf_counter() - started) * 1000
        input_labels = [tr('Entrada {v0}', v0=source.truth_table_number)
                        for source in connected_sources]
        input_widths = [getattr(source, "width", 1) for source in connected_sources]
        input_labels = [f"{label} ({width} bits)" if width > 1 else label
                        for label, width in zip(input_labels, input_widths)]
        output_labels = [tr('Salida {v0}', v0=widget.truth_table_number) for widget in outputs]
        output_labels = [f"{label} ({widget.width} bits)"
                         if getattr(widget, "width", 1) > 1 else label
                         for label, widget in zip(output_labels, outputs)]
        dialog = TruthTableDialog(rows, input_labels, output_labels,
                                  calculation_ms, ignored_summary, self, input_widths)
        dialog.exec()

    def _port_for_widget(self, widget, side, index):
        graphic = self.all_graphics.get(widget.id)
        if not graphic:
            return None
        ports = graphic._ports_in if side == "in" else graphic._ports_out
        return ports[index] if 0 <= index < len(ports) else None

    def _build_stateful_module_circuit(self, chosen_widgets, input_widgets,
                                       output_widgets):
        """Serialize a feedback circuit as a compact, reusable gate network."""
        node_types = (wdg.AND, wdg.OR, wdg.XOR, wdg.NOT, wdg.NAND, wdg.NOR,
                      wdg.Delay, wdg.Module, Native, wdg.BusViewer, wdg.Splitter, wdg.Combiner, wdg.TriState)
        interface_sources = set(input_widgets)
        interface_outputs = set(output_widgets)
        internal = [widget for widget in chosen_widgets
                    if widget not in interface_sources and widget not in interface_outputs]
        unsupported = [widget for widget in internal
                       if not isinstance(widget, node_types)]
        if unsupported:
            names = ", ".join(type(widget).__name__ for widget in unsupported[:4])
            return None, tr('La selección secuencial contiene módulos o elementos no compatibles: {v0}.', v0=names)

        components = []
        for widget in sorted(internal, key=lambda item: item.id):
            spec = {"id": widget.id, "type": self.type_for_widget(widget),
                    "inputs": len(widget.enter), "outputs": len(widget.exit),
                    "delay_ms": widget.delay_ms,
                    "delay_gates": widget.delay_gates}
            spec.update(input_widths=list(widget.input_widths), output_widths=list(widget.output_widths))
            if hasattr(widget, "width"):
                spec["bus_width"] = widget.width
            if isinstance(widget, Native):
                spec.update(address_bits=widget.address_bits, channels=widget.channels,
                            native_data=widget.export_native())
            if isinstance(widget, wdg.Module):
                spec.update(name=widget.name, truth_table=widget.truth_table,
                            input_numbers=widget.input_numbers,
                            output_numbers=widget.output_numbers,
                            stateful_circuit=widget.stateful_circuit)
                if widget.stateful_circuit:
                    spec["stateful_state"] = widget.export_stateful_state()
            components.append(spec)
        connections = []
        input_bindings = [{"input": index, "targets": []}
                          for index in range(len(input_widgets))]
        output_bindings = [{"output": index, "sources": []}
                           for index in range(len(output_widgets))]
        input_indexes = {widget: index for index, widget in enumerate(input_widgets)}
        output_indexes = {widget: index for index, widget in enumerate(output_widgets)}
        for source in chosen_widgets:
            for output_index, destinations in source.connections.items():
                for destination, input_index in destinations:
                    if destination not in chosen_widgets:
                        continue
                    if source in interface_sources and destination in internal:
                        input_bindings[input_indexes[source]]["targets"].append(
                            {"node": destination.id, "port": input_index})
                    elif source in internal and destination in internal:
                        connections.append({"source": source.id, "output": output_index,
                                            "destination": destination.id, "input": input_index})
                    elif source in internal and destination in interface_outputs:
                        output_bindings[output_indexes[destination]]["sources"].append(
                            {"node": source.id, "port": output_index})
                    elif source in interface_sources and destination in interface_outputs:
                        output_bindings[output_indexes[destination]]["sources"].append(
                            {"input": input_indexes[source]})

        if not input_widgets or not output_widgets:
            return None, tr("Selecciona al menos una entrada y una bombilla de salida para el módulo secuencial.")
        if any(not binding["sources"] for binding in output_bindings):
            return None, tr("Cada bombilla de salida del módulo debe estar conectada a una señal.")
        initial_nodes = {}
        for widget in internal:
            state = {"enter": list(widget.enter), "exit": list(widget.exit)}
            if isinstance(widget, Native):
                state["native"] = widget.export_native()
            if isinstance(widget, wdg.Module) and widget.stateful_circuit:
                state["stateful_state"] = widget.export_stateful_state()
            initial_nodes[str(widget.id)] = state
        initial_state = {
            "initialized": True,
            "inputs": [widget.exit[0] for widget in input_widgets],
            "nodes": initial_nodes,
        }
        extended = (any(isinstance(widget, Native) or isinstance(widget, (wdg.BusViewer, wdg.Splitter, wdg.Combiner, wdg.TriState)) for widget in internal)
                    or any(isinstance(widget, wdg.Module) and widget.stateful_circuit and widget.stateful_circuit.get("version", 1) >= 2 for widget in internal)
                    or any(width > 1 for widget in chosen_widgets for width in widget.input_widths + widget.output_widths))
        return {"version": 2 if extended else 1, "components": components,
                "connections": connections,
                "input_bindings": input_bindings,
                "output_bindings": output_bindings,
                "initial_state": initial_state}, None

    def _add_wire(self, source, destination):
        wire = Wire(source, destination)
        self.ui.graphicsView.scene.addItem(wire)
        wire.update_path()
        return wire

    @cancellable
    def crear_modulo(self):
        selected = self._selected_graphics()
        if not selected:
            QMessageBox.information(self, tr("Crear módulo"), tr("Selecciona los componentes que quieres convertir en módulo."))
            return
        chosen_widgets = {graphic.widg for graphic in selected}
        selected_edges = [(src, out_index, dst, in_index)
                          for src in chosen_widgets
                          for out_index, destinations in src.connections.items()
                          for dst, in_index in destinations if dst in chosen_widgets]
        stateful = (self._has_recursive_connections(selected_edges) or
                    any(isinstance(widget, wdg.Module) and widget.stateful_circuit
                        for widget in chosen_widgets) or
                    any(getattr(widget, "sequential", False) for widget in chosen_widgets))
        name, accepted = QInputDialog.getText(self, "Crear módulo", "Nombre del módulo:", text=tr("Mi módulo"))
        if not accepted or not name.strip():
            return
        module_inputs = sorted((w for w in chosen_widgets
                                if isinstance(w, (wdg.Switch, wdg.Button, wdg.Clock, wdg.BusInput))), key=lambda w: w.id)
        module_outputs = sorted((w for w in chosen_widgets
                                 if isinstance(w, (wdg.Bulb, wdg.BusLamp))), key=lambda w: w.id)

        if stateful:
            circuit, error = self._build_stateful_module_circuit(
                chosen_widgets, module_inputs, module_outputs)
            if error:
                QMessageBox.warning(self, tr("Crear módulo secuencial"), tr(error))
                return
            center = sum((graphic.pos() for graphic in selected), QPointF()) / len(selected)
            input_labels = _default_ci_labels(module_inputs, True)
            output_labels = _default_ci_labels(module_outputs, False)
            module_data = {"name": name.strip(), "inputs": len(module_inputs),
                           "outputs": len(module_outputs), "truth_table": [],
                           "stateful_circuit": circuit,
                           "input_widths": [getattr(widget, "width", 1) for widget in module_inputs],
                           "output_widths": [getattr(widget, "width", 1) for widget in module_outputs],
                           "input_labels": input_labels, "output_labels": output_labels}
            for graphic in selected:
                self.ui.graphicsView._remove_graphic(graphic)
            module_graphic = self.crear_widget("MODULO", center, module_data)
            self.ui.graphicsView.rebuild_connections()
            module_path = self._save_ci_definition(name.strip(), len(module_inputs),
                                                   len(module_outputs), [], circuit,
                                                   input_widths=module_data["input_widths"],
                                                   output_widths=module_data["output_widths"],
                                                   input_labels=input_labels,
                                                   output_labels=output_labels)
            if module_path:
                module_graphic.widg.module_path = str(module_path)
            self.actualizar_biblioteca_ci()
            self.statusBar().showMessage(
                tr("CI secuencial creado: su red interna conserva los estados anteriores."), 6000)
            return

        # Para el flujo habitual de un CI, los interruptores son entradas y las
        # bombillas seleccionadas son salidas, aunque no tengan cables externos.
        if module_inputs and module_outputs:
            input_widths = [getattr(widget, "width", 1) for widget in module_inputs]
            output_widths = [getattr(widget, "width", 1) for widget in module_outputs]
            if sum(input_widths) > 16:
                QMessageBox.warning(self, tr("Crear módulo"), tr("Un módulo combinacional admite como máximo 16 bits de entrada para su tabla."))
                return
            table = self._build_truth_table_from_io(selected, module_inputs, module_outputs)
            center = sum((graphic.pos() for graphic in selected), QPointF()) / len(selected)
            input_labels = _default_ci_labels(module_inputs, True)
            output_labels = _default_ci_labels(module_outputs, False)
            module_data = {"name": name.strip(), "inputs": len(module_inputs),
                           "outputs": len(module_outputs), "truth_table": table,
                           "input_widths": input_widths,
                           "output_widths": output_widths,
                           "input_labels": input_labels, "output_labels": output_labels}
            for graphic in selected:
                self.ui.graphicsView._remove_graphic(graphic)
            module_graphic = self.crear_widget("MODULO", center, module_data)
            self.ui.graphicsView.rebuild_connections()
            module_path = self._save_ci_definition(name.strip(), len(module_inputs),
                                                   len(module_outputs), table,
                                                   input_widths=input_widths,
                                                   output_widths=output_widths,
                                                   input_labels=input_labels,
                                                   output_labels=output_labels)
            if module_path:
                module_graphic.widg.module_path = str(module_path)
            self.actualizar_biblioteca_ci()
            return

        inputs, outputs, internal, all_incoming, all_outgoing = self._module_interface(selected)
        if not outputs:
            QMessageBox.warning(self, tr("Crear módulo"), tr("La selección necesita al menos una salida conectada al exterior."))
            return
        input_widths = [dst.input_widths[index] for _src, _out, dst, index in inputs]
        output_widths = [src.output_widths[index] for src, index, _dst, _in in outputs]
        if sum(input_widths) > 16:
            QMessageBox.warning(self, tr("Crear módulo"), tr("Un módulo combinacional admite como máximo 16 bits de entrada para su tabla."))
            return
        table = self._build_truth_table(selected, inputs, outputs, internal)
        center = sum((graphic.pos() for graphic in selected), QPointF()) / len(selected)
        input_labels = _default_ci_labels([edge[0] for edge in inputs], True)
        output_labels = _default_ci_labels([edge[0] for edge in outputs], False)
        module_data = {"name": name.strip(), "inputs": len(inputs), "outputs": len(outputs),
                       "truth_table": table,
                       "input_widths": input_widths, "output_widths": output_widths,
                       "input_labels": input_labels, "output_labels": output_labels}
        # Preservar los extremos externos antes de borrar el circuito original.
        input_indexes = {(dst.id, in_idx): index
                         for index, (_src, _out, dst, in_idx) in enumerate(inputs)}
        output_indexes = {(src.id, out_idx): index
                          for index, (src, out_idx, _dst, _in) in enumerate(outputs)}
        external_inputs = [(self._port_for_widget(src, "out", out_idx), input_indexes[(dst.id, in_idx)])
                           for src, out_idx, dst, in_idx in all_incoming]
        external_outputs = [(self._port_for_widget(dst, "in", in_idx), output_indexes[(src.id, out_idx)])
                            for src, out_idx, dst, in_idx in all_outgoing]
        for graphic in selected:
            self.ui.graphicsView._remove_graphic(graphic)
        module_graphic = self.crear_widget("MODULO", center, module_data)
        for external, index in external_inputs:
            if external and external.scene():
                self._add_wire(external, module_graphic._ports_in[index])
        for external, index in external_outputs:
            if external and external.scene():
                self._add_wire(module_graphic._ports_out[index], external)
        self.ui.graphicsView.rebuild_connections()

        module_path = self._save_ci_definition(name.strip(), len(inputs), len(outputs), table,
                                               input_widths=input_widths, output_widths=output_widths,
                                               input_labels=input_labels,
                                               output_labels=output_labels)
        if module_path:
            module_graphic.widg.module_path = str(module_path)
        self.actualizar_biblioteca_ci()

    def cargar_modulo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Cargar módulo", str(BASE_DIR), tr("Módulo DaLogic (*.dmodule)"))
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not _supported_dmodule(data):
                raise ValueError(tr("No es un módulo DaLogic compatible."))
            definition = self._module_definition(data)
            module_path = str(Path(path).resolve())
            self.imported_modules.append({**definition, "module_path": module_path})
            self.ui.graphicsView.begin_component_placement("MODULO", data={**definition, "source": "uploaded",
                                              "module_path": module_path})
            self.actualizar_biblioteca_ci()
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, tr("No se pudo cargar el módulo"), tr(str(exc)))

    def about(self):
        self.creditos_window = VentanaCreditos(self.Credit_Form, self)
        self.creditos_window.exec()
    def tutorial(self):
        QMessageBox.information(self, tr("Guía rápida"),
            tr("Elige un componente a la izquierda y haz clic en el tablero para colocarlo, o arrástralo hasta su posición. "
            "Esc o clic derecho cancela; Enter lo coloca en el centro visible. Haz clic en un puerto y después en otro para cablearlos.\n\n"
            "Un clic en vacío añade un codo; doble clic termina el cable con un extremo libre. Usa la rueda para zoom, "
            "la rueda central para desplazarte, Supr para borrar y doble clic sobre un interruptor para cambiarlo.\n\n"
            "RETARDO retrasa una señal; usa Editar para configurar el tiempo y el retraso de cálculo. Usa Ver para cambiar el tema o ajustar la vista.\n\n"
            "Selecciona un grupo y usa Widgets → Crear CI para convertirlo en un módulo reutilizable."))

    def mostrar_manual(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Manual de DaLogic"))
        dialog.resize(900, 680)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget(dialog)
        for title, path in (("Manual", BASE_DIR / ("README.md" if language_code() == "es" else f"docs/manual.{language_code()}.md")),
                            ("Componentes", BASE_DIR / "docs" / ("componentes-1.2.md" if language_code() == "es" else f"componentes.{language_code()}.md")),
                            ("Tiempo y memoria", BASE_DIR / "docs" / ("tiempo-y-realimentacion.md" if language_code() == "es" else f"tiempo.{language_code()}.md"))):
            browser = QTextBrowser(tabs)
            browser.setOpenExternalLinks(True)
            try:
                browser.setMarkdown(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                browser.setPlainText((tr("No se pudo leer este documento: ") + tr(path.name)))
            tabs.addTab(browser, tr(title))
        layout.addWidget(tabs)
        close = QPushButton(tr("Cerrar"), dialog)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def comprobar_circuito(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Comprobar circuito"))
        dialog.resize(850, 480)
        layout = QVBoxLayout(dialog)
        issues = inspect_circuit(self)
        summary = QLabel(tr('{v0} componentes · {v1} incidencias. Doble clic para localizar un elemento.', v0=len(self.all_widgets), v1=len(issues)), dialog)
        summary.setWordWrap(True)
        layout.addWidget(summary)
        table = QTableWidget(len(issues), 2, dialog)
        table.setHorizontalHeaderLabels([tr("Nivel"), tr("Descripción")])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().hide()
        for row, issue in enumerate(issues):
            table.setItem(row, 0, QTableWidgetItem(tr(issue.severity)))
            table.setItem(row, 1, QTableWidgetItem(tr(issue.message)))
        table.resizeColumnToContents(0)
        def locate(row, _column):
            target = issues[row].target
            if target is not None and target.scene() is self.ui.graphicsView.scene:
                self.ui.graphicsView.scene.clearSelection()
                target.setSelected(True)
                self.ui.graphicsView.centerOn(target)
                dialog.accept()
        table.cellDoubleClicked.connect(locate)
        layout.addWidget(table)
        layout.addWidget(QLabel((tr("No se han detectado incidencias.") if not issues else tr("Los puertos libres pueden ser intencionados; revisa los avisos según tu diseño.")), dialog))
        close = QPushButton(tr("Cerrar"), dialog)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()


if __name__ == "__main__":
    sys.exit(run(VentanaInicial))
