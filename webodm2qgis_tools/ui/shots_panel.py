"""Galleria degli scatti e prospetti prodotti dal plugin WebODM (miniature + metadati)."""
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import (QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListView, QListWidget,
                                 QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from ..i18n import T
from .icons import icon
from .place_tool import PlaceTool

THUMB = 120


class ShotsPanel(QWidget):
    def __init__(self, controller, canvas=None, parent=None):
        QWidget.__init__(self, parent)
        self.ctl = controller
        self.canvas = canvas
        self._prev_tool = None
        self.tool = PlaceTool(canvas, self._shot_size) if canvas is not None else None
        if self.tool is not None:
            self.tool.pointPicked.connect(self._picked)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        self.empty = QLabel(T("Nessuno scatto: li crea il plugin WebODM (Prospetti, sezioni, piante) e compaiono qui."))
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)
        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(QSize(THUMB, THUMB))
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setWordWrap(True)
        self.list.setSpacing(6)
        self.list.currentItemChanged.connect(self._changed)
        self.list.itemDoubleClicked.connect(lambda *_: self._load())
        lay.addWidget(self.list, 1)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        lay.addWidget(self.detail)
        row = QHBoxLayout()
        self.load_btn = QPushButton(icon('download'), T('Carica nel progetto'))
        self.load_btn.clicked.connect(self._load)
        row.addWidget(self.load_btn)
        self.open_btn = QPushButton(icon('open'), T('Apri PDF/PNG'))
        self.open_btn.setToolTip(T('Scarica nella sessione e apre il PDF (o l\'immagine) dello scatto'))
        self.open_btn.clicked.connect(self._open_web)
        row.addWidget(self.open_btn)
        lay.addLayout(row)

        # posizionamento sul canvas (modalita' acceso/spento)
        self.place_box = QGroupBox(T('Posiziona sul canvas'))
        pl = QVBoxLayout(self.place_box)
        self.place_btn = QPushButton(icon('photo_tool'), T('Modalita\' posizionamento: spenta'))
        self.place_btn.setCheckable(True)
        self.place_btn.setToolTip(T("Acceso: clicca un punto sul canvas di QGIS; l'angolo in alto a sinistra dello "
                                    "scatto andra' li', nel CRS del progetto."))
        self.place_btn.toggled.connect(self._toggle_place)
        pl.addWidget(self.place_btn)
        form = QFormLayout()
        self.px = QDoubleSpinBox()
        self.py = QDoubleSpinBox()
        for sp in (self.px, self.py):
            sp.setDecimals(3)
            sp.setRange(-1e12, 1e12)
            sp.setSingleStep(1.0)
            sp.setGroupSeparatorShown(False)
        self.px.valueChanged.connect(self._preview)
        self.py.valueChanged.connect(self._preview)
        self.crs_lab = QLabel()
        form.addRow('X', self.px)
        form.addRow('Y', self.py)
        form.addRow(T('CRS'), self.crs_lab)
        pl.addLayout(form)
        self.apply_btn = QPushButton(icon('check'), T('Posiziona qui'))
        self.apply_btn.setToolTip(T("Crea una copia georiferita dello scatto (file VRT leggero) e la carica; "
                                    "l'originale in CRS locale resta com'e'."))
        self.apply_btn.clicked.connect(self._apply)
        pl.addWidget(self.apply_btn)
        self.place_hint = QLabel()
        self.place_hint.setWordWrap(True)
        pl.addWidget(self.place_hint)
        lay.addWidget(self.place_box)
        self.place_box.setVisible(self.tool is not None)
        self._changed(None)

    # --- posizionamento ------------------------------------------------------------------------
    def _shot_size(self):
        p = self._current()
        return self.ctl.shot_size_m(p.key) if p is not None else None

    def _project_crs(self):
        from qgis.core import QgsProject
        return QgsProject.instance().crs()

    def _toggle_place(self, on):
        if self.tool is None:
            return
        self.place_btn.setText(T("Modalita' posizionamento: ACCESA") if on else T("Modalita' posizionamento: spenta"))
        if on:
            self._prev_tool = self.canvas.mapTool()
            self.canvas.setMapTool(self.tool)
            self._refresh_place()
        else:
            self.tool.clear()
            if self.canvas.mapTool() is self.tool:
                if self._prev_tool is not None:
                    self.canvas.setMapTool(self._prev_tool)
                else:
                    self.canvas.unsetMapTool(self.tool)
        self._refresh_place()

    def _refresh_place(self):
        crs = self._project_crs()
        self.crs_lab.setText('%s  %s' % (crs.authid() or T('(non impostato)'), crs.description()))
        p = self._current()
        loaded = p is not None and self.ctl.shot_layer(p.key) is not None
        self.apply_btn.setEnabled(loaded and self.place_btn.isChecked())
        if p is None:
            self.place_hint.setText(T('Scegli uno scatto nell\'elenco.'))
        elif not loaded:
            self.place_hint.setText(T('Carica prima lo scatto nel progetto: poi potrai posizionarlo.'))
        elif self.place_btn.isChecked():
            self.place_hint.setText(T("Clicca sul canvas: il punto diventa l'angolo in alto a sinistra. "
                                      "Puoi correggere X e Y a mano."))
        else:
            self.place_hint.setText(T('Accendi la modalita\' per scegliere un punto sul canvas.'))

    def _picked(self, x, y):
        for sp, v in ((self.px, x), (self.py, y)):
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)
        self._refresh_place()

    def _preview(self, *_):
        if self.tool is not None and self.place_btn.isChecked():
            self.tool.show_footprint(self.px.value(), self.py.value())

    def _apply(self):
        p = self._current()
        if p is None:
            return
        self.ctl.place_shot(p.key, self.px.value(), self.py.value())
        self.tool.release_point()

    def _shots(self):
        return [p for p in self.ctl.products if p.kind == 'shot']

    def refresh(self):
        self.list.clear()
        shots = self._shots()
        self.empty.setVisible(not shots)
        self.list.setVisible(bool(shots))
        for p in shots:
            it = QListWidgetItem(icon('shots'), p.label)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.list.addItem(it)
            prev = next((f for f in p.extra_files if f['name'].lower().endswith('_preview.jpg')), None)
            if prev and self.ctl.client:
                self.ctl.client.get_bytes(prev['url'], lambda data, err, it=it: self._thumb(it, data, err))
        self._changed(None)

    def _thumb(self, item, data, err):
        if err is None and data and self.list.row(item) >= 0:
            pm = QPixmap()
            if pm.loadFromData(data):
                item.setIcon(QIcon(pm.scaled(THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)))

    def _current(self):
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def _changed(self, _it, _prev=None):
        p = self._current()
        if hasattr(self, 'place_box'):
            self._refresh_place()
        self.load_btn.setEnabled(p is not None)
        self.open_btn.setEnabled(p is not None)
        if p is None:
            self.detail.setText('')
            return
        m = p.meta
        lines = ['<b>%s</b>' % p.label, m.get('label') or m.get('view') or '']
        if m.get('size_m'):
            lines.append(T('{w:g} x {h:g} m, {px}', w=m['size_m'][0], h=m['size_m'][1],
                           px='%d x %d px' % tuple(m.get('size_px') or (0, 0))))
        if m.get('scale'):
            lines.append(T('Scala 1:{s:g} a {d:g} dpi', s=m['scale'], d=m.get('dpi') or 0))
        if m.get('epsg'):
            lines.append('EPSG:%d' % m['epsg'])
        elif m.get('view') != 'top':
            lines.append(T('Piano immagine in metri (CRS locale): non e\' una posizione sulla Terra.'))
        else:
            lines.append(T('Non georiferito.'))
        self.detail.setText('<br>'.join(l for l in lines if l))

    def _load(self):
        p = self._current()
        if p is not None:
            self.ctl.load_products([p])

    def _open_web(self):
        p = self._current()
        if p is None or not self.ctl.client:
            return
        pref = next((f for f in p.extra_files if f['name'].lower().endswith('.pdf')), None) or \
            next((f for f in p.extra_files if f['name'].lower().endswith(('.png', '.jpg'))
                  and '_preview' not in f['name']), None)
        if pref is None:
            pref = {'name': p.filename, 'url': p.path}
        self.ctl.fetch_and_open(pref['url'], pref['name'])
