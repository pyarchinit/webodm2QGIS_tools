"""Strumento mappa "Foto": un clic su un punto di scatto mostra la foto, il doppio clic apre l'originale."""
from qgis.core import QgsCoordinateTransform, QgsFeatureRequest, QgsProject, QgsRectangle
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QCursor

from ..loaders import shots_points

TOLERANCE_PX = 12


def nearest_photo(canvas, map_point):
    """(layer, feature) del punto di scatto piu' vicino al clic entro la tolleranza, oppure None.
    Considera solo i layer di foto visibili."""
    root = QgsProject.instance().layerTreeRoot()
    best = None
    tol_map = canvas.mapUnitsPerPixel() * TOLERANCE_PX
    for lyr in QgsProject.instance().mapLayers().values():
        if not shots_points.is_photos_layer(lyr):
            continue
        node = root.findLayer(lyr.id())
        if node is not None and not node.isVisible():
            continue
        ct = QgsCoordinateTransform(canvas.mapSettings().destinationCrs(), lyr.crs(), QgsProject.instance())
        try:
            p = ct.transform(map_point)
            edge = ct.transform(map_point.x() + tol_map, map_point.y())
        except Exception:
            continue
        tol = max(abs(edge.x() - p.x()), abs(edge.y() - p.y()))
        rect = QgsRectangle(p.x() - tol, p.y() - tol, p.x() + tol, p.y() + tol)
        for f in lyr.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
            d = f.geometry().asPoint().distance(p)
            if best is None or d < best[0]:
                best = (d, lyr, f)
    return (best[1], best[2]) if best else None


class PhotoTool(QgsMapTool):
    def __init__(self, canvas, controller):
        QgsMapTool.__init__(self, canvas)
        self.ctl = controller
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def canvasReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        hit = nearest_photo(self.canvas(), e.mapPoint())
        if hit is None:
            return
        lyr, f = hit
        self.ctl.show_photo(lyr.id(), f.id())

    def canvasDoubleClickEvent(self, e):
        hit = nearest_photo(self.canvas(), e.mapPoint())
        if hit is not None:
            self.ctl.open_original(hit[0].id(), hit[1].id())
