# This Python file uses the following encoding: utf-8
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog, QTextBrowser
import re
import importlib
import json
import os

# This file is only for people who want to convert their modified UI to Py.
import scripts.build as build
build.convert()
# This file is only for people who want to convert their modified UI to Py.

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
        self.ui = self.MainWindow
        self.ui.setupUi(self)
        self.show()
        app.setStyle("Fusion")
        app.setStyleSheet(self.cargar_tema(self.config["theme"]))

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
            "theme": "light",
            "lang": "es",
            "main_UI": "ui_ventana1",
            "credits_UI": "ui_credits"
        }

        if os.path.exists(file_path):
            return

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def load_UI(self, ui, default, type_):
        """
        Load the UI.
        Use: load_UI("new_ui", "default_ui", 0/1)
        0 = Ui_MainWindow
        1 = Ui_Form
        """
        if type_ == 0:
            class_name = "Ui_MainWindow"
        elif type_ == 1:
            class_name = "Ui_Form"
        else:
            class_name = "Ui_MainWindow"

        try:
            module = importlib.import_module(ui)
            ui_class = getattr(module, class_name)
        except (ModuleNotFoundError, AttributeError):
            module = importlib.import_module("resources.compiled.ui_ventana1")
            ui_class = getattr(module, "Ui_MainWindow")

        return ui_class

    def change_settings(self, key, value):
        pass

    def get_settings(self, file_path="user/config.json"):
        if not os.path.exists(file_path):
            self.create_config(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def load_settings(self):
        self.get_settings()
        self.MainWindow = self.load_UI(self.config["main_UI"], "ui_ventana1", 0)()
        self.Credit_Form = self.load_UI(self.config["credits_UI"], "ui_credits", 1)()

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
        pass

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
