"""Finestra "Scegli progetto e task": ricerca, stato, anteprima."""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                                 QListWidgetItem, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core import selection
from ..core.models import status_label
from ..core.urls import task_api
from ..i18n import T
from .icons import icon, light


class TaskPicker(QDialog):
    def __init__(self, controller, parent=None):
        QDialog.__init__(self, parent)
        self.ctl = controller
        self.setWindowTitle(T('Scegli progetto e task'))
        self.setWindowIcon(icon('task'))
        self.resize(900, 520)
        self._chosen = None
        lay = QVBoxLayout(self)
        split = QSplitter()
        lay.addWidget(split, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel('<b>%s</b>' % T('Progetti')))
        self.pfilter = QLineEdit()
        self.pfilter.setPlaceholderText(T('Cerca un progetto...'))
        self.pfilter.setClearButtonEnabled(True)
        self.pfilter.textChanged.connect(self._fill_projects)
        ll.addWidget(self.pfilter)
        self.plist = QListWidget()
        self.plist.currentItemChanged.connect(self._project_changed)
        ll.addWidget(self.plist)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel('<b>%s</b>' % T('Task')))
        row = QHBoxLayout()
        self.tfilter = QLineEdit()
        self.tfilter.setPlaceholderText(T('Cerca un task...'))
        self.tfilter.setClearButtonEnabled(True)
        self.tfilter.textChanged.connect(self._fill_tasks)
        row.addWidget(self.tfilter, 1)
        self.only_done = QCheckBox(T('Solo completati'))
        self.only_done.setChecked(True)
        self.only_done.toggled.connect(self._fill_tasks)
        row.addWidget(self.only_done)
        rl.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setHeaderLabels([T('Nome'), T('Data'), T('Stato'), T('Foto'), T('Georiferito')])
        self.tree.currentItemChanged.connect(self._task_changed)
        self.tree.itemDoubleClicked.connect(lambda *_: self._accept())
        rl.addWidget(self.tree, 1)
        self.preview = QLabel()
        self.preview.setMinimumHeight(110)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        prow = QHBoxLayout()
        prow.addWidget(self.preview)
        prow.addWidget(self.detail, 1)
        rl.addLayout(prow)
        split.addWidget(right)
        split.setSizes([260, 640])

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        self._loading_tasks_for = None
        controller.projectsLoaded.connect(self._fill_projects)
        controller.tasksLoaded.connect(self._fill_tasks)
        self._fill_projects()
        self._fill_tasks()

    def closeEvent(self, e):
        self._disconnect()
        QDialog.closeEvent(self, e)

    def done(self, r):
        self._disconnect()
        QDialog.done(self, r)

    def _disconnect(self):
        for sig, slot in ((self.ctl.projectsLoaded, self._fill_projects), (self.ctl.tasksLoaded, self._fill_tasks)):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass

    # --- progetti ------------------------------------------------------------------------------
    def _fill_projects(self, *_):
        cur = self.ctl.selection.project_id
        self.plist.blockSignals(True)
        self.plist.clear()
        for p in selection.filter_projects(self.ctl.projects, self.pfilter.text()):
            it = QListWidgetItem(icon('folder'), '%s  (%d)' % (p.name, len(p.task_ids)))
            it.setData(Qt.ItemDataRole.UserRole, p.id)
            self.plist.addItem(it)
            if p.id == cur:
                self.plist.setCurrentItem(it)
        self.plist.blockSignals(False)

    def _project_changed(self, item, _prev=None):
        if item is None:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid != self.ctl.selection.project_id or not self.ctl.tasks:
            self.ctl.select_project(pid)

    # --- task ----------------------------------------------------------------------------------
    def _fill_tasks(self, *_):
        self.tree.clear()
        cur = self.ctl.selection.task_id
        for t in selection.filter_tasks(self.ctl.tasks, self.tfilter.text(), self.only_done.isChecked()):
            it = QTreeWidgetItem([t.label, t.created_at[:10], status_label(t.status), str(t.images_count),
                                  ('EPSG:%d' % t.epsg) if t.epsg else (T('si') if t.wkt else T('no'))])
            it.setData(0, Qt.ItemDataRole.UserRole, t)
            it.setIcon(0, light('green' if t.completed and t.georeferenced else ('yellow' if t.completed else 'grey')))
            self.tree.addTopLevelItem(it)
            if t.id == cur:
                self.tree.setCurrentItem(it)
        for c in range(5):
            self.tree.resizeColumnToContents(c)

    def _task_changed(self, item, _prev=None):
        ok = item is not None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok and item.data(0, Qt.ItemDataRole.UserRole).completed)
        self.preview.clear()
        if not ok:
            self.detail.setText('')
            return
        t = item.data(0, Qt.ItemDataRole.UserRole)
        lines = ['<b>%s</b>' % t.label, T('Stato: {s}', s=status_label(t.status)), T('Foto: {n}', n=t.images_count)]
        if t.georeferenced:
            lines.append(T('Georiferito: {e}', e=('EPSG:%d' % t.epsg) if t.epsg else T('(WKT)')))
        else:
            lines.append(T("Non georiferito: posizione senza significato, distanze reali."))
        if t.completed:
            lines.append(T('{n} prodotti disponibili', n=len(t.available_assets)))
        self.detail.setText('<br>'.join(lines))
        if t.completed and 'orthophoto.tif' in t.available_assets and self.ctl.client:
            tid = t.id

            def got(data, err):
                cur = self.tree.currentItem()
                if err is None and data and cur is not None and cur.data(0, Qt.ItemDataRole.UserRole).id == tid:
                    pm = QPixmap()
                    if pm.loadFromData(data):
                        self.preview.setPixmap(pm.scaledToHeight(110, Qt.TransformationMode.SmoothTransformation))
            self.ctl.client.get_bytes(task_api(t.project_id, t.id, 'thumbnail'), got, {'size': 220})

    def chosen(self):
        return self._chosen

    def _accept(self):
        item = self.tree.currentItem()
        if item is None:
            return
        t = item.data(0, Qt.ItemDataRole.UserRole)
        if not t.completed:
            return
        self._chosen = t
        self.accept()
