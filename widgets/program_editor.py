"""Edit and load machine programs directly into a circuit's program ROM."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
                               QLabel, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from resources import LocalizedFileDialog, translate_text as tr
from .processor import INSTRUCTIONS, PORTS, assemble, decode, format_binary, read_binary


class ProgramEditor(QDialog):
    def __init__(self, graphic):
        super().__init__(graphic.scene().views()[0].window())
        self.graphic = graphic
        self.rom = graphic.widg
        self.setWindowTitle(tr("Programar ROM · DaLogic-8"))
        self.resize(870, 550)
        layout = QVBoxLayout(self)
        header = QLabel(tr("Programa de hasta 256 instrucciones. Conecta PC → ADDR y Q → INST. Activa RESET antes de ejecutar un programa nuevo."))
        header.setWordWrap(True)
        layout.addWidget(header)

        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem(tr("Ensamblador"), "asm")
        self.mode.addItem(tr("Binario"), "bin")
        self.mode.setCurrentIndex(self.mode.findData(self.rom.program_mode))
        controls.addWidget(self.mode)
        for label, slot in (("Abrir código…", self.open_source),
                            ("Comprobar y ver binario", self.preview),
                            ("Copiar binario", self.copy_binary)):
            button = QPushButton(tr(label))
            button.clicked.connect(slot)
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)

        split = QSplitter(Qt.Horizontal)
        fixed = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName(tr("Código del programa"))
        self.editor.setFont(fixed)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setPlainText(self.rom.program_source or (
            format_binary(self.rom.memory[:self.rom.program_length]) if self.rom.program_mode == "bin" else ""))
        split.addWidget(self.editor)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(QLabel(tr("Código máquina · operación y operando")))
        self.binary = QPlainTextEdit()
        self.binary.setAccessibleName(tr("Código máquina"))
        self.binary.setReadOnly(True)
        self.binary.setFont(fixed)
        side_layout.addWidget(self.binary)
        side_layout.addWidget(QLabel(tr("Referencia DaLogic-8")))
        reference = QPlainTextEdit()
        reference.setAccessibleName(tr("Referencia DaLogic-8"))
        reference.setReadOnly(True)
        reference.setFont(fixed)
        reference.setPlainText("\n".join(
            f"{opcode:02X}  {mnemonic:3}  {tr(description)}"
            for opcode, (mnemonic, _kind, description) in enumerate(INSTRUCTIONS))
            + "\n\n" + tr("Puertos OUT") + "\n"
            + "\n".join(f"{number}  {name}" for number, name in enumerate(PORTS)))
        side_layout.addWidget(reference)
        split.addWidget(side)
        split.setSizes([465, 390])
        layout.addWidget(split, 1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        load = buttons.addButton(tr("Cargar en ROM"), QDialogButtonBox.AcceptRole)
        load.setDefault(False)
        load.clicked.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.editor.textChanged.connect(self._invalidate_preview)
        self._mode_changed()
        self.editor.setFocus()

    def _invalidate_preview(self):
        self.binary.clear()
        self.status.clear()

    def _mode_changed(self):
        self._invalidate_preview()
        example = "LDI 42\nHLT" if self.mode.currentData() == "asm" else "00000001 00101010\n00001110 00000000"
        self.editor.setPlaceholderText(example)

    def open_source(self):
        path, _ = LocalizedFileDialog.getOpenFileName(self, "Abrir código…", "",
                                                       "Programas (*.asm *.bin *.txt);;Todos (*)")
        if not path:
            return
        try:
            with Path(path).open(encoding="utf-8-sig") as stream:
                source = stream.read(65537)
            if len(source) > 65536:
                raise ValueError(tr("El código supera los 65536 caracteres."))
        except (OSError, ValueError) as error:
            self.status.setText(tr("No se pudo abrir el código · {v0}", v0=error))
            return
        suffix = Path(path).suffix.lower()
        if suffix in (".asm", ".bin"):
            self.mode.setCurrentIndex(0 if suffix == ".asm" else 1)
        self.editor.setPlainText(source)

    def preview(self):
        try:
            source = self.editor.toPlainText()
            if len(source) > 65536:
                raise ValueError(tr("El código supera los 65536 caracteres."))
            words = (assemble if self.mode.currentData() == "asm" else read_binary)(source)
            for address, word in enumerate(words):
                try:
                    decode(word)
                except ValueError as error:
                    raise ValueError(tr("Dirección 0x{v0:02X} · {v1}", v0=address, v1=error)) from None
        except ValueError as error:
            self.binary.clear()
            self.status.setText(str(error))
            return None
        self.binary.setPlainText(format_binary(words))
        self.status.setText(tr("{v0} / 256 instrucciones listas.", v0=len(words)))
        return words

    def copy_binary(self):
        if self.preview() is not None:
            QApplication.clipboard().setText(self.binary.toPlainText())

    def save(self):
        words = self.preview()
        if words is None:
            return
        self.rom.load_program(words, self.editor.toPlainText(), self.mode.currentData())
        self.rom._simulation_initialized = False
        view = self.graphic.scene().views()[0]
        view.rebuild_connections(recalculate=True)
        view.window()._schedule_history_capture()
        self.accept()
