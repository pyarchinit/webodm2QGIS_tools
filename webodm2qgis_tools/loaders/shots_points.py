"""Layer dei punti di scatto delle foto, con le azioni "Apri foto originale"."""
import os
from datetime import datetime, timezone

from qgis.core import (Qgis, QgsAction, QgsFeature, QgsGeometry, QgsMarkerSymbol, QgsPoint, QgsProject, QgsProperty,
                       QgsSymbolLayer, QgsVectorFileWriter, QgsVectorLayer)

from ..core.photos import ORIG_UNKNOWN
from ..i18n import T

PROP = 'webodm2qgis/'
FIELDS = ['nome_file:string', 'camera:string', 'quota:double', 'x_loc:double', 'y_loc:double', 'z_loc:double',
          'azimut:double', 'inclin:double', 'larghezza_px:integer', 'altezza_px:integer', 'data_scatto:string',
          'originale:string']


def _stamp(ct):
    if ct is None:
        return ''
    try:
        return datetime.fromtimestamp(float(ct), timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (OverflowError, OSError, ValueError):
        return ''


def build(shots, path, name, server_url, project_id, task_id, photos_dir='', model_crs=None):
    """Scrive `path` (GeoPackage) con un punto per foto e lo apre come layer. None se fallisce.

    `model_crs` = None: task georiferito, le posizioni sono quelle lon/lat WGS84 di shots.geojson.
    `model_crs` = un CRS: task NON georiferito. In shots.geojson le coordinate sono gradi senza significato
    (finirebbero a 0,0); le foto si posizionano con `translation`, i metri locali del modello, che sono nello
    stesso riferimento della nuvola e dell'ortofoto, e il layer prende il CRS del modello."""
    local = model_crs is not None
    mem = QgsVectorLayer('PointZ?crs=EPSG:4326&' + '&'.join('field=' + f for f in FIELDS), 'foto', 'memory')
    if local:
        mem.setCrs(model_crs)
    feats = []
    for s in shots:
        f = QgsFeature(mem.fields())
        if local:
            f.setGeometry(QgsGeometry(QgsPoint(s.position[0], s.position[1], s.position[2])))
        else:
            f.setGeometry(QgsGeometry(QgsPoint(s.lon, s.lat, s.alt)))
        f.setAttributes([s.filename, s.camera, s.position[2] if local else s.alt,
                         s.position[0], s.position[1], s.position[2],
                         s.azimuth, s.tilt, s.width, s.height, _stamp(s.capture_time), ORIG_UNKNOWN])
        feats.append(f)
    mem.dataProvider().addFeatures(feats)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = 'GPKG'
    opts.layerName = 'foto'
    res = QgsVectorFileWriter.writeAsVectorFormatV3(mem, path, QgsProject.instance().transformContext(), opts)
    if res[0] != QgsVectorFileWriter.WriterError.NoError:
        return None
    layer = QgsVectorLayer('%s|layername=foto' % path, name, 'ogr')
    if not layer.isValid():
        return None
    for k, v in (('kind', 'photos'), ('server_url', server_url), ('project_id', str(project_id)),
                 ('task_id', task_id), ('photos_dir', photos_dir)):
        layer.setCustomProperty(PROP + k, v)
    style(layer)
    add_actions(layer)
    return layer


def style(layer):
    sym = QgsMarkerSymbol.createSimple({'name': 'arrow', 'size': '4', 'color': '#e8590c',
                                        'outline_color': '#ffffff', 'outline_width': '0.4'})
    sym.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.Angle, QgsProperty.fromField('azimut'))
    layer.renderer().setSymbol(sym)
    layer.setDisplayExpression('"nome_file"')
    layer.setMapTipTemplate(
        '<b>[% "nome_file" %]</b><br>' + T('quota') + ': [% round("quota", 2) %] m<br>'
        + T('originale') + ': [% "originale" %]')


def add_actions(layer):
    """Due azioni: aprire l'originale e mostrare la foto nel pannello. La prima e' quella predefinita
    dello strumento "Esegui azione sull'elemento" di QGIS (clic sul punto)."""
    am = layer.actions()
    code_open = ("from webodm2qgis_tools.runtime import open_original; "
                 "open_original('[% @layer_id %]', [% $id %])")
    code_show = ("from webodm2qgis_tools.runtime import show_photo; "
                 "show_photo('[% @layer_id %]', [% $id %])")
    a_open = QgsAction(Qgis.AttributeActionType.GenericPython, T('Apri foto originale'), code_open)
    a_show = QgsAction(Qgis.AttributeActionType.GenericPython, T('Mostra nel pannello Foto'), code_show)
    for a in (a_open, a_show):
        a.setActionScopes({'Feature', 'Canvas', 'Field', 'Layer'})
        am.addAction(a)
    am.setDefaultAction('Canvas', a_open.id())


def is_photos_layer(layer):
    return isinstance(layer, QgsVectorLayer) and layer.customProperty(PROP + 'kind') == 'photos'


def context(layer):
    """Dati per risalire al server/task da un layer di foto (anche dopo la riapertura del progetto)."""
    return {'server_url': layer.customProperty(PROP + 'server_url') or '',
            'project_id': layer.customProperty(PROP + 'project_id') or '',
            'task_id': layer.customProperty(PROP + 'task_id') or '',
            'photos_dir': layer.customProperty(PROP + 'photos_dir') or ''}


def set_original_state(layer, fid, state):
    """Scrive si/no/? nel campo `originale` (provider diretto: non richiede di mettere il layer in modifica)."""
    idx = layer.fields().indexOf('originale')
    if idx < 0:
        return False
    ok = layer.dataProvider().changeAttributeValues({fid: {idx: state}})
    layer.triggerRepaint()
    return bool(ok)
