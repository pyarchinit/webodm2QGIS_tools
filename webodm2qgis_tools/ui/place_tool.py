"""Strumento mappa per posizionare uno scatto: il clic cattura un punto (angolo in alto a sinistra);
mentre il mouse si muove mostra l'impronta dello scatto."""
from qgis.core import Qgis, QgsPointXY
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor


class PlaceTool(QgsMapToolEmitPoint):
    pointPicked = pyqtSignal(float, float)

    def __init__(self, canvas, size_provider):
        """`size_provider()` -> (larghezza, altezza) in metri dello scatto scelto, oppure None."""
        QgsMapToolEmitPoint.__init__(self, canvas)
        self._size = size_provider
        self._band = QgsRubberBand(canvas, Qgis.GeometryType.Polygon)
        self._band.setColor(QColor(232, 89, 12, 70))
        self._band.setStrokeColor(QColor(232, 89, 12))
        self._band.setWidth(2)
        self._fixed = None

    def show_footprint(self, x, y):
        """Disegna l'impronta con l'angolo in alto a sinistra in (x, y)."""
        size = self._size()
        self._band.reset(Qgis.GeometryType.Polygon)
        if not size:
            return
        w, h = size
        for px, py in ((x, y), (x + w, y), (x + w, y - h), (x, y - h)):
            self._band.addPoint(QgsPointXY(px, py), False)
        self._band.closePoints()

    def canvasMoveEvent(self, e):
        if self._fixed is None:
            p = e.mapPoint()
            self.show_footprint(p.x(), p.y())

    def canvasReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        p = e.mapPoint()
        self._fixed = (p.x(), p.y())
        self.show_footprint(p.x(), p.y())
        self.pointPicked.emit(p.x(), p.y())

    def release_point(self):
        """Dopo "Posiziona" l'impronta torna a seguire il mouse."""
        self._fixed = None

    def clear(self):
        self._fixed = None
        self._band.reset(Qgis.GeometryType.Polygon)

    def deactivate(self):
        self.clear()
        QgsMapToolEmitPoint.deactivate(self)
