"""Mappa dedicata per i prospetti: CRS locale in metri, separata dal canvas principale."""
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QLabel, QVBoxLayout

from ..i18n import T
from .icons import icon


class ShotViewer(QDialog):
    def __init__(self, layer, product, parent=None):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(T('Prospetto: {n}', n=product.label))
        self.setWindowIcon(icon('shots'))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(900, 640)
        lay = QVBoxLayout(self)
        note = QLabel(T("CRS locale in metri: le coordinate sono quelle del piano dell'immagine, non una posizione "
                        "sulla Terra. Non sovrapporre questo layer alla mappa principale."))
        note.setWordWrap(True)
        note.setStyleSheet('color:#c92a2a')
        lay.addWidget(note)
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.GlobalColor.white)
        self.canvas.setDestinationCrs(layer.crs())
        self.canvas.setLayers([layer])
        self.canvas.setExtent(layer.extent())
        self.tool = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(self.tool)
        lay.addWidget(self.canvas, 1)
        m = product.meta
        bits = [m.get('label') or '']
        if m.get('size_m'):
            bits.append('%g x %g m' % tuple(m['size_m']))
        if m.get('scale'):
            bits.append('1:%g @ %g dpi' % (m['scale'], m.get('dpi') or 0))
        lay.addWidget(QLabel('   '.join(b for b in bits if b)))
        self.canvas.refresh()
