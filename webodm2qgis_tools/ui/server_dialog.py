"""Gestione dei server WebODM salvati e collegamento."""
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                                 QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)

from ..core.models import Server
from ..core.urls import normalize_base_url, plain_http_remote
from ..i18n import T
from ..net import auth
from ..net.client import WebODMClient
from .icons import icon


class ServerDialog(QDialog):
    connectRequested = pyqtSignal(object, str)      # Server, password

    def __init__(self, controller, parent=None):
        QDialog.__init__(self, parent)
        self.ctl = controller
        self.setWindowTitle(T('Server WebODM'))
        self.setWindowIcon(icon('connect'))
        self.setMinimumWidth(640)
        outer = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._pick)
        left.addWidget(QLabel(T('Server salvati')))
        left.addWidget(self.list)
        new = QPushButton(T('Nuovo'))
        new.clicked.connect(self._new)
        left.addWidget(new)
        outer.addLayout(left, 1)

        right = QVBoxLayout()
        form = QFormLayout()
        self.name = QLineEdit()
        self.url = QLineEdit()
        self.url.setPlaceholderText('http://localhost:29800')
        self.url.textChanged.connect(self._warn)
        self.user = QLineEdit()
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember = QCheckBox(T("Salva la password nel gestore di autenticazione di QGIS"))
        self.remember.setChecked(auth.available())
        self.remember.setEnabled(auth.available())
        form.addRow(T('Nome'), self.name)
        form.addRow(T('Indirizzo'), self.url)
        form.addRow(T('Utente'), self.user)
        form.addRow(T('Password'), self.pw)
        right.addLayout(form)
        right.addWidget(self.remember)
        self.note = QLabel()
        self.note.setWordWrap(True)
        right.addWidget(self.note)
        row = QHBoxLayout()
        local = QPushButton(T('WebODM locale'))
        local.setToolTip(T('Compila con http://127.0.0.1:29800 (app WebODM per Windows) e controlla che sia acceso'))
        local.clicked.connect(self._local)
        row.addWidget(local)
        row.addStretch(1)
        self.delete_btn = QPushButton(T('Elimina'))
        self.delete_btn.clicked.connect(self._delete)
        row.addWidget(self.delete_btn)
        self.connect_btn = QPushButton(icon('connect'), T('Salva e collega'))
        self.connect_btn.setDefault(True)
        self.connect_btn.clicked.connect(self._connect)
        row.addWidget(self.connect_btn)
        right.addLayout(row)
        right.addStretch(1)
        outer.addLayout(right, 2)
        self._fill()
        self._warn()

    def _fill(self, select=None):
        self.list.clear()
        for s in self.ctl.servers():
            it = QListWidgetItem('%s  (%s)' % (s.name or s.url, s.url))
            it.setData(Qt.ItemDataRole.UserRole, s)
            self.list.addItem(it)
            if select and s.url == select:
                self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)

    def _pick(self, item, _prev=None):
        if item is None:
            return
        s = item.data(Qt.ItemDataRole.UserRole)
        self.name.setText(s.name)
        self.url.setText(s.url)
        self.user.setText(s.user)
        self.pw.setText('')
        self.pw.setPlaceholderText(T('(salvata)') if s.authcfg else '')

    def _new(self):
        self.list.clearSelection()
        self.list.setCurrentItem(None)
        for w in (self.name, self.url, self.user, self.pw):
            w.setText('')

    def _local(self):
        """App WebODM per Windows: web server su 127.0.0.1:29800 (solo questo PC). Controlla se e' acceso."""
        self.name.setText(self.name.text() or T('WebODM locale'))
        self.url.setText('http://127.0.0.1:29800')
        if not self.user.text():
            self.user.setText('admin')
        self.note.setText(T('Cerco WebODM su 127.0.0.1:29800...'))
        client = WebODMClient('http://127.0.0.1:29800', None, self)

        def got(_data, err):
            if err is not None and err.kind == 'network':
                self.note.setText("<span style='color:#c92a2a'>%s</span>" % T(
                    "WebODM non risponde su 127.0.0.1:29800: apri l'app WebODM e attendi che finisca di avviarsi."))
            else:
                self.note.setText("<span style='color:#2f9e44'>%s</span> %s" % (
                    T('WebODM acceso e raggiungibile.'),
                    T("Inserisci utente e password con cui accedi all'app (predefiniti dell'app: admin / admin, "
                      "da cambiare).")))
        client.get_json('/api/', got)

    def _warn(self, *_):
        t = self.url.text().strip()
        msg = ''
        try:
            if t and plain_http_remote(normalize_base_url(t)):
                msg = ("<span style='color:#c92a2a'>%s</span>" %
                       T("Attenzione: indirizzo remoto senza HTTPS, la password viaggerebbe in chiaro."))
        except ValueError:
            pass
        self.note.setText(msg)

    def _server(self):
        url = normalize_base_url(self.url.text())
        old = next((s for s in self.ctl.servers() if s.url == url), None)
        return Server(name=self.name.text().strip() or url, url=url, user=self.user.text().strip(),
                      authcfg=old.authcfg if old else '')

    def _connect(self):
        try:
            server = self._server()
        except ValueError as e:
            QMessageBox.warning(self, T('Server WebODM'), T('Indirizzo non valido: {e}', e=e))
            return
        if not server.user:
            QMessageBox.warning(self, T('Server WebODM'), T('Indica l\'utente.'))
            return
        pw = self.pw.text()
        server = self.ctl.save_server(server, pw, self.remember.isChecked())
        self.connectRequested.emit(server, pw)
        self.accept()

    def _delete(self):
        item = self.list.currentItem()
        if item is None:
            return
        s = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, T('Server WebODM'), T('Eliminare {n}?', n=s.name or s.url)) == \
                QMessageBox.StandardButton.Yes:
            self.ctl.remove_server(s.url)
            self._fill()
            if not self.list.count():
                self._new()
