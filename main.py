# This Python file uses the following encoding: utf-8
import sys
import ast
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QTextBrowser,
    QPushButton, QFileDialog, QInputDialog, QMessageBox, QToolBar,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QWidget, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QGroupBox, QSpinBox, QLineEdit, QComboBox, QTabWidget
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QImage, QPainter, QPixmap,
    QPageLayout, QPageSize, QPdfWriter
)
from PySide6.QtCore import QRect, QRectF, QPointF, QSize, Qt, QEvent, QTimer
import csv
import re
import importlib
import json
import time
import zipfile
from xml.sax.saxutils import escape as xml_escape

from resources.app_icon import get_app_icon

import widgets.widgets as wdg
import widgets.graphics as gra
from widgets.graphics import Port, Wire, Junction, WireEndpoint
from project_io import dump_project, module_definition

BASE_DIR = Path(__file__).resolve().parent
USER_DIR = BASE_DIR / "user"
CI_LIBRARY_DIR = USER_DIR / "Biblioteca"
LEGACY_CI_LIBRARY_DIR = USER_DIR / "Biblioteca de CI"
LANGUAGE_DIR = USER_DIR / "Idiomas"
PROJECTS_DIR = BASE_DIR / "Proyectos"
EXPORTS_DIR = BASE_DIR / "Exports"
os.chdir(BASE_DIR)

# La interfaz generada se incluye en el repositorio. Compilarla en cada arranque
# hacía que la aplicación se bloqueara cuando Qt Creator no estaba instalado.


# ── Diálogos auxiliares ──────────────────────────────────────────────────────

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
            with open("NOTICE", "r", encoding="utf-8") as f:
                texto = f.read()
        except FileNotFoundError:
            texto = ("DaLogic\n\nCopyright 2026 David Lopez Borrego\n\n"
                     "https://github.com/davidlb025/DaLogic")
        label = self.findChild(QTextBrowser, "Creditos")
        if label:
            label.setHtml(self.format_notice(texto))


class TruthTableDialog(QDialog):
    def __init__(self, rows, input_labels, output_labels, calculation_ms,
                 ignored_summary="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tabla de verdad del circuito")
        self.resize(980, 620)

        layout = QVBoxLayout(self)
        summary = QLabel(
            f"{len(input_labels)} entradas · {len(rows)} combinaciones · "
            f"Cálculo: {calculation_ms:.2f} ms", self)
        summary.setStyleSheet("font-weight: 600; padding: 4px 0;")
        layout.addWidget(summary)
        notation = QLabel(
            "Bombillas: 0/1 · Displays: índices de segmentos encendidos (p. ej. 012); — sin segmentos",
            self)
        notation.setWordWrap(True)
        layout.addWidget(notation)
        if ignored_summary:
            ignored = QLabel(ignored_summary, self)
            ignored.setWordWrap(True)
            ignored.setStyleSheet("padding: 4px 0;")
            layout.addWidget(ignored)

        table_tools = QHBoxLayout()
        search = QLineEdit(self)
        search.setClearButtonEnabled(True)
        search.setPlaceholderText("Filtrar filas por valor (p. ej. 012 o 1)…")
        table_tools.addWidget(search, 1)
        fit_columns = QPushButton("Ajustar columnas", self)
        fit_columns.setToolTip("Ajusta el ancho al contenido; también puedes arrastrar los bordes de las cabeceras")
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
        table.horizontalHeader().setToolTip("Arrastra el borde entre cabeceras para cambiar el ancho")
        for row_index, row in enumerate(rows):
            values = [*("1" if value else "0" for value in row["inputs"]),
                      *row["outputs"], str(row["time_ms"])]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, column, cell)
        table.resizeColumnsToContents()
        fit_columns.clicked.connect(table.resizeColumnsToContents)
        search.textChanged.connect(self._filter_rows)
        layout.addWidget(table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        export = QPushButton("Exportar tabla…", self)
        export.clicked.connect(self._export_table)
        buttons.addWidget(export)
        close = QPushButton("Cerrar", self)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _export_table(self):
        formats = ("Imagen PNG (*.png);;Documento PDF (*.pdf);;Gráfico SVG (*.svg);;"
                   "Libro de Excel (*.xlsx);;CSV para Excel (*.csv)")
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path, selected_filter = QFileDialog.getSaveFileName(self, "Exportar tabla de verdad", str(EXPORTS_DIR / "tabla_verdad.png"),
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
            QMessageBox.critical(self, "No se pudo exportar la tabla", str(exc))

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
                             str(header))
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
                                 str(value))
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
                raise RuntimeError("No se pudo crear el PDF.")
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
            generator.setTitle("Tabla de verdad del circuito")
            painter = QPainter(generator)
            painter.fillRect(QRectF(0, 0, width, height), QColor("#ffffff"))
            self._paint_table_rows(painter, headers, rows, widths, 0, 0, head_h, row_h)
            painter.end()
        else:
            scale = min(1.0, (50_000_000 / max(1, width * height)) ** 0.5)
            image = QImage(max(1, int(width * scale)), max(1, int(height * scale)),
                           QImage.Format.Format_ARGB32)
            if image.isNull():
                raise RuntimeError("La imagen es demasiado grande para PNG.")
            image.fill(QColor("#ffffff"))
            painter = QPainter(image)
            painter.scale(scale, scale)
            self._paint_table_rows(painter, headers, rows, widths, 0, 0, head_h, row_h)
            painter.end()
            if not image.save(path, "PNG"):
                raise RuntimeError("No se pudo guardar el PNG.")


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
        self.setToolTip("Doble clic para localizar este componente en el circuito")

    def mouseDoubleClickEvent(self, event):
        self._on_double_click()
        event.accept()


class TruthTableOrderDialog(QDialog):
    def __init__(self, inputs, outputs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Orden de la tabla de verdad")
        self.resize(560, 500)
        self.input_fields = []
        self.output_fields = []

        layout = QVBoxLayout(self)
        instructions = QLabel(
            "Asigna un número único a cada columna; el número menor aparece primero.\n"
            "Haz doble clic en el nombre de una entrada o salida para localizarla en el circuito.", self)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        columns = QHBoxLayout(content)
        for title, widgets, fields in (("Entradas", inputs, self.input_fields),
                                       ("Salidas", outputs, self.output_fields)):
            group = QGroupBox(title, content)
            group_layout = QVBoxLayout(group)
            for index, widget in enumerate(widgets):
                if isinstance(widget, (wdg.Switch, wdg.Button)):
                    kind = "Botón" if isinstance(widget, wdg.Button) else "Interruptor"
                else:
                    kind = "Bombilla" if isinstance(widget, wdg.Bulb) else "Display"
                row = QHBoxLayout()
                label_text = f"{kind} {widget.id}"
                if parent is not None:
                    label = FocusLabel(label_text,
                        lambda target=widget: parent.localizar_elemento_tabla(target), group)
                else:
                    label = QLabel(label_text, group)
                row.addWidget(label)
                number = QSpinBox(group)
                number.setRange(0, 999)
                number.setPrefix("N.º ")
                number.setToolTip("Orden de esta columna en la tabla de verdad")
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
        calculate = QPushButton("Calcular tabla", self)
        calculate.clicked.connect(self.accept)
        cancel = QPushButton("Cancelar", self)
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
        "BOTON":       (wdg.Button,  gra.LogicGateGraphic, None, 1.0),
        "RETARDO":     (wdg.Delay,   gra.LogicGateGraphic, None, 1.0),
        "BOMBILLA":    (wdg.Bulb,    gra.BulbGraphic,    None,                          1.0),
        "DISPLAY":     (wdg.Display, gra.DisplayGraphic, None,                          1.0),
    }

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.load_settings()
        self.iniciarUI()
        self.def_actions()
        self._prepare_language_selector()
        self._apply_saved_language()
        self._setup_history()

    def iniciarUI(self):
        self.all_widgets: dict[int, wdg.Widget]   = {}
        self.all_graphics: dict[int, gra.Graphic] = {}
        self.next_id = 0
        self.project_path: Path | None = None
        self.project_name = "Sin título"
        self._clipboard: list[dict] = []
        self.imported_modules: list[dict] = []
        self._undo_history = []
        self._redo_history = []
        self._history_restoring = False
        self._history_snapshot_json = None

        self.ui = self.MainWindow
        self.ui.setupUi(self)
        self._original_icons = {}
        self._capturar_iconos()
        self.ui.tabWidget.setTabText(self.ui.tabWidget.indexOf(self.ui.Puertas), "Básico")
        self.ui.tabWidget.setTabText(self.ui.tabWidget.indexOf(self.ui.tab_2), "CI")
        self.app.setStyle("Fusion")
        self.theme_mode = "dark" if "dark" in self.config.get("theme", "") else "light"
        self.aplicar_tema(self.theme_mode, persist=False)

        self.ui.Show.hide()
        self.ui.Show.clicked.connect(self.devolver_widg_panel)

        self.ui.close = QPushButton("X", self.ui.menu.viewport(), flat=True)
        self.ui.close.move(-10, -10)
        self.ui.close.raise_()
        self.ui.close.show()
        self.ui.close.setFixedWidth(30)
        self.ui.close.clicked.connect(self.cerrar_widg_panel)
        self.ui.splitter.splitterMoved.connect(self.check_widg_panel)

        self.ui.graphicsView.board_ref = self.ui.graphicsView
        self.ui.graphicsView.owner = self
        self.ui.graphicsView.centerOn(0, 0)

        self.def_buttons()
        self._preparar_biblioteca_ci()
        self._preparar_interfaz_profesional()
        self.setWindowTitle("DaLogic — Sin título")
        self.show()

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
                btn.clicked.connect(lambda checked=False, t=tipo: self.crear_widget(t))
        self.ui.RETARDO = QPushButton("RETARDO", self.ui.Puertas)
        self.ui.RETARDO.setToolTip("Retrasa una señal; configura los milisegundos con clic derecho.")
        self.ui.verticalLayout_2.insertWidget(self.ui.verticalLayout_2.count() - 1, self.ui.RETARDO)
        self.ui.RETARDO.clicked.connect(lambda: self.crear_widget("RETARDO"))
        self.ui.BOTON = QPushButton("BOTÓN", self.ui.Puertas)
        self.ui.BOTON.setToolTip("Activa la salida solo mientras mantienes pulsado el componente.")
        self.ui.verticalLayout_2.insertWidget(self.ui.verticalLayout_2.count() - 1, self.ui.BOTON)
        self.ui.BOTON.clicked.connect(lambda: self.crear_widget("BOTON"))

    # ── Creación de widgets ──────────────────────────────────────────────────

    def crear_widget(self, tipo: str, position=None, data: dict | None = None):
        """Crea un componente y devuelve su representación gráfica."""
        data = data or {}
        widget_id = int(data.get("id", self.next_id))
        if tipo == "MODULO":
            new_widg = wdg.Module(widget_id, data.get("name", "Módulo"),
                                   int(data.get("inputs", 1)), int(data.get("outputs", 1)),
                                   data.get("truth_table", []),
                                   data.get("input_numbers"), data.get("output_numbers"))
            new_widg.delay_ms = int(data.get("delay_ms", new_widg.delay_ms))
            new_widg.module_source = data.get("source", "")
            module_path = data.get("module_path")
            if module_path and Path(module_path).parent.name.casefold() == LEGACY_CI_LIBRARY_DIR.name.casefold():
                migrated_path = CI_LIBRARY_DIR / Path(module_path).name
                if migrated_path.exists():
                    module_path = str(migrated_path)
            new_widg.module_path = module_path
            new_graph = gra.ModuleGraphic(new_widg)
        else:
            if tipo not in self.WIDGET_DEFS:
                raise ValueError(f"Componente desconocido: {tipo}")
            cls_widg, cls_graph, svg_path, scale = self.WIDGET_DEFS[tipo]
            new_widg = cls_widg(widget_id)
            if new_widg.can_set_enter() and "inputs" in data:
                new_widg.set_enter(int(data["inputs"]))
            if new_widg.can_set_exit() and "outputs" in data:
                new_widg.set_exit(int(data["outputs"]))
            new_widg.delay_ms = int(data.get("delay_ms", new_widg.delay_ms))
            if isinstance(new_widg, wdg.Bulb):
                new_widg.bulb_color = data.get("bulb_color")
            elif isinstance(new_widg, wdg.Display):
                colors = data.get("segment_colors", [None] * 7)
                new_widg.segment_colors = (list(colors) + [None] * 7)[:7]
            if isinstance(new_widg, (wdg.Switch, wdg.Button)):
                new_widg.state = bool(data.get("state", False))
                new_widg.exit[0] = new_widg.state
            new_graph = cls_graph(new_widg) if cls_graph else gra.Graphic(new_widg, svg_path, scale)

        if "truth_table_number" in data and data["truth_table_number"] is not None:
            new_widg.truth_table_number = int(data["truth_table_number"])
        elif isinstance(new_widg, (wdg.Switch, wdg.Button)):
            existing = [getattr(widget, "truth_table_number", -1)
                        for widget in self.all_widgets.values()
                        if isinstance(widget, (wdg.Switch, wdg.Button))]
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
        self.all_widgets[widget_id] = new_widg
        self.all_graphics[widget_id] = new_graph
        self.next_id = max(self.next_id, widget_id + 1)
        return new_graph

    def type_for_widget(self, widget) -> str:
        if isinstance(widget, wdg.Module):
            return "MODULO"
        for name, (klass, *_rest) in self.WIDGET_DEFS.items():
            if isinstance(widget, klass):
                return name
        raise ValueError(f"Tipo no serializable: {type(widget).__name__}")

    # ── Panel lateral ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updt_button()

    def updt_button(self):
        m = 1
        self.ui.close.move(
            self.ui.menu.viewport().width() - self.ui.close.width() - m, m
        )

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
        self.ui.actionGuardar.triggered.connect(self.guardar)
        self.ui.actionGuardar_Como.triggered.connect(self.guardarcomo)
        self.ui.actionImprimir.triggered.connect(self.imprimir)
        self.ui.actionNuevo.triggered.connect(self.nuevo)
        self.ui.actionRecientes.triggered.connect(self.recientes)
        self.ui.actionSalir.triggered.connect(self.salir_app)
        self.ui.actionCopiar.triggered.connect(self.copiar)
        self.ui.actionCortar.triggered.connect(self.cortar)
        self.ui.actionPegar.triggered.connect(self.pegar)
        self.ui.actionSobre_Nosotros.triggered.connect(self.about)
        self.ui.actionSobre_Nosotros_2.triggered.connect(self.about)
        self.ui.actionTutorial.triggered.connect(self.tutorial)
        self.ui.actionGuardar_CI.triggered.connect(self.crear_modulo)
        self.ui.actionCargar_CI.triggered.connect(self.cargar_modulo)
        self.ui.menuWidgets.removeAction(self.ui.actionCrear_Seccion)
        self.actionCalcularTabla = QAction("Calcular tabla de verdad", self)
        self.actionCalcularTabla.setShortcut("Ctrl+Shift+F")
        self.actionCalcularTabla.triggered.connect(self.calcular_tabla_verdad)
        self.ui.menuWidgets.addSeparator()
        self.ui.menuWidgets.addAction(self.actionCalcularTabla)
        self.actionDeshacer = QAction("Deshacer", self)
        self.actionDeshacer.setShortcut("Ctrl+Z")
        self.actionDeshacer.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.actionDeshacer.triggered.connect(self.deshacer)
        self.actionRehacer = QAction("Rehacer", self)
        self.actionRehacer.setShortcut("Ctrl+Y")
        self.actionRehacer.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.actionRehacer.triggered.connect(self.rehacer)
        self.ui.menuEditar.insertAction(self.ui.menuEditar.actions()[0]
                                        if self.ui.menuEditar.actions() else None,
                                        self.actionDeshacer)
        self.ui.menuEditar.insertAction(self.ui.menuEditar.actions()[1]
                                        if len(self.ui.menuEditar.actions()) > 1 else None,
                                        self.actionRehacer)

    def _preparar_interfaz_profesional(self):
        """Mantiene solo acciones útiles y ofrece los atajos visibles de uso diario."""
        # Configuración e impresión no tenían efecto real; se eliminan en vez de
        # presentar promesas vacías al usuario.
        self.ui.menuArchivo.removeAction(self.ui.actionConfiguracion)
        self.ui.menuArchivo.removeAction(self.ui.actionImprimir)
        self.ui.menuArchivo.removeAction(self.ui.actionSobre_Nosotros)

        self.actionTema = QAction("Tema oscuro", self)
        self.actionTema.setCheckable(True)
        self.actionTema.setShortcut("Ctrl+Shift+T")
        self.actionTema.setChecked(self.theme_mode == "dark")
        self.actionTema.toggled.connect(lambda dark: self.aplicar_tema("dark" if dark else "light"))
        self.actionAjustarVista = QAction("Ajustar a circuito", self)
        self.actionAjustarVista.setShortcut("Ctrl+0")
        self.actionAjustarVista.triggered.connect(self.ajustar_vista)
        self.actionEliminar = QAction("Eliminar selección", self)
        self.actionEliminar.setShortcut("Supr")
        self.actionEliminar.triggered.connect(self.eliminar_seleccion)

        self.menuVer = self.menuBar().addMenu("Ver")
        self.menuVer.addAction(self.actionTema)
        self.menuVer.addAction(self.actionAjustarVista)

        toolbar = QToolBar("Acciones principales", self)
        toolbar.setObjectName("barraPrincipal")
        toolbar.setMovable(False)
        toolbar.addAction(self.ui.actionNuevo)
        toolbar.addAction(self.ui.actionAbrir)
        toolbar.addAction(self.ui.actionGuardar)
        toolbar.addSeparator()
        toolbar.addAction(self.ui.actionCopiar)
        toolbar.addAction(self.ui.actionPegar)
        toolbar.addAction(self.actionEliminar)
        toolbar.addSeparator()
        toolbar.addAction(self.actionAjustarVista)
        toolbar.addAction(self.actionTema)
        self.addToolBar(toolbar)
        toolbar.addSeparator()
        language_label = QLabel("Idioma", self)
        self.language_combo = QComboBox(self)
        self.language_combo.setObjectName("languageSelector")
        self.language_combo.setToolTip("Seleccionar idioma")
        self.language_combo.setMinimumWidth(125)
        toolbar.addWidget(language_label)
        toolbar.addWidget(self.language_combo)
        self.statusBar().showMessage("Listo · rueda: zoom · botón central: desplazar", 5000)

    def _language_catalogs(self):
        LANGUAGE_DIR.mkdir(parents=True, exist_ok=True)
        spanish_path = LANGUAGE_DIR / "es.json"
        if not spanish_path.exists():
            spanish_path.write_text(json.dumps(
                {"code": "es", "name": "Español", "translations": {}},
                ensure_ascii=False, indent=2), encoding="utf-8")
        catalogs = {}
        for path in sorted(LANGUAGE_DIR.glob("*.json"), key=lambda item: item.name.casefold()):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                translations = payload.get("translations", {})
                if not isinstance(translations, dict):
                    continue
                code = str(payload.get("code") or path.stem)
                name = str(payload.get("name") or code)
                catalogs[code] = {
                    "code": code, "name": name,
                    "translations": {str(k): str(v) for k, v in translations.items()
                                    if isinstance(v, (str, int, float))}
                }
            except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
                continue
        return catalogs

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
        saved_name = "_dalogic_original_" + prop
        saved = getattr(obj, saved_name, None)
        if saved is not None:
            return saved
        getter = getattr(obj, prop, None)
        if not callable(getter):
            return None
        try:
            value = getter()
        except (RuntimeError, TypeError):
            return None
        if not isinstance(value, str) or not value:
            return None
        try:
            setattr(obj, saved_name, value)
        except (AttributeError, RuntimeError):
            return None
        return value

    def _collect_language_defaults(self):
        defaults = {}
        props = ("text", "windowTitle", "title", "toolTip", "statusTip",
                 "whatsThis", "placeholderText", "accessibleName")
        for obj in self._language_objects():
            for prop in props:
                value = self._original_text(obj, prop)
                if value:
                    defaults[value] = value
            if isinstance(obj, QTabWidget):
                original = getattr(obj, "_dalogic_original_tabs", None)
                if original is None:
                    original = [obj.tabText(i) for i in range(obj.count())]
                    obj._dalogic_original_tabs = original
                defaults.update((value, value) for value in original if value)
            if isinstance(obj, QComboBox):
                original = getattr(obj, "_dalogic_original_items", None)
                if original is None:
                    original = [obj.itemText(i) for i in range(obj.count())]
                    obj._dalogic_original_items = original
                defaults.update((value, value) for value in original if value)
        for relative in ("main.py", "board_view.py", "widgets/widgets.py",
                         "widgets/graphics.py", "resources/compiled/ui_ventana1.py",
                         "resources/compiled/ui_config.py", "resources/compiled/ui_credits.py"):
            try:
                syntax = ast.parse((BASE_DIR / relative).read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(syntax):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and 1 < len(node.value) <= 180 and node.value.strip()
                        and any(character.isalpha() for character in node.value)):
                    defaults.setdefault(node.value, node.value)
        return defaults

    def _prepare_language_selector(self):
        catalogs = self._language_catalogs()
        spanish = catalogs.get("es", {"translations": {}})
        translations = spanish["translations"]
        for source, value in self._collect_language_defaults().items():
            translations.setdefault(source, value)
        spanish.update(code="es", name=spanish.get("name") or "Español",
                       translations=translations)
        (LANGUAGE_DIR / "es.json").write_text(
            json.dumps(spanish, ensure_ascii=False, indent=2), encoding="utf-8")
        catalogs["es"] = spanish
        for catalog in sorted(catalogs.values(), key=lambda item: item["code"]):
            self.language_combo.addItem(catalog["name"], catalog["code"])
        selected = str(self.config.get("lang", "es"))
        index = self.language_combo.findData(selected)
        if index < 0:
            index = self.language_combo.findData("es")
        self.language_combo.setCurrentIndex(max(0, index))
        self.language_combo.currentIndexChanged.connect(self._select_language)
        self.language_catalogs = catalogs
        self.app.installEventFilter(self)

    def _localized_window_title(self):
        translated = self.language_translations.get(
            "DaLogic — Sin título", "DaLogic — Sin título")
        if self.project_path is None:
            return translated
        prefix = self.language_translations.get("DaLogic — ", "DaLogic — ")
        return f"{prefix}{self.project_name}"

    def _apply_saved_language(self):
        code = self.language_combo.currentData() or "es"
        self._apply_language(str(code), persist=False)

    def _select_language(self, index):
        code = self.language_combo.itemData(index)
        if code:
            self._apply_language(str(code), persist=True)

    def _apply_language(self, code, persist=True):
        catalogs = self._language_catalogs()
        catalog = catalogs.get(code) or catalogs.get("es", {})
        self.language_code = catalog.get("code", "es")
        self.language_translations = catalog.get("translations", {})
        self.language_catalogs = catalogs
        gra.set_language_translations(self.language_translations)
        self._apply_language_tree(self)
        for item in self.ui.graphicsView.scene.items():
            if isinstance(item, Port):
                item.update_tooltip()
            elif hasattr(item, "_update_bridge_tooltip"):
                item._update_bridge_tooltip()
            elif isinstance(item, Wire):
                item.setToolTip(gra.translate_text("Clic derecho para cambiar el color del cable"))
            if isinstance(item, gra.Graphic):
                item.update()
            if isinstance(item, gra.BulbGraphic):
                item.setToolTip(gra.translate_text("Bombilla") + f" {item.widg.id}" + gra.translate_text(" · clic derecho para ajustar el retardo"))
        if persist:
            self.config["lang"] = self.language_code
            try:
                (USER_DIR / "config.json").write_text(
                    json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass

    def _apply_language_tree(self, root):
        props = ("text", "windowTitle", "title", "toolTip", "statusTip",
                 "whatsThis", "placeholderText", "accessibleName")
        translations = getattr(self, "language_translations", {})
        for obj in self._language_objects(root):
            for prop in props:
                if obj is self and prop == "windowTitle":
                    obj.setWindowTitle(self._localized_window_title())
                    continue
                source = self._original_text(obj, prop)
                if source is None:
                    continue
                setter = getattr(obj, "set" + prop[0].upper() + prop[1:], None)
                if callable(setter):
                    try:
                        setter(translations.get(source, source))
                    except RuntimeError:
                        pass
            if isinstance(obj, QTabWidget):
                original = getattr(obj, "_dalogic_original_tabs", None)
                if original is None:
                    original = [obj.tabText(i) for i in range(obj.count())]
                    obj._dalogic_original_tabs = original
                for i, source in enumerate(original):
                    if i < obj.count():
                        obj.setTabText(i, translations.get(source, source))
            if isinstance(obj, QComboBox):
                original = getattr(obj, "_dalogic_original_items", None)
                if original is None:
                    original = [obj.itemText(i) for i in range(obj.count())]
                    obj._dalogic_original_items = original
                for i, source in enumerate(original):
                    if i < obj.count():
                        obj.setItemText(i, translations.get(source, source))

    def eventFilter(self, watched, event):
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
        return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _reset_history(self):
        if hasattr(self, "_history_timer"):
            self._history_timer.stop()
        self._undo_history = []
        self._redo_history = []
        self._history_snapshot_json = self._history_key(self._history_state())
        self._update_history_actions()

    def _schedule_history_capture(self, *_args):
        if not self._history_restoring and hasattr(self, "_history_timer"):
            self._history_timer.start()

    def _capture_history_change(self):
        if self._history_restoring:
            return
        state = self._history_state()
        key = self._history_key(state)
        if key == self._history_snapshot_json:
            return
        previous = json.loads(self._history_snapshot_json)
        self._undo_history.append(previous)
        del self._undo_history[:-100]
        self._redo_history.clear()
        self._history_snapshot_json = key
        self._update_history_actions()

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
        return module_definition(str(data.get("name", "Módulo")),
            int(data.get("inputs", 1)), int(data.get("outputs", 1)),
            data.get("truth_table", []), int(data.get("delay_ms", 0)),
            data.get("input_numbers"), data.get("output_numbers"))

    def _module_signature(self, data):
        definition = self._module_definition(data)
        rows = tuple((tuple(row["inputs"]), tuple(row["outputs"]), row["time_ms"])
                     for row in definition["truth_table"])
        return (definition["name"].casefold(), definition["inputs"],
                definition["outputs"], tuple(definition["input_numbers"]),
                tuple(definition["output_numbers"]), rows)

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
        for path in sorted(CI_LIBRARY_DIR.glob("*.dmodule"), key=lambda item: item.name.casefold()):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("format") == "DaLogic module" and int(data.get("version", 0)) in {1, 2}:
                    modules.append((path, self._module_definition(data)))
            except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
                continue
        return modules

    def _preparar_biblioteca_ci(self):
        self._ci_layout = QVBoxLayout(self.ui.tab_2)
        self._ci_layout.setContentsMargins(8, 8, 8, 8)
        self._ci_layout.setSpacing(0)
        self._ci_scroll = QScrollArea(self.ui.tab_2)
        self._ci_scroll.setObjectName("ciLibraryScroll")
        self._ci_scroll.setWidgetResizable(True)
        self._ci_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._ci_content = QWidget()
        self._ci_content.setObjectName("ciLibraryContent")
        self._ci_content_layout = QVBoxLayout(self._ci_content)
        self._ci_content_layout.setContentsMargins(4, 4, 4, 8)
        self._ci_content_layout.setSpacing(6)
        self._ci_scroll.setWidget(self._ci_content)
        self._ci_layout.addWidget(self._ci_scroll)
        self.actualizar_biblioteca_ci()

    def _add_ci_section(self, title, entries, empty_text):
        heading = QLabel(title, self._ci_content)
        heading.setObjectName("ciSectionTitle")
        self._ci_content_layout.addWidget(heading)
        if not entries:
            empty = QLabel(empty_text, self._ci_content)
            empty.setObjectName("ciEmptyState")
            empty.setWordWrap(True)
            self._ci_content_layout.addWidget(empty)
            return
        for label, definition, source in entries:
            button = QPushButton(label, self._ci_content)
            button.setObjectName("ciModuleButton")
            button.setToolTip(f"{definition['inputs']} entradas · {definition['outputs']} salidas")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            module_data = {**definition, "source": source}
            if definition.get("module_path"):
                module_data["module_path"] = definition["module_path"]
            button.clicked.connect(lambda checked=False, d=module_data:
                                    self.crear_widget("MODULO", data=d))
            self._ci_content_layout.addWidget(button)

    def actualizar_biblioteca_ci(self):
        if not hasattr(self, "_ci_content_layout"):
            return
        while self._ci_content_layout.count():
            item = self._ci_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        library = self._read_ci_library()
        library_sigs = {self._module_signature(data) for _path, data in library}
        imported = []
        imported_sigs = set()
        imported_definitions = list(self.imported_modules)
        imported_definitions.extend(
            self._module_definition({"name": widget.name,
                "inputs": len(widget.enter), "outputs": len(widget.exit),
                "truth_table": widget.truth_table,
                "input_numbers": widget.input_numbers,
                "output_numbers": widget.output_numbers})
            for widget in self.all_widgets.values()
            if isinstance(widget, wdg.Module) and
            getattr(widget, "module_source", "") == "uploaded")
        for data in imported_definitions:
            signature = self._module_signature(data)
            if signature not in imported_sigs:
                imported.append((data["name"], data, "uploaded"))
                imported_sigs.add(signature)
        current_modules = [widget for widget in self.all_widgets.values()
                           if isinstance(widget, wdg.Module)]
        loaded = []
        for widget in current_modules:
            source = getattr(widget, "module_source", "")
            if source == "uploaded":
                continue
            definition = self._module_definition({"name": widget.name,
                "inputs": len(widget.enter), "outputs": len(widget.exit),
                "truth_table": widget.truth_table,
                "input_numbers": widget.input_numbers,
                "output_numbers": widget.output_numbers})
            signature = self._module_signature(definition)
            if signature in library_sigs or signature in imported_sigs or source not in {"project", "library"}:
                continue
            if any(self._module_signature(item[1]) == signature for item in loaded):
                continue
            loaded.append((definition["name"], definition, "project"))

        self._add_ci_section("Biblioteca", [(data["name"],
                            {**data, "module_path": str(path.resolve())}, "library")
                            for path, data in library], "Guarda un CI para tenerlo disponible aquí.")
        separator = QFrame(self._ci_content)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("ciSeparator")
        self._ci_content_layout.addWidget(separator)
        self._add_ci_section("Subido", imported, "Los CI importados aparecerán aquí.")
        if loaded:
            separator = QFrame(self._ci_content)
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setObjectName("ciSeparator")
            self._ci_content_layout.addWidget(separator)
            self._add_ci_section("Cargado", loaded, "")
        self._ci_content_layout.addStretch(1)

    def _save_ci_definition(self, name, inputs, outputs, table):
        suggested = CI_LIBRARY_DIR / f"{name}.dmodule"
        save, _ = QFileDialog.getSaveFileName(
            self, "Guardar CI en Biblioteca", str(suggested), "Módulo DaLogic (*.dmodule)")
        if not save:
            return None
        path = Path(save).with_suffix(".dmodule")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(module_definition(name, inputs, outputs, table),
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "No se pudo guardar el CI", str(exc))
            return None
        self._mark_module_source(name, inputs, outputs, table, "library")
        self.actualizar_biblioteca_ci()
        return path.resolve()

    def _mark_module_source(self, name, inputs, outputs, table, source):
        target = self._module_signature({"name": name, "inputs": inputs,
                                         "outputs": outputs, "truth_table": table})
        for widget in self.all_widgets.values():
            if isinstance(widget, wdg.Module) and self._module_signature({
                    "name": widget.name, "inputs": len(widget.enter),
                    "outputs": len(widget.exit), "truth_table": widget.truth_table,
                    "input_numbers": widget.input_numbers,
                    "output_numbers": widget.output_numbers}) == target:
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
        path = BASE_DIR / "resources" / "styles" / f"{self.theme_mode}.qss"
        self.app.setStyleSheet(self.cargar_tema(str(path)))
        if hasattr(self, "ui"):
            self.ui.graphicsView.set_theme(self.theme_mode)
            self._actualizar_tinta_iconos()
        if persist:
            self.config["theme"] = str(path.relative_to(BASE_DIR)).replace("\\", "/")
            (BASE_DIR / "user" / "config.json").write_text(
                json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        if hasattr(self, "actionTema"):
            self.actionTema.blockSignals(True)
            self.actionTema.setChecked(self.theme_mode == "dark")
            self.actionTema.setText("Tema claro" if self.theme_mode == "dark" else "Tema oscuro")
            self.actionTema.blockSignals(False)

    def ajustar_vista(self):
        items = [item for item in self.ui.graphicsView.scene.items()
                 if not (hasattr(item, "zValue") and item.zValue() == -1)]
        if items:
            rect = QRectF()
            for item in items:
                rect = rect.united(item.sceneBoundingRect())
            rect = rect.adjusted(-60, -60, 60, 60)
            self.ui.graphicsView.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.ui.graphicsView.zoom_act = 1.0
        else:
            self.ui.graphicsView.centerOn(0, 0)

    def eliminar_seleccion(self):
        board = self.ui.graphicsView
        for item in list(board.scene.selectedItems()):
            if isinstance(item, Wire):
                board._remove_wire(item)
            elif isinstance(item, gra.Graphic):
                board._remove_graphic(item)
            elif isinstance(item, Junction):
                board._remove_junction(item)

    # ── Config ───────────────────────────────────────────────────────────────

    def create_config(self, file_path="user/config.json"):
        config = {
            "theme":      "resources/styles/light.qss",
            "lang":       "es",
            "main_UI":    "resources.compiled.ui_ventana1",
            "credits_UI": "resources.compiled.ui_credits",
            "config_UI":  "resources.compiled.ui_config",
        }
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def load_UI(self, ui, default, type_name):
        try:
            module   = importlib.import_module(ui)
            ui_class = getattr(module, type_name)
        except (ModuleNotFoundError, AttributeError):
            module   = importlib.import_module("resources.compiled.ui_ventana1")
            ui_class = getattr(module, "Ui_MainWindow")
        return ui_class

    def get_settings(self, file_path="user/config.json"):
        REQUIRED = ["theme", "lang", "main_UI", "credits_UI", "config_UI"]
        if not os.path.exists(file_path):
            self.create_config(file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except json.JSONDecodeError:
            self.create_config(file_path)
            self.get_settings(file_path)
        if any(k not in self.config for k in REQUIRED):
            self.create_config(file_path)
            self.get_settings(file_path)

    def load_settings(self):
        self.get_settings()
        self.MainWindow  = self.load_UI(self.config["main_UI"],    "ui_ventana1", "Ui_MainWindow")()
        self.Credit_Form = self.load_UI(self.config["credits_UI"], "ui_credits",  "Ui_Form")()
        self.Config_Form = self.load_UI(self.config["config_UI"],  "ui_config",   "Ui_Form")()

    def cargar_tema(self, path="resources/styles/light.qss"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # ── Proyectos ───────────────────────────────────────────────────────────

    def _confirm_discard(self, message="¿Descartar el proyecto actual?"):
        return QMessageBox.question(self, "DaLogic", message,
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No) == QMessageBox.Yes

    def _clear_project(self):
        board = self.ui.graphicsView
        board._prop_timer.stop()
        board._signal_queue.clear()
        board._input_drivers.clear()
        board.scene.clear()
        board._draw_center()
        self.all_widgets.clear()
        self.all_graphics.clear()
        self.next_id = 0
        self.actualizar_biblioteca_ci()

    def nuevo(self):
        if self.all_widgets and not self._confirm_discard():
            return
        self._clear_project()
        self.project_path, self.project_name = None, "Sin título"
        self.setWindowTitle(self._localized_window_title())
        self._reset_history()

    def cerrar_proj(self):
        self.nuevo()

    def _remember_recent(self, path: Path):
        recent_file = BASE_DIR / "user" / "recent.json"
        try:
            recent = json.loads(recent_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            recent = []
        normalized = str(path.resolve())
        recent = [p for p in recent if p != normalized]
        recent_file.write_text(json.dumps([normalized, *recent][:10], indent=2), encoding="utf-8")

    def guardar(self):
        if self.project_path is None:
            return self.guardarcomo()
        try:
            self.project_path.write_text(json.dumps(dump_project(self), ensure_ascii=False, indent=2),
                                         encoding="utf-8")
            self._remember_recent(self.project_path)
            self.statusBar().showMessage("Proyecto guardado", 3000)
        except OSError as exc:
            QMessageBox.critical(self, "No se pudo guardar", str(exc))

    def guardarcomo(self):
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", str(PROJECTS_DIR / "proyecto.dalogic"), "Proyecto DaLogic (*.dalogic)")
        if not path:
            return
        self.project_path = Path(path).with_suffix(".dalogic")
        self.project_name = self.project_path.stem
        self.setWindowTitle(self._localized_window_title())
        self._reset_history()
        self.guardar()

    def abrir_archivo(self):
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", str(PROJECTS_DIR), "Proyecto DaLogic (*.dalogic);;JSON (*.json)")
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

    def cargar_proyecto(self, path: Path | None = None, _history_state=None):
        if _history_state is None and self.all_widgets and not self._confirm_discard("¿Cerrar el proyecto actual para abrir otro?"):
            return
        try:
            data = (_history_state["data"] if _history_state is not None else
                    json.loads(path.read_text(encoding="utf-8")))
            if data.get("format") != "DaLogic" or int(data.get("version", 0)) != 1:
                raise ValueError("No es un proyecto DaLogic compatible.")
            if not isinstance(data.get("components"), list):
                raise ValueError("El proyecto no contiene componentes válidos.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return

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
                self.crear_widget(item["type"], position=QPointF(x, y), data=component_data)
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
            QMessageBox.critical(self, "Proyecto inválido", f"No se pudo reconstruir el circuito: {exc}")
            return
        self.ui.graphicsView.rebuild_connections()
        if _history_state is None:
            self.project_path = path
            self.project_name = data.get("name") or path.stem
            self._remember_recent(path)
        else:
            saved_path = _history_state.get("project_path")
            self.project_path = Path(saved_path) if saved_path else None
            self.project_name = _history_state.get("project_name") or "Sin título"
            self.imported_modules = _history_state.get("imported_modules", [])
        self.setWindowTitle(self._localized_window_title())
        self.statusBar().showMessage("Proyecto cargado", 3000)
        self.actualizar_biblioteca_ci()
        if _history_state is None and not self._history_restoring:
            self._reset_history()

    def configure(self):
        self.config_window = VentanaConfig(self.Config_Form, self)
        self.config_window.exec()
    def exportar(self):
        filters = ("Imagen PNG (*.png);;Documento PDF (*.pdf);;"
                   "Gráfico vectorial SVG (*.svg)")
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
            QMessageBox.information(self, "Exportar", "No hay ningún circuito que exportar.")
            return
        if extension == ".svg":
            try:
                from PySide6.QtSvg import QSvgGenerator
            except ImportError as exc:
                QMessageBox.critical(self, "Exportar", f"No está disponible el exportador SVG: {exc}")
                return
            size = QSize(max(1, int(rect.width())), max(1, int(rect.height())))
            generator = QSvgGenerator()
            generator.setFileName(path)
            generator.setSize(size)
            generator.setViewBox(QRect(0, 0, size.width(), size.height()))
            generator.setTitle("DaLogic · circuito")
            painter = QPainter(generator)
            if not painter.isActive():
                QMessageBox.critical(self, "Exportar", "No se pudo crear el archivo SVG.")
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
                QMessageBox.critical(self, "Exportar", "No se pudo crear el documento PDF.")
                return
            target = QRectF(0, 0, writer.width(), writer.height())
            self.ui.graphicsView.scene.render(painter, target.adjusted(36, 36, -36, -36), rect)
            painter.end()
            return
        image = QImage(max(1, int(rect.width())), max(1, int(rect.height())), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.ui.graphicsView.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        image.save(path, "PNG")

    def imprimir(self):
        self.exportar()

    def recientes(self):
        try:
            recent = json.loads((BASE_DIR / "user" / "recent.json").read_text(encoding="utf-8"))
            recent = [p for p in recent if Path(p).is_file()]
        except (OSError, json.JSONDecodeError):
            recent = []
        if not recent:
            QMessageBox.information(self, "Recientes", "No hay proyectos recientes.")
            return
        choice, accepted = QInputDialog.getItem(self, "Proyectos recientes", "Abrir:", recent, 0, False)
        if accepted:
            self.cargar_proyecto(Path(choice))

    def salir_app(self):
        self.close()

    def copiar(self):
        selected = [g for g in self.ui.graphicsView.scene.selectedItems() if isinstance(g, gra.Graphic)]
        self._clipboard = []
        for graphic in selected:
            widget = graphic.widg
            item = {"type": self.type_for_widget(widget), "position": [graphic.x(), graphic.y()],
                    "inputs": len(widget.enter), "outputs": len(widget.exit), "delay_ms": widget.delay_ms,
                    "truth_table_number": getattr(widget, "truth_table_number", widget.id)}
            if isinstance(widget, (wdg.Switch, wdg.Button)): item["state"] = widget.state
            if isinstance(widget, wdg.Bulb): item["bulb_color"] = widget.bulb_color
            if isinstance(widget, wdg.Display): item["segment_colors"] = widget.segment_colors.copy()
            if isinstance(widget, wdg.Module):
                item.update(name=widget.name, truth_table=widget.truth_table,
                            input_numbers=widget.input_numbers,
                            output_numbers=widget.output_numbers,
                            source=getattr(widget, "module_source", ""),
                            module_path=getattr(widget, "module_path", None))
            self._clipboard.append(item)

    def cortar(self):
        self.copiar()
        for graphic in list(g for g in self.ui.graphicsView.scene.selectedItems() if isinstance(g, gra.Graphic)):
            self.ui.graphicsView._remove_graphic(graphic)

    def pegar(self):
        if not self._clipboard:
            return
        for item in self._clipboard:
            copy = dict(item)
            x, y = copy.pop("position")
            self.crear_widget(copy.pop("type"), QPointF(x + 30, y + 30), copy)
        self.ui.graphicsView.rebuild_connections()

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
        backups = {widget: (widget.enter.copy(), widget.exit.copy(),
                            getattr(widget, "response_ms", None)) for widget in chosen}
        table = []
        try:
            for combination in range(1 << len(inputs)):
                base_inputs = {widget: [False] * len(widget.enter) for widget in chosen}
                input_row = [bool(combination & (1 << index)) for index in range(len(inputs))]
                for index, (_src, _out, dst, in_index) in enumerate(inputs):
                    base_inputs[dst][in_index] |= input_row[index]
                # Resolver combinacionalmente hasta alcanzar estabilidad.
                for _ in range(max(4, len(chosen) * 4)):
                    values = {widget: row.copy() for widget, row in base_inputs.items()}
                    for src, out_index, dst, in_index in internal:
                        values[dst][in_index] |= bool(src.exit[out_index])
                    changed = False
                    for widget in chosen:
                        widget.enter = values[widget]
                        before = widget.exit.copy()
                        widget.logic()
                        changed |= before != widget.exit
                    if not changed:
                        break
                output_row = [bool(src.exit[out_index])
                              for src, out_index, _dst, _in in outputs]
                response_ms = self._estimate_response_ms(
                    chosen, [(dst, in_index) for _src, _out, dst, in_index in inputs],
                    internal, [(src, "out", out_index)
                               for src, out_index, _dst, _in in outputs])
                table.append({"inputs": input_row, "outputs": output_row,
                              "time_ms": response_ms})
        finally:
            for widget, (enter, exit_, response_ms) in backups.items():
                widget.enter, widget.exit = enter, exit_
                if response_ms is not None:
                    widget.response_ms = response_ms
        return table

    def _estimate_response_ms(self, chosen, input_bindings, internal, output_bindings,
                              source_outputs=()):
        """Estimate the longest settled path through delayed widgets for this row."""
        arrivals = {widget: [None] * len(widget.enter) for widget in chosen}
        output_times = {(widget, index): 0 for widget, index in source_outputs}
        for widget, index in input_bindings:
            if widget in arrivals and 0 <= index < len(arrivals[widget]):
                arrivals[widget][index] = 0

        # A bounded relaxation handles ordinary DAG circuits and gives feedback
        # circuits a finite, deterministic estimate instead of looping forever.
        for _ in range(max(1, len(chosen))):
            changed = False
            for widget in chosen:
                known = [value for value in arrivals[widget] if value is not None]
                if not known:
                    continue
                response = max(known) + max(0, int(widget.delay_ms)) + max(
                    0, int(getattr(widget, "response_ms", 0)))
                for index in range(len(widget.exit)):
                    key = (widget, index)
                    if key not in output_times or response > output_times[key]:
                        output_times[key] = response
                        changed = True
            for src, out_index, dst, in_index in internal:
                value = output_times.get((src, out_index))
                if value is None or dst not in arrivals or not 0 <= in_index < len(arrivals[dst]):
                    continue
                old = arrivals[dst][in_index]
                if old is None or value > old:
                    arrivals[dst][in_index] = value
                    changed = True
            if not changed:
                break

        times = []
        for widget, side, index in output_bindings:
            if side == "in":
                arrival = arrivals.get(widget, [None] * len(widget.enter))[index]
                if arrival is not None:
                    times.append(arrival + max(0, int(widget.delay_ms)))
            else:
                value = output_times.get((widget, index))
                if value is not None:
                    times.append(value)
        return max(times, default=0)

    def _build_truth_table_from_io(self, selected, input_widgets, output_widgets):
        """Evalúa el circuito usando interruptores/botones y bombillas como interfaz."""
        chosen = {graphic.widg for graphic in selected}
        edges = [(src, out_index, dst, in_index)
                 for src in chosen for out_index, destinations in src.connections.items()
                 for dst, in_index in destinations if dst in chosen]
        backups = {widget: (widget.enter.copy(), widget.exit.copy(),
                            getattr(widget, "state", None),
                            getattr(widget, "response_ms", None)) for widget in chosen}
        table = []
        try:
            for combination in range(1 << len(input_widgets)):
                for widget in chosen:
                    widget.enter = [False] * len(widget.enter)
                    widget.exit = [False] * len(widget.exit)
                for index, source in enumerate(input_widgets):
                    source.state = bool(combination & (1 << index))
                    source.exit[0] = source.state

                # La iteración propaga valores por cada etapa lógica; se limita
                # el número de pasos para que circuitos cíclicos no se bloqueen.
                for _ in range(max(8, len(chosen) * 8)):
                    for widget in chosen:
                        widget.enter = [False] * len(widget.enter)
                    for src, out_index, dst, in_index in edges:
                        if out_index < len(src.exit) and in_index < len(dst.enter):
                            dst.enter[in_index] |= bool(src.exit[out_index])
                    previous = {widget: widget.exit.copy() for widget in chosen}
                    for widget in chosen:
                        if isinstance(widget, (wdg.Switch, wdg.Button, wdg.Bulb, wdg.Display)):
                            continue
                        widget.logic()
                    if all(previous[widget] == widget.exit for widget in chosen):
                        break

                input_row = [bool(combination & (1 << index))
                             for index in range(len(input_widgets))]
                output_row = [bool(bulb.enter and bulb.enter[0])
                              for bulb in output_widgets]
                response_ms = self._estimate_response_ms(
                    chosen, [], edges, [(bulb, "in", 0) for bulb in output_widgets],
                    [(source, 0) for source in input_widgets])
                table.append({"inputs": input_row, "outputs": output_row,
                              "time_ms": response_ms})
        finally:
            for widget, (enter, exit_, state, response_ms) in backups.items():
                widget.enter, widget.exit = enter, exit_
                if state is not None:
                    widget.state = state
                if response_ms is not None:
                    widget.response_ms = response_ms
        return table

    def localizar_elemento_tabla(self, widget):
        graphic = self.all_graphics.get(widget.id)
        if not graphic or not graphic.scene():
            return
        self.ui.graphicsView.scene.clearSelection()
        graphic.setSelected(True)
        self.ui.graphicsView.centerOn(graphic)
        self.ui.graphicsView.setFocus()
        self.ui.graphicsView.viewport().update()
    def calcular_tabla_verdad(self):
        """Calcula la tabla del circuito completo con interruptores y botones como entradas."""
        widgets = list(self.all_widgets.values())
        sources = sorted((widget for widget in widgets
                          if isinstance(widget, (wdg.Switch, wdg.Button))),
                         key=lambda widget: widget.id)
        edges = [(src, out_index, dst, in_index)
                 for src in widgets for out_index, destinations in src.connections.items()
                 for dst, in_index in destinations]
        incoming = {(dst, in_index) for _src, _out, dst, in_index in edges}
        connected_sources = [source for source in sources
                             if any(source.connections.values())]
        if len(connected_sources) > 12:
            combinations = 1 << len(connected_sources)
            combination_count = f"{combinations:,}".replace(",", ".")
            choice = QMessageBox.warning(
                self, "Muchas entradas",
                f"La tabla tendrá {len(connected_sources)} entradas y "
                f"{combination_count} combinaciones. El cálculo puede tardar "
                "mucho y consumir bastante memoria. ¿Quieres continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                return

        ignored_inputs = []
        ignored_outputs = []
        for source in sources:
            if not any(source.connections.values()):
                kind = "Botón" if isinstance(source, wdg.Button) else "Interruptor"
                ignored_inputs.append(f"{kind} {source.id}: sin conexión; se excluye como entrada")

        bulbs, displays = [], []
        for widget in widgets:
            if isinstance(widget, (wdg.Switch, wdg.Button)):
                continue
            if isinstance(widget, wdg.Bulb):
                if (widget, 0) in incoming:
                    bulbs.append(widget)
                else:
                    ignored_outputs.append(f"Bombilla {widget.id}: sin conexión; se excluye como salida")
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
                            f"Display {widget.id}: segmentos sin conexión "
                            f"{', '.join(map(str, disconnected))}; se tomarán apagados")
                else:
                    ignored_outputs.append(f"Display {widget.id}: sin segmentos conectados; se excluye como salida")
                continue

            for index in range(len(widget.enter)):
                if (widget, index) not in incoming:
                    ignored_inputs.append(
                        f"{type(widget).__name__} {widget.id}: entrada {index} sin conexión; se tomará apagada")
            for index, destinations in widget.connections.items():
                if not destinations:
                    ignored_outputs.append(
                        f"{type(widget).__name__} {widget.id}: salida {index} sin conexión; se ignora")

        outputs = sorted([*bulbs, *displays], key=lambda widget: widget.id)
        if not outputs:
            details = []
            if ignored_inputs:
                details.append(f"Entradas ignoradas: {len(ignored_inputs)}")
            if ignored_outputs:
                details.append(f"Salidas ignoradas: {len(ignored_outputs)}")
            message = "No hay bombillas ni displays conectados que puedan usarse como salida."
            if details:
                message += "\n" + "\n".join(details)
            QMessageBox.warning(self, "Tabla de verdad", message)
            return

        warning_lines = []
        if ignored_inputs:
            warning_lines.append("Entradas sin conexión: " + "; ".join(ignored_inputs[:6]) +
                                 (f"; y {len(ignored_inputs) - 6} más" if len(ignored_inputs) > 6 else ""))
        if ignored_outputs:
            warning_lines.append("Salidas sin conexión: " + "; ".join(ignored_outputs[:6]) +
                                 (f"; y {len(ignored_outputs) - 6} más" if len(ignored_outputs) > 6 else ""))
        ignored_summary = "\n".join(warning_lines)
        if ignored_summary:
            choice = QMessageBox.warning(
                self, "Puertos sin conexión",
                ignored_summary + "\n\nSe ignorarán al calcular la tabla. ¿Continuar?",
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
        backups = {widget: (widget.enter.copy(), widget.exit.copy(),
                            getattr(widget, "state", None),
                            getattr(widget, "response_ms", None)) for widget in widgets}
        row_count = 1 << len(connected_sources)
        rows = []
        started = time.perf_counter()
        try:
            for combination in range(row_count):
                for widget in widgets:
                    widget.enter = [False] * len(widget.enter)
                    widget.exit = [False] * len(widget.exit)
                input_values = [bool(combination & (1 << (len(connected_sources) - index - 1)))
                                for index in range(len(connected_sources))]
                for index, source in enumerate(connected_sources):
                    source.state = input_values[index]
                    source.exit[0] = source.state

                for _ in range(max(8, len(chosen) * 8)):
                    for widget in widgets:
                        widget.enter = [False] * len(widget.enter)
                    for src, out_index, dst, in_index in edges:
                        if out_index < len(src.exit) and in_index < len(dst.enter):
                            dst.enter[in_index] |= bool(src.exit[out_index])
                    previous = {widget: widget.exit.copy() for widget in widgets}
                    for widget in widgets:
                        if isinstance(widget, (wdg.Switch, wdg.Button,
                                               wdg.Bulb, wdg.Display)):
                            continue
                        widget.logic()
                    if all(previous[widget] == widget.exit for widget in widgets):
                        break

                row_outputs = []
                for widget in outputs:
                    if isinstance(widget, wdg.Bulb):
                        row_outputs.append("1" if widget.enter[0] else "0")
                    else:
                        active_segments = [str(index) for index, value in enumerate(widget.enter)
                                           if value]
                        row_outputs.append("".join(active_segments) if active_segments else "—")
                response_ms = self._estimate_response_ms(
                    chosen, [], edges,
                    [(bulb, "in", 0) for bulb in bulbs] +
                    [(display, "in", index) for display in displays
                     for index in range(len(display.enter)) if (display, index) in incoming],
                    [(source, 0) for source in connected_sources])
                rows.append({
                    "inputs": input_values,
                    "outputs": row_outputs,
                    "time_ms": response_ms,
                })
        finally:
            for widget, (enter, exit_, state, response_ms) in backups.items():
                widget.enter, widget.exit = enter, exit_
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
                    if isinstance(widget, (wdg.Switch, wdg.Button)):
                        widget.graphic.update_switch_look()

        calculation_ms = (time.perf_counter() - started) * 1000
        input_labels = [f"Entrada {source.truth_table_number}"
                        for source in connected_sources]
        output_labels = [f"Salida {widget.truth_table_number}" for widget in outputs]
        dialog = TruthTableDialog(rows, input_labels, output_labels,
                                  calculation_ms, ignored_summary, self)
        dialog.exec()

    def _port_for_widget(self, widget, side, index):
        graphic = self.all_graphics.get(widget.id)
        if not graphic:
            return None
        ports = graphic._ports_in if side == "in" else graphic._ports_out
        return ports[index] if 0 <= index < len(ports) else None

    def _add_wire(self, source, destination):
        wire = Wire(source, destination)
        self.ui.graphicsView.scene.addItem(wire)
        wire.update_path()
        return wire

    def crear_modulo(self):
        selected = self._selected_graphics()
        if not selected:
            QMessageBox.information(self, "Crear módulo", "Selecciona los componentes que quieres convertir en módulo.")
            return
        name, accepted = QInputDialog.getText(self, "Crear módulo", "Nombre del módulo:", text="Mi módulo")
        if not accepted or not name.strip():
            return
        chosen_widgets = {graphic.widg for graphic in selected}
        module_inputs = sorted((w for w in chosen_widgets
                                if isinstance(w, (wdg.Switch, wdg.Button))), key=lambda w: w.id)
        module_outputs = sorted((w for w in chosen_widgets if isinstance(w, wdg.Bulb)),
                                key=lambda w: w.id)

        # Para el flujo habitual de un CI, los interruptores son entradas y las
        # bombillas seleccionadas son salidas, aunque no tengan cables externos.
        if module_inputs and module_outputs:
            if len(module_inputs) > 12:
                QMessageBox.warning(self, "Crear módulo", "Un módulo admite como máximo 12 entradas.")
                return
            table = self._build_truth_table_from_io(selected, module_inputs, module_outputs)
            center = sum((graphic.pos() for graphic in selected), QPointF()) / len(selected)
            module_data = {"name": name.strip(), "inputs": len(module_inputs),
                           "outputs": len(module_outputs), "truth_table": table}
            for graphic in selected:
                self.ui.graphicsView._remove_graphic(graphic)
            module_graphic = self.crear_widget("MODULO", center, module_data)
            self.ui.graphicsView.rebuild_connections()
            module_path = self._save_ci_definition(name.strip(), len(module_inputs),
                                                   len(module_outputs), table)
            if module_path:
                module_graphic.widg.module_path = str(module_path)
            self.actualizar_biblioteca_ci()
            return

        inputs, outputs, internal, all_incoming, all_outgoing = self._module_interface(selected)
        if not outputs:
            QMessageBox.warning(self, "Crear módulo", "La selección necesita al menos una salida conectada al exterior.")
            return
        table = self._build_truth_table(selected, inputs, outputs, internal)
        center = sum((graphic.pos() for graphic in selected), QPointF()) / len(selected)
        module_data = {"name": name.strip(), "inputs": len(inputs), "outputs": len(outputs),
                       "truth_table": table}
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

        module_path = self._save_ci_definition(name.strip(), len(inputs), len(outputs), table)
        if module_path:
            module_graphic.widg.module_path = str(module_path)
        self.actualizar_biblioteca_ci()

    def cargar_modulo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Cargar módulo", str(BASE_DIR), "Módulo DaLogic (*.dmodule)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if data.get("format") != "DaLogic module" or int(data.get("version", 0)) not in {1, 2}:
                raise ValueError("No es un módulo DaLogic compatible.")
            definition = self._module_definition(data)
            module_path = str(Path(path).resolve())
            self.imported_modules.append({**definition, "module_path": module_path})
            self.crear_widget("MODULO", data={**definition, "source": "uploaded",
                                              "module_path": module_path})
            self.actualizar_biblioteca_ci()
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "No se pudo cargar el módulo", str(exc))

    def about(self):
        self.creditos_window = VentanaCreditos(self.Credit_Form, self)
        self.creditos_window.exec()
    def tutorial(self):
        QMessageBox.information(self, "Guía rápida",
            "Añade componentes desde la izquierda. Haz clic en un puerto y después en otro para cablearlos.\n\n"
            "Un clic en vacío añade un codo; doble clic termina el cable con un extremo libre. Usa la rueda para zoom, "
            "la rueda central para desplazarte, Supr para borrar y doble clic sobre un interruptor para cambiarlo.\n\n"
            "RETARDO retrasa una señal; configura sus milisegundos con clic derecho. Usa Ver para cambiar el tema o ajustar la vista.\n\n"
            "Selecciona un grupo y usa Widgets → Crear CI para convertirlo en un módulo reutilizable.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(get_app_icon())
    ventana = VentanaInicial(app)
    sys.exit(app.exec())
