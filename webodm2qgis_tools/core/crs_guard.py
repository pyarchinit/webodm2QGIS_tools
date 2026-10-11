"""Avvisi su CRS / EPSG / georiferimento prima (e dopo) l'import di un prodotto. Puro Python.

Livelli: info (si procede, se ne parla in barra messaggi), warn (si chiede conferma, con scelte),
block (non si procede senza una decisione dell'utente: es. file senza CRS).
Codici stabili (C01..C13, P01..P04): vedi PROGETTO.md §7.
"""
from ..i18n import T
from .models import Alert

LEVEL_RANK = {'info': 0, 'warn': 1, 'block': 2}

# prodotti che hanno una posizione sulla Terra
GEO_KINDS = ('raster', 'pointcloud', 'vector', 'photos', 'xyz', 'shot')
METRIC_KINDS = ('raster', 'pointcloud', 'xyz')
VERTICAL_ASSETS = ('dsm.tif', 'dtm.tif', 'georeferenced_model.laz', 'georeferenced_model.las')

BIG_FILE = 2 * 1024 ** 3
FAR_KM = 100.0


def _a(code, level, text, choices=()):
    return Alert(code=code, level=level, text=text, choices=tuple(choices))


def worst(alerts):
    return max((a.level for a in alerts), key=lambda l: LEVEL_RANK[l], default=None)


def traffic_light(alerts):
    """'green' | 'yellow' | 'red'."""
    w = worst(alerts)
    return {'block': 'red', 'warn': 'yellow'}.get(w, 'green')


def _auth(epsg):
    return 'EPSG:%d' % epsg if epsg else ''


def predict(product, task, plugin_scaled=False):
    """Avvisi che si possono prevedere SENZA scaricare nulla (solo dai dati del task):
    servono al semaforo dell'elenco. Non conosce il CRS del file ne' quello del progetto."""
    alerts = []
    meta = product.meta or {}
    if product.kind == 'shot':
        if meta.get('view') != 'top':
            alerts.append(_a('P01', 'warn', T(
                "Prospetto/sezione: il raster e' georiferito solo nel suo piano immagine (metri), "
                "non e' una posizione sulla Terra. Va visto in una mappa a parte, con un CRS locale.")))
        elif meta.get('epsg'):
            alerts.append(_a('P02', 'info', T("Pianta georiferita in EPSG:{epsg}: si sovrappone al resto.",
                                              epsg=meta['epsg'])))
        else:
            alerts.append(_a('P03', 'warn', T("Pianta non georiferita: posizione senza significato, distanze reali.")))
        if meta.get('scale') and meta.get('dpi'):
            alerts.append(_a('P04', 'info', T("Scatto in scala 1:{scale:g} a {dpi:g} dpi: il progetto QGIS deve essere in metri.",
                                              scale=meta['scale'], dpi=meta['dpi'])))
    elif product.source == 'plugin' and meta.get('local'):
        alerts.append(_a('P05', 'warn', T(
            "Modello scalato e orientato ma NON georiferito: coordinate locali in metri, non una posizione sulla "
            "Terra. Si carica con un CRS locale, a parte dalla mappa.")))
    elif product.source == 'plugin' and meta.get('epsg'):
        alerts.append(_a('P06', 'info', T(
            "Georiferito con il plugin WebODM in EPSG:{epsg} (coordinate assolute): si sovrappone al resto.",
            epsg=meta['epsg'])))
    elif product.kind == 'photos' and not task.georeferenced:
        alerts.append(_a('P10', 'info', T(
            "Task non georiferito: le foto si posizionano con le coordinate metriche locali del modello, nello "
            "stesso riferimento di ortofoto e nuvola (le coordinate lon/lat del file non hanno significato). "
            "La posizione sulla Terra non c'e'.")))
    elif product.kind in GEO_KINDS and not task.georeferenced:
        alerts.append(_a('C01', 'warn', T(
            "Il task non e' georiferito: ODM usa una zona UTM fittizia. La posizione non ha significato, "
            "le distanze sono reali. Non sovrapporlo a dati reali.")))
    if product.kind == 'photos':
        alerts.append(_a('C12', 'info', T(
            "Le posizioni sono quelle stimate dalla ricostruzione (non il GPS grezzo dell'EXIF).")))
    if product.filename in VERTICAL_ASSETS and task.georeferenced:
        alerts.append(_a('C07', 'info', T(
            "Quote: nessun datum verticale dichiarato (altezza ellissoidale o del modello, geoide non applicato).")))
    if plugin_scaled and product.source == 'odm' and product.kind in ('pointcloud', 'model', 'raster'):
        alerts.append(_a('C08', 'warn', T(
            "Il task ha una scala/orientamento salvati con il plugin WebODM: questo e' il prodotto ORIGINALE, "
            "non quello scalato (vedi \"Export del plugin WebODM\").")))
    if product.source == 'plugin' and product.kind != 'shot' and not meta.get('local') and not meta.get('epsg'):
        alerts.append(_a('C08', 'info', T("Versione scalata/orientata con il plugin WebODM.")))
    return alerts


def check(product, task, file_crs=None, project_crs=None, project_has_layers=False,
          size_bytes=None, free_bytes=None, distance_km=None, plugin_scaled=False):
    """Tutti gli avvisi, con il CRS reale del file e quello del progetto (CrsInfo o None)."""
    alerts = predict(product, task, plugin_scaled)
    kind = product.kind
    meta = product.meta or {}

    if size_bytes and size_bytes > BIG_FILE:
        alerts.append(_a('C11', 'info', T("File molto grande ({gb:.1f} GB): il download puo' richiedere molto tempo.",
                                          gb=size_bytes / 1024 ** 3)))
    if size_bytes and free_bytes is not None and free_bytes < size_bytes * 1.2:
        alerts.append(_a('C11', 'warn', T("Spazio su disco insufficiente per il download ({free:.1f} GB liberi).",
                                          free=free_bytes / 1024 ** 3)))

    if kind in ('raster', 'pointcloud', 'vector', 'xyz', 'shot') and kind != 'photos':
        local = kind == 'shot' and meta.get('view') != 'top'
        if local:
            return alerts                      # niente confronti con CRS terrestri
        if file_crs is None or not file_crs.valid:
            if file_crs is not None:           # file aperto ma senza CRS leggibile
                alerts.append(_a('C03', 'block', T(
                    "Il file non ha un CRS leggibile. Indica tu l'EPSG: nessun CRS viene assegnato a caso."),
                    choices=('assign_crs', 'cancel')))
            return alerts
        if file_crs.problem:
            alerts.append(_a('C06', 'warn', T("Problema col CRS del file: {p}", p=file_crs.problem)))
        want = _auth(meta.get('epsg')) or _auth(task.epsg)      # per i prodotti del plugin vale il suo EPSG
        if want and file_crs.authid and want != file_crs.authid:
            alerts.append(_a('C04', 'warn', T(
                "Il task dichiara {want} ma il file e' in {have}: si usa quello del file.",
                want=want, have=file_crs.authid)))
        if file_crs.geographic and kind in METRIC_KINDS:
            alerts.append(_a('C05', 'warn', T(
                "Il CRS del file e' geografico (gradi): scala grafica, misure e pixel non sono in metri. "
                "Per misurare usa un CRS proiettato.")))
        project_unset = project_crs is None or not project_crs.valid
        if (project_unset and not project_has_layers) or \
                (not project_unset and file_crs.authid != project_crs.authid):
            if project_has_layers:
                alerts.append(_a('C02', 'warn', T(
                    "Il CRS del prodotto ({have}) e' diverso da quello del progetto ({proj}).",
                    have=file_crs.authid, proj=project_crs.authid),
                    choices=('reproject', 'set_project_crs', 'cancel')))
            else:
                alerts.append(_a('C02', 'info', T(
                    "Il progetto e' vuoto: si adotta il CRS del prodotto ({have}).", have=file_crs.authid),
                    choices=('set_project_crs',)))
        if distance_km is not None and distance_km > FAR_KM and project_has_layers:
            alerts.append(_a('C10', 'warn', T(
                "Il prodotto e' a {km:.0f} km dall'area del progetto: forse il CRS e' sbagliato o il task "
                "non e' georiferito.", km=distance_km)))
    return alerts


def original_missing_alert(filename):
    return _a('C13', 'info', T("L'originale di {f} non e' sul server.", f=filename))


def needs_dialog(alerts):
    """True se c'e' qualcosa da decidere (warn/block); le info vanno solo in barra messaggi."""
    return any(a.level in ('warn', 'block') for a in alerts)
