"""Pannello "Foto": miniatura, metadati, [Apri originale], cartella locale di ripiego, verifica degli originali."""
from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (QDockWidget, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QProgressBar,
                                 QPushButton, QVBoxLayout, QWidget)

from ..i18n import T
from ..loaders import shots_points
from .icons import icon


class PhotoPanel(QDockWidget):
    def __init__(self, controller, canvas, parent=None):
        QDockWidget.__init__(self, T('WebODM - Foto'), parent)
        self.setObjectName('WebODM2QGISPhotoDock')
        self.ctl = controller
        self.canvas = canvas
        self.layer_id, self.fid = None, None
        body = QWidget()
        self.setWidget(body)
        lay = QVBoxLayout(body)
        self.thumb = QLabel(T('Clicca un punto di scatto sulla mappa (strumento Foto)'))
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setFixedHeight(220)
        self.thumb.setMinimumWidth(240)
        self.thumb.setWordWrap(True)
        self.thumb.setStyleSheet('background:#00000010; border:1px solid #8884;')
        lay.addWidget(self.thumb)
        form = QFormLayout()
        self.labels = {}
        for key, text in (('nome_file', T('File')), ('quota', T('Quota')), ('camera', T('Camera')),
                          ('data_scatto', T('Scatto')), ('orient', T('Orientamento')), ('originale', T('Originale'))):
            lab = QLabel('-')
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(text, lab)
            self.labels[key] = lab
        lay.addLayout(form)
        row = QHBoxLayout()
        self.open_btn = QPushButton(icon('open'), T('Apri originale'))
        self.open_btn.clicked.connect(self._open)
        row.addWidget(self.open_btn)
        self.zoom_btn = QPushButton(icon('photo_tool'), T('Zoom'))
        self.zoom_btn.clicked.connect(self._zoom)
        row.addWidget(self.zoom_btn)
        lay.addLayout(row)
        self.dir_btn = QPushButton(icon('folder'), T('Cartella locale delle foto...'))
        self.dir_btn.setToolTip(T("Se l'originale non e' piu' sul server lo si cerca qui, per nome"))
        self.dir_btn.clicked.connect(self._pick_dir)
        lay.addWidget(self.dir_btn)
        self.dir_lab = QLabel()
        self.dir_lab.setWordWrap(True)
        lay.addWidget(self.dir_lab)
        self.verify_btn = QPushButton(icon('check'), T('Verifica tutti gli originali'))
        self.verify_btn.setToolTip(T('Controlla sul server quali originali esistono e riempie la colonna "originale"'))
        self.verify_btn.clicked.connect(self._verify)
        lay.addWidget(self.verify_btn)
        self.bar = QProgressBar()
        self.bar.hide()
        lay.addWidget(self.bar)
        lay.addStretch(1)
        self._enable(False)
        controller.photoSelected.connect(self.show_photo)

    def _enable(self, on):
        for b in (self.open_btn, self.zoom_btn, self.dir_btn, self.verify_btn):
            b.setEnabled(on)

    def _layer(self):
        return QgsProject.instance().mapLayer(self.layer_id) if self.layer_id else None

    def show_photo(self, layer_id, fid):
        self.layer_id, self.fid = layer_id, fid
        layer = self._layer()
        if layer is None or not shots_points.is_photos_layer(layer):
            return
        f = layer.getFeature(fid)
        if not f.isValid():
            return
        self._enable(True)
        self.labels['nome_file'].setText(str(f['nome_file']))
        self.labels['quota'].setText('%.2f m' % f['quota'] if f['quota'] is not None else '-')
        self.labels['camera'].setText(str(f['camera'] or '-'))
        self.labels['data_scatto'].setText(str(f['data_scatto'] or '-'))
        az, tilt = f['azimut'], f['inclin']
        txt = []
        if az is not None and str(az) != 'NULL':
            txt.append(T('verso {a:.0f} gradi da nord', a=float(az)))
        if tilt is not None and str(tilt) != 'NULL':
            txt.append(T('{t:.0f} gradi dal nadir', t=float(tilt)))
        self.labels['orient'].setText(', '.join(txt) or '-')
        self._state(f['originale'])
        ctx = shots_points.context(layer)
        self.dir_lab.setText(ctx['photos_dir'])
        self.thumb.setPixmap(QPixmap())
        self.thumb.setText(T('Miniatura...'))
        want = (layer_id, fid)

        def got(data):
            if (self.layer_id, self.fid) != want:
                return
            pm = QPixmap()
            if data and pm.loadFromData(data):
                self.thumb.setPixmap(pm.scaled(max(200, self.thumb.width() - 4), self.thumb.height() - 4,
                                               Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))
            else:
                self.thumb.setText(T('Miniatura non disponibile'))
        self.ctl.photo_thumbnail(layer_id, fid, 480, got)
        self.show()
        self.raise_()

    def _state(self, s):
        self.labels['originale'].setText({'si': T('presente'), 'no': T('NON presente sul server'),
                                          '?': T('da verificare')}.get(s, str(s)))

    def _refresh_state(self):
        layer = self._layer()
        if layer is not None:
            self._state(layer.getFeature(self.fid)['originale'])

    def _open(self):
        if self.layer_id is None:
            return
        self.ctl.open_original(self.layer_id, self.fid)
        # lo stato si aggiorna a risposta ricevuta: si rilegge a breve
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(1500, self._refresh_state)

    def _zoom(self):
        layer = self._layer()
        if layer is None:
            return
        self.canvas.zoomToFeatureIds(layer, [self.fid])
        self.canvas.flashFeatureIds(layer, [self.fid])

    def _pick_dir(self):
        layer = self._layer()
        if layer is None:
            return
        d = QFileDialog.getExistingDirectory(self, T('Cartella con le foto originali'),
                                             shots_points.context(layer)['photos_dir'])
        if d:
            layer.setCustomProperty(shots_points.PROP + 'photos_dir', d)
            self.ctl.selection.photos_dir = d
            self.dir_lab.setText(d)

    def _verify(self):
        layer = self._layer()
        if layer is None:
            return
        if self.verify_btn.text() == T('Interrompi'):
            self.ctl.stop_verify()
            return
        self.verify_btn.setText(T('Interrompi'))
        self.bar.setRange(0, max(1, layer.featureCount()))
        self.bar.setValue(0)
        self.bar.show()

        def prog(done, total):
            self.bar.setValue(done)

        def done(yes, no):
            self.bar.hide()
            self.verify_btn.setText(T('Verifica tutti gli originali'))
            self.ctl.ui.message('info', T('Originali: {y} presenti, {n} assenti', y=yes, n=no))
            self._refresh_state()
        self.ctl.verify_originals(self.layer_id, prog, done)
