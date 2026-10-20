from resources import translate_text as tr
"""Application paths, user data, update checks and desktop startup."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSizePolicy, QTextBrowser, QVBoxLayout,
)
from shiboken6 import isValid

from project_io import write_json_atomic
from resources import APP_VERSION, get_app_icon


# Application paths and writable user data.
BASE_DIR = Path(__file__).resolve().parent


def _writable(directory):
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=directory):
            pass
        return True
    except OSError:
        return False


def data_paths():
    override = os.environ.get("DALOGIC_DATA_DIR")
    frozen = getattr(sys, "frozen", False)
    local = BASE_DIR / "user"
    if override:
        user = Path(override).expanduser().resolve()
    elif not frozen and _writable(local):
        # Preserve existing source checkouts and their personal libraries.
        user = local
    else:
        user = Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)) / "DaLogic"
    documents = (BASE_DIR if user == local else
                 user if override else
                 Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)) / "DaLogic")
    return user, documents / "Proyectos", documents / "Exports"


USER_DIR, PROJECTS_DIR, EXPORTS_DIR = data_paths()
CI_LIBRARY_DIR = USER_DIR / "Biblioteca"
LEGACY_CI_LIBRARY_DIR = USER_DIR / "Biblioteca de CI"
LANGUAGE_DIR = USER_DIR / "Idiomas"


def initialize_user_data():
    """Seed missing assets without replacing user files or old preferences."""
    USER_DIR.mkdir(parents=True, exist_ok=True)
    sources = ([Path(sys.executable).resolve().parent / "user"]
               if getattr(sys, "frozen", False) else []) + [BASE_DIR / "user", BASE_DIR / "resources" / "defaults"]
    for source in sources:
        if source.resolve() == USER_DIR.resolve() or not source.is_dir():
            continue
        for name in ("config.json", "recent.json"):
            old, new = source / name, USER_DIR / name
            if old.is_file() and not new.exists():
                shutil.copy2(old, new)
        for name in ("Biblioteca", "Biblioteca de CI", "Idiomas"):
            for old in (source / name).rglob("*"):
                if old.is_file() and old.suffix.lower() in (".json", ".dmodule"):
                    new = USER_DIR / name / old.relative_to(source / name)
                    if not new.exists():
                        new.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(old, new)
    CI_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    LANGUAGE_DIR.mkdir(parents=True, exist_ok=True)


# Asynchronous release checks and notification dialog.
VERSION_ACTUAL = APP_VERSION
RELEASES_API_URL = "https://api.github.com/repos/davidlb025/DaLogic/releases/latest"
CONFIG_PATH = USER_DIR / "config.json"
CONFIG_KEY_VERSION_IGNORADA = "version_update_ignorada"


def _leer_configuracion(config_path):
    try:
        with config_path.open("r", encoding="utf-8") as archivo:
            configuracion = json.load(archivo)
        return configuracion if isinstance(configuracion, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _guardar_configuracion(config_path, configuracion):
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(config_path, configuracion)
    except OSError:
        # Un error al guardar las preferencias no debe impedir que se abra la app.
        pass


def _parse_release(release):
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    version = str(release.get("tag_name", "")).strip()
    if _version_key(version) is None:
        return None
    url = str(release.get("html_url") or "")
    if not url.startswith("https://github.com/davidlb025/DaLogic/releases/"):
        url = "https://github.com/davidlb025/DaLogic/releases"
    return {
        "version": version,
        "nombre": str(release.get("name") or version),
        "notas": str(release.get("body") or tr("No se incluyeron detalles para esta versión.")),
        "url": url,
    }


def _normalizar_version(version):
    return str(version).strip().lower().removeprefix("v")


def _version_key(version):
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", _normalizar_version(version))
    return tuple(int(part or 0) for part in match.groups()) if match else None


def update_notifications_enabled(parent=None, config_path=CONFIG_PATH):
    configuration = getattr(parent, "config", None)
    if not isinstance(configuration, dict):
        configuration = _leer_configuracion(Path(config_path))
    return configuration.get("update_notifications", True) is not False


def comprobar_actualizaciones(parent=None, config_path=CONFIG_PATH):
    """Fetch a release asynchronously so startup remains responsive."""
    if not update_notifications_enabled(parent, config_path):
        return None
    app = QApplication.instance()
    if app is None:
        raise RuntimeError(tr("Debe crearse QApplication antes de comprobar actualizaciones."))

    manager = QNetworkAccessManager(app)
    request = QNetworkRequest(QUrl(RELEASES_API_URL))
    request.setRawHeader(b"Accept", b"application/vnd.github+json")
    request.setRawHeader(b"User-Agent", b"DaLogic-update-checker")
    request.setTransferTimeout(3000)
    reply = manager.get(request)

    def finished():
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            release = _parse_release(json.loads(bytes(reply.readAll()).decode("utf-8")))
            if release is not None and (parent is None or isValid(parent)):
                _mostrar_actualizacion(parent, config_path, release)
        except (ValueError, UnicodeError):
            pass
        finally:
            reply.deleteLater()
            manager.deleteLater()

    reply.finished.connect(finished)
    return manager


def _mostrar_actualizacion(parent, config_path, release):
    # Recheck at response time: the user may disable notices while a request is in flight.
    if not update_notifications_enabled(parent, config_path):
        return
    configuracion = _leer_configuracion(Path(config_path))
    version_ignorada = configuracion.get(CONFIG_KEY_VERSION_IGNORADA)

    remote, current = _version_key(release["version"]), _version_key(VERSION_ACTUAL)
    if remote is None or current is None:
        return
    if remote <= current:
        if version_ignorada:
            configuracion.pop(CONFIG_KEY_VERSION_IGNORADA, None)
            _guardar_configuracion(Path(config_path), configuracion)
        return

    if version_ignorada == release["version"]:
        return

    if version_ignorada:
        configuracion.pop(CONFIG_KEY_VERSION_IGNORADA, None)
        _guardar_configuracion(Path(config_path), configuracion)

    dialogo = QDialog(parent)
    dialogo.setWindowTitle(tr("Actualización disponible para DaLogic"))
    dialogo.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    layout = QVBoxLayout(dialogo)

    resumen = QLabel(
        tr('Hay una nueva versión de DaLogic: {v0} ({v1}).', v0=release['nombre'], v1=release['version']),
        dialogo,
    )
    resumen.setWordWrap(True)
    layout.addWidget(resumen)

    notas = QTextBrowser(dialogo)
    notas.setOpenExternalLinks(True)
    notas.setMarkdown(release["notas"])
    notas.setMinimumHeight(120)
    notas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout.addWidget(notas, 1)

    botones = QHBoxLayout()
    botones.addStretch(1)
    boton_release = QPushButton(tr("Ver release"), dialogo)
    boton_ignorar = QPushButton(tr("No recordar esta versión"), dialogo)
    boton_aceptar = QPushButton(tr("Aceptar"), dialogo)
    boton_aceptar.setDefault(True)
    for boton in (boton_release, boton_ignorar, boton_aceptar):
        botones.addWidget(boton)
    layout.addLayout(botones)

    resultado = {"accion": "aceptar"}
    boton_release.clicked.connect(lambda: (resultado.update(accion="release"), dialogo.accept()))
    boton_ignorar.clicked.connect(lambda: (resultado.update(accion="ignorar"), dialogo.accept()))
    boton_aceptar.clicked.connect(dialogo.accept)

    pantalla = None
    if parent is not None and parent.windowHandle() is not None:
        pantalla = parent.windowHandle().screen()
    if pantalla is None:
        pantalla = QApplication.primaryScreen()
    if pantalla is not None:
        disponible = pantalla.availableGeometry()
        ancho = min(700, max(420, int(disponible.width() * 0.72)))
        alto = min(600, max(300, int(disponible.height() * 0.78)))
        ancho = min(ancho, disponible.width())
        alto = min(alto, disponible.height())
        dialogo.setMaximumSize(disponible.size())
        dialogo.resize(ancho, alto)
    else:
        dialogo.resize(620, 480)

    dialogo.exec()

    if resultado["accion"] == "release":
        QDesktopServices.openUrl(QUrl(release["url"]))
    elif resultado["accion"] == "ignorar":
        configuracion[CONFIG_KEY_VERSION_IGNORADA] = release["version"]
        _guardar_configuracion(Path(config_path), configuracion)


# Desktop startup, single-instance lock and recoverable error reporting.
def run(window_class, argv=None):
    parser = argparse.ArgumentParser(description="Editor y simulador de circuitos DaLogic")
    parser.add_argument("project", nargs="?", type=Path, help="Proyecto .dalogic que se abrirá al iniciar")
    parser.add_argument("--no-update-check", action="store_true", help="Iniciar sin consultar actualizaciones")
    parser.add_argument("--smoke-test", action="store_true", help="Comprobar arranque y cerrar sin modificar proyectos")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    from resources import load_catalogs, set_language_translations
    catalogs = load_catalogs(LANGUAGE_DIR)
    code = str(_leer_configuracion(CONFIG_PATH).get("lang", "es"))
    catalog = catalogs.get(code, catalogs["es"])
    set_language_translations(catalog["translations"], catalog["code"])
    app.setApplicationName("DaLogic")
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(get_app_icon())
    try:
        initialize_user_data()
    except OSError as exc:
        if not args.smoke_test:
            QMessageBox.critical(None, tr("No se puede iniciar DaLogic"),
                                 tr('No se puede preparar la carpeta de datos:\n{v0}\n\n{v1}', v0=USER_DIR, v1=exc))
        return 1
    lock = QLockFile(str(USER_DIR / "dalogic.lock"))
    if not lock.tryLock(100):
        if not args.smoke_test:
            QMessageBox.warning(None, tr("DaLogic ya está abierto"),
                                tr("Otra instancia utiliza esta carpeta de datos. Vuelve a la ventana abierta."))
        return 2
    try:
        handler = RotatingFileHandler(USER_DIR / "dalogic.log", maxBytes=1_000_000,
                                      backupCount=2, encoding="utf-8")
    except OSError as exc:
        lock.unlock()
        if not args.smoke_test:
            QMessageBox.critical(None, tr("No se puede iniciar DaLogic"), tr('No se puede escribir el registro:\n{v0}', v0=exc))
        return 1
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("dalogic")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    window = None
    previous_hook = sys.excepthook

    def report_error(kind, value, traceback):
        if issubclass(kind, KeyboardInterrupt):
            app.quit()
            return
        logger.error("Error no controlado", exc_info=(kind, value, traceback))
        if window is not None:
            try:
                window._write_autosave()
            except Exception:
                logger.exception("No se pudo crear la recuperación tras el error")
        message = QMessageBox(QMessageBox.Critical, tr("Error en DaLogic"),
            tr('Se ha producido un error. Revisa el circuito y guarda una copia de tu trabajo.\nEl diagnóstico está en {v0}', v0=USER_DIR / 'dalogic.log'), parent=window)
        message.setDetailedText(tr('{v0}: {v1}', v0=kind.__name__, v1=value))
        message.exec()

    sys.excepthook = report_error
    try:
        logger.info("Inicio DaLogic %s", APP_VERSION)
        window = window_class(app, recover=not args.smoke_test)
        if args.project:
            if not window.cargar_proyecto(args.project.resolve(), _report_errors=not args.smoke_test):
                if args.smoke_test:
                    window._document_saved_key = window._project_content_key()
                    window.close()
                    return 1
            else:
                window.ajustar_vista()
        if args.smoke_test:
            app.processEvents()
            window._document_saved_key = window._project_content_key()
            window.close()
            return 0
        if not args.no_update_check and update_notifications_enabled(window):
            QTimer.singleShot(0, lambda: comprobar_actualizaciones(window))
        return app.exec()
    except Exception:
        logger.exception("Error al iniciar DaLogic")
        if not args.smoke_test:
            QMessageBox.critical(None, tr("No se pudo iniciar DaLogic"),
                                 tr('Consulta el registro: {v0}', v0=USER_DIR / 'dalogic.log'))
        return 1
    finally:
        sys.excepthook = previous_hook
        logger.removeHandler(handler)
        handler.close()
        lock.unlock()
