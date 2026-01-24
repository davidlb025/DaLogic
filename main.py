# This Python file uses the following encoding: utf-8
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog, QTextBrowser
import re


# This file is only for people who want to convert they modified UI to Py.
import build
build.convert()
# This file is only for people who want to convert they modified UI to Py.

from compiled.ui_ventana1 import Ui_MainWindow as MainWindow
from compiled.ui_credits import Ui_Form as Credit_Form

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
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ventana = VentanaInicial()
    sys.exit(app.exec())
