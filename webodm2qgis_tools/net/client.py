"""Client di sola lettura per l'API REST di WebODM, asincrono (non blocca l'interfaccia).

Usa QgsNetworkAccessManager: rispetta proxy, certificati e impostazioni di rete di QGIS.
Ogni chiamata prende una callback `cb(result, error)`: `error` e' un ApiError oppure None.
"""
import json
from urllib.parse import urlencode

from qgis.core import QgsNetworkAccessManager
from qgis.PyQt.QtCore import QObject, QByteArray, QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from ..core.urls import normalize_base_url
from ..i18n import T

TIMEOUT_MS = 30000


class ApiError(Exception):
    """kind: network | auth | notfound | forbidden | server | badjson | cancelled"""

    def __init__(self, kind, message, status=0):
        Exception.__init__(self, message)
        self.kind = kind
        self.status = status

    def __str__(self):
        return self.args[0]


def _status(reply):
    v = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    return int(v) if v is not None else 0


def classify(reply):
    """ApiError per una risposta fallita (None se e' andata bene)."""
    st = _status(reply)
    err = reply.error()
    if err == QNetworkReply.NetworkError.NoError and 200 <= st < 300:
        return None
    if err == QNetworkReply.NetworkError.OperationCanceledError:
        return ApiError('cancelled', T('Operazione annullata'))
    if st == 401:
        return ApiError('auth', T('Credenziali non valide o sessione scaduta'), st)
    if st == 403:
        return ApiError('forbidden', T('Permesso negato dal server'), st)
    if st == 404:
        return ApiError('notfound', T('Non trovato sul server'), st)
    if st >= 500:
        return ApiError('server', T('Errore del server WebODM ({st})', st=st), st)
    if st:
        return ApiError('server', T('Risposta inattesa dal server ({st})', st=st), st)
    return ApiError('network', T('Server non raggiungibile: {e}', e=reply.errorString()))


class WebODMClient(QObject):
    """`creds` e' una funzione () -> (utente, password) oppure None."""

    def __init__(self, base_url, creds=None, parent=None):
        QObject.__init__(self, parent)
        self.base = normalize_base_url(base_url)
        self._creds = creds
        self.token = None
        self._replies = set()

    # --- richieste -----------------------------------------------------------------------------
    def url(self, path, query=None):
        u = self.base + path
        if query:
            u += '?' + urlencode(query)
        return u

    def make_request(self, path, query=None, accept=None):
        req = QNetworkRequest(QUrl(self.url(path, query)))
        req.setTransferTimeout(TIMEOUT_MS)
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        if self.token:
            req.setRawHeader(b'Authorization', ('JWT ' + self.token).encode('ascii'))
        if accept:
            req.setRawHeader(b'Accept', accept.encode('ascii'))
        return req

    def _track(self, reply):
        self._replies.add(reply)
        reply.finished.connect(lambda r=reply: self._replies.discard(r))
        return reply

    def abort_all(self):
        for r in list(self._replies):
            r.abort()

    def nam(self):
        return QgsNetworkAccessManager.instance()

    # --- accesso -------------------------------------------------------------------------------
    def login(self, cb):
        """Ottiene il token JWT con utente e password (POST /api/token-auth/)."""
        creds = self._creds() if self._creds else None
        if not creds or not creds[0]:
            cb(None, ApiError('auth', T('Utente e password mancanti')))
            return
        req = self.make_request('/api/token-auth/')
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, 'application/json')
        body = QByteArray(json.dumps({'username': creds[0], 'password': creds[1]}).encode('utf-8'))
        reply = self._track(self.nam().post(req, body))

        def done():
            err = classify(reply)
            data = None
            if err is None:
                try:
                    data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                    self.token = data['token']
                except (ValueError, KeyError, TypeError):
                    err = ApiError('badjson', T('Risposta di accesso non valida: e\' davvero un server WebODM?'))
            elif err.kind == 'server' and err.status == 400:
                err = ApiError('auth', T('Utente o password errati'), 400)
            reply.deleteLater()
            cb(self.token if err is None else None, err)
        reply.finished.connect(done)

    def _with_login(self, start, cb):
        """Esegue start(cb2); se risponde 401 rifa' il login una volta e riprova."""
        def first(result, err):
            if err is not None and err.kind == 'auth' and self._creds and self._creds():
                self.token = None

                def after_login(_tok, lerr):
                    if lerr is not None:
                        cb(None, lerr)
                    else:
                        start(cb)
                self.login(after_login)
            else:
                cb(result, err)
        if self.token is None and self._creds and self._creds():
            def logged(_tok, lerr):
                if lerr is not None:
                    cb(None, lerr)
                else:
                    start(first)
            self.login(logged)
        else:
            start(first)

    # --- letture -------------------------------------------------------------------------------
    def get_json(self, path, cb, query=None):
        def start(cb2):
            reply = self._track(self.nam().get(self.make_request(path, query, 'application/json')))

            def done():
                err = classify(reply)
                data = None
                if err is None:
                    try:
                        data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                    except ValueError:
                        err = ApiError('badjson', T('Risposta non valida dal server'))
                reply.deleteLater()
                cb2(data, err)
            reply.finished.connect(done)
        self._with_login(start, cb)

    def get_bytes(self, path, cb, query=None):
        def start(cb2):
            reply = self._track(self.nam().get(self.make_request(path, query)))

            def done():
                err = classify(reply)
                data = bytes(reply.readAll()) if err is None else None
                reply.deleteLater()
                cb2(data, err)
            reply.finished.connect(done)
        self._with_login(start, cb)

    def probe(self, path, cb):
        """Il file c'e'? `cb({'size': int|None}, err)`. Legge solo le intestazioni (poi interrompe),
        quindi funziona anche se il server non accetta HEAD e non scarica foto da decine di MB."""
        def start(cb2):
            reply = self._track(self.nam().get(self.make_request(path)))
            state = {'sent': False}

            def headers():
                if state['sent'] or _status(reply) == 0:
                    return
                state['sent'] = True
                st = _status(reply)
                length = reply.header(QNetworkRequest.KnownHeaders.ContentLengthHeader)
                size = int(length) if length is not None else None
                err = None
                if st == 404:
                    err = ApiError('notfound', T('Non trovato sul server'), 404)
                elif st == 401:
                    err = ApiError('auth', T('Credenziali non valide o sessione scaduta'), 401)
                elif st == 403:
                    err = ApiError('forbidden', T('Permesso negato dal server'), 403)
                elif not 200 <= st < 300:
                    err = ApiError('server', T('Risposta inattesa dal server ({st})', st=st), st)
                reply.abort()
                cb2({'size': size} if err is None else None, err)
            reply.metaDataChanged.connect(headers)

            def done():
                if not state['sent']:                 # chiusa senza intestazioni: errore di rete
                    state['sent'] = True
                    cb2(None, classify(reply) or ApiError('network', T('Server non raggiungibile')))
                reply.deleteLater()
            reply.finished.connect(done)
        self._with_login(start, cb)


def as_list(data):
    """WebODM risponde con una lista oppure, se paginato, con {'results': [...]}."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('results'), list):
        return data['results']
    return []
