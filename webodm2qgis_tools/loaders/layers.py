"""Caricamento dei prodotti come layer di QGIS e piccoli aiuti sui CRS."""
from urllib.parse import quote

from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointCloudLayer, QgsProject,
                       QgsProviderRegistry, QgsRasterLayer, QgsVectorLayer)

from ..core.models import CrsInfo
from ..i18n import T

# CRS ingegneristico locale (metri) per gli scatti non georiferiti: niente EPSG terrestre
LOCAL_WKT = ('LOCAL_CS["WebODM scatto (piano immagine, m)",LOCAL_DATUM["Unknown",0],UNIT["metre",1],'
             'AXIS["X",EAST],AXIS["Y",NORTH]]')


def local_crs():
    return QgsCoordinateReferenceSystem.fromWkt(LOCAL_WKT)


def crs_info(crs):
    if crs is None or not crs.isValid():
        return CrsInfo()
    return CrsInfo(authid=crs.authid(), valid=True, geographic=crs.isGeographic(),
                   description=crs.description())


def transform_problem(src, dst):
    """Testo del problema se QGIS non riesce a trasformare src -> dst (es. griglia PROJ mancante)."""
    if src is None or dst is None or not src.isValid() or not dst.isValid() or src == dst:
        return ''
    ct = QgsCoordinateTransform(src, dst, QgsProject.instance())
    if not ct.isValid():
        return T('trasformazione {a} -> {b} non disponibile', a=src.authid(), b=dst.authid())
    return ''


def ensure_group(name, parent=None):
    root = QgsProject.instance().layerTreeRoot()
    parent = parent or root
    return parent.findGroup(name) or parent.addGroup(name)


def group_for_task(task_label):
    return ensure_group('WebODM - %s' % task_label)


def add_to_group(layer, group, visible=True):
    QgsProject.instance().addMapLayer(layer, False)
    node = group.addLayer(layer)
    if node is not None:
        node.setItemVisibilityChecked(visible)
    return layer


def project_has_layers():
    return len(QgsProject.instance().mapLayers()) > 0


def open_raster(path, name):
    layer = QgsRasterLayer(path, name)
    return layer if layer.isValid() else None


def open_pointcloud(path, name):
    if 'pdal' not in QgsProviderRegistry.instance().providerList():
        return None
    layer = QgsPointCloudLayer(path, name, 'pdal')
    return layer if layer.isValid() else None


def open_vector(path, name):
    layer = QgsVectorLayer(path, name, 'ogr')
    return layer if layer.isValid() else None


def open_xyz(url_template, name, zmax=21, authcfg=''):
    """Tile in streaming. `url_template` contiene {z}/{x}/{y}; l'autenticazione passa da `authcfg`
    (mai un token nell'URL: finirebbe scritto nel progetto)."""
    enc = quote(url_template, safe=':/{}')
    uri = 'type=xyz&url=%s&zmax=%d&zmin=0' % (enc, zmax)
    if authcfg:
        uri += '&authcfg=' + authcfg
    layer = QgsRasterLayer(uri, name, 'wms')
    return layer if layer.isValid() else None
