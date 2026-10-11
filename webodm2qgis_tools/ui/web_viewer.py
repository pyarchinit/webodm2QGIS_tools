"""Visualizzatore WebODM dentro QGIS (3D Potree, mappa 2D, dashboard) con QtWebEngine.

Se QtWebEngine non e' disponibile nella tua installazione di QGIS il pulsante apre il browser di sistema.
Il login e' automatico: se WebODM mostra la sua pagina di accesso, i campi si compilano con le credenziali del
server (da QgsAuthManager o dalla sessione) e si invia una sola volta.
"""
import json
import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QComboBox, QDockWidget, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ..core.urls import web_url
from ..i18n import T
from .icons import icon

_webengine = None


def webengine():
    """(QWebEngineView, QWebEngineProfile, QWebEnginePage) oppure None se non disponibile."""
    global _webengine
    if _webengine is None:
        try:
            from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
            from qgis.PyQt.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
            _webengine = (QWebEngineView, QWebEngineProfile, QWebEnginePage)
        except Exception:
            _webengine = False
    return _webengine or None


class WebViewerDock(QDockWidget):
    def __init__(self, controller, parent=None):
        QDockWidget.__init__(self, T('WebODM - Visualizzatore'), parent)
        self.setObjectName('WebODM2QGISViewerDock')
        self.ctl = controller
        self._view = None
        self._login_tried = False
        body = QWidget()
        self.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItem(T('Vista 3D'), '3d')
        self.kind.addItem(T('Mappa 2D'), 'map')
        self.kind.addItem(T('Dashboard'), 'dashboard')
        self.kind.activated.connect(lambda *_: self.go())
        row.addWidget(self.kind)
        self.btns = {}
        for name, ic, tip in (('reload', 'refresh', T('Ricarica')),
                              ('browser', 'open', T('Apri nel browser di sistema'))):
            b = QToolButton()
            b.setIcon(icon(ic))
            b.setToolTip(tip)
            row.addWidget(b)
            self.btns[name] = b
        row.addStretch(1)
        lay.addLayout(row)
        self.note = QLabel()
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        self.holder = QVBoxLayout()
        lay.addLayout(self.holder, 1)
        self.btns['browser'].clicked.connect(self.open_external)
        self.btns['reload'].clicked.connect(lambda: self._view.reload() if self._view else None)

    def url(self):
        t = self.ctl.task
        if self.ctl.client is None:
            return None
        k = self.kind.currentData()
        if k == 'dashboard' or t is None:
            return self.ctl.client.base + '/dashboard/'
        return web_url(self.ctl.client.base, k, t.project_id, t.id)

    def open_external(self):
        u = self.url()
        if u:
            QDesktopServices.openUrl(QUrl(u))

    def _ensure_view(self):
        if self._view is not None:
            return True
        we = webengine()
        if we is None:
            self.note.setText(T("QtWebEngine non e' disponibile in questa installazione di QGIS: si apre il "
                                "browser di sistema."))
            return False
        View, Profile, Page = we
        store = os.path.join(QgsApplication.qgisSettingsDirPath(), 'webodm2qgis_web')
        os.makedirs(store, exist_ok=True)
        self._profile = Profile('webodm2qgis', self)
        self._profile.setPersistentStoragePath(store)
        self._profile.setCachePath(os.path.join(store, 'cache'))
        self._page = Page(self._profile, self)
        self._view = View(self)
        self._view.setPage(self._page)
        self._view.loadFinished.connect(self._loaded)
        self.holder.addWidget(self._view)
        return True

    def go(self, kind=None):
        if kind:
            i = self.kind.findData(kind)
            if i >= 0:
                self.kind.setCurrentIndex(i)
        u = self.url()
        if not u:
            self.note.setText(T('Collegati a un server WebODM.'))
            return
        self.show()
        self.raise_()
        if not self._ensure_view():
            self.open_external()
            return
        self.note.setText('')
        self._login_tried = False
        self._view.setUrl(QUrl(u))

    def _loaded(self, ok):
        if not ok or self._view is None:
            return
        path = self._view.url().path()
        if not path.startswith('/login'):
            self._login_tried = False
            return
        if self._login_tried or self.ctl.server is None:
            return
        creds = self.ctl._creds_for(self.ctl.server)()
        if not creds:
            return
        self._login_tried = True            # una volta sola: se le credenziali sono sbagliate non si insiste
        js = ("(function(){var u=document.querySelector('input[name=username]'),p=document.querySelector('input[name=password]');"
              "if(!u||!p)return;u.value=%s;p.value=%s;var f=u.form;if(f)f.submit();})();" %
              (json.dumps(creds[0]), json.dumps(creds[1])))
        self._page.runJavaScript(js)
