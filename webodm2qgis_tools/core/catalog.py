"""Dall'elenco degli asset del task (e dalle risposte del plugin WebODM) all'elenco dei prodotti. Puro Python."""
import os

from ..i18n import T
from .models import Product
from .safety import safe_filename
from .urls import task_api

# ordine dei gruppi nel pannello
GROUPS = ['Ortofoto', 'Quote', 'Nuvola di punti', 'Foto', 'Mesh', 'Vettori', 'Scatti e prospetti',
          'Export del plugin WebODM', 'Documenti', 'Altro']


def group_label(g):
    return {'Ortofoto': T('Ortofoto'), 'Quote': T('Quote'), 'Nuvola di punti': T('Nuvola di punti'),
            'Foto': T('Foto'), 'Mesh': T('Mesh'), 'Vettori': T('Vettori'),
            'Scatti e prospetti': T('Scatti e prospetti'),
            'Export del plugin WebODM': T('Export del plugin WebODM'),
            'Documenti': T('Documenti'), 'Altro': T('Altro')}.get(g, g)


# asset di WebODM (Task.ASSETS_MAP) -> (etichetta, gruppo, tipo)
ASSETS = {
    'orthophoto.tif': ('Ortofoto (GeoTIFF)', 'Ortofoto', 'raster'),
    'orthophoto.png': ('Ortofoto (PNG)', 'Ortofoto', 'file'),
    'orthophoto.mbtiles': ('Ortofoto (MBTiles)', 'Ortofoto', 'file'),
    'orthophoto.kmz': ('Ortofoto (KMZ)', 'Ortofoto', 'file'),
    'orthophoto_tiles.zip': ('Ortofoto (tile, zip)', 'Ortofoto', 'archive'),
    'dsm.tif': ('Modello digitale di superficie (DSM)', 'Quote', 'raster'),
    'dtm.tif': ('Modello digitale del terreno (DTM)', 'Quote', 'raster'),
    'dsm_tiles.zip': ('DSM (tile, zip)', 'Quote', 'archive'),
    'dtm_tiles.zip': ('DTM (tile, zip)', 'Quote', 'archive'),
    'georeferenced_model.laz': ('Nuvola di punti (LAZ)', 'Nuvola di punti', 'pointcloud'),
    'georeferenced_model.las': ('Nuvola di punti (LAS)', 'Nuvola di punti', 'pointcloud'),
    'georeferenced_model.ply': ('Nuvola di punti (PLY)', 'Nuvola di punti', 'file'),
    'georeferenced_model.csv': ('Nuvola di punti (CSV)', 'Nuvola di punti', 'file'),
    '3d_tiles_pointcloud.zip': ('Nuvola di punti (3D Tiles, zip)', 'Nuvola di punti', 'archive'),
    'shots.geojson': ('Punti di scatto delle foto', 'Foto', 'photos'),
    'textured_model.zip': ('Mesh texturizzata (OBJ, zip)', 'Mesh', 'model'),
    'textured_model.glb': ('Mesh texturizzata (GLB)', 'Mesh', 'file'),
    '3d_tiles_model.zip': ('Mesh (3D Tiles, zip)', 'Mesh', 'archive'),
    'ground_control_points.geojson': ('Punti di controllo a terra (GCP)', 'Vettori', 'vector'),
    'cutline.gpkg': ('Linea di taglio dell\'ortofoto', 'Vettori', 'vector'),
    'cameras.json': ('Parametri delle camere (JSON)', 'Documenti', 'file'),
    'report.pdf': ('Rapporto di elaborazione (PDF)', 'Documenti', 'document'),
    'all.zip': ('Tutti i file del task (zip)', 'Altro', 'archive'),
    'splats.rad': ('Gaussian splats', 'Altro', 'file'),
}

_EXT_KIND = {'.tif': 'raster', '.tiff': 'raster', '.laz': 'pointcloud', '.las': 'pointcloud',
             '.geojson': 'vector', '.gpkg': 'vector', '.shp': 'vector',
             '.obj': 'model', '.ply': 'file', '.glb': 'file', '.zip': 'archive', '.pdf': 'document',
             '.png': 'image', '.jpg': 'image', '.jpeg': 'image'}


def kind_of(filename):
    return _EXT_KIND.get(os.path.splitext(filename)[1].lower(), 'file')


def odm_products(task):
    """Prodotti standard di ODM presenti in `task.available_assets`."""
    out = []
    for asset in task.available_assets:
        info = ASSETS.get(asset)
        if info is None:
            label, group, kind = asset, 'Altro', 'file'
        else:
            label, group, kind = info
        out.append(Product(key=asset, label=T(label) if info else label, group=group, kind=kind,
                           path=task_api(task.project_id, task.id, 'download/' + asset), filename=asset))
    if 'orthophoto.tif' in task.available_assets:
        out.append(Product(key='orthophoto.xyz', label=T('Ortofoto in streaming (tile)'), group='Ortofoto',
                           kind='xyz', path=task_api(task.project_id, task.id, 'orthophoto/tiles/{z}/{x}/{y}.png'),
                           filename=''))
    return out


def plugin_export_label(name):
    n = name.lower()
    if n.startswith('georeferenced_model.'):
        return 'Nuvola georiferita (plugin WebODM)'
    if n.startswith('scaled_model.'):
        return 'Nuvola scalata e orientata (plugin WebODM)'
    return None


def plugin_export_products(data, plugin_epsg=None):
    """Risposta di .../task/<id>/export del plugin WebODM -> prodotti. `plugin_epsg` = EPSG scelto nella
    sezione Georiferimento del plugin: le nuvole 'georeferenced_*' sono in quel sistema (coordinate assolute),
    le 'scaled_*' sono in coordinate locali in metri (nessuna posizione sulla Terra)."""
    out = []
    if not isinstance(data, dict):
        return out
    for f in data.get('files') or []:
        name = f.get('name') if isinstance(f, dict) else None
        url = f.get('url') if isinstance(f, dict) else None
        if not isinstance(url, str) or not url.startswith('/api/'):
            continue
        segs = str(name or '').replace('\\', '/').split('/')       # puo' essere 'cartella/file.obj'
        if not all(safe_filename(s) for s in segs):
            continue
        kind = kind_of(segs[-1])
        meta = {'subdir': '/'.join(segs[:-1])}
        label = str(name)
        special = plugin_export_label(segs[-1]) if kind == 'pointcloud' and len(segs) == 1 else None
        if special:
            if segs[-1].lower().startswith('georeferenced_') and plugin_epsg:
                meta['epsg'] = int(plugin_epsg)
                label = '%s - EPSG:%d' % (T(special), int(plugin_epsg))
            elif segs[-1].lower().startswith('georeferenced_'):
                label = T(special)
            else:
                meta['local'] = True
                label = T(special)
        out.append(Product(key='plugin:out:' + str(name), label=label, group='Export del plugin WebODM',
                           kind=kind, path=url, filename=segs[-1], source='plugin', meta=meta))
    return out


def plugin_shot_products(data):
    """Risposta di .../task/<id>/ortho del plugin WebODM -> un prodotto per scatto (il TIFF), con gli
    altri formati in `extra_files` e i metadati in `meta`."""
    out = []
    if not isinstance(data, dict):
        return out
    for meta in data.get('results') or []:
        if not isinstance(meta, dict) or not isinstance(meta.get('name'), str):
            continue
        files = {}
        for f in meta.get('files') or []:
            if isinstance(f, dict) and isinstance(f.get('url'), str) and f['url'].startswith('/api/') \
                    and safe_filename(os.path.basename(str(f.get('name') or ''))) is not None:
                files[os.path.basename(f['name'])] = f['url']
        tif = next((n for n in files if n.lower().endswith(('.tif', '.tiff')) and '_preview' not in n), None)
        if tif is None:
            continue
        title = meta.get('title') or meta.get('label') or meta['name']
        extra = [{'name': n, 'url': u} for n, u in files.items() if n != tif]
        out.append(Product(key='plugin:ortho:' + meta['name'], label=str(title), group='Scatti e prospetti',
                           kind='shot', path=files[tif], filename=tif, source='plugin', meta=meta,
                           extra_files=extra))
    return out


def plugin_photo_products(task, matrix_scaled=None, matrix_abs=None, epsg=None):
    """Punti di scatto delle foto nel riferimento del modello trasformato dal plugin WebODM. Le foto di
    shots.geojson sono nel riferimento ORIGINALE di ODM: se il modello e' stato scalato/ruotato (e georiferito)
    con il plugin, per seguirlo vanno trasformate con la stessa matrice."""
    if 'shots.geojson' not in task.available_assets:
        return []
    path = task_api(task.project_id, task.id, 'download/shots.geojson')
    out = []
    if matrix_abs and epsg:
        out.append(Product(key='shots.geojson:georef', label=T('Punti di scatto - georiferiti con il plugin WebODM')
                           + ' - EPSG:%d' % int(epsg), group='Foto', kind='photos', path=path,
                           filename='shots.geojson', source='plugin',
                           meta={'frame': 'georef', 'epsg': int(epsg), 'matrix': matrix_abs}))
    if matrix_scaled:
        out.append(Product(key='shots.geojson:scaled', label=T('Punti di scatto - scalati e orientati con il plugin WebODM'),
                           group='Foto', kind='photos', path=path, filename='shots.geojson', source='plugin',
                           meta={'frame': 'scaled', 'local': True, 'matrix': matrix_scaled}))
    return out


def build(task, plugin_export=None, plugin_ortho=None, plugin_epsg=None, matrix_scaled=None, matrix_abs=None):
    items = (odm_products(task) + plugin_export_products(plugin_export, plugin_epsg) +
             plugin_shot_products(plugin_ortho) + plugin_photo_products(task, matrix_scaled, matrix_abs, plugin_epsg))
    order = {g: i for i, g in enumerate(GROUPS)}
    items.sort(key=lambda p: (order.get(p.group, 99)))
    return items


def grouped(products):
    """[(gruppo, [prodotti])] nell'ordine dei GROUPS."""
    result = []
    for g in GROUPS:
        items = [p for p in products if p.group == g]
        if items:
            result.append((g, items))
    return result


def is_top_shot(meta):
    return (meta or {}).get('view') == 'top'
