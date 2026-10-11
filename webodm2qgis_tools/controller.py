"""Regia del plugin: connessione, scelta progetto/task, sessione di import, scarico e caricamento dei
prodotti, avvisi CRS, foto. Non conosce finestre: le domande all'utente passano da `UiHooks`
(l'interfaccia le implementa; i test le sostituiscono)."""
import json
import math
import os
import shutil
from dataclasses import dataclass
from typing import Optional

from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsSettings
from qgis.PyQt.QtCore import QObject, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices

from . import i18n
from .core import catalog, crs_guard, photos, session as sess_mod
from .core.models import Product, Project, Server, Task
from .core.safety import extract_zip_safe
from .core.selection import ENTRY_KEY, ENTRY_SCOPE, Selection
from .core.urls import normalize_base_url, plugin_api, task_api
from .i18n import T
from .loaders import layers, shots_points
from .net import auth
from .net.client import ApiError, WebODMClient, as_list
from .net.downloader import Download

SETTINGS = 'webodm2qgis_tools/'
LOCAL_GROUP = 'Prospetti (CRS locale)'


@dataclass
class Decision:
    proceed: bool = True
    set_project_crs: bool = False
    assign_crs: Optional[QgsCoordinateReferenceSystem] = None


class UiHooks:
    """Le domande all'utente. Il comportamento predefinito e' non interattivo (usato dai test)."""

    def ask_session(self, default_name, default_folder):
        from .core.session import Session
        return Session(default_name, default_folder)

    def ask_crs(self, product, alerts, file_crs, project_crs, can_assign):
        # senza interfaccia: si adotta il CRS solo a progetto vuoto (C02 info); altrimenti si riproietta al volo
        return Decision(True, set_project_crs=any(a.code == 'C02' and a.level == 'info' and
                                                  'set_project_crs' in a.choices for a in alerts))

    def confirm(self, text):
        return True

    def message(self, level, text):
        pass

    def open_file(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def show_shot(self, layer, product):
        pass


class Controller(QObject):
    serversChanged = pyqtSignal()
    connectionChanged = pyqtSignal(bool, str)       # connesso, testo di stato
    projectsLoaded = pyqtSignal(list)
    tasksLoaded = pyqtSignal(list)
    taskLoaded = pyqtSignal(object)                 # Task (con prodotti in self.products)
    productsChanged = pyqtSignal()
    busyChanged = pyqtSignal(bool, str)
    progress = pyqtSignal(int, int)
    sessionChanged = pyqtSignal()
    photoSelected = pyqtSignal(str, int)            # id layer, fid
    layerAdded = pyqtSignal(object, object)         # layer, product

    def __init__(self, ui=None, parent=None):
        QObject.__init__(self, parent)
        self.ui = ui or UiHooks()
        self.client = None
        self.server = None
        self._pw = {}
        self.projects = []
        self.tasks = []
        self.task = None
        self.products = []
        self.plugin_scaled = False
        self.plugin_present = False
        self.plugin_epsg = None
        self.shot_layer_ids = {}                    # chiave prodotto -> id del layer dello scatto caricato
        self.selection = Selection()
        self.session = sess_mod.Session()
        self._gen = 0
        self._downloads = []
        self._queue = []
        self._working = False

    # --- impostazioni --------------------------------------------------------------------------
    def servers(self):
        raw = QgsSettings().value(SETTINGS + 'servers', '[]')
        try:
            return [Server(**d) for d in json.loads(raw)]
        except (ValueError, TypeError):
            return []

    def _save_servers(self, servers):
        QgsSettings().setValue(SETTINGS + 'servers', json.dumps([s.__dict__ for s in servers]))
        self.serversChanged.emit()

    def save_server(self, server, password='', remember=True):
        """Aggiunge/aggiorna un server. La password va nel gestore di autenticazione di QGIS (se richiesto
        e disponibile), altrimenti resta solo in memoria per questa sessione di QGIS."""
        server.url = normalize_base_url(server.url)
        if password:
            self._pw[server.url] = password
            if remember:
                server.authcfg = auth.store(server.name or server.url, server.user, password, server.authcfg)
                if not server.authcfg:
                    self.ui.message('warn', T("Password non salvata nel gestore di autenticazione di QGIS: "
                                              "resta valida solo finche' QGIS e' aperto."))
        servers = [s for s in self.servers() if s.url != server.url]
        servers.append(server)
        self._save_servers(servers)
        return server

    def remove_server(self, url):
        for s in self.servers():
            if s.url == url:
                auth.remove(s.authcfg)
        self._save_servers([s for s in self.servers() if s.url != url])
        self._pw.pop(url, None)

    def last_session_folder(self):
        return QgsSettings().value(SETTINGS + 'session_folder', '') or os.path.join(
            os.path.expanduser('~'), 'Documents', 'WebODM2QGIS')

    # --- connessione ---------------------------------------------------------------------------
    def _creds_for(self, server):
        def creds():
            pw = self._pw.get(server.url)
            if pw is None and server.authcfg:
                c = auth.load(server.authcfg)
                if c:
                    self._pw[server.url] = pw = c[1]
                    if not server.user:
                        server.user = c[0]
            return (server.user, pw) if server.user and pw is not None else None
        return creds

    def client_for(self, url):
        """Client del server `url` (quello attivo, oppure uno salvato), None se non c'e' modo di accedervi."""
        try:
            url = normalize_base_url(url)
        except ValueError:
            return None
        if self.client is not None and self.client.base == url:
            return self.client
        for s in self.servers():
            if s.url == url:
                return WebODMClient(url, self._creds_for(s), self)
        return WebODMClient(url, None, self)

    def connect_server(self, server, password=None):
        self.server = server
        if password:
            self._pw[server.url] = password
        self.client = WebODMClient(server.url, self._creds_for(server), self)
        self.selection.server_url = self.client.base
        self.busyChanged.emit(True, T('Connessione a {u}...', u=server.url))

        def logged(_tok, err):
            if err is not None:
                self.busyChanged.emit(False, '')
                self.connectionChanged.emit(False, str(err))
                return
            self.connectionChanged.emit(True, T('Collegato a {u} come {user}', u=server.url, user=server.user))
            self.load_projects()
        self.client.login(logged)

    def disconnect_server(self):
        if self.client:
            self.client.abort_all()
        self.client = None
        self.projects, self.tasks, self.products, self.task = [], [], [], None
        self.connectionChanged.emit(False, T('Non collegato'))
        self.projectsLoaded.emit([])
        self.tasksLoaded.emit([])
        self.productsChanged.emit()

    # --- progetti e task -----------------------------------------------------------------------
    def load_projects(self):
        if self.client is None:
            return
        self.busyChanged.emit(True, T('Elenco dei progetti...'))

        def done(data, err):
            self.busyChanged.emit(False, '')
            if err is not None:
                self.ui.message('crit', T('Progetti non leggibili: {e}', e=err))
                return
            self.projects = []
            for d in as_list(data):
                try:
                    self.projects.append(Project.from_json(d))
                except (KeyError, TypeError, ValueError):
                    continue
            self.projectsLoaded.emit(self.projects)
        self.client.get_json('/api/projects/', done, {'ordering': '-created_at'})

    def select_project(self, project_id):
        self.selection.project_id = project_id
        self.selection.task_id = ''
        self.tasks, self.task, self.products = [], None, []
        self.tasksLoaded.emit([])
        self.productsChanged.emit()
        if project_id is None or self.client is None:
            return
        gen = self._bump()
        self.busyChanged.emit(True, T('Elenco dei task...'))

        def done(data, err):
            if gen != self._gen:
                return
            self.busyChanged.emit(False, '')
            if err is not None:
                self.ui.message('crit', T('Task non leggibili: {e}', e=err))
                return
            self.tasks = []
            for d in as_list(data):
                try:
                    self.tasks.append(Task.from_json(d, project_id))
                except (KeyError, TypeError, ValueError):
                    continue
            self.tasksLoaded.emit(self.tasks)
        self.client.get_json('/api/projects/%d/tasks/' % int(project_id), done, {'ordering': '-created_at'})

    def _bump(self):
        self._gen += 1
        return self._gen

    def select_task(self, task_id):
        """Rilegge il task dal server e cerca cio' che ha prodotto il plugin WebODM (se c'e')."""
        self.selection.task_id = task_id or ''
        self.task, self.products, self.plugin_scaled, self.plugin_present = None, [], False, False
        self.productsChanged.emit()
        if not task_id or self.client is None or self.selection.project_id is None:
            return
        gen = self._bump()
        pid = int(self.selection.project_id)
        self.busyChanged.emit(True, T('Prodotti del task...'))
        got = {}

        def finish():
            if gen != self._gen:
                return
            self.busyChanged.emit(False, '')
            task = got['task']
            self.task = task
            self.plugin_present = got.get('ortho_ok', False) or got.get('export_ok', False) or got.get('transform_ok', False)
            self.plugin_scaled = bool((got.get('transform') or {}).get('transform'))
            rec = (got.get('georef') or {}).get('georef') if isinstance(got.get('georef'), dict) else None
            try:
                self.plugin_epsg = int(rec['epsg']) if isinstance(rec, dict) and rec.get('epsg') else None
            except (TypeError, ValueError):
                self.plugin_epsg = None
            trf = (got.get('transform') or {}).get('transform') if isinstance(got.get('transform'), dict) else None
            res = (got.get('georef') or {}).get('result') if isinstance(got.get('georef'), dict) else None
            m_scaled = trf.get('matrix') if isinstance(trf, dict) and photos.valid_matrix(trf.get('matrix')) else None
            m_abs = res.get('matrix_abs') if isinstance(res, dict) and photos.valid_matrix(res.get('matrix_abs')) else None
            if res and not self.plugin_epsg and res.get('epsg'):
                self.plugin_epsg = int(res['epsg'])
            self.products = catalog.build(task, got.get('export'), got.get('ortho'), self.plugin_epsg, m_scaled, m_abs)
            self.taskLoaded.emit(task)
            self.productsChanged.emit()

        def task_done(data, err):
            if gen != self._gen:
                return
            if err is not None:
                self.busyChanged.emit(False, '')
                self.ui.message('crit', T('Task non leggibile: {e}', e=err))
                return
            try:
                got['task'] = Task.from_json(data, pid)
            except (KeyError, TypeError, ValueError):
                self.busyChanged.emit(False, '')
                self.ui.message('crit', T('Risposta del task non valida'))
                return
            if not got['task'].completed:
                finish()
                return
            pending = {'n': 4}

            def plugin_cb(name):
                def cb(d, e):
                    if e is None:
                        got[name], got[name + '_ok'] = d, True
                    pending['n'] -= 1
                    if pending['n'] == 0:
                        finish()
                return cb
            for name in ('export', 'ortho', 'transform', 'georef'):
                self.client.get_json(plugin_api(task_id, name), plugin_cb(name))
        self.client.get_json(task_api(pid, task_id), task_done)

    # --- sessione di import --------------------------------------------------------------------
    def set_session(self, session):
        self.session = session
        self.selection.session_name = session.name
        self.selection.session_folder = session.folder
        if session.folder:
            QgsSettings().setValue(SETTINGS + 'session_folder', session.folder)
        self.sessionChanged.emit()

    def ensure_session(self):
        """True se c'e' una sessione valida (la chiede all'utente se manca)."""
        if self.session.valid():
            return True
        label = self.task.label if self.task else ''
        s = self.ui.ask_session(sess_mod.default_name(label), self.last_session_folder())
        if s is None or not s.valid():
            return False
        self.set_session(s)
        return True

    # --- salvataggio nel progetto QGIS ---------------------------------------------------------
    def save_to_project(self):
        QgsProject.instance().writeEntry(ENTRY_SCOPE, ENTRY_KEY, self.selection.to_json())

    def restore_from_project(self):
        text, ok = QgsProject.instance().readEntry(ENTRY_SCOPE, ENTRY_KEY, '')
        self.selection = Selection.from_json(text if ok else '')
        self.session = sess_mod.Session(self.selection.session_name, self.selection.session_folder)
        self.sessionChanged.emit()
        return self.selection

    # --- caricamento dei prodotti --------------------------------------------------------------
    def load_products(self, products):
        """Carica in coda (uno alla volta) i prodotti indicati."""
        if self.task is None or not products:
            return
        if not self.ensure_session():
            return
        self._queue.extend(products)
        if not self._working:
            self._next()

    def _next(self):
        if not self._queue:
            self._working = False
            self.busyChanged.emit(False, '')
            self.save_to_project()
            return
        self._working = True
        product = self._queue.pop(0)
        self.busyChanged.emit(True, T('Carico: {p}', p=product.label))
        try:
            self._load_one(product, self._next)
        except Exception as e:                      # un prodotto che fallisce non ferma gli altri
            self.ui.message('crit', T('{p}: errore inatteso: {e}', p=product.label, e=e))
            self._next()

    def cancel(self):
        self._queue = []
        for d in list(self._downloads):
            d.cancel()

    def _dest(self, product, *sub):
        t = self.task
        return self.session.file_path(t.label, t.id, *(sub + (product.filename,)))

    def _group(self):
        return layers.ensure_group(self.session.name)

    def _free_bytes(self, path):
        d = os.path.dirname(path)
        while d and not os.path.isdir(d):
            d = os.path.dirname(d)
        try:
            return shutil.disk_usage(d or '.').free
        except OSError:
            return None

    def _load_one(self, product, done):
        task = self.task
        if product.kind == 'xyz':
            self._load_xyz(product, done)
            return
        sub = {'raster': 'raster', 'pointcloud': 'nuvola', 'vector': 'vettori', 'photos': 'foto', 'model': 'mesh',
               'shot': 'scatti', 'archive': 'download', 'document': 'documenti', 'image': 'immagini'}.get(product.kind, 'altro')
        if product.meta.get('subdir'):
            sub = os.path.join('export_plugin', product.meta['subdir'])
        dest = self._dest(product, sub)
        if dest is None:
            self.ui.message('crit', T('{p}: percorso di destinazione non valido', p=product.label))
            done()
            return

        def after_probe(info, err):
            if err is not None:
                self.ui.message('crit' if err.kind != 'notfound' else 'warn',
                                T('{p}: {e}', p=product.label, e=err))
                done()
                return
            size = info.get('size')
            product.size = size
            pre = [a for a in crs_guard.check(product, task, size_bytes=size, free_bytes=self._free_bytes(dest))
                   if a.code == 'C11']
            if any(a.level == 'warn' for a in pre) or (size and size > crs_guard.BIG_FILE):
                if not self.ui.confirm('\n'.join(a.text for a in pre) + '\n\n' + T('Procedo con il download?')):
                    done()
                    return
            if os.path.isfile(dest) and size and os.path.getsize(dest) == size:
                self._after_download(product, dest, done)       # gia' scaricato in questa sessione
                return
            self._download(product.path, dest, product.label,
                           lambda ok, res: self._after_download(product, res, done) if ok else self._fail(product, res, done))
        self.client.probe(product.path, after_probe)

    def _fail(self, product, message, done):
        self.ui.message('crit', T('{p}: {e}', p=product.label, e=message))
        done()

    def _download(self, path, dest, label, cb):
        d = Download(self.client, path, dest, self)
        self._downloads.append(d)
        d.progress.connect(self.progress)

        def fin(ok, res):
            if d in self._downloads:
                self._downloads.remove(d)
            d.deleteLater()
            cb(ok, res)
        d.finished.connect(fin)
        d.start()

    def _after_download(self, product, path, done):
        kind = product.kind
        if kind in ('raster', 'pointcloud', 'vector'):
            self._add_geo_layer(product, path)
        elif kind == 'photos':
            self._add_photos(product, path)
        elif kind == 'shot':
            self._add_shot(product, path, done)
            return
        elif kind in ('model', 'archive'):
            self._unpack(product, path)
        elif kind in ('document', 'image'):
            self.ui.open_file(path)
            self.ui.message('info', T('{p} salvato in {d}', p=product.label, d=path))
        else:
            self.ui.message('info', T('{p} salvato in {d}', p=product.label, d=path))
        self._log(product, path)
        done()

    def _log(self, product, path):
        sess_mod.write_manifest(self.session, self.client.base if self.client else '', [{
            'task': self.task.label, 'task_id': self.task.id, 'project_id': self.task.project_id,
            'product': product.key, 'file': os.path.relpath(path, self.session.root) if self.session.root else path}])

    # --- tipi di prodotto ----------------------------------------------------------------------
    def _layer_name(self, product):
        return '%s [%s]' % (product.label, self.task.label)

    def _distance_km(self, layer):
        """Distanza tra il centro del prodotto e il centro dei dati gia' nel progetto (km), None se non calcolabile."""
        try:
            wgs = QgsCoordinateReferenceSystem('EPSG:4326')
            centers = []
            for other in QgsProject.instance().mapLayers().values():
                if other.id() == layer.id() or not other.crs().isValid() or other.crs() == layers.local_crs():
                    continue
                if other.extent().isNull() or other.extent().isEmpty():
                    continue
                centers.append(QgsCoordinateTransform(other.crs(), wgs, QgsProject.instance())
                               .transform(other.extent().center()))
            if not centers:
                return None
            ref = (sum(c.x() for c in centers) / len(centers), sum(c.y() for c in centers) / len(centers))
            c = QgsCoordinateTransform(layer.crs(), wgs, QgsProject.instance()).transform(layer.extent().center())
            dlat, dlon = math.radians(c.y() - ref[1]), math.radians(c.x() - ref[0])
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(ref[1])) * math.cos(math.radians(c.y())) * math.sin(dlon / 2) ** 2
            return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))
        except Exception:
            return None

    def _decide(self, product, layer, kind_has_crs=True):
        """Avvisi con il CRS reale + domanda all'utente. -> Decision."""
        project_crs = QgsProject.instance().crs()
        file_crs = layer.crs()
        has_layers = layers.project_has_layers()
        info = layers.crs_info(file_crs)
        pinfo = layers.crs_info(project_crs if (has_layers or project_crs.isValid()) else None)
        if info.valid:
            info.problem = layers.transform_problem(file_crs, project_crs) if has_layers else ''
        alerts = crs_guard.check(product, self.task, info, pinfo, has_layers,
                                 distance_km=self._distance_km(layer) if has_layers else None,
                                 plugin_scaled=self.plugin_scaled)
        if crs_guard.needs_dialog(alerts):
            return self.ui.ask_crs(product, alerts, file_crs, project_crs, not info.valid), alerts
        for a in alerts:
            self.ui.message('info', '%s: %s' % (a.code, a.text))
        return Decision(True, set_project_crs=any(a.code == 'C02' and 'set_project_crs' in a.choices for a in alerts)), alerts

    def _apply_decision(self, layer, decision):
        if decision.assign_crs is not None and decision.assign_crs.isValid():
            layer.setCrs(decision.assign_crs)
        if decision.set_project_crs and layer.crs().isValid():
            QgsProject.instance().setCrs(layer.crs())

    def _add_geo_layer(self, product, path):
        name = self._layer_name(product)
        opener = {'raster': layers.open_raster, 'pointcloud': layers.open_pointcloud,
                  'vector': layers.open_vector}[product.kind]
        layer = opener(path, name)
        if layer is None:
            hint = ''
            if product.kind == 'pointcloud':
                hint = ' ' + T('(manca il provider di nuvole di punti di QGIS?)')
            self.ui.message('crit', T('{p}: QGIS non riesce ad aprire {f}', p=product.label, f=path) + hint)
            return None
        meta = product.meta
        if meta.get('local'):
            # modello scalato dal plugin WebODM ma non georiferito: CRS locale, gruppo a parte e spento
            layer.setCrs(layers.local_crs())
            alerts = crs_guard.predict(product, self.task, self.plugin_scaled)
            d = self.ui.ask_crs(product, alerts, layers.local_crs(), QgsProject.instance().crs(), False)
            if not d.proceed:
                self.ui.message('info', T('{p}: caricamento annullato', p=product.label))
                return None
            self._tag(layer)
            layers.add_to_group(layer, layers.ensure_group(LOCAL_GROUP, self._group()), visible=False)
            self.layerAdded.emit(layer, product)
            return layer
        if meta.get('epsg') and not layer.crs().isValid():
            # il file non porta il CRS ma lo conosciamo: e' quello scelto nel Georiferimento del plugin WebODM
            layer.setCrs(QgsCoordinateReferenceSystem('EPSG:%d' % int(meta['epsg'])))
            self.ui.message('info', T('{p}: CRS EPSG:{e} assegnato dal georiferimento del plugin WebODM',
                                      p=product.label, e=int(meta['epsg'])))
        decision, _alerts = self._decide(product, layer)
        if not decision.proceed:
            self.ui.message('info', T('{p}: caricamento annullato', p=product.label))
            return None
        self._apply_decision(layer, decision)
        self._tag(layer)
        layers.add_to_group(layer, self._group())
        self.layerAdded.emit(layer, product)
        return layer

    @staticmethod
    def _free_path(path):
        """`path` se si puo' (ri)scrivere; se esiste ed e' aperto in QGIS (Windows lo blocca) un nome libero con
        suffisso _2, _3..."""
        if path is None:
            return None
        stem, ext = os.path.splitext(path)
        n = 1
        cand = path
        while os.path.exists(cand):
            try:
                os.remove(cand)
                break
            except OSError:
                n += 1
                cand = '%s_%d%s' % (stem, n, ext)
        return cand

    def _tag(self, layer):
        """Segna i layer di questo task: servono a trovare il riferimento del modello (vedi _model_crs)."""
        layer.setCustomProperty(shots_points.PROP + 'task_id', self.task.id)

    def _model_layer(self):
        """Un layer del modello (ortofoto, nuvola...) di questo task gia' nel progetto, con CRS valido."""
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.customProperty(shots_points.PROP + 'task_id') == self.task.id and lyr.crs().isValid()                     and lyr.customProperty(shots_points.PROP + 'kind') != 'photos':
                return lyr
        return None

    def _model_crs(self):
        """CRS del modello di un task NON georiferito: quello di un layer dello stesso task gia' caricato;
        altrimenti il CRS del progetto se e' proiettato in metri; altrimenti un CRS locale in metri."""
        lyr = self._model_layer()
        if lyr is not None:
            return lyr.crs()
        crs = QgsProject.instance().crs()
        if crs.isValid() and not crs.isGeographic() and crs.mapUnits() == Qgis.DistanceUnit.Meters:
            return crs
        return layers.local_crs()

    def _add_photos(self, product, path):
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            self.ui.message('crit', T('shots.geojson non leggibile: {e}', e=e))
            return
        shots, skipped = photos.parse_shots(data)
        if not shots:
            self.ui.message('warn', T('Nessun punto di scatto valido nel task'))
            return
        frame = product.meta.get('frame')
        if frame:
            # foto trasformate come il modello del plugin WebODM: stessa matrice di nuvola ed export
            try:
                shots = photos.apply_matrix(shots, product.meta['matrix'])
            except (ValueError, KeyError) as e:
                self.ui.message('crit', T('Matrice del plugin WebODM non valida: {e}', e=e))
                return
            model_crs = (QgsCoordinateReferenceSystem('EPSG:%d' % int(product.meta['epsg']))
                         if frame == 'georef' else layers.local_crs())
        else:
            model_crs = None if self.task.georeferenced else self._model_crs()
        alerts = crs_guard.check(product, self.task, layers.crs_info(QgsCoordinateReferenceSystem('EPSG:4326')),
                                 None, False)
        if crs_guard.needs_dialog(alerts):
            d = self.ui.ask_crs(product, alerts, QgsCoordinateReferenceSystem('EPSG:4326'),
                                QgsProject.instance().crs(), False)
            if not d.proceed:
                return
        else:
            for a in alerts:
                self.ui.message('info', '%s: %s' % (a.code, a.text))
        if model_crs is not None and self._model_layer() is None:
            self.ui.message('info', T("Le foto usano il CRS {c}. Carica anche ortofoto o nuvola dello stesso task: "
                                      "avranno lo stesso riferimento e le foto seguiranno il modello.",
                                      c=model_crs.authid() or T('locale')))
        base = {'georef': 'foto_georiferite', 'scaled': 'foto_scalate'}.get(frame, 'foto')
        gpkg = self._free_path(self._dest(Product(key='f', label='f', group='Foto', kind='photos',
                                                  filename=base + '.gpkg'), 'foto'))
        if gpkg is None:
            self.ui.message('crit', T('Percorso di destinazione non valido'))
            return
        sel = self.selection
        layer = shots_points.build(shots, gpkg, T('Foto - {t}', t=self.task.label), self.client.base,
                                   self.task.project_id, self.task.id, sel.photos_dir, model_crs)
        if layer is not None and frame:
            layer.setName('%s - %s' % (layer.name(), T('georiferite') if frame == 'georef' else T('scalate')))
        if layer is None:
            self.ui.message('crit', T('Impossibile creare il layer delle foto'))
            return
        layer.setCustomProperty(shots_points.PROP + 'cache_dir',
                                self.session.file_path(self.task.label, self.task.id, 'foto', 'originali') or '')
        if frame == 'scaled':
            layers.add_to_group(layer, layers.ensure_group(LOCAL_GROUP, self._group()), visible=False)
        else:
            layers.add_to_group(layer, self._group())
        self.layerAdded.emit(layer, product)
        msg = T('{n} punti di scatto caricati', n=len(shots))
        if skipped:
            msg += ' ' + T('({k} scartati: nome file o coordinate non validi)', k=skipped)
        self.ui.message('success', msg)

    def _unpack(self, product, path):
        if product.filename.lower().endswith('.zip'):
            target = os.path.join(os.path.dirname(path), os.path.splitext(product.filename)[0])
            try:
                files = extract_zip_safe(path, target)
            except (ValueError, OSError) as e:
                self.ui.message('crit', T('{p}: archivio non decomprimibile: {e}', p=product.label, e=e))
                return
            self.ui.message('success', T('{p}: {n} file estratti in {d}', p=product.label, n=len(files), d=target))
            if product.kind == 'model':
                self.ui.message('info', T("QGIS non mostra le mesh OBJ texturizzate: aprile nel visualizzatore 3D di "
                                          "WebODM (menu WebODM) o in un programma 3D."))
        else:
            self.ui.message('success', T('{p} salvato in {d}', p=product.label, d=path))

    def _load_xyz(self, product, done):
        server = self.server
        if not (server and server.authcfg):
            self.ui.message('warn', T("Lo streaming richiede le credenziali salvate nel gestore di autenticazione di "
                                      "QGIS (nessun token viene scritto nel progetto). Salva la password nella "
                                      "finestra del server, oppure scarica l'ortofoto."))
            done()
            return
        tj = self.task and task_api(self.task.project_id, self.task.id, 'orthophoto/tiles.json')

        def got(data, err):
            zmax = 21
            if err is None and isinstance(data, dict):
                try:
                    zmax = max(1, min(24, int(data.get('maxzoom', 21))))
                except (TypeError, ValueError):
                    pass
            layer = layers.open_xyz(self.client.base + product.path, self._layer_name(product), zmax, server.authcfg)
            if layer is None:
                self.ui.message('crit', T('{p}: streaming non disponibile', p=product.label))
            else:
                layers.add_to_group(layer, self._group())
                self.layerAdded.emit(layer, product)
            done()
        self.client.get_json(tj, got)

    def _add_shot(self, product, path, done):
        """Scatti/prospetti. Non-pianta o non georiferiti: CRS locale in metri (mai un EPSG terrestre)."""
        meta = product.meta
        local = meta.get('view') != 'top' or not meta.get('epsg')
        name = '%s [%s]' % (product.label, self.task.label)
        layer = layers.open_raster(path, name)
        if layer is None:
            self.ui.message('crit', T('{p}: QGIS non riesce ad aprire {f}', p=product.label, f=path))
            self._log(product, path)
            done()
            return

        def finish():
            if local:
                layer.setCrs(layers.local_crs())
                alerts = crs_guard.predict(product, self.task)
                if crs_guard.needs_dialog(alerts):
                    d = self.ui.ask_crs(product, alerts, layers.local_crs(), QgsProject.instance().crs(), False)
                    if not d.proceed:
                        done()
                        return
                group = layers.ensure_group(LOCAL_GROUP, self._group())
                layers.add_to_group(layer, group, visible=False)       # spento: non va sovrapposto alla mappa
                self.ui.show_shot(layer, product)
            else:
                decision, _a = self._decide(product, layer)
                if not decision.proceed:
                    done()
                    return
                self._apply_decision(layer, decision)
                self._tag(layer)
                layers.add_to_group(layer, self._group())
            self.shot_layer_ids[product.key] = layer.id()
            self.layerAdded.emit(layer, product)
            self._log(product, path)
            done()

        pts = next((f for f in product.extra_files if f['name'].lower().endswith('.points')), None)
        if pts:                                          # punti di controllo per il Georeferenziatore: piccoli
            dest = os.path.join(os.path.dirname(path), pts['name'])
            self._download(pts['url'], dest, pts['name'], lambda ok, res: finish())
        else:
            finish()

    def fetch_and_open(self, path, filename, subdir='scatti'):
        """Scarica un file del task nella cartella della sessione (se manca) e lo apre col programma del sistema."""
        if self.task is None or self.client is None or not self.ensure_session():
            return
        dest = self.session.file_path(self.task.label, self.task.id, subdir, filename)
        if dest is None:
            self.ui.message('crit', T('Percorso di destinazione non valido'))
            return
        if os.path.isfile(dest):
            self.ui.open_file(dest)
            return
        self.busyChanged.emit(True, T('Scarico {f}...', f=filename))

        def fin(ok, res):
            self.busyChanged.emit(False, '')
            if ok:
                self.ui.open_file(res)
            else:
                self.ui.message('crit', T('{f}: {e}', f=filename, e=res))
        self._download(path, dest, filename, fin)

    # --- posizionare uno scatto sul canvas -----------------------------------------------------
    def shot_layer(self, product_key):
        lid = self.shot_layer_ids.get(product_key)
        return QgsProject.instance().mapLayer(lid) if lid else None

    def shot_size_m(self, product_key):
        """(larghezza, altezza) in metri dello scatto caricato, oppure None."""
        layer = self.shot_layer(product_key)
        if layer is None:
            return None
        e = layer.extent()
        return (e.width(), e.height()) if e.width() > 0 and e.height() > 0 else None

    def place_shot(self, product_key, x, y):
        """Crea una copia georiferita (VRT, nessun dato copiato) dello scatto con l'angolo in alto a sinistra in
        (x, y), nel CRS del progetto, e la carica. L'originale in CRS locale resta com'e'."""
        from .core import placement
        layer = self.shot_layer(product_key)
        product = next((p for p in self.products if p.key == product_key), None)
        if layer is None or product is None:
            self.ui.message('warn', T("Carica prima lo scatto nel progetto (scheda Scatti e prospetti)."))
            return None
        crs = QgsProject.instance().crs()
        metres = crs.isValid() and crs.mapUnits() == Qgis.DistanceUnit.Meters
        problems = placement.crs_problems(crs.isValid(), crs.isValid() and crs.isGeographic(), metres)
        if problems:
            self.ui.message('crit', problems[0].text)
            return None
        size = self.shot_size_m(product_key)
        try:
            ulx, uly, lrx, lry = placement.placed_bounds(size[0], size[1], float(x), float(y))
        except (TypeError, ValueError) as e:
            self.ui.message('crit', T('Posizione non valida: {e}', e=e))
            return None
        src = layer.source().split('|')[0]
        folder = os.path.dirname(src)
        name = placement.placed_name(os.path.splitext(os.path.basename(src))[0], set(os.listdir(folder)))
        dst = os.path.join(folder, name)
        try:
            from osgeo import gdal
            gdal.UseExceptions()
            gdal.Translate(dst, src, format='VRT', outputBounds=[ulx, uly, lrx, lry], outputSRS=crs.authid() or crs.toWkt())
        except Exception as e:
            self.ui.message('crit', T('Posizionamento non riuscito: {e}', e=e))
            return None
        new = layers.open_raster(dst, '%s - %s' % (product.label, T('posizionato')))
        if new is None:
            self.ui.message('crit', T('{p}: QGIS non riesce ad aprire {f}', p=product.label, f=dst))
            return None
        new.setCrs(crs)
        layers.add_to_group(new, self._group() if self.session.valid() else layers.ensure_group('WebODM'), visible=True)
        self.ui.message('success', T('{p}: angolo in alto a sinistra in X={x:.3f} Y={y:.3f} ({c})',
                                     p=product.label, x=float(x), y=float(y), c=crs.authid()))
        if self.session.valid():
            self._log(product, dst)
        self.layerAdded.emit(new, product)
        return new

    # --- foto ----------------------------------------------------------------------------------
    def show_photo(self, layer_id, fid):
        self.photoSelected.emit(layer_id, int(fid))

    def _photo_ref(self, layer_id, fid):
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None or not shots_points.is_photos_layer(layer):
            return None
        feat = layer.getFeature(int(fid))
        if not feat.isValid():
            return None
        return layer, feat, shots_points.context(layer)

    def open_original(self, layer_id, fid, cb=None):
        """Apre la foto originale: cartella locale -> copia gia' scaricata -> server.
        Se non c'e' da nessuna parte lo scrive nel campo `originale` e lo dice."""
        ref = self._photo_ref(layer_id, fid)
        if ref is None:
            self.ui.message('warn', T('Foto non trovata nel layer'))
            return
        layer, feat, ctx = ref
        name = feat['nome_file']
        local = photos.find_local(ctx['photos_dir'], name)
        if local:
            shots_points.set_original_state(layer, int(fid), photos.ORIG_YES)
            self.ui.open_file(local)
            return
        cache_dir = layer.customProperty(shots_points.PROP + 'cache_dir') or ''
        cached = os.path.join(cache_dir, name) if cache_dir else ''
        if cached and os.path.isfile(cached):
            shots_points.set_original_state(layer, int(fid), photos.ORIG_YES)
            self.ui.open_file(cached)
            return
        client = self.client_for(ctx['server_url'])
        if client is None or not cache_dir:
            self.ui.message('warn', T("Per scaricare l'originale collegati al server {u} e usa una sessione di import.",
                                      u=ctx['server_url']))
            return
        path = task_api(int(ctx['project_id']), ctx['task_id'], 'images/download/' + name)
        self.busyChanged.emit(True, T('Controllo {f} sul server...', f=name))

        def probed(info, err):
            if err is not None:
                self.busyChanged.emit(False, '')
                if err.kind == 'notfound':
                    shots_points.set_original_state(layer, int(fid), photos.ORIG_NO)
                    a = crs_guard.original_missing_alert(name)
                    msg = a.text
                    if not ctx['photos_dir']:
                        msg += ' ' + T("Puoi indicare una cartella locale con le foto nel pannello Foto.")
                    self.ui.message('warn', msg)
                else:
                    self.ui.message('crit', T('{f}: {e}', f=name, e=err))
                return
            size = info.get('size') or 0
            if size > 30 * 1024 * 1024 and not self.ui.confirm(
                    T('La foto pesa {mb:.0f} MB. La scarico e la apro?', mb=size / 1048576)):
                self.busyChanged.emit(False, '')
                return
            d = Download(client, path, cached, self)
            self._downloads.append(d)
            d.progress.connect(self.progress)

            def fin(ok, res):
                self._downloads.remove(d) if d in self._downloads else None
                d.deleteLater()
                self.busyChanged.emit(False, '')
                if ok:
                    shots_points.set_original_state(layer, int(fid), photos.ORIG_YES)
                    self.ui.open_file(res)
                    if cb:
                        cb(res)
                else:
                    self.ui.message('crit', T('{f}: {e}', f=name, e=res))
            d.finished.connect(fin)
            d.start()
        client.probe(path, probed)

    def photo_thumbnail(self, layer_id, fid, size, cb):
        """cb(bytes JPEG | None). Miniatura generata dal server."""
        ref = self._photo_ref(layer_id, fid)
        if ref is None:
            cb(None)
            return
        layer, feat, ctx = ref
        client = self.client_for(ctx['server_url'])
        if client is None:
            cb(None)
            return
        path = task_api(int(ctx['project_id']), ctx['task_id'], 'images/thumbnail/' + feat['nome_file'])
        client.get_bytes(path, lambda data, err: cb(data if err is None else None), {'size': size})

    def verify_originals(self, layer_id, progress_cb=None, done_cb=None, parallel=4):
        """Controlla sul server quali originali esistono e riempie il campo `originale` (annullabile con cancel())."""
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None or not shots_points.is_photos_layer(layer):
            return
        ctx = shots_points.context(layer)
        client = self.client_for(ctx['server_url'])
        if client is None:
            self.ui.message('warn', T('Collegati al server per verificare le foto'))
            return
        todo = [(f.id(), f['nome_file']) for f in layer.getFeatures()]
        state = {'i': 0, 'done': 0, 'yes': 0, 'no': 0, 'active': 0, 'stop': False}
        total = len(todo)
        self._verify_stop = state

        def pump():
            while state['active'] < parallel and state['i'] < total and not state['stop']:
                fid, name = todo[state['i']]
                state['i'] += 1
                state['active'] += 1
                local = photos.find_local(ctx['photos_dir'], name) if ctx['photos_dir'] else None
                if local:
                    got(fid, {'size': 0}, None)
                    continue
                client.probe(task_api(int(ctx['project_id']), ctx['task_id'], 'images/download/' + name),
                             lambda info, err, fid=fid: got(fid, info, err))
            if state['active'] == 0 and (state['i'] >= total or state['stop']):
                layer.triggerRepaint()
                if done_cb:
                    done_cb(state['yes'], state['no'])

        def got(fid, info, err):
            state['active'] -= 1
            state['done'] += 1
            if err is None:
                state['yes'] += 1
                shots_points.set_original_state(layer, fid, photos.ORIG_YES)
            elif err.kind == 'notfound':
                state['no'] += 1
                shots_points.set_original_state(layer, fid, photos.ORIG_NO)
            if progress_cb:
                progress_cb(state['done'], total)
            pump()
        pump()

    def stop_verify(self):
        st = getattr(self, '_verify_stop', None)
        if st:
            st['stop'] = True
