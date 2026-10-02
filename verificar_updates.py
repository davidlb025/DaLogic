"""Comprueba si hay una versión nueva de DaLogic en GitHub."""

import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import QApplication, QMessageBox


VERSION_ACTUAL = "1.1.0"
RELEASES_API_URL = "https://api.github.com/repos/davidlb025/DaLogic/releases/latest"
CONFIG_PATH = Path(__file__).resolve().parent / "user" / "config.json"
CONFIG_KEY_VERSION_IGNORADA = "version_update_ignorada"


def _leer_configuracion(config_path):
    try:
        with config_path.open("r", encoding="utf-8") as archivo:
            configuracion = json.load(archivo)
        return configuracion if isinstance(configuracion, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _guardar_configuracion(config_path, configuracion):
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(configuracion, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # Un error al guardar las preferencias no debe impedir que se abra la app.
        pass


def _consultar_ultima_release():
    solicitud = Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DaLogic-update-checker",
        },
    )
    try:
        with urlopen(solicitud, timeout=3) as respuesta:
            release = json.loads(respuesta.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    version = str(release.get("tag_name", "")).strip()
    if not version:
        return None
    return {
        "version": version,
        "nombre": str(release.get("name") or version),
        "notas": str(release.get("body") or "No se incluyeron detalles para esta versión."),
        "url": str(release.get("html_url") or "https://github.com/davidlb025/DaLogic/releases"),
    }


def _normalizar_version(version):
    return version.strip().lower().removeprefix("v")


def comprobar_actualizaciones(parent=None, config_path=CONFIG_PATH):
    """Muestra el aviso de actualización si GitHub publica una versión nueva."""
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Debe crearse QApplication antes de comprobar actualizaciones.")

    release = _consultar_ultima_release()
    if release is None:
        return

    configuracion = _leer_configuracion(Path(config_path))
    version_ignorada = configuracion.get(CONFIG_KEY_VERSION_IGNORADA)

    if _normalizar_version(release["version"]) == _normalizar_version(VERSION_ACTUAL):
        if version_ignorada:
            configuracion.pop(CONFIG_KEY_VERSION_IGNORADA, None)
            _guardar_configuracion(Path(config_path), configuracion)
        return

    if version_ignorada == release["version"]:
        return

    if version_ignorada:
        configuracion.pop(CONFIG_KEY_VERSION_IGNORADA, None)
        _guardar_configuracion(Path(config_path), configuracion)

    dialogo = QMessageBox(parent)
    dialogo.setIcon(QMessageBox.Information)
    dialogo.setWindowTitle("Actualización disponible para DaLogic")
    dialogo.setText(f"Hay una nueva versión de DaLogic: {release['nombre']} ({release['version']}).")
    documento = QTextDocument()
    documento.setMarkdown(release["notas"])
    dialogo.setInformativeText(documento.toHtml())
    boton_release = dialogo.addButton("Ver release", QMessageBox.ActionRole)
    boton_ignorar = dialogo.addButton("No recordar esta versión", QMessageBox.DestructiveRole)
    dialogo.addButton("Aceptar", QMessageBox.AcceptRole)
    dialogo.exec()

    if dialogo.clickedButton() is boton_release:
        QDesktopServices.openUrl(QUrl(release["url"]))
    elif dialogo.clickedButton() is boton_ignorar:
        configuracion[CONFIG_KEY_VERSION_IGNORADA] = release["version"]
        _guardar_configuracion(Path(config_path), configuracion)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    comprobar_actualizaciones()
