# This Python file uses the following encoding: utf-8
import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog, QTextBrowser, QPushButton, QGraphicsScene,QGraphicsTextItem
from PySide6.QtGui import QColor, QFont
import re
import importlib
import json
import widgets.widgets as wdg
import widgets.graphics as gra
# This file is only for people who want to convert their modified UI to Py.
import scripts.build as build
build.convert()
# This file is only for people who want to convert their modified UI to Py.

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
        url_regex = r"(https?://[^\s]+)"
        return re.sub(url_regex, r'<a href="\1">\1</a>', texto)

    def format_notice(self, texto):
        lineas = texto.splitlines()
        html_lineas = []

        for i, linea in enumerate(lineas):
            linea = self.convertir_links(linea)
            linea = linea.replace(
                "David Lopez Borrego",
                "<b>David Lopez Borrego</b>"
            )

            if linea == "":
                html_lineas.append("<p></p>")
            else:
                if i == 0:
                    html_lineas.append(
                        f"<h1 style='text-align:center;'>{linea}</h1>"
                    )
                elif i == 1:
                    html_lineas.append(
                        f"<h3 style='text-align:center;'>{linea}</h3>"
                    )
                else:
                    html_lineas.append(f"<p>{linea}</p>")

        return "".join(html_lineas)

    def cargar_creditos(self):
        try:
            with open("NOTICE", "r", encoding="utf-8") as credit:
                texto = credit.read()
        except FileNotFoundError:
            texto = """DaLogic

Copyright 2026 David Lopez Borrego

Project repository:
https://github.com/davidlb025/DaLogic

This product includes software developed by David Lopez Borrego
"""

        label = self.findChild(QTextBrowser, "Creditos")
        if label:
            label.setHtml(self.format_notice(texto))




class VentanaInicial(QMainWindow):

    def __init__(self,app):
        super().__init__()
        self.load_settings()
        self.iniciarUI()
        self.def_actions()

    def iniciarUI(self):
        self.widgets = {}
        self.conectors = {}
        self.graphics = {}
        self.next_id=0
        self.ui = self.MainWindow
        self.ui.setupUi(self)
        app.setStyle("Fusion")
        app.setStyleSheet(self.cargar_tema(self.config["theme"]))
        self.ui.Show.hide()
        self.ui.Show.clicked.connect(self.devolver_widg_panel)
        self.ui.close = QPushButton("X", self.ui.menu.viewport(),flat=True)
        self.ui.close.move(-10, -10)
        self.ui.close.raise_()
        self.ui.close.show()
        self.ui.close.setFixedWidth(30)
        self.ui.close.clicked.connect(self.cerrar_widg_panel)
        self.ui.splitter.splitterMoved.connect(self.check_widg_panel)
        self.def_buttons()
        self.show()

    def def_buttons(self):
        self.ui.AND.clicked.connect(self.crear_and)

    def crear_and(self):
        and_widg = wdg.AND(self.next_id)
        and_graph = gra.Graphic(
            widg=and_widg,
            svg_path="resources/icons/AND.svg",
            scale=0.2
        )

        self.ui.graphicsView.scene.addItem(and_graph)

        and_graph.setPos(
            self.ui.graphicsView.scene.width() / 2,
            self.ui.graphicsView.scene.height() / 2
        )

        self.widgets[self.next_id] = and_widg
        self.graphics[self.next_id] = and_graph

        self.next_id += 1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updt_button()

    def updt_button(self):
        margen = 1
        self.ui.close.move(
                self.ui.menu.viewport().width() - self.ui.close.width() - margen,
                margen
        )

    def check_widg_panel(self, pos, index):
        self.updt_button()

    def cerrar_widg_panel(self):
        self.ui.menu.hide()
        self.ui.splitter.setSizes([0, self.ui.splitter.width()])
        self.ui.Show.show()
    def devolver_widg_panel(self):

        total_width = self.ui.splitter.width()
        left_min = self.ui.menu.minimumWidth()
        right_width = total_width - left_min
        self.ui.splitter.setSizes([left_min, right_width])
        self.ui.menu.show()
        self.ui.Show.hide()
        self.ui.close.show()

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





    # ================= Configuración =================

    def create_config(self, file_path="user/config.json"):
        """
        Crea un archivo config.json con valores por defecto si no existe.
        """
        config = {
            "theme": "resources/styles/light.qss",
            "lang": "es",
            "main_UI": "resources.compiled.ui_ventana1",
            "credits_UI": "resources.compiled.ui_credits",
            "config_UI": "resources.compiled.ui_config",
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def load_UI(self, ui, default, type):
        """
        Load the UI.
        Use: load_UI("new_ui", "default_ui", "")"""

        try:
            module = importlib.import_module(ui)
            ui_class = getattr(module, type)
        except (ModuleNotFoundError, AttributeError):
            print("Err")
            module = importlib.import_module("resources.compiled.ui_ventana1")
            ui_class = getattr(module, "Ui_MainWindow")

        return ui_class

    def change_settings(self, key, value):
        pass

    def get_settings(self, file_path="user/config.json"):
        REQUIRED_KEYS = ["theme", "lang", "main_UI", "credits_UI","config_UI"]
        if not os.path.exists(file_path):
            self.create_config(file_path)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except json.JSONDecodeError:
            self.create_config(file_path)
            self.get_settings(file_path)

        falta = [key for key in REQUIRED_KEYS if key not in self.config]

        if falta:
            self.create_config(file_path)
            self.get_settings(file_path)
    def load_settings(self):
        self.get_settings()
        self.MainWindow = self.load_UI(self.config["main_UI"], "ui_ventana1", "Ui_MainWindow")()
        self.Credit_Form = self.load_UI(self.config["credits_UI"], "ui_credits", "Ui_Form")()
        self.Config_Form = self.load_UI(self.config["config_UI"], "ui_config", "Ui_Form")()

    def cargar_tema(self, path="resources/styles/light.qss"):
        with open(path, "r", encoding="utf-8") as f:
            qss = f.read()
        return qss

    # =================Creditos =================

    # ================= Acciones =================

    def abrir_archivo(self):
        pass

    def cerrar_proj(self):
        pass

    def configure(self):
        self.config_window = VentanaConfig(self.Config_Form, self)
        self.config_window.exec()

    def exportar(self):
        pass

    def guardar(self):
        pass

    def guardarcomo(self):
        pass

    def imprimir(self):
        pass

    def nuevo(self):
        pass

    def recientes(self):
        pass

    def salir_app(self):
        pass

    def copiar(self):
        pass

    def cortar(self):
        pass

    def pegar(self):
        pass

    def about(self):
        self.creditos_window = VentanaCreditos(self.Credit_Form, self)
        self.creditos_window.exec()

    def tutorial(self):
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaInicial(app)
    sys.exit(app.exec())
