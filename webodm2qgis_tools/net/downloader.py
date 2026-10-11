"""Download in streaming su file (non in memoria), con avanzamento, annullo e ripresa.

Il file arriva in `<nome>.part` e viene rinominato solo a download completo: un file parziale non puo'
essere scambiato per un prodotto valido. Se esiste gia' un .part si chiede al server di riprendere
(Range); se il server risponde 200 invece di 206 si riparte da zero.
"""
import os

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from ..i18n import T
from .client import ApiError, classify, _status


class Download(QObject):
    progress = pyqtSignal(int, int)             # byte scaricati, totali (0 se ignoti)
    finished = pyqtSignal(bool, str)            # ok, percorso del file oppure messaggio d'errore

    def __init__(self, client, path, dest, parent=None):
        QObject.__init__(self, parent)
        self.client = client
        self.path = path
        self.dest = dest
        self.part = dest + '.part'
        self._reply = None
        self._fh = None
        self._offset = 0
        self._cancelled = False
        self._retried = False

    def start(self):
        os.makedirs(os.path.dirname(self.dest), exist_ok=True)
        if self.client.token is None and self.client._creds and self.client._creds():
            self.client.login(lambda _t, err: self._fail(err) if err else self._begin())
        else:
            self._begin()

    def cancel(self):
        self._cancelled = True
        if self._reply is not None:
            self._reply.abort()

    # ---------------------------------------------------------------------------------------------
    def _begin(self):
        self._offset = os.path.getsize(self.part) if os.path.isfile(self.part) else 0
        req = self.client.make_request(self.path)
        if self._offset > 0:
            req.setRawHeader(b'Range', ('bytes=%d-' % self._offset).encode('ascii'))
        self._reply = self.client.nam().get(req)
        self._fh = None
        self._reply.readyRead.connect(self._on_data)
        self._reply.downloadProgress.connect(self._on_progress)
        self._reply.finished.connect(self._on_done)

    def _open(self):
        if self._fh is None:
            st = _status(self._reply)
            if st == 206 and self._offset > 0:
                self._fh = open(self.part, 'ab')
            else:
                self._offset = 0
                self._fh = open(self.part, 'wb')
        return self._fh

    def _on_data(self):
        st = _status(self._reply)
        if not 200 <= st < 300:
            return                              # il corpo di un errore non e' il file
        try:
            self._open().write(bytes(self._reply.readAll()))
        except OSError as e:
            self._reply.abort()
            self._fail(ApiError('network', T('Impossibile scrivere il file: {e}', e=e)))

    def _on_progress(self, got, total):
        self.progress.emit(int(got) + self._offset, int(total) + self._offset if total > 0 else 0)

    def _close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def _on_done(self):
        reply = self._reply
        self._close()
        if self._cancelled:
            reply.deleteLater()
            self.finished.emit(False, T('Download annullato'))
            return
        err = classify(reply)
        st = _status(reply)
        if st == 416 and os.path.isfile(self.part):      # .part gia' completo o disallineato: riparti da zero
            reply.deleteLater()
            if not self._retried:
                self._retried = True
                os.remove(self.part)
                self._begin()
                return
        if err is not None and err.kind == 'auth' and not self._retried and self.client._creds:
            self._retried = True
            reply.deleteLater()
            self.client.token = None
            self.client.login(lambda _t, e: self._fail(e) if e else self._begin())
            return
        reply.deleteLater()
        if err is not None:
            self._fail(err)
            return
        try:
            if os.path.isfile(self.dest):
                os.remove(self.dest)
            if not os.path.isfile(self.part):           # risposta vuota
                open(self.part, 'wb').close()
            os.replace(self.part, self.dest)
        except OSError as e:
            self._fail(ApiError('network', T('Impossibile salvare il file: {e}', e=e)))
            return
        self.finished.emit(True, self.dest)

    def _fail(self, err):
        self.finished.emit(False, str(err))
