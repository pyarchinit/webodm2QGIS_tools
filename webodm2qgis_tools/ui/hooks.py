"""Le domande all'utente del controller, realizzate con finestre di QGIS."""
from qgis.core import Qgis
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QDialog, QMessageBox

from ..controller import Decision, UiHooks
from ..i18n import T
from .crs_dialog import CrsDialog
from .qt_helpers import ask_yes_no
from .session_dialog import SessionDialog
from .shot_viewer import ShotViewer

_LEVELS = {'info': Qgis.MessageLevel.Info, 'warn': Qgis.MessageLevel.Warning, 'crit': Qgis.MessageLevel.Critical,
           'success': Qgis.MessageLevel.Success}


class QtHooks(UiHooks):
    def __init__(self, iface):
        self.iface = iface
        self._viewers = []

    def ask_session(self, default_name, default_folder):
        from ..core.session import Session
        dlg = SessionDialog(default_name, default_folder, self.iface.mainWindow())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.session()
        return None

    def ask_crs(self, product, alerts, file_crs, project_crs, can_assign):
        dlg = CrsDialog(product, alerts, file_crs, project_crs, can_assign, self.iface.mainWindow())
        dlg.exec()
        return dlg.decision()

    def confirm(self, text):
        return ask_yes_no(self.iface.mainWindow(), 'WebODM2QGIS-tools', text)

    def message(self, level, text):
        self.iface.messageBar().pushMessage('WebODM', text, _LEVELS.get(level, Qgis.MessageLevel.Info),
                                            12 if level in ('info', 'success') else 0)

    def open_file(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def show_shot(self, layer, product):
        v = ShotViewer(layer, product, self.iface.mainWindow())
        self._viewers.append(v)
        v.destroyed.connect(lambda *_: self._viewers.remove(v) if v in self._viewers else None)
        v.show()
