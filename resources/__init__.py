"""Shared Qt resource helpers."""
from PySide6.QtGui import QIcon, QColor
from .compiled import img_rc  # Registers the embedded resources.

APP_VERSION = "1.2.0"
SELECTION_COLOR = QColor("#2d7ff9")


def get_app_icon():
    return QIcon(":/images/icons/dalogic.ico")


"""Application and Qt translations, with immutable bundled fallbacks."""
import json
from pathlib import Path
from string import Formatter

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication, QFileDialog as _FileDialog, QInputDialog as _InputDialog

DEFAULTS = Path(__file__).resolve().parent / 'defaults' / 'Idiomas'
_translations = {}
_language = 'es'
_qt_translator = None
_app_translator = None


def load_catalogs(user_directory):
    """Overlay user entries without deleting keys or losing new bundled strings."""
    catalogs = {}
    for directory in (DEFAULTS, Path(user_directory)):
        for path in sorted(directory.glob('*.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8-sig'))
                code = data.get('code', path.stem)
                entries = data.get('translations', {})
                if not isinstance(code, str) or not isinstance(entries, dict):
                    continue
                catalog = catalogs.setdefault(code, {'code': code, 'name': code, 'translations': {}})
                catalog['name'] = str(data.get('name') or catalog['name'])
                for source, target in entries.items():
                    if not isinstance(target, str) or not target:
                        continue
                    # Old auto-generated copies containing untranslated Spanish
                    # must not hide an updated bundled translation.
                    if source == target and source in catalog['translations']:
                        continue
                    try:
                        fields = lambda text: sorted(field for _, field, _, _ in Formatter().parse(text) if field is not None)
                        if fields(source) != fields(target):
                            continue
                    except ValueError:
                        continue
                    catalog['translations'][source] = target
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    catalogs.setdefault('es', {'code': 'es', 'name': 'Español', 'translations': {}})
    return catalogs


def translate_text(text, **values):
    if not isinstance(text, str):
        return text
    result = _translations.get(text, text)
    return result.format(**values) if values else result


def translate_items(items):
    return [translate_text(item) for item in items]


def source_text(text):
    """Recover the source of a static label already translated at construction."""
    return next((source for source, target in _translations.items()
                 if target == text and source != target), text)


class _ApplicationTranslator(QTranslator):
    def translate(self, context, source, disambiguation=None, n=-1):
        # QMenu measures NativeText even when it paints our portable hint.
        # Keep modifier names consistent so translated long names do not
        # reserve an invisible second shortcut column.
        if context == 'QShortcut' and source in ('Ctrl', 'Shift', 'Alt', 'Meta'):
            return source
        # None is a null QString: let Qt try its own catalogs and source text.
        # An empty Python string is an actual empty translation, swallowing
        # Qt's labels and %1 placeholders used by numeric/accessibility text.
        return _translations.get(source)


def set_language_translations(translations, code=None):
    global _translations, _language, _qt_translator, _app_translator
    _translations = dict(translations or {})
    if code is None:
        return
    _language = code
    app = QApplication.instance()
    if app is None:
        return
    for translator in (_app_translator, _qt_translator):
        if translator is not None:
            app.removeTranslator(translator)
    _qt_translator = QTranslator(app)
    locale = {'ca': 'ca', 'es': 'es', 'en': 'en'}.get(code, code)
    if _qt_translator.load('qtbase_' + locale, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(_qt_translator)
    _app_translator = _ApplicationTranslator(app)
    app.installTranslator(_app_translator)


def language_code():
    return _language


def library_module_name(name, path=None, library=None):
    """Module names are document content and never follow the UI language."""
    return name


def module_display_name(widget):
    return widget.name


class LocalizedInputDialog:
    """Translate choices while returning their stable source values to callers."""
    @staticmethod
    def getItem(parent, title, label, items, *args, **kwargs):
        literal_items = set(kwargs.pop('literal_items', ()))
        shown = [item if item in literal_items else translate_text(item) for item in items]
        selected, accepted = _InputDialog.getItem(parent, translate_text(title), translate_text(label), shown, *args, **kwargs)
        return (items[shown.index(selected)] if accepted and selected in shown else selected), accepted

    @staticmethod
    def getText(parent, title, label, *args, **kwargs):
        return _InputDialog.getText(parent, translate_text(title), translate_text(label), *args, **kwargs)

    @staticmethod
    def getInt(parent, title, label, *args, **kwargs):
        return _InputDialog.getInt(parent, translate_text(title), translate_text(label), *args, **kwargs)

    @staticmethod
    def getDouble(parent, title, label, *args, **kwargs):
        return _InputDialog.getDouble(parent, translate_text(title), translate_text(label), *args, **kwargs)


class LocalizedFileDialog:
    @staticmethod
    def _file(method, parent, caption='', directory='', filter='', *args, **kwargs):
        filter = source_text(filter)
        translated = translate_text(filter)
        if args and isinstance(args[0], str):
            sources, targets = filter.split(';;'), translated.split(';;')
            if args[0] in sources:
                args = (targets[sources.index(args[0])], *args[1:])
        path, selected = method(parent, translate_text(caption), directory, translated, *args, **kwargs)
        originals, targets = filter.split(';;'), translated.split(';;')
        if selected in targets:
            selected = originals[targets.index(selected)]
        return path, selected

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        return LocalizedFileDialog._file(_FileDialog.getOpenFileName, *args, **kwargs)

    @staticmethod
    def getOpenFileNames(*args, **kwargs):
        return LocalizedFileDialog._file(_FileDialog.getOpenFileNames, *args, **kwargs)

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        return LocalizedFileDialog._file(_FileDialog.getSaveFileName, *args, **kwargs)

    @staticmethod
    def getExistingDirectory(parent, caption='', *args, **kwargs):
        return _FileDialog.getExistingDirectory(parent, translate_text(caption), *args, **kwargs)
