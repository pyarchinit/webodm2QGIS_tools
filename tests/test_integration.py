"""Flusso completo contro un finto WebODM, dentro QGIS 4 senza interfaccia.
Si esegue con l'ambiente QGIS pulito:  python qgis_dev.py test   (o tests/run_qgis.py)."""
import io
import json
import os
import struct
import sys
import tempfile
import time
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

TMP = tempfile.mkdtemp(prefix='w2q_')
os.environ['QGIS_AUTH_DB_DIR_PATH'] = os.path.join(TMP, 'auth')
os.makedirs(os.environ['QGIS_AUTH_DB_DIR_PATH'])

from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsProject, QgsSettings)   # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication, QSettings                                       # noqa: E402

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, os.path.join(TMP, 'settings'))
QCoreApplication.setOrganizationName('w2q_test')
QCoreApplication.setApplicationName('w2q_test')
if os.environ.get('QGIS_PREFIX_PATH'):
    QgsApplication.setPrefixPath(os.environ['QGIS_PREFIX_PATH'], True)
app = QgsApplication([], False)
app.initQgis()

from osgeo import gdal, osr                                                                    # noqa: E402
gdal.UseExceptions()
osr.UseExceptions()
from qgis.PyQt.QtGui import QImage                                                             # noqa: E402
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice                                    # noqa: E402

from fake_webodm import FakeWebODM, PID                                                       # noqa: E402
from webodm2qgis_tools import controller as ctl_mod, i18n                                      # noqa: E402
from webodm2qgis_tools.core import session as sess_mod                                         # noqa: E402
from webodm2qgis_tools.core.models import Server                                               # noqa: E402
from webodm2qgis_tools.loaders import layers, shots_points                                     # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('FAIL', msg)


def wait(cond, timeout=25):
    t0 = time.time()
    while not cond():
        QCoreApplication.processEvents()
        time.sleep(0.005)
        if time.time() - t0 > timeout:
            raise TimeoutError('timeout in attesa')
    QCoreApplication.processEvents()


def idle(ctl):
    wait(lambda: not ctl._working and not ctl._downloads)


from sample_data import *   # noqa: E402,F401,F403


class Hooks(ctl_mod.UiHooks):
    def __init__(self):
        self.msgs, self.crs_calls, self.opened, self.shots_shown, self.sessions_asked = [], [], [], [], 0
        self.crs_answer = None
        self.confirm_answer = True

    def ask_session(self, default_name, default_folder):
        self.sessions_asked += 1
        return sess_mod.Session('Prova import', os.path.join(TMP, 'sessioni'))

    def ask_crs(self, product, alerts, file_crs, project_crs, can_assign):
        self.crs_calls.append((product.key, [a.code for a in alerts], can_assign))
        if self.crs_answer:
            return self.crs_answer(product, alerts)
        return super().ask_crs(product, alerts, file_crs, project_crs, can_assign)

    def confirm(self, text):
        return self.confirm_answer

    def message(self, level, text):
        self.msgs.append((level, text))

    def open_file(self, path):
        self.opened.append(path)

    def show_shot(self, layer, product):
        self.shots_shown.append(product.key)


hooks = Hooks()
ctl = ctl_mod.Controller(hooks)
i18n.set_language('it')

try:
    # ---- connessione ------------------------------------------------------------------------------
    events = []
    ctl.connectionChanged.connect(lambda ok, txt: events.append((ok, txt)))
    ctl.projectsLoaded.connect(lambda p: events.append(('projects', len(p))))
    ctl.connect_server(Server('test', server.url, 'admin'), 'sbagliata')
    wait(lambda: events)
    check(events[0][0] is False and 'password' in events[0][1].lower(), 'password sbagliata: errore chiaro (%s)' % (events,))
    events.clear()
    ctl.connect_server(Server('test', server.url, 'admin'), 'admin')
    wait(lambda: ('projects', 1) in events)
    check(events[0][0] is True, 'collegato')
    check(ctl.projects[0].name == 'Rilievo test', 'progetti letti')

    # ---- progetto e task --------------------------------------------------------------------------
    ctl.select_project(PID)
    wait(lambda: len(ctl.tasks) == 3)
    check({t.name for t in ctl.tasks} == {'Chiesa', 'Ponte', 'Casa'}, 'task letti')
    ctl.select_task(T3)
    wait(lambda: ctl.task is not None)
    check(not ctl.task.completed and ctl.products and all(p.source == 'odm' for p in ctl.products) or not ctl.products,
          'task in elaborazione: nessun prodotto')
    ctl.select_task(T1)
    wait(lambda: ctl.task is not None and ctl.task.id == T1 and ctl.products)
    keys = {p.key for p in ctl.products}
    check({'orthophoto.tif', 'dsm.tif', 'shots.geojson', 'plugin:ortho:ortho_front'} <= keys, 'prodotti ODM + plugin: %s' % keys)
    check(ctl.plugin_present and ctl.plugin_scaled, 'plugin WebODM rilevato, task scalato')
    check(ctl.selection.task_id == T1 and ctl.selection.project_id == PID, 'selezione aggiornata')

    # ---- sessione + ortofoto ----------------------------------------------------------------------
    prod = {p.key: p for p in ctl.products}
    check(not ctl.session.valid(), 'nessuna sessione all\'inizio')
    ctl.load_products([prod['orthophoto.tif']])
    idle(ctl)
    check(hooks.sessions_asked == 1 and ctl.session.name == 'Prova import', 'sessione chiesta una volta')
    root = QgsProject.instance().layerTreeRoot()
    grp = root.findGroup('Prova import')
    check(grp is not None and len(grp.findLayers()) == 1, 'gruppo col nome della sessione con 1 layer')
    ortho_path = os.path.join(TMP, 'sessioni', 'Prova import', 'Chiesa_aaaaaaaa', 'raster', 'orthophoto.tif')
    check(os.path.isfile(ortho_path), 'file nella cartella della sessione: %s' % ortho_path)
    check(not os.path.exists(ortho_path + '.part'), 'nessun .part rimasto')
    lay = grp.findLayers()[0].layer()
    check(lay.isValid() and lay.crs().authid() == 'EPSG:32632', 'raster valido in EPSG:32632')
    check(QgsProject.instance().crs().authid() == 'EPSG:32632', 'progetto vuoto: adotta il CRS del prodotto')
    check(os.path.isfile(os.path.join(TMP, 'sessioni', 'Prova import', 'sessione.json')), 'manifesto della sessione')
    n_dl = server.count('/download/orthophoto.tif')
    ctl.load_products([prod['orthophoto.tif']])
    idle(ctl)
    check(server.count('/download/orthophoto.tif') == n_dl + 1, 'secondo caricamento: solo il controllo, niente nuovo scarico '
                                                              '(richieste %d -> %d)' % (n_dl, server.count('/download/orthophoto.tif')))

    # ---- CRS diverso dal progetto: avviso con scelte ---------------------------------------------
    hooks.crs_calls.clear()
    ctl.load_products([prod['dsm.tif']])
    idle(ctl)
    check(hooks.crs_calls and 'C02' in hooks.crs_calls[0][1], 'DSM in UTM33 con progetto UTM32: avviso C02 (%s)' % hooks.crs_calls)
    check(QgsProject.instance().crs().authid() == 'EPSG:32632', 'scelta predefinita: riproiettare al volo, CRS progetto invariato')

    # ---- nuvola senza CRS: blocco, l'utente assegna l'EPSG ----------------------------------------
    hooks.crs_calls.clear()
    hooks.crs_answer = lambda p, a: ctl_mod.Decision(True, assign_crs=QgsCoordinateReferenceSystem('EPSG:32632'))
    las_prod = prod['georeferenced_model.las']
    ctl.load_products([las_prod])
    idle(ctl)
    pc_layers = [n.layer() for n in grp.findLayers() if n.layer().name().startswith('Nuvola')]
    check(os.path.isfile(os.path.join(TMP, 'sessioni', 'Prova import', 'Chiesa_aaaaaaaa', 'nuvola', 'georeferenced_model.las')),
          'nuvola scaricata')
    if pc_layers:
        check(hooks.crs_calls and 'C03' in hooks.crs_calls[0][1], 'nuvola senza CRS: blocco C03 (%s)' % hooks.crs_calls)
        check(pc_layers[0].crs().authid() == 'EPSG:32632', 'EPSG assegnato dall\'utente applicato')
    else:
        print('NOTA: provider nuvole di punti non ha aperto il LAS sintetico:', [m for m in hooks.msgs if 'Nuvola' in m[1]][-1:])
    hooks.crs_answer = None

    # ---- punti di scatto ---------------------------------------------------------------------------
    ctl.load_products([prod['shots.geojson']])
    idle(ctl)
    ph = [n.layer() for n in grp.findLayers() if shots_points.is_photos_layer(n.layer())]
    check(len(ph) == 1, 'layer foto creato')
    pl = ph[0]
    check(pl.featureCount() == 2, 'una feature ostile scartata (%d)' % pl.featureCount())
    check(pl.crs().authid() == 'EPSG:4326', 'foto in EPSG:4326')
    check(pl.fields().indexOf('originale') >= 0 and pl.fields().indexOf('azimut') >= 0, 'campi')
    check(len(pl.actions().actions()) == 2 and pl.actions().defaultAction('Canvas').isValid(), 'azioni e azione predefinita')
    check(pl.customProperty('webodm2qgis/task_id') == T1, 'proprieta del layer')
    f1 = next(f for f in pl.getFeatures() if f['nome_file'] == 'IMG1.jpg')
    check(f1['originale'] == '?' and abs(f1['quota'] - 31.0) < 1e-9 and f1['inclin'] is not None, 'attributi foto')
    check(os.path.join('Prova import', 'Chiesa_aaaaaaaa', 'foto', 'foto.gpkg') in pl.source().replace('/', os.sep), 'gpkg nella sessione')

    # ---- foto nel riferimento del modello trasformato dal plugin WebODM ------------------------------
    check({'shots.geojson:georef', 'shots.geojson:scaled'} <= set(prod), 'prodotti foto del plugin offerti')
    ctl.load_products([prod['shots.geojson:georef']])
    idle(ctl)
    pg = [n.layer() for n in grp.findLayers() if shots_points.is_photos_layer(n.layer()) and n.layer().name().endswith('georiferite')]
    check(len(pg) == 1, 'layer foto georiferite create')
    if pg:
        check(pg[0].crs().authid() == 'EPSG:32632', 'foto georiferite in EPSG:32632')
        fg = next(f for f in pg[0].getFeatures() if f['nome_file'] == 'IMG1.jpg')
        q = fg.geometry().asPoint()
        check(abs(q.x() - 499996.0) < 1e-6 and abs(q.y() - 4000002.0) < 1e-6, 'IMG1 = matrice assoluta . translation: (%s, %s)' % (q.x(), q.y()))
        check(abs(fg['quota'] - 60.0) < 1e-6, 'quota trasformata')
    ctl.load_products([prod['shots.geojson:scaled']])
    idle(ctl)
    loc_g = grp.findGroup(ctl_mod.LOCAL_GROUP)
    ps = [n for n in (loc_g.findLayers() if loc_g else []) if n.layer().name().endswith('scalate')]
    check(len(ps) == 1 and ps[0].layer().crs() == layers.local_crs() and not ps[0].isVisible(),
          'foto scalate: CRS locale, nel sottogruppo, spente')
    if ps:
        fs = next(f for f in ps[0].layer().getFeatures() if f['nome_file'] == 'IMG1.jpg')
        q = fs.geometry().asPoint()
        check(abs(q.x() - 2.0) < 1e-6 and abs(q.y() - 4.0) < 1e-6, 'IMG1 scalata = 2 x translation: (%s, %s)' % (q.x(), q.y()))
    ph_original = [n.layer() for n in grp.findLayers() if shots_points.is_photos_layer(n.layer())
                   and n.layer().name().endswith('Chiesa')]
    check(len(ph_original) == 1 and ph_original[0].crs().authid() == 'EPSG:4326', 'le foto originali restano in lon/lat')

    # ---- apri originale ----------------------------------------------------------------------------
    hooks.opened.clear()
    ctl.open_original(pl.id(), f1.id())
    wait(lambda: hooks.opened)
    check(os.path.isfile(hooks.opened[0]) and 'originali' in hooks.opened[0], 'originale scaricato in sessione/foto/originali')
    check(pl.getFeature(f1.id())['originale'] == 'si', 'campo originale = si')
    hooks.opened.clear()
    n_img = server.count('/images/download/IMG1.jpg')
    ctl.open_original(pl.id(), f1.id())
    check(hooks.opened and server.count('/images/download/IMG1.jpg') == n_img, 'seconda apertura: dalla copia, senza rete')
    f2 = next(f for f in pl.getFeatures() if f['nome_file'] == 'IMG2.jpg')
    hooks.opened.clear()
    hooks.msgs.clear()
    ctl.open_original(pl.id(), f2.id())
    wait(lambda: any('non e\' sul server' in m[1] for m in hooks.msgs))
    check(not hooks.opened and pl.getFeature(f2.id())['originale'] == 'no', 'originale assente: campo no, nessuna apertura')
    # cartella locale di ripiego
    locdir = os.path.join(TMP, 'fotolocali')
    os.makedirs(locdir)
    open(os.path.join(locdir, 'IMG2.JPG'), 'wb').write(jpeg(0xff00ff00))
    pl.setCustomProperty('webodm2qgis/photos_dir', locdir)
    ctl.open_original(pl.id(), f2.id())
    check(hooks.opened and hooks.opened[-1].lower().endswith('img2.jpg') and pl.getFeature(f2.id())['originale'] == 'si',
          'ripiego sulla cartella locale')
    # miniatura
    thumb = []
    ctl.photo_thumbnail(pl.id(), f1.id(), 128, thumb.append)
    wait(lambda: thumb)
    check(thumb[0] and thumb[0][:2] == b'\xff\xd8', 'miniatura JPEG dal server')
    # verifica massiva
    pl.setCustomProperty('webodm2qgis/photos_dir', '')
    res = []
    ctl.verify_originals(pl.id(), done_cb=lambda y, n: res.append((y, n)))
    wait(lambda: res)
    check(res[0] == (1, 1), 'verifica massiva: 1 si, 1 no (%s)' % (res[0],))

    # ---- export del plugin WebODM: nuvola georiferita e nuvola scalata -----------------------------
    check(ctl.plugin_epsg == 32632, 'EPSG del georiferimento del plugin letto')
    geo_p = prod['plugin:out:georeferenced_model.laz']
    loc_p = prod['plugin:out:scaled_model.laz']
    check(geo_p.meta.get('epsg') == 32632 and 'EPSG:32632' in geo_p.label, 'nuvola georiferita riconosciuta: %s' % geo_p.label)
    check(loc_p.meta.get('local') and geo_p.kind == 'pointcloud', 'nuvola scalata = coordinate locali')
    hooks.crs_calls.clear()
    hooks.msgs.clear()
    ctl.load_products([geo_p])
    idle(ctl)
    gl = [n.layer() for n in grp.findLayers() if n.layer().name().startswith('Nuvola georiferita')]
    if gl:
        check(gl[0].crs().authid() == 'EPSG:32632', 'nuvola georiferita: EPSG del plugin assegnato (%s)' % gl[0].crs().authid())
        check(not any('C03' in c[1] for c in hooks.crs_calls), 'nessun blocco C03 per la nuvola georiferita dal plugin')
        check(any('assegnato dal georiferimento' in m[1] for m in hooks.msgs), "messaggio sull'EPSG assegnato")
    else:
        check(False, 'nuvola georiferita non caricata: %s' % hooks.msgs[-3:])
    hooks.crs_calls.clear()
    ctl.load_products([loc_p])
    idle(ctl)
    sub0 = grp.findGroup(ctl_mod.LOCAL_GROUP)
    ll = [n for n in (sub0.findLayers() if sub0 else []) if n.layer().name().startswith('Nuvola scalata')]
    check(len(ll) == 1 and ll[0].layer().crs() == layers.local_crs() and not ll[0].isVisible(),
          'nuvola scalata in CRS locale, nel sottogruppo, spenta')
    check(any('P05' in c[1] for c in hooks.crs_calls), 'avviso P05 per la nuvola non georiferita')

    # ---- scatti / prospetti ------------------------------------------------------------------------
    ctl.load_products([prod['plugin:ortho:ortho_front']])
    idle(ctl)
    sub = grp.findGroup(ctl_mod.LOCAL_GROUP)
    fac = [n for n in (sub.findLayers() if sub else []) if n.layer().name().startswith('Facciata')]
    check(len(fac) == 1, 'prospetto nel sottogruppo CRS locale (insieme alla nuvola scalata)')
    sl = fac[0].layer()
    check(sl.crs() == layers.local_crs() and sl.crs().authid() == '', 'prospetto in CRS locale (non un EPSG terrestre)')
    check(not fac[0].isVisible(), 'prospetto spento di default')
    check(hooks.shots_shown == ['plugin:ortho:ortho_front'], 'visualizzatore dedicato richiesto')
    check(any('P01' in c[1] for c in hooks.crs_calls), 'avviso P01 per il prospetto')
    check(os.path.isfile(os.path.join(TMP, 'sessioni', 'Prova import', 'Chiesa_aaaaaaaa', 'scatti', 'ortho_front.points')),
          'file .points scaricato accanto')

    # ---- posizionare il prospetto sul canvas ------------------------------------------------------
    pk = 'plugin:ortho:ortho_front'
    size = ctl.shot_size_m(pk)
    check(size is not None and size[0] > 0, 'dimensioni dello scatto note: %s' % (size,))
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem('EPSG:32632'))
    before = len(QgsProject.instance().mapLayers())
    new = ctl.place_shot(pk, 500000.0, 4000000.0)
    check(new is not None and len(QgsProject.instance().mapLayers()) == before + 1, 'copia posizionata caricata')
    if new is not None:
        e = new.extent()
        check(new.crs().authid() == 'EPSG:32632', 'posizionato nel CRS del progetto (%s)' % new.crs().authid())
        check(abs(e.xMinimum() - 500000.0) < 1e-6 and abs(e.yMaximum() - 4000000.0) < 1e-6,
              'angolo in alto a sinistra sul punto scelto: %s' % e.toString(3))
        check(abs(e.width() - size[0]) < 1e-6 and abs(e.height() - size[1]) < 1e-6, 'dimensioni conservate')
        check(new.source().lower().endswith('.vrt') and os.path.getsize(new.source()) < 20000, 'file VRT leggero, nessun dato copiato')
    orig = ctl.shot_layer(pk)
    check(orig is not None and orig.crs() == layers.local_crs(), 'originale rimasto in CRS locale')
    new2 = ctl.place_shot(pk, 1.0, 2.0)
    check(new2 is not None and new2.source() != new.source(), "secondo posizionamento: altro file, il primo non e' sovrascritto")
    hooks.msgs.clear()
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    check(ctl.place_shot(pk, 1.0, 2.0) is None and any('gradi' in m[1] for m in hooks.msgs), 'CRS del progetto in gradi: rifiutato con messaggio')
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem('EPSG:32632'))
    check(ctl.place_shot('chiave-inesistente', 1.0, 2.0) is None, 'scatto non caricato: nessun posizionamento')

    # ---- mesh e archivio ostile --------------------------------------------------------------------
    hooks.msgs.clear()
    ctl.load_products([prod['textured_model.zip']])
    idle(ctl)
    check(os.path.isfile(os.path.join(TMP, 'sessioni', 'Prova import', 'Chiesa_aaaaaaaa', 'mesh', 'textured_model',
                                      'odm_texturing', 'odm_textured_model_geo.obj')), 'zip della mesh estratto')
    hooks.msgs.clear()
    ctl.load_products([prod['all.zip']])
    idle(ctl)
    check(any('non decomprimibile' in m[1] for m in hooks.msgs), 'zip con percorso ostile rifiutato')
    check(not os.path.exists(os.path.join(TMP, 'sessioni', 'Prova import', 'fuori.txt')), 'niente scritto fuori dalla sessione')

    # ---- task non georiferito ----------------------------------------------------------------------
    ctl.select_task(T2)
    wait(lambda: ctl.task is not None and ctl.task.id == T2 and ctl.products)
    check(not ctl.plugin_scaled, 'task 2 non scalato')
    hooks.crs_calls.clear()
    p2 = {p.key: p for p in ctl.products}
    ctl.load_products([p2['orthophoto.tif']])
    idle(ctl)
    check(hooks.crs_calls and 'C01' in hooks.crs_calls[0][1], 'task non georiferito: avviso C01 (%s)' % hooks.crs_calls)
    check(os.path.isdir(os.path.join(TMP, 'sessioni', 'Prova import', 'Ponte_bbbbbbbb')), 'cartelle separate per task')
    # foto di un task NON georiferito: seguono il modello (translation nel CRS dell'ortofoto), non finiscono a 0,0
    ctl.load_products([p2['shots.geojson']])
    idle(ctl)
    g2 = QgsProject.instance().layerTreeRoot().findGroup('Prova import')
    ph2 = [n.layer() for n in g2.findLayers() if shots_points.is_photos_layer(n.layer())
           and n.layer().customProperty('webodm2qgis/task_id') == T2]
    check(len(ph2) == 1, 'layer foto del task non georiferito creato')
    if ph2:
        pl2 = ph2[0]
        ortho2 = [n.layer() for n in g2.findLayers() if n.layer().name().startswith('Ortofoto (GeoTIFF)') and
                  n.layer().customProperty('webodm2qgis/task_id') == T2]
        check(ortho2 and pl2.crs() == ortho2[0].crs(), 'foto nello stesso CRS dell ortofoto del task: %s' % pl2.crs().authid())
        f1 = next(f for f in pl2.getFeatures() if f['nome_file'] == 'IMG1.jpg')
        pt = f1.geometry().asPoint()
        check(abs(pt.x() - 1.0) < 1e-9 and abs(pt.y() - 2.0) < 1e-9, 'posizione = translation (1, 2), non gradi: (%s, %s)' % (pt.x(), pt.y()))
        check(abs(f1['quota'] - 30.0) < 1e-9, 'quota = z locale')
    # utente rifiuta
    hooks.crs_answer = lambda p, a: ctl_mod.Decision(False)
    n_layers = len(QgsProject.instance().mapLayers())
    ctl.load_products([p2['orthophoto.tif']])
    idle(ctl)
    check(len(QgsProject.instance().mapLayers()) == n_layers, "rifiuto dell'utente: nessun layer aggiunto")
    hooks.crs_answer = None

    # ---- sessione nel progetto QGIS ----------------------------------------------------------------
    ctl.save_to_project()
    ctl.selection = ctl_mod.Selection()
    ctl.session = sess_mod.Session()
    sel = ctl.restore_from_project()
    check(sel.task_id == T2 and sel.session_name == 'Prova import' and ctl.session.valid(), 'sessione e task ripristinati dal .qgz')
    check(ctl.session.folder == os.path.join(TMP, 'sessioni'), 'cartella della sessione ripristinata')

    # ---- ripresa del download ----------------------------------------------------------------------
    ctl.select_task(T1)
    wait(lambda: ctl.task is not None and ctl.task.id == T1 and ctl.products)
    pr = {p.key: p for p in ctl.products}
    dest = ctl.session.file_path(ctl.task.label, ctl.task.id, 'documenti', 'report.pdf')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    full = files[(T1, 'report.pdf')]
    open(dest + '.part', 'wb').write(full[:5])
    server.log.clear()
    hooks.opened.clear()
    ctl.load_products([pr['report.pdf']])
    idle(ctl)
    check(open(dest, 'rb').read() == full, 'download ripreso: contenuto identico')
    check(any(r == 'bytes=5-' for r in server.ranges()), 'richiesta Range inviata')

    # ---- server che sparisce -----------------------------------------------------------------------
    ctl.client.base = 'http://127.0.0.1:1'        # porta chiusa (il finto server tiene vive le connessioni aperte)
    events.clear()
    errs = []
    hooks.message = lambda level, text: errs.append((level, text))
    ctl.select_task(T2)
    wait(lambda: errs)
    check(errs and errs[0][0] == 'crit', 'server spento: errore segnalato, nessun blocco')
finally:
    try:
        server.stop()
    except Exception:
        pass
    app.exitQgis()

print('FALLITI: %d' % len(FAILS) if FAILS else 'test_integration: tutto ok')
sys.exit(1 if FAILS else 0)
