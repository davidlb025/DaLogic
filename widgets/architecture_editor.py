"""Programming tools for the ROM or RAM attached to a user circuit."""

from pathlib import Path
import re

from PySide6.QtCore import QIODevice, QSaveFile, Qt
from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

from project_io import write_json_atomic
from resources import LocalizedFileDialog, translate_text as tr
from .custom_isa import MAX_ISA, MAX_SOURCE, assemble_custom, read_words
from .gate_rom import gate_rom_project


class AssemblyHighlighter(QSyntaxHighlighter):
    def __init__(self, document, dark):
        super().__init__(document)
        colors = ("#a0c7ff", "#8de7c4", "#9db0c3") if dark else ("#245d9d", "#22674d", "#536b83")
        self.rules = []
        for pattern, color in zip((r"^\s*\.?[A-Za-z_][\w.]*", r"\b(?:0[xXbB])?\d[\da-fA-F_]*\b",
                                   r"[;#].*$"), colors):
            style = QTextCharFormat()
            style.setForeground(QColor(color))
            self.rules.append((re.compile(pattern), style))

    def highlightBlock(self, text):
        for pattern, style in self.rules:
            for match in pattern.finditer(text):
                # QSyntaxHighlighter indices are UTF-16 code units.
                offset = len(text[:match.start()].encode("utf-16-le", "surrogatepass")) // 2
                length = len(match[0].encode("utf-16-le", "surrogatepass")) // 2
                self.setFormat(offset, length, style)


class ArchitectureEditor(QDialog):
    def __init__(self, graphic):
        view = graphic.scene().views()[0]
        super().__init__(view.window())
        self.view = view
        self.memory = graphic.widg
        self.width = self.memory.width
        self.capacity = 1 << self.memory.address_bits
        self.setWindowTitle(tr("Programar memoria · {v0}", v0=tr(self.memory.title)))
        self.resize(960, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)
        headline = QHBoxLayout()
        heading = QLabel(tr("Programar memoria"))
        font = heading.font()
        font.setPointSize(18)
        font.setBold(True)
        heading.setFont(font)
        headline.addWidget(heading, 1)
        headline.addWidget(QLabel(tr("{v0} palabras × {v1} bits", v0=self.capacity, v1=self.width)))
        layout.addLayout(headline)
        description = QLabel(tr("El circuito selecciona ADDR y lee Q. La definición de instrucciones traduce el código a bits."))
        description.setWordWrap(True)
        layout.addWidget(description)

        self.tabs = QTabWidget()
        self.code, self.isa = self._editor("Código del programa"), self._editor("Definición de instrucciones")
        dark = view.theme_mode == "dark"
        self.highlighters = [AssemblyHighlighter(editor.document(), dark) for editor in (self.code, self.isa)]
        details = self.memory.program_definition or {}
        self.mode = QComboBox()
        self.mode.addItem(tr("Ensamblador"), "asm")
        self.mode.addItem(tr("Binario"), "bin")
        self.mode.setCurrentIndex(self.mode.findData(details.get("mode", "asm")))
        self.code.setPlainText(details.get("source", ""))
        if not details and any(self.memory.memory):
            last = max(index for index, value in enumerate(self.memory.memory) if value)
            words = self.memory.memory[:last + 1]
            if all(type(word) is int for word in words):
                self.mode.setCurrentIndex(1)
                self.code.setPlainText("\n".join(format(word, f"0{self.width}b") for word in words))
        example_isa = "NOP = " + "0" * self.width
        if self.width >= 2:
            example_isa += "\nLDI v = 1" + "v" * (self.width - 1)
        self.isa.setPlainText(details.get("isa", example_isa))
        self.code.setPlaceholderText("LDI 1\nNOP" if self.width >= 2 else "NOP")
        self.tabs.addTab(self._edit_page(self.code, is_isa=False), tr("Programa"))
        self.tabs.addTab(self._edit_page(self.isa, is_isa=True), tr("Instrucciones"))

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.tabs)
        preview = QWidget()
        right = QVBoxLayout(preview)
        right.setContentsMargins(8, 0, 0, 0)
        right.addWidget(QLabel(tr("Imagen de memoria")))
        right.addWidget(QLabel(tr("Dirección  /  Hexadecimal  /  Binario")))
        self.listing = self._editor("Imagen de memoria")
        self.listing.setReadOnly(True)
        self.listing.setPlaceholderText(tr("Comprueba el programa para ver las palabras por dirección."))
        right.addWidget(self.listing, 1)
        actions = QHBoxLayout()
        copy = QPushButton(tr("Copiar binario"))
        copy.clicked.connect(self.copy_binary)
        actions.addWidget(copy)
        self.export_gates = QPushButton(tr("Exportar ROM de puertas…"))
        self.export_gates.clicked.connect(self.save_gates)
        self.export_gates.setEnabled(self.memory.address_bits <= 4 and self.width <= 16)
        self.export_gates.setToolTip(tr("La ROM cableada admite 1–4 bits de dirección y 1–16 bits de datos."))
        actions.addWidget(self.export_gates)
        right.addLayout(actions)
        split.addWidget(preview)
        split.setSizes([510, 410])
        layout.addWidget(split, 1)

        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        check = buttons.addButton(tr("Comprobar"), QDialogButtonBox.ActionRole)
        check.clicked.connect(self.preview)
        load = buttons.addButton(tr("Cargar en memoria"), QDialogButtonBox.AcceptRole)
        load.setStyleSheet("color: white; background: #2c64ae; border: 1px solid #5c92d8;")
        load.clicked.connect(self.apply_program)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.code.textChanged.connect(self.invalidate)
        self.isa.textChanged.connect(self.invalidate)
        self.mode.currentIndexChanged.connect(self.invalidate)
        self.code.setFocus()

    @staticmethod
    def _editor(name):
        editor = QPlainTextEdit()
        editor.setAccessibleName(tr(name))
        editor.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        return editor

    def _edit_page(self, editor, *, is_isa):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        if not is_isa:
            row.addWidget(self.mode)
        for name, slot in (("Abrir…", self.import_text), ("Guardar…", self.export_text)):
            button = QPushButton(tr(name))
            button.clicked.connect(lambda checked=False, fn=slot: fn(is_isa))
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        help_text = (
            "Una regla por línea. Usa 0, 1 y letras para los campos. | separa palabras de la misma instrucción."
            if is_isa else "Escribe una instrucción o palabra por línea. El ensamblador admite etiquetas, .equ y .word.")
        hint = QLabel(tr(help_text))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(editor, 1)
        return page

    def invalidate(self):
        self.listing.clear()
        self.status.clear()

    def _file_options(self, is_isa):
        if is_isa:
            return "arquitectura.isa", "Definición DaLogic (*.isa);;Texto (*.txt)"
        return ("programa.bin" if self.mode.currentData() == "bin" else "programa.asm",
                "Programas (*.asm *.bin *.txt);;Todos (*)")

    def import_text(self, is_isa):
        _, filters = self._file_options(is_isa)
        path, _ = LocalizedFileDialog.getOpenFileName(self, "Abrir…", "", filters)
        if not path:
            return
        maximum = MAX_ISA if is_isa else MAX_SOURCE
        try:
            with Path(path).open(encoding="utf-8-sig") as stream:
                value = stream.read(maximum + 1)
            if len(value) > maximum:
                raise ValueError(tr("El archivo supera el tamaño admitido."))
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        if not is_isa and Path(path).suffix.lower() in (".bin", ".asm"):
            self.mode.setCurrentIndex(int(Path(path).suffix.lower() == ".bin"))
        (self.isa if is_isa else self.code).setPlainText(value)

    def export_text(self, is_isa):
        suggested, filters = self._file_options(is_isa)
        path, _ = LocalizedFileDialog.getSaveFileName(self, "Guardar…", suggested, filters)
        if not path:
            return
        data = (self.isa if is_isa else self.code).toPlainText().encode("utf-8")
        stream = QSaveFile(path)
        if not stream.open(QIODevice.WriteOnly) or stream.write(data) != len(data) or not stream.commit():
            self.status.setText(stream.errorString())
        else:
            self.status.setText(tr("Archivo guardado."))

    def preview(self):
        code = self.code.toPlainText()
        try:
            if self.mode.currentData() == "asm":
                words = assemble_custom(code, self.isa.toPlainText(), self.width, self.capacity)
            else:
                words = read_words(code, self.width, self.capacity)
            if not words:
                raise ValueError(tr("Introduce al menos una palabra o instrucción."))
        except ValueError as exc:
            self.listing.clear()
            self.status.setText(str(exc))
            return None
        address_digits = (self.memory.address_bits + 3) // 4
        data_digits = (self.width + 3) // 4
        self.listing.setPlainText("\n".join(f"{address:0{address_digits}X}   {word:0{data_digits}X}   {word:0{self.width}b}"
                                            for address, word in enumerate(words)))
        self.status.setText(tr("{v0} de {v1} palabras listas.", v0=len(words), v1=self.capacity))
        return words

    def copy_binary(self):
        words = self.preview()
        if words is not None:
            QApplication.clipboard().setText("\n".join(f"{word:0{self.width}b}" for word in words))

    def save_gates(self):
        words = self.preview()
        if words is None:
            return
        project = gate_rom_project(words, self.memory.address_bits, self.width)
        path, _ = LocalizedFileDialog.getSaveFileName(self, "Exportar ROM de puertas…", "rom-de-puertas.dalogic",
                                                      "Proyecto DaLogic (*.dalogic)")
        if path:
            try:
                write_json_atomic(Path(path).with_suffix(".dalogic"), project)
                self.status.setText(tr("Archivo guardado."))
            except OSError as exc:
                self.status.setText(str(exc))

    def apply_program(self):
        words = self.preview()
        if words is None:
            return
        try:
            self.memory.load_image(words, dict(mode=self.mode.currentData(), source=self.code.toPlainText(),
                                               isa=self.isa.toPlainText()))
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.view.rebuild_connections(recalculate=True)
        self.view.window()._schedule_history_capture()
        self.accept()
