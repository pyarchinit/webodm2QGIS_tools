"""Nucleo puro (niente QGIS): sicurezza, URL, catalogo, avvisi CRS, foto, selezione.
Esegui: python tests/test_core.py"""
import json
import math
import os
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from webodm2qgis_tools import i18n                                    # noqa: E402
from webodm2qgis_tools.core import catalog, crs_guard, photos, safety, selection, urls   # noqa: E402
from webodm2qgis_tools.core.models import CrsInfo, Product, Task, Project   # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('FAIL', msg)


def codes(alerts):
    return sorted(set(a.code for a in alerts))


# ---- safety ---------------------------------------------------------------------------------------
for bad in ['../x.jpg', '..\\x.jpg', '/etc/passwd', 'C:\\x.jpg', 'a/b.jpg', '', '   ', '.hidden.jpg', 'x.jpg.',
            'con.jpg', 'a\x00b.jpg', 'a:b.jpg', 'x' * 300 + '.jpg', None, 5]:
    check(safety.safe_filename(bad, safety.IMAGE_EXT) is None, 'nome ostile accettato: %r' % (bad,))
for good in ['IMG_0001.JPG', 'foto (1).jpeg', "l'ultima.png", 'DJI_0001.DNG']:
    check(safety.safe_filename(good, safety.IMAGE_EXT) == good, 'nome valido rifiutato: %r' % good)
check(safety.safe_filename('a.exe', safety.IMAGE_EXT) is None, 'estensione non ammessa')
check(safety.safe_filename('a.exe') == 'a.exe', 'senza filtro estensioni')

d = tempfile.mkdtemp()
check(safety.safe_join(d, 'a', 'b.txt') is not None, 'safe_join ok')
check(safety.safe_join(d, '..', 'x') is None, 'safe_join fuori base')
zp = os.path.join(d, 'ok.zip')
with zipfile.ZipFile(zp, 'w') as z:
    z.writestr('odm_texturing/model.obj', 'v 0 0 0')
files = safety.extract_zip_safe(zp, os.path.join(d, 'out'))
check(len(files) == 1 and os.path.isfile(files[0]), 'zip normale estratto')
for evil in ['../evil.txt', '/abs.txt', 'C:/abs.txt', 'a/../../evil.txt']:
    zp2 = os.path.join(d, 'evil.zip')
    with zipfile.ZipFile(zp2, 'w') as z:
        z.writestr(evil, 'x')
    try:
        safety.extract_zip_safe(zp2, os.path.join(d, 'out2'))
        check(False, 'zip slip non fermato: %s' % evil)
    except ValueError:
        pass
check(not os.path.exists(os.path.join(d, 'evil.txt')), 'file scritto fuori dalla cartella')

# ---- urls -----------------------------------------------------------------------------------------
check(urls.normalize_base_url('localhost:29800/') == 'http://localhost:29800', 'normalizza host:porta')
check(urls.normalize_base_url('https://x.org/odm/api/') == 'https://x.org/odm', 'toglie /api finale')
for bad in ['', 'ftp://x', 'http://', 'file:///c:/x']:
    try:
        urls.normalize_base_url(bad)
        check(False, 'url accettato: %r' % bad)
    except ValueError:
        pass
check(urls.is_local_host('http://127.0.0.1:8000') and urls.is_local_host('http://localhost'), 'host locale')
check(not urls.is_local_host('http://odm.example.org'), 'host remoto')
check(urls.plain_http_remote('http://odm.example.org') and not urls.plain_http_remote('https://odm.example.org')
      and not urls.plain_http_remote('http://localhost:29800'), 'http in chiaro verso remoto')
check(urls.task_api(7, 'f4742737-352c-4618-b2a9-5f9f0082dfd9', 'x') ==
      '/api/projects/7/tasks/f4742737-352c-4618-b2a9-5f9f0082dfd9/x', 'task_api')
for bad_id in ['../x', 'a b', '', 'zz;rm']:
    try:
        urls.task_api(7, bad_id)
        check(False, 'task id accettato: %r' % bad_id)
    except ValueError:
        pass
check('/' not in urls.server_key('http://localhost:29800') and ':' not in urls.server_key('http://localhost:29800'),
      'server_key sicuro')

# ---- catalogo -------------------------------------------------------------------------------------
TID = 'f4742737-352c-4618-b2a9-5f9f0082dfd9'
task = Task.from_json({'id': TID, 'name': 'Rilievo', 'status': 40, 'epsg': None, 'images_count': 26,
                       'available_assets': ['orthophoto.tif', 'dsm.tif', 'georeferenced_model.laz', 'shots.geojson',
                                            'textured_model.zip', 'report.pdf', 'all.zip', 'strano.bin']}, 7)
check(not task.georeferenced and task.completed, 'task non georiferito')
ps = catalog.odm_products(task)
byk = {p.key: p for p in ps}
check(byk['orthophoto.tif'].kind == 'raster' and byk['georeferenced_model.laz'].kind == 'pointcloud', 'tipi')
check(byk['shots.geojson'].kind == 'photos' and byk['strano.bin'].group == 'Altro', 'foto e sconosciuto')
check('orthophoto.xyz' in byk, 'streaming virtuale')
check(byk['dsm.tif'].path == '/api/projects/7/tasks/%s/download/dsm.tif' % TID, 'percorso download')

exp = {'state': 'done', 'files': [{'name': 'scaled_model.laz', 'url': '/api/projects/7/tasks/%s/assets/scaling_tool/out/scaled_model.laz' % TID},
                                  {'name': '../evil.laz', 'url': '/api/x'},
                                  {'name': 'cartella/../evil.laz', 'url': '/api/x'},
                                  {'name': 'x.laz', 'url': 'http://evil.example/x.laz'},
                                  {'name': 'scaled_textured_model/model.obj', 'url': '/api/y'}]}
pe = catalog.plugin_export_products(exp)
check([p.filename for p in pe] == ['scaled_model.laz', 'model.obj'], 'export: solo file sicuri con URL interno')
check(pe[1].meta['subdir'] == 'scaled_textured_model', 'export: sottocartella conservata')
base = '/api/projects/7/tasks/%s/assets/scaling_tool/ortho/' % TID
ortho = {'results': [
    {'name': 'ortho_a', 'view': 'front', 'epsg': None, 'files': [{'name': 'ortho_a.tif', 'url': base + 'ortho_a.tif'},
                                                              {'name': 'ortho_a.png', 'url': base + 'ortho_a.png'},
                                                              {'name': 'ortho_a_preview.jpg', 'url': base + 'ortho_a_preview.jpg'}]},
    {'name': 'ortho_b', 'view': 'top', 'epsg': 32632, 'title': 'Pianta', 'scale': 100, 'dpi': 150,
     'files': [{'name': 'ortho_b.tif', 'url': base + 'ortho_b.tif'}]},
    {'name': 'ortho_c', 'files': []}, 'spazzatura']}
sh = catalog.plugin_shot_products(ortho)
check(len(sh) == 2 and sh[0].kind == 'shot' and len(sh[0].extra_files) == 2, 'scatti dal plugin')
check(sh[1].label == 'Pianta', 'titolo dello scatto')
all_p = catalog.build(task, exp, ortho)
check([g for g, _ in catalog.grouped(all_p)][0] == 'Ortofoto', 'ordine gruppi')
check(catalog.grouped(all_p)[-1][0] == 'Altro', 'Altro in fondo')

# ---- avvisi CRS -----------------------------------------------------------------------------------
geo = Task.from_json({'id': TID, 'name': 'g', 'status': 40, 'epsg': 32632, 'available_assets': []}, 7)
ortho_p = Product(key='orthophoto.tif', label='o', group='Ortofoto', kind='raster', filename='orthophoto.tif')
pc_p = Product(key='georeferenced_model.laz', label='l', group='Nuvola di punti', kind='pointcloud',
               filename='georeferenced_model.laz')
c32 = CrsInfo('EPSG:32632', True, False, 'WGS 84 / UTM 32N')
c32b = CrsInfo('EPSG:32633', True, False, 'WGS 84 / UTM 33N')
c4326 = CrsInfo('EPSG:4326', True, True, 'WGS 84')
none = CrsInfo('', False)

check('C01' in codes(crs_guard.predict(ortho_p, task)), 'C01 task non georiferito')
check('C01' not in codes(crs_guard.predict(ortho_p, geo)), 'niente C01 se georiferito')
check(crs_guard.traffic_light(crs_guard.predict(ortho_p, task)) == 'yellow', 'semaforo giallo')
check(crs_guard.traffic_light(crs_guard.predict(ortho_p, geo)) == 'green', 'semaforo verde')
a = crs_guard.check(ortho_p, geo, c32, c32, True)
check(codes(a) == [], 'tutto coerente: nessun avviso, era %s' % codes(a))
a = crs_guard.check(ortho_p, geo, c32, c32b, True)
check('C02' in codes(a) and a[-1].choices, 'C02 CRS diverso dal progetto con scelte')
a = crs_guard.check(ortho_p, geo, c32, c32b, False)
check([x.level for x in a if x.code == 'C02'] == ['info'], 'C02 info se progetto vuoto')
a = crs_guard.check(ortho_p, geo, none, c32, True)
check('C03' in codes(a) and crs_guard.traffic_light(a) == 'red', 'C03 file senza CRS = blocco')
a = crs_guard.check(ortho_p, geo, c32b, c32b, True)
check('C04' in codes(a), 'C04 EPSG del task diverso da quello del file')
a = crs_guard.check(ortho_p, geo, c4326, c4326, True)
check('C05' in codes(a), 'C05 CRS geografico per un raster')
a = crs_guard.check(ortho_p, geo, c32, c32, True, distance_km=800)
check('C10' in codes(a), 'C10 prodotto lontano')
a = crs_guard.check(ortho_p, geo, c32, c32, True, size_bytes=5 * 1024 ** 3, free_bytes=1024 ** 3)
check([x.level for x in a if x.code == 'C11'] == ['info', 'warn'], 'C11 grande e poco spazio')
a = crs_guard.check(pc_p, geo, c32, c32, True)
check('C07' in codes(a), 'C07 quote senza datum verticale')
a = crs_guard.check(pc_p, geo, c32, c32, True, plugin_scaled=True)
check('C08' in codes(a), 'C08 originale mentre esiste la versione scalata')
a = crs_guard.check(CrsInfo and Product(key='k', label='k', group='g', kind='raster', filename='x.tif'), geo,
                    CrsInfo('EPSG:32632', True, False, '', problem='griglia mancante'), c32, True)
check('C06' in codes(a), 'C06 problema PROJ')
photos_p = Product(key='shots.geojson', label='f', group='Foto', kind='photos', filename='shots.geojson')
check(codes(crs_guard.check(photos_p, task, c4326, c32, True)) == ['C12', 'P10'], 'foto di task non georiferito: C12+P10 (posizione dal modello)')
check(codes(crs_guard.check(photos_p, geo, c4326, c32, True)) == ['C12'], 'foto di task georiferito: solo C12')
front = Product(key='s', label='s', group='Scatti e prospetti', kind='shot', filename='a.tif',
                meta={'view': 'front', 'epsg': None}, source='plugin')
a = crs_guard.check(front, geo, none, c32, True)
check(codes(a) == ['P01'], 'prospetto: solo P01 (nessun confronto con CRS terrestri), era %s' % codes(a))
top = Product(key='s', label='s', group='Scatti e prospetti', kind='shot', filename='a.tif',
              meta={'view': 'top', 'epsg': 32632, 'scale': 100, 'dpi': 150}, source='plugin')
check(codes(crs_guard.check(top, geo, c32, c32, True)) == ['P02', 'P04'], 'pianta georiferita in scala: P02+P04')
top2 = Product(key='s', label='s', group='x', kind='shot', filename='a.tif', meta={'view': 'top', 'epsg': None}, source='plugin')
check('P03' in codes(crs_guard.check(top2, task, none, c32, True)), 'pianta non georiferita: P03')
check(crs_guard.needs_dialog(crs_guard.predict(ortho_p, task)) and not crs_guard.needs_dialog(crs_guard.predict(ortho_p, geo)),
      'needs_dialog')

# ---- foto -----------------------------------------------------------------------------------------
gj = {'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'properties': {'filename': 'IMG1.jpg', 'camera': 'cam', 'focal': 0.7, 'width': 4000, 'height': 3000,
                                       'capture_time': 1790844232.5, 'translation': [1.0, 2.0, 30.0], 'rotation': [0, 0, 0]},
     'geometry': {'type': 'Point', 'coordinates': [11.5, 44.5, 31.0]}},
    {'type': 'Feature', 'properties': {'filename': '../evil.jpg'}, 'geometry': {'type': 'Point', 'coordinates': [1, 1, 1]}},
    {'type': 'Feature', 'properties': {'filename': 'a.jpg'}, 'geometry': {'type': 'Point', 'coordinates': [999, 1, 1]}},
    {'type': 'Feature', 'properties': {'filename': 'b.exe'}, 'geometry': {'type': 'Point', 'coordinates': [1, 1, 1]}},
    {'type': 'Feature', 'properties': {'filename': 'c.jpg'}, 'geometry': None},
    'spazzatura']}
shots, skipped = photos.parse_shots(gj)
check(len(shots) == 1 and skipped == 5, 'parse_shots: 1 valida, 5 scartate (%d, %d)' % (len(shots), skipped))
s = shots[0]
check(s.filename == 'IMG1.jpg' and s.alt == 31.0 and s.position == [1.0, 2.0, 30.0], 'campi della foto')
# rotazione nulla: la camera guarda lungo +Z del mondo => verso l'alto in questo riferimento
az, tilt = photos.orientation([0, 0, 0])
check(az is None and abs(tilt - 180) < 1e-6, 'rotazione nulla')
# camera nadirale tipica: rotazione di 180 gradi attorno a x => asse ottico -Z (verso il basso)
az, tilt = photos.orientation([math.pi, 0, 0])
check(abs(tilt) < 1e-6, 'nadir: inclinazione 0, era %s' % tilt)
az, tilt = photos.orientation([math.pi / 2, 0, 0])      # 90 gradi: orizzontale
check(abs(tilt - 90) < 1e-6 and az is not None, 'orizzontale')
check(photos.parse_shots(None) == ([], 0) and photos.parse_shots({'features': 5}) == ([], 0), 'input sporco')

d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, 'sotto'))
open(os.path.join(d, 'sotto', 'IMG9.JPG'), 'wb').close()
open(os.path.join(d, 'IMG1.jpg'), 'wb').close()
check(photos.find_local(d, 'IMG1.jpg') == os.path.join(d, 'IMG1.jpg'), 'foto locale diretta')
check(photos.find_local(d, 'img9.jpg') == os.path.join(d, 'sotto', 'IMG9.JPG'), 'foto locale in sottocartella, maiuscole')
check(photos.find_local(d, 'manca.jpg') is None and photos.find_local('', 'IMG1.jpg') is None, 'foto locale assente')
check(photos.find_local(d, '../x.jpg') is None, 'foto locale: nome ostile')

# ---- selezione ------------------------------------------------------------------------------------
sel = selection.Selection('http://localhost:29800', 7, TID, 'C:/foto')
check(selection.Selection.from_json(sel.to_json()) == sel and sel.complete(), 'selezione andata e ritorno')
check(not selection.Selection.from_json('{rotto').complete(), 'selezione rovinata tollerata')
check(selection.Selection.from_json(None) == selection.Selection(), 'selezione vuota')
tasks = [Task.from_json({'id': 'aaaaaaaa-0000', 'name': 'Chiesa', 'status': 40, 'created_at': '2026-01-01'}, 1),
         Task.from_json({'id': 'bbbbbbbb-0000', 'name': 'Ponte', 'status': 20, 'created_at': '2026-02-01'}, 1)]
check([t.name for t in selection.filter_tasks(tasks)] == ['Ponte', 'Chiesa'], 'task ordinati dal piu\' recente')
check([t.name for t in selection.filter_tasks(tasks, only_completed=True)] == ['Chiesa'], 'solo completati')
check([t.name for t in selection.filter_tasks(tasks, 'pon')] == ['Ponte'], 'ricerca per nome')
check(len(selection.filter_projects([Project(1, 'A b'), Project(2, 'C')], 'a')) == 1, 'ricerca progetti')

# ---- foto nel riferimento del modello trasformato dal plugin ---------------------------------------
ms, _sk = photos.parse_shots(gj)
rot90 = [[0, -2, 0, 500000], [2, 0, 0, 4000000], [0, 0, 2, 0], [0, 0, 0, 1]]      # scala 2, rotazione 90 gradi, traslazione
moved = photos.apply_matrix(ms, rot90)
check(abs(moved[0].position[0] - (500000 - 4)) < 1e-9 and abs(moved[0].position[1] - (4000000 + 2)) < 1e-9
      and abs(moved[0].alt - 60) < 1e-9, 'posizione foto = M . translation')
check(ms[0].position == [1.0, 2.0, 30.0], 'foto originali non modificate')
horiz = [s for s in photos.parse_shots({'features': [{'type': 'Feature', 'properties': {
    'filename': 'h.jpg', 'translation': [0, 0, 0], 'rotation': [math.pi / 2, 0, 0]},
    'geometry': {'type': 'Point', 'coordinates': [1, 1, 1]}}]})[0]]
az0 = horiz[0].azimuth
az1 = photos.apply_matrix(horiz, rot90)[0].azimuth
check(abs(((az0 - az1) % 360) - 90) < 1e-6, 'rotazione di 90 gradi del modello = azimut ruotato di 90 (%s -> %s)' % (az0, az1))
check(abs(photos.apply_matrix(horiz, rot90)[0].tilt - horiz[0].tilt) < 1e-6, 'la scala non cambia l inclinazione')
for badm in (None, [[1, 0, 0]], [[1, 0, 0, 0]] * 3 + [[0, 0, 0, float('nan')]], 'x'):
    check(not photos.valid_matrix(badm), 'matrice non valida rifiutata: %r' % (badm,))
try:
    photos.apply_matrix(ms, [[1]])
    check(False, 'apply_matrix con matrice sbagliata')
except ValueError:
    pass
tk = Task.from_json({'id': TID, 'name': 'g', 'status': 40, 'epsg': 32632, 'available_assets': ['shots.geojson']}, 7)
pp = catalog.plugin_photo_products(tk, [[1, 0, 0, 0]] * 3 + [[0, 0, 0, 1]], rot90, 32632)
check([p.key for p in pp] == ['shots.geojson:georef', 'shots.geojson:scaled'], 'due prodotti foto del plugin')
check(pp[0].meta['epsg'] == 32632 and pp[1].meta['local'], 'meta dei prodotti foto del plugin')
check(catalog.plugin_photo_products(tk) == [] and
      catalog.plugin_photo_products(Task.from_json({'id': TID, 'available_assets': []}, 7), rot90, rot90, 1) == [],
      'senza matrici o senza shots.geojson: nessun prodotto')

# ---- sessione di import ---------------------------------------------------------------------------
from webodm2qgis_tools.core import session as sess   # noqa: E402

check(sess.dirname_of('Chiesa: rilievo/1') == 'Chiesa_ rilievo_1', 'nome sessione -> cartella')
check(sess.dirname_of('  ..  ') == 'sessione' and sess.dirname_of('CON') == 'sessione', 'nomi vuoti/riservati')
check(len(sess.dirname_of('x' * 500)) == 80, 'nome troppo lungo')
base_dir = tempfile.mkdtemp()
se = sess.Session('Rilievo ottobre', base_dir)
check(se.valid() and se.root == os.path.realpath(os.path.join(base_dir, 'Rilievo ottobre')), 'root della sessione')
check(not sess.Session('', base_dir).valid() and not sess.Session('x', '').valid(), 'sessione non valida')
check(sess.Session('x', '').root is None and sess.Session('x', '').task_dir('a', 'b') is None, 'root None se non valida')
td = se.task_dir('Chiesa', 'f4742737-352c-4618-b2a9-5f9f0082dfd9')
check(td.endswith('Chiesa_f4742737'), 'cartella del task')
check(se.task_dir('Chiesa', 'aaaaaaaa-1') != se.task_dir('Chiesa', 'bbbbbbbb-1'), 'task omonimi in cartelle diverse')
check(se.file_path('Chiesa', 'aaaaaaaa-1', 'x.tif').endswith('x.tif'), 'file della sessione')
check(se.file_path('Chiesa', 'aaaaaaaa-1', '..', '..', 'fuori.tif') is None, 'file fuori dalla sessione rifiutato')
check(sess.Session.from_dict(se.to_dict()) == se and sess.Session.from_dict(None) == sess.Session(), 'dict andata e ritorno')
mp = sess.write_manifest(se, 'http://localhost:29800', [{'task': 'a', 'file': 'x.tif'}])
mp = sess.write_manifest(se, 'http://localhost:29800', [{'task': 'b', 'file': 'y.tif'}])
check(mp and len(json.load(open(mp, encoding='utf-8'))['items']) == 2, 'manifesto accumulato')
sel2 = selection.Selection('http://l', 1, TID, '', 'Rilievo', base_dir)
check(selection.Selection.from_json(sel2.to_json()) == sel2, 'selezione con sessione')

# ---- posizionamento sul canvas --------------------------------------------------------------------
from webodm2qgis_tools.core import placement   # noqa: E402

check(placement.placed_bounds(10, 4, 100, 200) == (100, 200, 110, 196), 'angolo in alto a sinistra -> limiti')
for bad_args in [(0, 4, 1, 1), (10, -1, 1, 1), (10, 4, float('nan'), 1), (10, 4, 'a', 1), (10, 4, 1, float('inf'))]:
    try:
        placement.placed_bounds(*bad_args)
        check(False, 'limiti accettati: %r' % (bad_args,))
    except ValueError:
        pass
check(placement.crs_problems(True, False, True) == [], 'CRS proiettato in metri: ok')
check([a.code for a in placement.crs_problems(False, False, True)] == ['P07'], 'progetto senza CRS')
check([a.code for a in placement.crs_problems(True, True, False)] == ['P08'], 'CRS in gradi rifiutato')
check([a.code for a in placement.crs_problems(True, False, False)] == ['P09'], 'CRS non in metri rifiutato')
check(placement.placed_name('a', set()) == 'a_posizionato.vrt', 'nome libero')
check(placement.placed_name('a', {'a_posizionato.vrt', 'a_posizionato_2.vrt'}) == 'a_posizionato_3.vrt', 'nome libero con suffisso')

# ---- i18n -----------------------------------------------------------------------------------------
i18n.set_language('it_IT')
check(i18n.T('Ciao {n}', n=3) == 'Ciao 3', 'T italiano con segnaposto')
for code, want in (('de_DE', 'de'), ('fr-FR', 'fr'), ('es_ES', 'es'), ('pt_BR', 'pt'), ('en_GB', 'en'), ('it', 'it'),
                   ('ja_JP', 'en'), ('', 'it'), (None, 'it')):
    i18n.set_language(code)
    check(i18n.language() == want, 'lingua %r -> %r (era %r)' % (code, want, i18n.language()))
i18n.set_language('de')
check(i18n.T('Annulla') == 'Abbrechen' and i18n.T('Nuovo') == 'Neu', 'tedesco tradotto')
check(i18n.T('Collegato a {u} come {user}', u='x', user='y') == 'Verbunden mit x als y', 'tedesco con segnaposto')
check(i18n.T(' - plugin WebODM presente') == ' - WebODM-Plugin vorhanden', 'chiave con spazio iniziale')
i18n.set_language('fr')
check(i18n.T('Annulla') == 'Annuler', 'francese tradotto')
check(i18n.T('testo mai tradotto') == 'testo mai tradotto', 'testo sconosciuto: invariato')
i18n.set_language('it')
check(i18n.T('Annulla') == 'Annulla', 'italiano = chiave')

print('FALLITI: %d' % len(FAILS) if FAILS else 'test_core: tutto ok')
sys.exit(1 if FAILS else 0)
