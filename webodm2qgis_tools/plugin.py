"""Plugin QGIS: menu WebODM, barra degli strumenti, pannelli e strumento Foto."""
import os

from qgis.core import QgsApplication, QgsProject, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import QDialog, QMenu, QMessageBox

from . import i18n, runtime
from .controller import Controller
from .core import session as sess_mod
from .i18n import T
from .loaders import layers, shots_points
from .ui.dock import MainDock
from .ui.hooks import QtHooks
from .ui.icons import icon
from .ui.photo_panel import PhotoPanel
from .ui.photo_tool import PhotoTool
from .ui.server_dialog import ServerDialog
from .ui.session_dialog import SessionDialog
from .ui.task_picker import TaskPicker
from .ui.web_viewer import WebViewerDock

def _read_version():
    """La versione sta solo in metadata.txt (la incrementa qgis_dev.py)."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'metadata.txt'), encoding='utf-8') as f:
            for line in f:
                if line.startswith('version='):
                    return line.split('=', 1)[1].strip()
    except OSError:
        pass
    return '?'


VERSION = _read_version()
TITLE = 'WebODM2QGIS-tools'


def _guess_language():
    from .ui.about_dialog import chosen_language
    chosen = chosen_language()
    if chosen != 'auto':
        return chosen
    s = QgsSettings()
    if s.value('locale/overrideFlag', False, type=bool):
        return s.value('locale/userLocale', 'en')
    try:
        return QgsApplication.locale() or 'en'
    except Exception:
        return 'en'


class WebODM2QGISPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = None
        self.toolbar = None
        self.ctl = None
        self.dock = None
        self.photo_panel = None
        self.viewer = None
        self.photo_tool = None

    # --- ciclo di vita -------------------------------------------------------------------------
    def initGui(self):
        i18n.set_language(_guess_language())
        win = self.iface.mainWindow()
        canvas = self.iface.mapCanvas()
        self.ctl = Controller(QtHooks(self.iface))
        runtime.controller = self.ctl

        self.dock = MainDock(self.ctl, canvas, win)
        self.iface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)
        self.photo_panel = PhotoPanel(self.ctl, canvas, win)
        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.photo_panel)
        self.photo_panel.hide()
        self.viewer = WebViewerDock(self.ctl, win)
        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.viewer)
        self.viewer.hide()
        self.photo_tool = PhotoTool(canvas, self.ctl)

        self.dock.serverDialogRequested.connect(self.server_dialog)
        self.dock.sessionDialogRequested.connect(self.session_dialog)
        self.dock.pickerRequested.connect(self.pick_task)
        self.dock.viewerRequested.connect(self.open_viewer)
        self.dock.helpRequested.connect(self.help)
        self.dock.aboutRequested.connect(self.about)

        self._build_actions()
        self.ctl.productsChanged.connect(self._update_actions)
        self.ctl.connectionChanged.connect(lambda *_: self._update_actions())
        QgsProject.instance().writeProject.connect(self._on_write)
        QgsProject.instance().readProject.connect(self._on_read)
        QgsProject.instance().cleared.connect(self._on_clear)
        self._update_actions()
        self._on_read()

    def unload(self):
        try:
            QgsProject.instance().writeProject.disconnect(self._on_write)
            QgsProject.instance().readProject.disconnect(self._on_read)
            QgsProject.instance().cleared.disconnect(self._on_clear)
        except TypeError:
            pass
        runtime.controller = None
        if self.iface.mapCanvas().mapTool() is self.photo_tool:
            self.iface.mapCanvas().unsetMapTool(self.photo_tool)
        for a in self.actions:
            self.iface.removePluginMenu('&' + TITLE, a)
        if self.menu is not None:
            self.menu.deleteLater()
        if self.toolbar is not None:
            self.toolbar.deleteLater()
        for d in (self.dock, self.photo_panel, self.viewer):
            if d is not None:
                self.iface.removeDockWidget(d)
                d.deleteLater()
        if self.ctl is not None:
            self.ctl.cancel()
            self.ctl.deleteLater()
        self.actions = []

    # --- azioni, menu, barra -------------------------------------------------------------------
    def _act(self, name, text, slot, ic, tip='', checkable=False):
        a = QAction(icon(ic), text, self.iface.mainWindow())
        a.setObjectName('w2q_' + name)
        a.setToolTip(tip or text)
        a.setStatusTip(tip or text)
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        self.actions.append(a)
        setattr(self, 'act_' + name, a)
        return a

    def _build_actions(self):
        win = self.iface.mainWindow()
        self.toolbar = self.iface.addToolBar('WebODM')
        self.toolbar.setObjectName('WebODM2QGISToolbar')
        self.menu = QMenu('&WebODM', win)
        self.menu.setObjectName('WebODM2QGISMenu')
        # menu di primo livello, prima di "Aiuto"
        mb = win.menuBar()
        help_menu = self.iface.helpMenu()
        mb.insertMenu(help_menu.menuAction(), self.menu)

        plan = [
            ('connect', T('Collega a WebODM...'), self.server_dialog, 'connect', '', False, True, True),
            ('pick', T('Scegli progetto e task...'), self.pick_task, 'task', T('Scegli il progetto e il task di WebODM'), False, True, True),
            ('session', T('Sessione di import...'), self.session_dialog, 'session',
             T("Nome e cartella dell'import"), False, True, False),
            ('refresh', T('Aggiorna elenco'), self.refresh, 'refresh', '', False, True, True),
            None,
            ('panel', T('Pannello WebODM'), self.toggle_panel, 'panel', '', True, True, True),
            ('ortho', T('Carica ortofoto'), lambda: self.quick(('orthophoto.tif',)), 'ortho', '', False, True, True),
            ('cloud', T('Carica nuvola di punti'), lambda: self.quick(('georeferenced_model.laz', 'georeferenced_model.las')),
             'cloud', '', False, True, True),
            ('photos', T('Punti di scatto delle foto'), lambda: self.quick(('shots.geojson',)), 'photos',
             T('Importa la posizione di ogni foto'), False, True, True),
            ('phototool', T('Strumento Foto'), self.toggle_photo_tool, 'photo_tool',
             T('Clic su un punto di scatto: mostra la foto. Doppio clic: apre l\'originale'), True, True, True),
            ('shots', T('Scatti e prospetti'), self.show_shots, 'shots', '', False, True, True),
            None,
            ('viewer', T('Visualizzatore WebODM'), lambda: self.open_viewer('3d'), 'viewer', '', False, True, True),
            ('crsrep', T('Verifica CRS del progetto'), self.crs_report, 'crs', '', False, True, False),
            None,
            ('help', T('Guida'), self.help, 'help', '', False, True, False),
            ('about', T('Informazioni'), self.about, 'help', '', False, True, False),
        ]
        for p in plan:
            if p is None:
                self.menu.addSeparator()
                continue
            name, text, slot, ic, tip, checkable, in_menu, in_bar = p
            a = self._act(name, text, slot, ic, tip, checkable)
            self.menu.addAction(a)
            self.iface.addPluginToMenu('&' + TITLE, a)
            if in_bar:
                self.toolbar.addAction(a)
        self.act_panel.setChecked(True)
        self.dock.visibilityChanged.connect(self.act_panel.setChecked)
        self.photo_tool.setAction(self.act_phototool)

    def _update_actions(self):
        t = self.ctl.task
        have = {p.key for p in self.ctl.products}
        ok = t is not None and t.completed
        self.act_pick.setEnabled(self.ctl.client is not None)
        self.act_refresh.setEnabled(self.ctl.client is not None)
        self.act_ortho.setEnabled(ok and 'orthophoto.tif' in have)
        self.act_cloud.setEnabled(ok and bool(have & {'georeferenced_model.laz', 'georeferenced_model.las'}))
        self.act_photos.setEnabled(ok and 'shots.geojson' in have)
        self.act_shots.setEnabled(ok and any(p.kind == 'shot' for p in self.ctl.products))
        self.act_viewer.setEnabled(self.ctl.client is not None)

    # --- comandi -------------------------------------------------------------------------------
    def server_dialog(self):
        dlg = ServerDialog(self.ctl, self.iface.mainWindow())
        dlg.connectRequested.connect(lambda s, pw: self.ctl.connect_server(s, pw))
        dlg.exec()

    def session_dialog(self):
        dlg = SessionDialog(sess_mod.default_name(self.ctl.task.label if self.ctl.task else ''),
                            self.ctl.last_session_folder(), self.iface.mainWindow(), self.ctl.session)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.ctl.set_session(dlg.session())

    def pick_task(self):
        if self.ctl.client is None:
            self.server_dialog()
            return
        dlg = TaskPicker(self.ctl, self.iface.mainWindow())
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chosen() is not None:
            self.dock.select_task_in_ui(dlg.chosen())
            self.dock.show()

    def refresh(self):
        if self.ctl.client is not None:
            self.ctl.load_projects()
            if self.ctl.selection.project_id is not None:
                self.ctl.select_project(self.ctl.selection.project_id)

    def toggle_panel(self, on):
        self.dock.setVisible(on)

    def quick(self, keys):
        for p in self.ctl.products:
            if p.key in keys:
                self.ctl.load_products([p])
                return

    def toggle_photo_tool(self, on):
        canvas = self.iface.mapCanvas()
        if on:
            canvas.setMapTool(self.photo_tool)
            self.photo_panel.show()
        elif canvas.mapTool() is self.photo_tool:
            canvas.unsetMapTool(self.photo_tool)

    def show_shots(self):
        self.dock.show()
        self.dock.tabs.setCurrentWidget(self.dock.shots)

    def open_viewer(self, kind='3d'):
        if self.ctl.client is None:
            self.server_dialog()
            return
        self.viewer.go(kind)

    def crs_report(self):
        proj = QgsProject.instance()
        lines = [T('CRS del progetto: {c}', c=proj.crs().authid() or T('(non impostato)')) + '  ' + proj.crs().description(), '']
        for lyr in proj.mapLayers().values():
            c = lyr.crs()
            tag = ''
            if c == layers.local_crs():
                tag = T('CRS LOCALE (prospetto): non sovrapporre alla mappa')
            elif not c.isValid():
                tag = T('SENZA CRS')
            elif c.isGeographic():
                tag = T('in gradi')
            if tag or c.authid() != proj.crs().authid():
                lines.append('%s: %s %s' % (lyr.name(), c.authid() or '-', tag))
        if len(lines) == 2:
            lines.append(T('Tutti i layer sono nel CRS del progetto.'))
        QMessageBox.information(self.iface.mainWindow(), T('Verifica CRS del progetto'), '\n'.join(lines))

    def help(self):
        from .ui.about_dialog import open_guide
        if not open_guide():
            QMessageBox.warning(self.iface.mainWindow(), TITLE, T('Guida non trovata'))

    def about(self):
        from .ui.about_dialog import AboutDialog
        AboutDialog(VERSION, self.iface.mainWindow()).exec()

    # --- progetto QGIS -------------------------------------------------------------------------
    def _on_write(self, *_):
        self.ctl.save_to_project()

    def _on_read(self, *_):
        sel = self.ctl.restore_from_project()
        if sel.server_url:
            self.dock.status.setText(T('Progetto collegato a {u}: premi Collega per riprendere.', u=sel.server_url))
            i = self.dock.servers.findText(sel.server_url, Qt.MatchFlag.MatchContains)
            if i >= 0:
                self.dock.servers.setCurrentIndex(i)

    def _on_clear(self, *_):
        if self.ctl.session.valid():
            self.ctl.set_session(sess_mod.Session())
