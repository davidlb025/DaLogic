from resources import translate_text as tr
"""Named native ports, compact peripherals and editable memory."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QFont, QPainterPath, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QSpinBox, QLineEdit, QPushButton, QPlainTextEdit,
                              QMessageBox, QCheckBox)
from .graphics import LogicGateGraphic
from .native import (Native, DIPSwitch, HexKeyboard, LEDBar, LEDMatrix,
                     Constant, PullUp, Buzzer, RGBLED, TrafficLight)
from .widgets import BusInput


from resources import LocalizedInputDialog as QInputDialog, LocalizedFileDialog as QFileDialog

class NativeGraphic(LogicGateGraphic):
    def boundingRect(self):
        count = max(len(self.widg.enter), len(self.widg.exit), 1)
        height = max(136, count * 24 + 36)
        width = 200
        if isinstance(self.widg, (Constant, PullUp, Buzzer)):
            width, height = 108, 76
        elif isinstance(self.widg, TrafficLight):
            height = 180
        if isinstance(self.widg, HexKeyboard):
            height = 176
        if isinstance(self.widg, LEDMatrix):
            height = max(height, self.widg.rows * 18 + 86)
            width = max(width, self.widg.columns * 18 + 128)
        elif isinstance(self.widg, LEDBar):
            width = max(width, self.widg.width * 16 + 128)
        return QRectF(-width / 2, -height / 2, width, height)

    def shape(self):
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect().adjusted(8, 8, -8, -8), 8, 8)
        return path

    def _reposition_ports(self):
        rect = self.boundingRect()
        for is_input, ports in ((True, self._ports_in), (False, self._ports_out)):
            for i, port in enumerate(ports):
                y = rect.top() + 20 + (rect.height() - 40) * (i + 1) / (len(ports) + 1)
                port.setPos(self.mapToScene(QPointF(rect.left() + 4 if is_input else rect.right() - 4, y)))
                port.update_tooltip()

    def update_port_color(self, idx, is_input):
        super().update_port_color(idx, is_input)
        self.update()

    def paint(self, painter, option, widget=None):
        dark = self._theme_is_dark()
        rect = self.boundingRect().adjusted(8, 8, -8, -8)
        if not isinstance(self.widg, Buzzer):
            painter.setPen(QPen(QColor('#79aaf5' if dark else '#3569b1'), 2))
            painter.setBrush(QColor('#243244' if dark else '#f2f7fd'))
            painter.drawRoundedRect(rect, 8, 8)
            painter.setPen(QColor('#eff5fc' if dark else '#1f2f42'))
        if not isinstance(self.widg, (Buzzer, TrafficLight, Constant, PullUp)):
            painter.setFont(QFont('Arial', 9, QFont.Weight.Bold))
            self._draw_upright_text(painter, QRectF(-86, rect.top() + 5, 172, 28),
                                    Qt.AlignCenter, tr(self.widg.title))
        painter.setFont(QFont('Arial', 8))
        if not isinstance(self.widg, Buzzer):
            for is_input, ports in ((True, self._ports_in), (False, self._ports_out)):
                labels = getattr(self.widg, 'input_labels' if is_input else 'output_labels', [])
                for i, port in enumerate(ports):
                    y = self.mapFromScene(port.pos()).y()
                    label = labels[i] if i < len(labels) else 'BUS'
                    self._draw_upright_text(painter, QRectF(rect.left() + 8 if is_input else rect.right() - 54, y - 8, 46, 16),
                                            Qt.AlignLeft if is_input else Qt.AlignRight, tr(label))
        if isinstance(self.widg, HexKeyboard):
            for value in range(16):
                x, y = -60 + (value % 4) * 30, -38 + (value // 4) * 28
                cell = QRectF(x, y, 26, 24)
                painter.setBrush(QColor('#3569b1' if self.widg.value == value else '#526477'))
                painter.drawRoundedRect(cell, 3, 3)
                self._draw_upright_text(painter, cell, Qt.AlignCenter, tr('{v0:X}', v0=value))
            self._paint_selection(painter, rect)
            return
        if isinstance(self.widg, (LEDBar, LEDMatrix, DIPSwitch)):
            value = self.widg.value if isinstance(self.widg, BusInput) else self.widg.enter[0]
            columns = (self.widg.columns if isinstance(self.widg, LEDMatrix) else
                       self.widg.width if isinstance(self.widg, LEDBar) else 8)
            rows = (self.widg.width + columns - 1) // columns
            spacing = 18 if isinstance(self.widg, LEDMatrix) else 16
            left = -60 if isinstance(self.widg, DIPSwitch) else -columns * spacing / 2
            top = -rows * spacing / 2 + 8 if isinstance(self.widg, LEDMatrix) else -12
            for bit in range(self.widg.width):
                x, y = left + (bit % columns) * spacing, top + (bit // columns) * spacing
                state = (self.widg.pixel(bit // columns, bit % columns) if isinstance(self.widg, LEDMatrix)
                         else value if value in ('X', 'Z') else bool(int(value) & (1 << bit)))
                color = '#e9b853' if state == 'X' else '#70e7ac' if state is True else '#526477'
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(QRectF(x, y, 12, 12), 2, 2)
            caption = (tr('{v0} × {v1} · bit 0 arriba izquierda', v0=rows, v1=columns) if isinstance(self.widg, LEDMatrix)
                       else 'Bit 0: izquierda' if isinstance(self.widg, LEDBar) else 'Bit 0: arriba izquierda')
            self._draw_upright_text(painter, QRectF(rect.left() + 8, top + rows * spacing + 3, rect.width() - 16, 18),
                                    Qt.AlignCenter, tr(caption))
        elif isinstance(self.widg, RGBLED):
            values = self.widg.enter
            channels = []
            for value in values:
                channels.append(max(0, min(255, int(value))) if value not in ('X', 'Z') else 112 if value == 'X' else 0)
            painter.setPen(QPen(QColor('#f2bb55' if 'X' in values else '#68798b'), 2))
            painter.setBrush(QColor(*channels))
            painter.drawEllipse(QRectF(-28, -28, 56, 56))
            if any(value == 'X' for value in values):
                painter.setPen(QPen(QColor('#f2bb55'), 2, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QRectF(-33, -33, 66, 66))
            self._draw_upright_text(painter, QRectF(-55, 34, 110, 18), Qt.AlignCenter,
                                    tr('R · G · B  (0–255)'))
        elif isinstance(self.widg, TrafficLight):
            housing = QRectF(9, -58, 50, 116)
            housing_gradient = QLinearGradient(housing.topLeft(), housing.topRight())
            housing_gradient.setColorAt(0, QColor('#141b24' if dark else '#29323b'))
            housing_gradient.setColorAt(0.5, QColor('#394551' if dark else '#68747e'))
            housing_gradient.setColorAt(1, QColor('#161e27' if dark else '#303a44'))
            painter.setPen(QPen(QColor('#83909c'), 1.5))
            painter.setBrush(housing_gradient)
            painter.drawRoundedRect(housing, 15, 15)
            colors = ('#ff514d', '#ffc84a', '#52d483')
            for index, (value, color) in enumerate(zip(self.widg.enter, colors)):
                y = -36 + index * 36
                active = value == 1
                unknown = value == 'X'
                if active:
                    glow = QColor(color)
                    glow.setAlpha(70)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(glow)
                    painter.drawEllipse(QRectF(18, y - 15, 32, 32))
                lens = QRectF(22, y - 11, 24, 24)
                base = QColor('#e9b853' if unknown else color if active else '#424b54')
                shade = QColor(base).darker(185 if active else 150)
                lens_gradient = QRadialGradient(QPointF(29, y - 5), 19)
                lens_gradient.setColorAt(0, QColor(base).lighter(135 if active else 110))
                lens_gradient.setColorAt(1, shade)
                painter.setPen(QPen(QColor('#f1f4f6' if active else '#7d8993'), 1))
                painter.setBrush(lens_gradient)
                painter.drawEllipse(lens)
            painter.setPen(QPen(QColor('#a3adb7'), 2))
            painter.drawRoundedRect(QRectF(27, 58, 14, 13), 2, 2)
        elif isinstance(self.widg, Buzzer):
            icon = QPainterPath()
            icon.moveTo(-18, -9)
            icon.lineTo(-8, -9)
            icon.lineTo(5, -20)
            icon.lineTo(5, 20)
            icon.lineTo(-8, 9)
            icon.lineTo(-18, 9)
            icon.closeSubpath()
            painter.setPen(QPen(QColor('#a9c7e8' if dark else '#456b92'), 2))
            painter.setBrush(QColor('#79aaf5' if dark else '#5c88b4'))
            painter.drawPath(icon)
            painter.setBrush(Qt.NoBrush)
            for radius in (14, 23):
                wave = QPainterPath()
                wave.moveTo(10, -radius * 0.72)
                wave.cubicTo(10 + radius, -radius * 0.35,
                            10 + radius, radius * 0.35, 10, radius * 0.72)
                painter.drawPath(wave)
        elif isinstance(self.widg, (Constant, PullUp)):
            painter.setFont(QFont('Arial', 7, QFont.Weight.Bold))
            self._draw_upright_text(painter, QRectF(-44, rect.top() + 8, 88, 15),
                                    Qt.AlignCenter, tr(self.widg.title))
            if isinstance(self.widg, PullUp):
                symbol = '↑ 1' if self.widg.value else '↓ 0'
                painter.setFont(QFont('Arial', 14, QFont.Weight.Bold))
                self._draw_upright_text(painter, QRectF(-40, -12, 80, 26),
                                        Qt.AlignCenter, tr(symbol))
            else:
                painter.setFont(QFont('Arial', 12, QFont.Weight.Bold))
                self._draw_upright_text(painter, QRectF(-44, -12, 88, 25),
                                        Qt.AlignCenter, tr(str(self.widg.value)))
                painter.setFont(QFont('Arial', 7))
                self._draw_upright_text(painter, QRectF(-42, 15, 84, 13), Qt.AlignCenter,
                                        tr('{v0} bits', v0=self.widg.width))
        else:
            value = (self.widg.value if isinstance(self.widg, (Constant, BusInput))
                     else self.widg.exit[0] if self.widg.exit else self.widg.enter[0])
            text = str(value) if value in ('X', 'Z') else str(int(value))
            self._draw_upright_text(painter, QRectF(-38, -8, 76, 22), Qt.AlignCenter, tr(text))
            if value not in ('X', 'Z'):
                self._draw_upright_text(painter, QRectF(-38, 14, 76, 18), Qt.AlignCenter, tr('0x{v0:X}', v0=int(value)))
            width = (self.widg.width if getattr(self.widg, 'configurable_width', True)
                     else max(self.widg.input_widths + self.widg.output_widths, default=1))
            self._draw_upright_text(painter, QRectF(-38, rect.bottom() - 22, 76, 18), Qt.AlignCenter,
                                    tr('{v0} bits', v0=width))
        self._paint_selection(painter, rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and isinstance(self.widg, (DIPSwitch, HexKeyboard)):
            p = event.pos()
            value = None
            if isinstance(self.widg, HexKeyboard):
                col, row = int((p.x() + 60) // 30), int((p.y() + 38) // 28)
                if 0 <= col < 4 and 0 <= row < 4 and -60 <= p.x() < 60 and -38 <= p.y() < 74:
                    value = row * 4 + col
            else:
                col, row = int((p.x() + 60) // 16), int((p.y() + 12) // 16)
                bit = row * 8 + col
                if 0 <= col < 8 and row >= 0 and 0 <= bit < self.widg.width:
                    value = self.widg.value ^ (1 << bit)
            if value is not None:
                view = self.scene().views()[0]
                self.widg.set_value(value, view.board_ref)
                window = view.window()
                if hasattr(window, '_schedule_history_capture'):
                    window._schedule_history_capture()
                event.accept()
                return
        super().mousePressEvent(event)

    def show_config(self):
        if isinstance(self.widg, LEDMatrix):
            MatrixDialog(self).exec()
        elif isinstance(self.widg, Native):
            NativeDialog(self).exec()
        else:
            super().show_config()


class MatrixDialog(QDialog):
    def __init__(self, graphic):
        super().__init__(graphic.scene().views()[0].window())
        self.graphic = graphic
        self.setWindowTitle(tr('Matriz de LED'))
        layout = QVBoxLayout(self)
        self.rows, self.columns = QSpinBox(), QSpinBox()
        for label, field, value in (('Filas', self.rows, graphic.widg.rows),
                                     ('Columnas', self.columns, graphic.widg.columns)):
            row = QHBoxLayout()
            row.addWidget(QLabel(tr(label)))
            field.setRange(1, 32)
            field.setValue(value)
            row.addWidget(field)
            layout.addLayout(row)
        self.total = QLabel()
        layout.addWidget(self.total)
        layout.addWidget(QLabel(tr('Bit 0 arriba a la izquierda; bits consecutivos por filas.')))
        self.rows.valueChanged.connect(self.update_total)
        self.columns.valueChanged.connect(self.update_total)
        self.update_total()
        buttons = QHBoxLayout()
        save = QPushButton(tr('Guardar'))
        save.clicked.connect(self.save)
        cancel = QPushButton(tr('Cancelar'))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def update_total(self):
        self.total.setText(tr('Bus de {v0} bits (2–32 admitidos)', v0=self.rows.value() * self.columns.value()))

    def save(self):
        try:
            self.graphic.widg.set_dimensions(self.rows.value(), self.columns.value())
        except ValueError as error:
            QMessageBox.warning(self, tr('Dimensiones no válidas'), tr(str(error)))
            return
        view = self.graphic.scene().views()[0]
        view.rebuild_connections(recalculate=True)
        view.window()._schedule_history_capture()
        self.accept()


class NativeDialog(QDialog):
    def __init__(self, graphic):
        super().__init__(graphic.scene().views()[0].window())
        self.graphic = graphic
        self.widg = graphic.widg
        self.setWindowTitle(tr(self.widg.title))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        self.fields = {}
        for key, title, low, high, value, visible in (
                ('width', 'Ancho de datos (bits)', 1, 32, self.widg.width, self.widg.configurable_width),
                ('address_bits', tr('Bits de dirección (máximo 4096 palabras)'), 1, 12, self.widg.address_bits, self.widg.configurable_address),
                ('channels', 'Canales (2, 4, 8 o 16)', 2, 16, self.widg.channels, self.widg.configurable_channels)):
            if visible:
                row = QHBoxLayout()
                row.addWidget(QLabel(tr(title)))
                field = QSpinBox()
                field.setRange(low, high)
                field.setValue(value)
                self.fields[key] = field
                row.addWidget(field)
                layout.addLayout(row)
        self.constant = None
        self.sound = None
        if isinstance(self.widg, Buzzer):
            self.sound = QCheckBox(tr('Activar sonido al recibir un 1'))
            self.sound.setChecked(self.widg.sound_enabled)
            layout.addWidget(self.sound)
        if isinstance(self.widg, Constant) and not isinstance(self.widg, PullUp):
            layout.addWidget(QLabel(tr('Valor decimal o hexadecimal')))
            self.constant = QLineEdit(str(self.widg.value))
            layout.addWidget(self.constant)
        self.memory = None
        if self.widg.configurable_address:
            layout.addWidget(QLabel(tr('Contenido: palabras decimales o 0xHEX separadas por espacios.\nLas direcciones restantes se rellenan con cero; X es indeterminado.')))
            self.memory = QPlainTextEdit(' '.join('X' if v == 'X' else f'0x{v:X}' for v in self.widg.memory))
            layout.addWidget(self.memory)
            load = QPushButton(tr('Importar contenido de texto…'))
            load.clicked.connect(self.import_memory)
            layout.addWidget(load)
        layout.addWidget(QLabel((((tr('Puertos: ') + tr(', '.join(self.widg.input_labels))) + tr('\nSalidas: ')) + tr(', '.join(self.widg.output_labels)))))
        buttons = QHBoxLayout()
        save = QPushButton(tr('Guardar'))
        save.clicked.connect(self.save)
        cancel = QPushButton(tr('Cancelar'))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def import_memory(self):
        from pathlib import Path
        from resources import LocalizedFileDialog as QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, 'Importar memoria', '', tr('Texto (*.txt *.hex);;Todos (*)'))
        if path:
            try:
                self.memory.setPlainText(Path(path).read_text(encoding='utf-8'))
            except (OSError, UnicodeError) as error:
                QMessageBox.warning(self, tr('No se pudo importar'), tr(str(error)))

    def save(self):
        settings = {key: field.value() for key, field in self.fields.items()}
        settings.setdefault('width', self.widg.width)
        settings.setdefault('address_bits', self.widg.address_bits)
        settings.setdefault('channels', self.widg.channels)
        try:
            if settings['channels'] not in (2, 4, 8, 16):
                raise ValueError(tr('Elige 2, 4, 8 o 16 canales.'))
            data = self.widg.export_native()
            if self.sound is not None:
                data['sound_enabled'] = self.sound.isChecked()
            if self.constant:
                text = self.constant.text().strip()
                value = int(text, 16 if text.lower().startswith('0x') else 10)
                if not 0 <= value < (1 << settings['width']):
                    raise ValueError(tr('El valor no cabe en el ancho seleccionado.'))
                data['native_value'] = value
            if self.memory:
                tokens = self.memory.toPlainText().replace(',', ' ').split()
                values = ['X' if token.upper() == 'X' else int(token, 16 if token.lower().startswith('0x') else 10) for token in tokens]
                if len(values) > 1 << settings['address_bits']:
                    raise ValueError(tr('Hay más palabras que direcciones disponibles.'))
                if any(v != 'X' and not 0 <= v < (1 << settings['width']) for v in values):
                    raise ValueError(tr('Una palabra no cabe en el ancho de datos.'))
                data['memory'] = values
            replacement = type(self.widg)(self.widg.id, **settings)
            replacement.restore_native(data)
        except (ValueError, TypeError) as error:
            QMessageBox.warning(self, tr('Configuración no válida'), tr(str(error)))
            return
        graphic = self.graphic
        graphic.prepareGeometryChange()
        for key, value in replacement.__dict__.items():
            if key not in ('id', 'graphic', 'delay_ms', 'connections'):
                setattr(self.widg, key, value)
        self.widg.connections = {i: self.widg.connections.get(i, []) for i in range(len(self.widg.exit))}
        graphic.rebuild_ports()
        view = graphic.scene().views()[0]
        view.rebuild_connections(recalculate=True)
        graphic.update()
        window = view.window()
        if hasattr(window, '_schedule_history_capture'):
            window._schedule_history_capture()
        self.accept()
