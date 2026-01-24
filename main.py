# This Python file uses the following encoding: utf-8
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog, QTextBrowser
import re
import importlib
import json
import os

# This file is only for people who want to convert they modified UI to Py.
import build
build.convert()
# This file is only for people who want to convert they modified UI to Py.




def create_config(file_path="config.json"):
    """
    Crea un archivo config.json con valores por defecto si no existe.
    """
    # Valores por defecto de la configuración
    config = {
        "theme":"light",
        "lang":"es",
        "main_UI":"ui_ventana1",
        "credits_UI":"ui_credits"
    }

    # Verificar si ya existe el archivo
    if os.path.exists(file_path):
        return

    with open(file_path, "w") as f:
        json.dump(config, f, indent=4)


def load_UI(ui,default,type):
    """
    Load the UI.
    Use: load_UI("new_ui", "default_ui", 0/1)
    0 = Ui_MainWindow
    1 = Ui_Form
    """
    if type == 0:
        type = "Ui_MainWindow"
    elif type == 1:
        type = "Ui_Form"
    else:
        type = "Ui_MainWindow"
    try:

        module = importlib.import_module(f"compiled.{ui}")
        ui_class = getattr(module, type)

    except (ModuleNotFoundError, AttributeError):

        module = importlib.import_module("compiled.ui_ventana1")
        ui_class = getattr(module, "Ui_MainWindow")

    return ui_class


def load_settings(file_path="config.json"):
    global MainWindow,Credit_Form
    if not os.path.exists(file_path):
        create_config(file_path)

    with open(file_path, "r") as f:
        config = json.load(f)


    MainWindow = load_UI(config["main_UI"],"ui_ventana1",0)
    Credit_Form = load_UI(config["credits_UI"],"ui_credits",1)



def cargar_tema(nombre="light"):
    path = f"styles/{nombre}.qss"
    with open(path, "r", encoding="utf-8") as f:
        qss = f.read()
    return qss



def convertir_links(texto):
    url_regex = r"(https?://[^\s]+)"
    return re.sub(url_regex, r'<a href="\1">\1</a>', texto)

def format_notice(texto):
    lineas = texto.splitlines()

    html_lineas = []

    i = 0
    for linea in lineas:

        linea = convertir_links(linea)

        linea = linea.replace("David Lopez Borrego", "<b>David Lopez Borrego</b>")
        if linea == "":
            html_lineas.append(f"<p>{linea}</p>")
        else:
            if i == 0:
                html_lineas.append(f"<h1 style='text-align:center;'>{linea}</h1>")
            elif i == 1:
                html_lineas.append(f"<h3 style='text-align:center;'>{linea}</h3>")
            else:
                html_lineas.append(f"<p>{linea}</p>")
            i +=1

    return "".join(html_lineas)

class VentanaInicial(QMainWindow):

    def __init__(self):
        super().__init__()
        self.iniciarUI()
        self.def_actions()

    def iniciarUI(self):
        self.ui = MainWindow()
        self.ui.setupUi(self)
        self.show()


    def def_actions(self):

        self.ui.actionAbrir.triggered.connect(self.abrir_archivo)
        self.ui.actionCerrar.triggered.connect(self.cerrar_proj)

        self.ui.actionConfiguracion.triggered.connect(self.config)
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

    def abrir_archivo(self):
        pass

    def cerrar_proj(self):
        pass

    def config(self):
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
        self.creditos_window = QDialog()
        self.ui_creditos = Credit_Form()
        self.ui_creditos.setupUi(self.creditos_window)

        try:
            with open("NOTICE", "r", encoding="utf-8") as credit:
                texto = credit.read()
        except:
            texto = """DaLogic

            Copyright 2026 David Lopez Borrego

            Project repository:
            https://github.com/davidlb025/DaLogic

            This product includes software developed by David Lopez Borrego"""

        label = self.creditos_window.findChild(QTextBrowser, "Creditos")


        label.setHtml(format_notice(texto))




        self.creditos_window.exec() # Bloquear Fondo

    def tutorial(self):
        pass


if __name__ == "__main__":
    load_settings()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(cargar_tema("light"))
    ventana = VentanaInicial()
    sys.exit(app.exec())
