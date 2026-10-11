"""WebODM2QGIS-tools: importa in QGIS 4 i prodotti di WebODM."""


def classFactory(iface):
    from .plugin import WebODM2QGISPlugin
    return WebODM2QGISPlugin(iface)
