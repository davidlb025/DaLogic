"""Visual Qt components: layouts, menus, canvas annotations and palette docks."""
import re

from resources import translate_text as tr, SELECTION_COLOR
from resources import LocalizedInputDialog as QInputDialog, LocalizedFileDialog as QFileDialog
from PySide6.QtCore import Qt, QRectF, QPointF, QRect, QSize, QEvent, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPainterPathStroker, QPen, QActionEvent, QKeySequence
from PySide6.QtWidgets import (
    QGraphicsObject, QGraphicsItem, QDockWidget, QWidget, QVBoxLayout,
    QFormLayout, QPushButton, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QColorDialog, QMessageBox, QMenu, QSizePolicy, QDialog, QLayout, QGridLayout,
    QDialogButtonBox, QPlainTextEdit, QCheckBox, QFontComboBox, QScrollArea,
    QHBoxLayout, QStyleOptionMenuItem, QStyledItemDelegate, QStyleOptionViewItem,
    QStyle, QTreeWidget,
)


class _LibraryItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option = QStyleOptionViewItem(option)
        # Selection is the keyboard focus indicator for this single-column tree.
        # The native dotted focus frame would split its continuous highlight.
        option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, option, index)


class LibraryTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_LibraryItemDelegate(self))
        self.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(10, 6, 10, 6)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _arrange(self, rect, apply):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            size = item.sizeHint()
            if row_height and x + size.width() > area.right() + 1:
                x, y, row_height = area.x(), y + row_height + self.spacing(), 0
            if apply:
                item.setGeometry(QRect(x, y, min(size.width(), max(1, area.width())), size.height()))
            x += size.width() + self.spacing()
            row_height = max(row_height, size.height())
        return y + row_height - rect.y() + margins.bottom()

class ComponentPalette(QWidget):
    """Equal-width component columns, sized from their translated labels."""
    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.setObjectName("componentPalette")
        self.buttons = list(buttons)
        self.columns = 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        self.grid.setAlignment(Qt.AlignTop)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        minimum = max((button.minimumSizeHint().width() for button in self.buttons), default=120)
        width = max(1, self.width() - 20)
        columns = max(1, min(3, (width + 6) // (minimum + 6)))
        if columns == self.columns:
            return
        previous = self.columns
        self.columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(max(previous, columns)):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, button in enumerate(self.buttons):
            self.grid.addWidget(button, index // columns, index % columns)
        self.updateGeometry()

class ActionBar(QWidget):
    """Keep a wrapping action row at its actual height after every resize."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("actionBar")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        FlowLayout(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_height()

    def event(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.LayoutRequest and self.layout() is not None:
            self._sync_height()
        return super().event(event)

    def _sync_height(self):
        height = self.layout().heightForWidth(self.width())
        if self.minimumHeight() != height or self.maximumHeight() != height:
            self.setFixedHeight(height)

def shortcut_hint(action):
    source = getattr(action, "shortcut_hint_source", action)
    hints = []
    for sequence in source.shortcuts():
        text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        # Leave a literal plus key intact: Ctrl++ becomes Ctrl + +.
        text = re.sub(r"\+(?=.)", " + ", text)
        if text and text not in hints:
            hints.append(text)
    return " / ".join(hints)

class ShortcutMenu(QMenu):
    def __init__(self, *args):
        super().__init__(*args)
        self._sizing_shortcuts = False
        self._refresh_pending = False
        self.aboutToShow.connect(self._reserve_shortcuts)

    def _shortcut_width(self):
        return max((self.fontMetrics().horizontalAdvance(shortcut_hint(action))
                    for action in self.actions() if action.isVisible()), default=0)

    def _reserve_shortcuts(self):
        if getattr(self, "_sizing_shortcuts", False):
            return
        self._sizing_shortcuts = True
        try:
            # Native QMenu measures only the primary QAction shortcut. Reserve
            # the difference for our complete hint (aliases included), without
            # ever changing QAction.text() shared by the action-bar buttons.
            self.ensurePolished()
            self.setMinimumWidth(0)
            actions = self.actions()
            if actions:
                super().actionEvent(QActionEvent(QEvent.ActionChanged, actions[0]))
            native_size = super().sizeHint()
            native_width = max((self.fontMetrics().horizontalAdvance(
                action.shortcut().toString(QKeySequence.NativeText))
                for action in actions if action.isVisible()), default=0)
            width = native_size.width() + max(0, self._shortcut_width() - native_width)
            self.setMinimumWidth(width)
            if actions:
                super().actionEvent(QActionEvent(QEvent.ActionChanged, actions[0]))
        finally:
            self._sizing_shortcuts = False

    def sizeHint(self):
        self._reserve_shortcuts()
        return super().sizeHint()

    def showEvent(self, event):
        self._reserve_shortcuts()
        super().showEvent(event)

    def _queue_geometry_refresh(self):
        if (self.isVisible() and not getattr(self, "_sizing_shortcuts", False)
                and not getattr(self, "_refresh_pending", False)):
            self._refresh_pending = True
            QTimer.singleShot(0, self._refresh_visible_geometry)

    def _refresh_visible_geometry(self):
        self._refresh_pending = False
        if self.isVisible():
            self.resize(self.sizeHint())
            self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.FontChange,
                            QEvent.PaletteChange, QEvent.LanguageChange):
            self._queue_geometry_refresh()

    def actionEvent(self, event):
        super().actionEvent(event)
        self._queue_geometry_refresh()

    def addMenu(self, *args):
        if len(args) == 1 and isinstance(args[0], str):
            menu = ShortcutMenu(args[0], self)
            super().addMenu(menu)
            return menu
        return super().addMenu(*args)

    def initStyleOption(self, option, action):
        super().initStyleOption(option, action)
        width = self._shortcut_width()
        option.reservedShortcutWidth = max(option.reservedShortcutWidth, width)
        if width and not action.isSeparator():
            # Give plain captions the same column gap as captions with hints.
            option.text = action.text().split("\t", 1)[0] + "\t" + shortcut_hint(action)

# Canvas annotations and their dock.
class VisualItem(QGraphicsObject):
    KINDS = {"text": "Texto", "square": "Cuadrado", "circle": "Círculo", "plane": "Plano"}

    def __init__(self, kind, text="", color="#467bb5", width=160, height=160, font_size=18):
        super().__init__()
        if kind not in self.KINDS:
            raise ValueError(tr("Tipo de elemento visual desconocido"))
        self.kind = kind
        self.text = str(text).strip() if kind == "plane" else str(text)
        self.color = QColor(color)
        if not self.color.isValid():
            raise ValueError(tr("Color de elemento visual inválido"))
        self.width = max(20, min(10000, int(width)))
        self.height = max(20, min(10000, int(height)))
        self.font_size = max(8, min(200, int(font_size)))
        self.border_color = QColor(self.color)
        self.fill_color = QColor(self.color) if kind in ("square", "circle") else None
        self.border_width = 2.0
        self.corner_radius = 0
        self.font_family = QFont().family()
        self.font_bold = kind == "plane"
        self.font_italic = False
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(-20 if kind == "plane" else -10)
        self._resizing = False
        self.setToolTip(tr("Arrastra para mover · doble clic o clic derecho para editar · selecciona para cambiar el tamaño"))

    def font(self):
        font = QFont(self.font_family)
        font.setPointSize(self.font_size)
        font.setBold(self.font_bold)
        font.setItalic(self.font_italic)
        return font

    def text_rect(self):
        metrics = QFontMetricsF(self.font())
        lines = self.text.split("\n") or [""]
        width = max(20, max(metrics.horizontalAdvance(line) for line in lines)) + 12
        height = metrics.lineSpacing() * len(lines) + 8
        return QRectF(0, -height - 6 if self.kind == "plane" else 0, width, height)

    def handle_rect(self):
        return QRectF(self.width - 7, self.height - 7, 14, 14)

    def boundingRect(self):
        if self.kind == "text":
            return self.text_rect().adjusted(-3, -3, 3, 3)
        rect = QRectF(0, 0, self.width, self.height)
        if self.kind == "plane":
            rect = rect.united(self.text_rect())
        margin = max(8, self.border_width / 2 + 2)
        return rect.adjusted(-margin, -margin, margin, margin)

    def outline(self):
        path = QPainterPath()
        rect = QRectF(0, 0, self.width, self.height)
        if self.kind == "circle":
            path.addEllipse(rect)
        else:
            radius = min(self.corner_radius, self.width / 2, self.height / 2)
            path.addRoundedRect(rect, radius, radius)
        return path

    def shape(self):
        path = QPainterPath()
        if self.kind == "text":
            path.addRect(self.text_rect())
        elif self.kind == "plane" or self.fill_color is None:
            stroker = QPainterPathStroker()
            stroker.setWidth(max(10, self.border_width + 6))
            path = stroker.createStroke(self.outline())
            if self.kind == "plane":
                path.addRect(self.text_rect())
        else:
            path = self.outline()
        if self.isSelected() and self.kind != "text":
            path.addRect(self.handle_rect())
        return path

    def paint(self, painter, option, widget=None):
        painter.setPen(QPen(self.border_color, self.border_width) if self.border_width > 0 else Qt.NoPen)
        painter.setBrush(self.fill_color if self.fill_color is not None and self.kind != "plane" else Qt.NoBrush)
        rect = QRectF(0, 0, self.width, self.height)
        if self.kind != "text":
            painter.drawPath(self.outline())
        if self.kind in ("text", "plane"):
            painter.setPen(self.color)
            painter.setFont(self.font())
            painter.drawText(self.text_rect(), Qt.AlignLeft | Qt.AlignTop, self.text)
        if self.isSelected():
            pen = QPen(SELECTION_COLOR, 1, Qt.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.text_rect() if self.kind == "text" else rect)
            if self.kind != "text":
                painter.setBrush(SELECTION_COLOR)
                painter.drawRect(self.handle_rect())

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            board = self.scene().parent()
            if getattr(board, "snap_to_grid", False):
                grid = board.grid_size
                return QPointF(round(value.x() / grid) * grid, round(value.y() / grid) * grid)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected() and self.kind != "text" and self.handle_rect().contains(event.pos()):
            self._resizing = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            self.prepareGeometryChange()
            self.width = max(20, min(10000, int(event.pos().x())))
            self.height = max(20, min(10000, int(event.pos().y())))
            if self.kind in ("square", "circle") and event.modifiers() & Qt.ShiftModifier:
                self.width = self.height = max(self.width, self.height)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            owner = self.scene().parent().owner
            owner._capture_history_change()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def edit(self):
        if self.scene():
            owner = self.scene().parent().owner
            VisualEditDialog(self, owner).exec()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.edit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self.scene().clearSelection()
        self.setSelected(True)
        owner = self.scene().parent().owner
        menu = QMenu()
        edit = menu.addAction(tr("Editar elemento visual…"))
        delete = menu.addAction(tr("Eliminar"))
        action = menu.exec(event.screenPos())
        if action == edit:
            self.edit()
        elif action == delete:
            owner.eliminar_seleccion()
        event.accept()

    def to_data(self):
        return {"kind": self.kind, "text": self.text, "color": self.color.name(),
                "width": self.width, "height": self.height, "font_size": self.font_size,
                "border_color": self.border_color.name(),
                "fill_color": self.fill_color.name() if self.fill_color is not None else None,
                "border_width": self.border_width, "corner_radius": self.corner_radius,
                "font_family": self.font_family, "font_bold": self.font_bold,
                "font_italic": self.font_italic, "opacity": round(self.opacity(), 2),
                "position": [round(self.pos().x(), 3), round(self.pos().y(), 3)]}

    @classmethod
    def from_data(cls, data):
        item = cls(data["kind"], data.get("text", ""), data.get("color", "#467bb5"),
                   data.get("width", 160), data.get("height", 160), data.get("font_size", 18))
        item.border_color = QColor(data.get("border_color", item.color.name()))
        fill = data.get("fill_color", item.color.name() if item.kind in ("square", "circle") else None)
        item.fill_color = QColor(fill) if fill is not None and item.kind in ("square", "circle") else None
        if not item.border_color.isValid() or (item.fill_color is not None and not item.fill_color.isValid()):
            raise ValueError(tr("Color de borde o relleno inválido"))
        item.border_width = max(1 if item.kind == "plane" else 0, min(50, float(data.get("border_width", 2))))
        item.corner_radius = max(0, min(5000, int(data.get("corner_radius", 0))))
        item.font_family = str(data.get("font_family", item.font_family))
        item.font_bold = bool(data.get("font_bold", item.font_bold))
        item.font_italic = bool(data.get("font_italic", False))
        item.setOpacity(max(.05, min(1, float(data.get("opacity", 1)))))
        item.setPos(QPointF(*data.get("position", [0, 0])))
        return item


class VisualEditDialog(QDialog):
    """Type-specific editing; changes enter the history only when accepted."""
    def __init__(self, item, owner):
        super().__init__(owner)
        self.item = item
        self.owner = owner
        self.colors = {}
        self.fields = {}
        self.setWindowTitle((tr("Editar ") + tr(VisualItem.KINDS[item.kind]).lower()))
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addLayout(form)
        if item.kind in ("text", "plane"):
            if item.kind == "text":
                self.text = QPlainTextEdit(item.text)
                self.text.setFixedHeight(90)
                form.addRow(tr("Texto"), self.text)
            else:
                self.text = QLineEdit(item.text)
                form.addRow(tr("Nombre único"), self.text)
            self.color_field(form, "color", "Color del texto", item.color)
            self.font_family = QFontComboBox()
            self.font_family.setCurrentFont(item.font())
            form.addRow(tr("Fuente"), self.font_family)
            self.spin_field(form, "font_size", "Tamaño del texto", 8, 200, item.font_size, " pt")
            self.bold = QCheckBox(tr("Negrita"))
            self.bold.setChecked(item.font_bold)
            self.italic = QCheckBox(tr("Cursiva"))
            self.italic.setChecked(item.font_italic)
            form.addRow(self.bold)
            form.addRow(self.italic)
        if item.kind != "text":
            self.spin_field(form, "width", "Ancho", 20, 10000, item.width)
            self.spin_field(form, "height", "Alto", 20, 10000, item.height)
            self.color_field(form, "border_color", "Color del borde", item.border_color)
            self.border_width = QDoubleSpinBox()
            self.border_width.setRange(1 if item.kind == "plane" else 0, 50)
            self.border_width.setDecimals(1)
            self.border_width.setSuffix(tr(" px"))
            self.border_width.setValue(item.border_width)
            self.border_width.setToolTip((tr("0 oculta el borde") if item.kind != "plane" else tr("Los planos siempre conservan su marco")))
            form.addRow(tr("Grosor del borde"), self.border_width)
            if item.kind in ("square", "circle"):
                self.no_fill = QCheckBox(tr("Sin relleno"))
                self.no_fill.setChecked(item.fill_color is None)
                form.addRow(self.no_fill)
                fill_button = self.color_field(form, "fill_color", "Color del relleno", item.fill_color or item.color)
                fill_button.setEnabled(not self.no_fill.isChecked())
                self.no_fill.toggled.connect(lambda checked: fill_button.setEnabled(not checked))
            if item.kind in ("square", "plane"):
                self.spin_field(form, "corner_radius", "Radio de las esquinas", 0, 5000, item.corner_radius)
        self.spin_field(form, "opacity", "Opacidad", 5, 100, round(item.opacity() * 100), " %")
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(tr("Guardar cambios"))
        self.buttons.button(QDialogButtonBox.Cancel).setText(tr("Cancelar"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def spin_field(self, form, name, label, minimum, maximum, value, suffix=" px"):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(tr(suffix))
        spin.setValue(value)
        self.fields[name] = spin
        form.addRow(tr(label), spin)

    def color_field(self, form, name, label, color):
        self.colors[name] = QColor(color)
        button = QPushButton()
        def show_color():
            current = self.colors[name]
            channels = [current.redF(), current.greenF(), current.blueF()]
            linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
                      for value in channels]
            luminance = sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))
            foreground = "#000000" if luminance > .179 else "#ffffff"
            button.setText(tr(current.name()))
            button.setStyleSheet(
                f"QPushButton {{ background-color: {current.name()}; color: {foreground}; }}"
                f"QPushButton:hover, QPushButton:pressed, QPushButton:disabled {{ "
                f"background-color: {current.name()}; color: {foreground}; }}")
        show_color()
        def choose():
            selected = QColorDialog.getColor(self.colors[name], self, tr(label))
            if selected.isValid():
                self.colors[name] = selected
                show_color()
        button.clicked.connect(choose)
        form.addRow(tr(label), button)
        return button

    def accept(self):
        item = self.item
        if item.scene() is None:
            self.reject()
            return
        if item.kind in ("text", "plane"):
            text = self.text.toPlainText() if item.kind == "text" else self.text.text().strip()
            if not text.strip():
                QMessageBox.warning(self, tr("Texto vacío"), tr("Introduce un texto o nombre para el elemento."))
                return
            if item.kind == "plane" and any(plane is not item and plane.text.casefold() == text.casefold()
                                            for plane in self.owner.visual_planes()):
                QMessageBox.warning(self, tr("Nombre repetido"), tr("Ya existe un plano con ese nombre. Elige otro identificador."))
                return
        # A shape must retain at least a fill or an outline to remain visible.
        if item.kind in ("square", "circle") and self.no_fill.isChecked() and self.border_width.value() == 0:
            QMessageBox.warning(self, tr("Elemento invisible"), tr("Activa el relleno o utiliza un grosor de borde mayor que 0."))
            return
        self.owner._capture_history_change()
        item.prepareGeometryChange()
        if item.kind in ("text", "plane"):
            item.text = text
            item.color = QColor(self.colors["color"])
            item.font_family = self.font_family.currentFont().family()
            item.font_bold = self.bold.isChecked()
            item.font_italic = self.italic.isChecked()
            item.font_size = self.fields["font_size"].value()
        if item.kind != "text":
            item.width = self.fields["width"].value()
            item.height = self.fields["height"].value()
            item.border_color = QColor(self.colors["border_color"])
            item.border_width = self.border_width.value()
            if item.kind in ("square", "circle"):
                item.fill_color = None if self.no_fill.isChecked() else QColor(self.colors["fill_color"])
            if item.kind in ("square", "plane"):
                item.corner_radius = self.fields["corner_radius"].value()
        item.setOpacity(self.fields["opacity"].value() / 100)
        item.update()
        self.owner._refresh_fit_menu()
        self.owner._capture_history_change()
        super().accept()


class VisualDock(QDockWidget):
    """Insertion palette, matching the circuit component palette."""
    def __init__(self, owner):
        super().__init__(tr("Componentes visuales"), owner)
        self.setObjectName("componentesVisuales")
        self.setFeatures(QDockWidget.DockWidgetClosable)
        self.setAllowedAreas(Qt.RightDockWidgetArea)
        self.topLevelChanged.connect(lambda floating: self.setFloating(False) if floating else None)
        self.setMinimumWidth(180)
        self.owner = owner
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 4)
        title = QLabel(tr("Componentes visuales"), header)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        header_layout.addWidget(title, 1)
        close = QPushButton("X", header)
        close.setFlat(True)
        close.setFixedSize(30, 26)
        close.setAccessibleName(tr("Cerrar panel"))
        close.clicked.connect(self.hide)
        header_layout.addWidget(close)
        self.setTitleBarWidget(header)
        body = QWidget(self)
        body.setObjectName("visualPaletteBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        intro = QLabel(tr("Añade un elemento y haz clic en el tablero para colocarlo."))
        intro.setWordWrap(True)
        intro.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(intro)
        buttons = []
        for kind, title in VisualItem.KINDS.items():
            button = QPushButton(tr(title))
            owner._style_component_button(button)
            button.setCheckable(True)
            button.setProperty("visual_kind", kind)
            button.clicked.connect(lambda checked=False, kind=kind: owner.ui.graphicsView.begin_visual_placement(kind))
            owner.ui.graphicsView.visualPlacementChanged.connect(
                lambda active, button=button, kind=kind: button.setChecked(active == kind))
            buttons.append(button)
        scroll = QScrollArea(body)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.palette = ComponentPalette(buttons, scroll)
        scroll.setWidget(self.palette)
        layout.addWidget(scroll, 1)
        hint = QLabel(tr("Solo decorativos: no modifican las señales del circuito.\nEsc cancela la colocación."))
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(hint)
        self.setWidget(body)


