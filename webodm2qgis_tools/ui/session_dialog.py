"""Finestra "Sessione di import": scegli una cartella e dai un nome all'importazione."""
import os

from qgis.core import QgsSettings
from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                                 QVBoxLayout)

from ..core.session import Session, dirname_of
from ..i18n import T
from .icons import icon

RECENT = 'webodm2qgis_tools/recent_sessions'


def recent_sessions():
    import json
    try:
        return [Session.from_dict(d) for d in json.loads(QgsSettings().value(RECENT, '[]'))]
    except (ValueError, TypeError):
        return []


def remember_session(session, keep=10):
    import json
    items = [s for s in recent_sessions() if s.to_dict() != session.to_dict()]
    items.insert(0, session)
    QgsSettings().setValue(RECENT, json.dumps([s.to_dict() for s in items[:keep]]))


class SessionDialog(QDialog):
    def __init__(self, default_name, default_folder, parent=None, current=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(T('Sessione di import'))
        self.setWindowIcon(icon('session'))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        intro = QLabel(T("Dai un nome a questo import e scegli dove salvare i file. I prodotti scaricati, il "
                         "GeoPackage delle foto e il gruppo nel pannello Livelli useranno questo nome."))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.recent = QComboBox()
        self.recent.addItem(T('(nuova sessione)'), None)
        for s in recent_sessions():
            self.recent.addItem('%s  -  %s' % (s.name, s.folder), s.to_dict())
        self.recent.currentIndexChanged.connect(self._pick_recent)
        form.addRow(T('Sessioni recenti'), self.recent)
        self.name = QLineEdit(current.name if current and current.name else default_name)
        self.name.textChanged.connect(self._update)
        form.addRow(T('Nome della sessione'), self.name)
        self.folder = QgsFileWidget()
        self.folder.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)
        self.folder.setDialogTitle(T('Cartella in cui salvare la sessione'))
        self.folder.setFilePath(current.folder if current and current.folder else default_folder)
        self.folder.fileChanged.connect(self._update)
        form.addRow(T('Cartella'), self.folder)
        lay.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.info)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self._update()

    def _pick_recent(self, _i):
        d = self.recent.currentData()
        if d:
            self.name.setText(d['name'])
            self.folder.setFilePath(d['folder'])

    def session(self):
        return Session(self.name.text().strip(), self.folder.filePath().strip())

    def _update(self, *_):
        s = self.session()
        ok = s.valid()
        if ok:
            root = s.root
            exists = os.path.isdir(root)
            msg = T('I file andranno in:') + '\n' + root
            if exists:
                msg += '\n' + T("La cartella esiste gia': i nuovi file si aggiungono a quelli presenti.")
            if dirname_of(s.name) != s.name.strip():
                msg += '\n' + T('Il nome della cartella sara\' adattato: {n}', n=dirname_of(s.name))
        else:
            msg = T('Indica un nome e una cartella.')
        self.info.setText(msg)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    def accept(self):
        s = self.session()
        try:
            os.makedirs(s.root, exist_ok=True)
        except OSError as e:
            self.info.setText(T('Impossibile creare la cartella: {e}', e=e))
            return
        remember_session(s)
        QDialog.accept(self)
