"""Pannello principale: server, sessione di import, progetto/task, prodotti, scatti."""
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QGuiApplication
from qgis.PyQt.QtWidgets import (QComboBox, QCompleter, QDockWidget, QHBoxLayout, QLabel, QMenu, QMessageBox,
                                 QProgressBar, QPushButton, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem,
                                 QVBoxLayout, QWidget, QAbstractItemView)

from ..core import catalog, crs_guard
from ..core.models import status_label
from ..i18n import T
from .icons import icon, light
from .shots_panel import ShotsPanel


class MainDock(QDockWidget):
    serverDialogRequested = pyqtSignal()
    sessionDialogRequested = pyqtSignal()
    pickerRequested = pyqtSignal()
    viewerRequested = pyqtSignal(str)
    helpRequested = pyqtSignal()
    aboutRequested = pyqtSignal()

    def __init__(self, controller, canvas=None, parent=None):
        QDockWidget.__init__(self, T('WebODM'), parent)
        self.setObjectName('WebODM2QGISDock')
        self.ctl = controller
        body = QWidget()
        self.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 6, 6, 6)

        # server
        row = QHBoxLayout()
        self.servers = QComboBox()
        self.servers.setToolTip(T('Server WebODM'))
        row.addWidget(self.servers, 1)
        self.connect_btn = QPushButton(icon('connect'), T('Collega'))
        self.connect_btn.clicked.connect(self._connect)
        row.addWidget(self.connect_btn)
        edit = QToolButton()
        edit.setIcon(icon('folder'))
        edit.setText('...')
        edit.setToolTip(T('Gestisci i server...'))
        edit.clicked.connect(self.serverDialogRequested)
        row.addWidget(edit)
        lay.addLayout(row)
        self.status = QLabel(T('Non collegato'))
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        # sessione di import
        srow = QHBoxLayout()
        srow.addWidget(QLabel('<b>%s</b>' % T('Sessione:')))
        self.session_lab = QLabel()
        self.session_lab.setWordWrap(True)
        srow.addWidget(self.session_lab, 1)
        sbtn = QPushButton(icon('session'), T('Sessione...'))
        sbtn.setToolTip(T("Nome e cartella dell'import: i file e il gruppo dei layer useranno questo nome"))
        sbtn.clicked.connect(self.sessionDialogRequested)
        srow.addWidget(sbtn)
        lay.addLayout(srow)

        # progetto e task
        lay.addWidget(QLabel('<b>%s</b>' % T('Progetto')))
        self.project = QComboBox()
        self.project.setEditable(True)
        self.project.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        comp = QCompleter(self.project.model(), self.project)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.project.setCompleter(comp)
        self.project.activated.connect(self._project_activated)
        lay.addWidget(self.project)
        trow = QHBoxLayout()
        trow.addWidget(QLabel('<b>%s</b>' % T('Task')))
        trow.addStretch(1)
        pick = QPushButton(icon('task'), T('Scegli...'))
        pick.setToolTip(T('Finestra con ricerca, stato e anteprima'))
        pick.clicked.connect(self.pickerRequested)
        trow.addWidget(pick)
        lay.addLayout(trow)
        self.task = QComboBox()
        self.task.activated.connect(self._task_activated)
        lay.addWidget(self.task)
        self.task_info = QLabel()
        self.task_info.setWordWrap(True)
        lay.addWidget(self.task_info)

        # schede
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        prodw = QWidget()
        pl = QVBoxLayout(prodw)
        pl.setContentsMargins(0, 4, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([T('Prodotto'), T('Tipo')])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemDoubleClicked.connect(lambda *_: self._load_selected())
        self.tree.itemSelectionChanged.connect(self._sel_changed)
        pl.addWidget(self.tree, 1)
        brow = QHBoxLayout()
        self.load_btn = QPushButton(icon('download'), T('Carica nel progetto'))
        self.load_btn.clicked.connect(self._load_selected)
        brow.addWidget(self.load_btn, 1)
        refresh = QToolButton()
        refresh.setIcon(icon('refresh'))
        refresh.setToolTip(T('Aggiorna prodotti'))
        refresh.clicked.connect(lambda: self.ctl.select_task(self.ctl.selection.task_id))
        brow.addWidget(refresh)
        pl.addLayout(brow)
        self.tabs.addTab(prodw, icon('ortho'), T('Prodotti'))
        self.shots = ShotsPanel(controller, canvas)
        self.tabs.addTab(self.shots, icon('shots'), T('Scatti e prospetti'))

        # avanzamento
        prow = QHBoxLayout()
        self.bar = QProgressBar()
        self.bar.setTextVisible(True)
        self.bar.hide()
        prow.addWidget(self.bar, 1)
        self.cancel_btn = QPushButton(T('Annulla'))
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self.ctl.cancel)
        prow.addWidget(self.cancel_btn)
        lay.addLayout(prow)
        self.busy_lab = QLabel()
        lay.addWidget(self.busy_lab)

        # piede: guida, informazioni, avviso di software sperimentale
        frow = QHBoxLayout()
        guide = QPushButton(icon('help'), T('Guida'))
        guide.setToolTip(T('Apri la guida (con immagini)'))
        guide.clicked.connect(self.helpRequested)
        frow.addWidget(guide)
        about = QPushButton(T('Informazioni'))
        about.clicked.connect(self.aboutRequested)
        frow.addWidget(about)
        lay.addLayout(frow)
        warn = QLabel('<small><span style="color:#c92a2a"><b>%s</b></span> %s</small>' % (
            T('Sperimentale.'), T("Per QGIS 4, di Luca Mandolesi (Flyoveracademy.it), scritto con Claude Code. "
                                  "Puo' fare danni: leggi Informazioni.")))
        warn.setWordWrap(True)
        lay.addWidget(warn)

        c = controller
        c.serversChanged.connect(self.fill_servers)
        c.connectionChanged.connect(self._connection)
        c.projectsLoaded.connect(self._fill_projects)
        c.tasksLoaded.connect(self._fill_tasks)
        c.taskLoaded.connect(lambda t: self._update_task_info())
        c.productsChanged.connect(self._fill_products)
        c.sessionChanged.connect(self._update_session)
        c.busyChanged.connect(self._busy)
        c.progress.connect(self._progress)
        self.fill_servers()
        self._update_session()
        self._sel_changed()

    # --- server --------------------------------------------------------------------------------
    def fill_servers(self):
        cur = self.servers.currentData()
        self.servers.clear()
        for s in self.ctl.servers():
            self.servers.addItem('%s  (%s)' % (s.name or s.url, s.url), s)
        if cur:
            i = self.servers.findText(cur.url, Qt.MatchFlag.MatchContains)
            if i >= 0:
                self.servers.setCurrentIndex(i)
        if not self.servers.count():
            self.servers.addItem(T('(nessun server: premi "...")'), None)

    def _connect(self):
        s = self.servers.currentData()
        if s is None:
            self.serverDialogRequested.emit()
            return
        if not self.ctl._creds_for(s)():
            self.serverDialogRequested.emit()       # manca la password: la si chiede li'
            return
        self.ctl.connect_server(s)

    def _connection(self, ok, text):
        self.status.setText(('<span style="color:#2f9e44">&#9679;</span> ' if ok else
                             '<span style="color:#c92a2a">&#9679;</span> ') + text)

    # --- progetti e task -----------------------------------------------------------------------
    def _fill_projects(self, projects):
        self.project.blockSignals(True)
        self.project.clear()
        for p in projects:
            self.project.addItem('%s  (%d)' % (p.name, len(p.task_ids)), p.id)
        cur = self.ctl.selection.project_id
        i = self.project.findData(cur) if cur is not None else -1
        self.project.setCurrentIndex(i)
        if i < 0:
            self.project.setEditText('')
        self.project.blockSignals(False)

    def _project_activated(self, i):
        pid = self.project.itemData(i)
        if pid is not None:
            self.ctl.select_project(pid)

    def _fill_tasks(self, tasks):
        self.task.blockSignals(True)
        self.task.clear()
        for t in sorted(tasks, key=lambda x: x.created_at, reverse=True):
            self.task.addItem(light('green' if t.completed else 'grey'),
                              '%s  -  %s  -  %s' % (t.label, t.created_at[:10], status_label(t.status)), t.id)
            if not t.completed:
                self.task.model().item(self.task.count() - 1).setEnabled(False)
        i = self.task.findData(self.ctl.selection.task_id) if self.ctl.selection.task_id else -1
        self.task.setCurrentIndex(i)
        self.task.blockSignals(False)
        self._update_task_info()

    def _task_activated(self, i):
        tid = self.task.itemData(i)
        if tid:
            self.ctl.select_task(tid)

    def select_task_in_ui(self, task):
        """Dopo la scelta nella finestra del selettore."""
        self._fill_projects(self.ctl.projects)
        self._fill_tasks(self.ctl.tasks)
        self.ctl.select_task(task.id)

    def _update_task_info(self):
        t = self.ctl.task
        if t is None:
            self.task_info.setText('')
            return
        geo = ('EPSG:%d' % t.epsg) if t.epsg else (T('georiferito (WKT)') if t.wkt else T('NON georiferito'))
        extra = T(' - plugin WebODM: scalato') if self.ctl.plugin_scaled else (
            T(' - plugin WebODM presente') if self.ctl.plugin_present else '')
        self.task_info.setText(T('{n} foto - {g}{x}', n=t.images_count, g=geo, x=extra))

    def _update_session(self):
        s = self.ctl.session
        if s.valid():
            short = s.folder if len(s.folder) <= 38 else '...' + s.folder[-35:]
            self.session_lab.setText('<b>%s</b><br><small>%s</small>' % (s.name, short))
            self.session_lab.setToolTip(s.root or s.folder)
        else:
            self.session_lab.setText('<i>%s</i>' % T('(da scegliere al primo caricamento)'))

    # --- prodotti ------------------------------------------------------------------------------
    def _fill_products(self):
        self.tree.clear()
        t = self.ctl.task
        if t is None:
            return
        if not t.completed:
            QTreeWidgetItem(self.tree, [T('Task non completato: nessun prodotto disponibile')])
            return
        kinds = {'raster': 'GeoTIFF', 'pointcloud': T('nuvola'), 'photos': T('punti'), 'model': T('mesh'),
                 'vector': T('vettore'), 'shot': T('scatto'), 'xyz': T('tile'), 'archive': 'zip',
                 'document': 'PDF', 'file': T('file'), 'image': T('immagine')}
        for g, items in catalog.grouped(self.ctl.products):
            gi = QTreeWidgetItem(self.tree, [catalog.group_label(g)])
            gi.setFlags(gi.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for p in items:
                alerts = crs_guard.predict(p, t, self.ctl.plugin_scaled)
                it = QTreeWidgetItem(gi, [p.label, kinds.get(p.kind, p.kind)])
                it.setData(0, Qt.ItemDataRole.UserRole, p)
                it.setIcon(0, light({'green': 'green', 'yellow': 'yellow', 'red': 'red'}[crs_guard.traffic_light(alerts)]))
                it.setToolTip(0, '\n\n'.join('%s: %s' % (a.code, a.text) for a in alerts) or T('Nessun avviso previsto.'))
            gi.setExpanded(True)
        self.tree.resizeColumnToContents(0)
        self.shots.refresh()

    def _selected_products(self):
        out = []
        for it in self.tree.selectedItems():
            p = it.data(0, Qt.ItemDataRole.UserRole)
            if p is not None:
                out.append(p)
        return out

    def _sel_changed(self):
        self.load_btn.setEnabled(bool(self._selected_products()))

    def _load_selected(self):
        prods = self._selected_products()
        if prods:
            self.ctl.load_products(prods)

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if it is None or it.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        p = it.data(0, Qt.ItemDataRole.UserRole)
        m = QMenu(self)
        m.addAction(icon('download'), T('Carica nel progetto'), self._load_selected)
        m.addAction(icon('crs'), T('Mostra gli avvisi CRS'), lambda: self._alerts(p))
        m.addAction(icon('viewer'), T('Apri il task nel visualizzatore 3D'), lambda: self.viewerRequested.emit('3d'))
        m.addAction(icon('viewer'), T('Apri il task nella mappa 2D'), lambda: self.viewerRequested.emit('map'))
        if p.path and self.ctl.client:
            m.addAction(T("Copia l'URL"), lambda: QGuiApplication.clipboard().setText(self.ctl.client.base + p.path))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def _alerts(self, p):
        alerts = crs_guard.predict(p, self.ctl.task, self.ctl.plugin_scaled)
        text = '\n\n'.join('%s (%s): %s' % (a.code, a.level, a.text) for a in alerts) or T('Nessun avviso previsto.')
        text += '\n\n' + T("Gli avvisi definitivi (CRS reale del file e del progetto) compaiono al caricamento.")
        QMessageBox.information(self, p.label, text)

    # --- avanzamento ---------------------------------------------------------------------------
    def _busy(self, on, text):
        self.busy_lab.setText(text if on else '')
        self.bar.setVisible(on)
        self.cancel_btn.setVisible(on)
        if on:
            self.bar.setRange(0, 0)

    def _progress(self, done, total):
        if total > 0:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(1000 * done / total))
            self.bar.setFormat('%.1f / %.1f MB' % (done / 1048576, total / 1048576))
        else:
            self.bar.setRange(0, 0)
