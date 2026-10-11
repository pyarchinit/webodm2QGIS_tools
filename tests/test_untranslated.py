"""Cerca nel codice testi dell'interfaccia (etichette, pulsanti, tooltip, titoli, messaggi) scritti direttamente
come stringa invece che con T(): sono quelli che resterebbero in italiano in tutte le lingue.
    python tests/test_untranslated.py"""
import ast
import os
import re
import sys

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'webodm2qgis_tools')

# metodi/classi il cui argomento stringa e' un testo visibile
SETTERS = {'setText', 'setToolTip', 'setStatusTip', 'setWindowTitle', 'setPlaceholderText', 'setTitle', 'setHtml',
           'setDialogTitle', 'setFormat', 'addTab', 'setHeaderLabels', 'setWhatsThis', 'pushMessage', 'setInformativeText'}
WIDGETS = {'QLabel', 'QPushButton', 'QGroupBox', 'QCheckBox', 'QRadioButton', 'QAction', 'QMenu', 'QToolButton'}
# stringhe che non sono testo da tradurre: simboli, nomi propri, formati, placeholder tecnici
OK = re.compile(r'^([a-z_]+|&WebODM|\s*|[.…<>/\\()\-+:,;|&#%0-9xXyY]+|WebODM|WebODM2QGIS-tools|\.\.\.|EPSG:\d+|QGIS|X|Y|Zoom|Dashboard|'
                r'http://localhost:29800|http://127\.0\.0\.1:29800|Flyoveracademy\.it)$')


def has_letters(s):
    return re.search(r'[A-Za-zÀ-ÿ]{3,}', re.sub(r'<[^>]+>|%[sdr]|\{[^}]*\}', '', s)) is not None


def is_T(node):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'T'


def strings_in(node):
    """Stringhe letterali dell'argomento, ignorando quelle dentro T()."""
    if is_T(node):
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    out = []
    for child in ast.iter_child_nodes(node):
        out += strings_in(child)
    return out


def main():
    problems = []
    for d, _dirs, files in os.walk(PKG):
        for f in sorted(files):
            if not f.endswith('.py') or f in ('i18n.py', 'i18n_en.py'):
                continue
            path = os.path.join(d, f)
            tree = ast.parse(open(path, encoding='utf-8').read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else '')
                if name in SETTERS or name in WIDGETS or name in ('addItem', 'addRow', 'addAction', 'addMenu'):
                    args = node.args
                    if name in ('addItem', 'addRow', 'addAction', 'addMenu', 'addTab'):
                        args = args[:2]
                    for a in args:
                        for s in strings_in(a):
                            if has_letters(s) and not OK.match(s.strip()):
                                problems.append('%s:%d  %s(...%r...)' % (os.path.relpath(path, PKG), node.lineno, name, s[:70]))
    if problems:
        for p in problems:
            print('NON TRADOTTO?', p)
    print('test_untranslated: %s (%d sospetti)' % ('tutto ok' if not problems else 'DA CONTROLLARE', len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
