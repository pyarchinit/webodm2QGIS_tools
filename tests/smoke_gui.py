"""Prova nel QGIS 4 vero (interfaccia reale, piattaforma offscreen): carica il plugin, lo collega a un finto
WebODM, usa pannelli e azioni e salva le schermate in W2Q_OUT. Lanciare con:  python run_qgis.py --gui tests/smoke_gui.py"""
import json
import os
import sys
import traceback

ROOT = os.environ['W2Q_ROOT']          # impostato da run_qgis.py (con --code non esiste __file__)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tests'))
OUT = os.environ.get('W2Q_OUT') or os.path.join(os.environ.get('TEMP', '.'), 'w2q_smoke')
os.makedirs(OUT, exist_ok=True)
REPORT = {'ok': [], 'fail': []}


def ok(msg):
    REPORT['ok'].append(msg)


def fail(msg):
    REPORT['fail'].append(msg)


def finish():
    with open(os.path.join(OUT, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(REPORT, f, indent=2, ensure_ascii=False)
    from qgis.core import QgsApplication, QgsProject
    from qgis.PyQt.QtCore import QCoreApplication, QTimer
    code = 0 if not REPORT['fail'] else 1
    # Chiudere QGIS con exit() lasciando layer nel progetto manda in crash ~QgsProject (il pannello Livelli
    # reagisce alla rimozione quando la finestra e' gia' distrutta): si svuota il progetto a interfaccia viva.
    try:
        QgsProject.instance().clear()
        QCoreApplication.processEvents()
    except Exception:
        pass
    # lo script gira prima dell'avvio del loop eventi: si chiude appena parte
    QTimer.singleShot(0, lambda: QgsApplication.exit(code))


def main():
    from qgis.core import QgsProject
    from qgis.PyQt.QtCore import QCoreApplication, Qt
    from qgis.utils import iface
    import time

    from sample_data import T1, T2 as sample_T2, server, PID
    from webodm2qgis_tools import controller as ctl_mod, plugin as plug_mod
    from webodm2qgis_tools.core import session as sess_mod
    from webodm2qgis_tools.core.models import Server
    from webodm2qgis_tools.ui.shot_viewer import ShotViewer

    def wait(cond, timeout=25):
        t0 = time.time()
        while not cond():
            QCoreApplication.processEvents()
            time.sleep(0.01)
            if time.time() - t0 > timeout:
                raise TimeoutError('timeout')
        QCoreApplication.processEvents()

    def shot(widget, name):
        from qgis.PyQt.QtWidgets import QDialog
        if isinstance(widget, QDialog) and widget is not win:
            widget.setMinimumWidth(max(widget.minimumWidth(), 560))
            widget.adjustSize()            # dimensione naturale: niente spazi vuoti stirati nelle schermate della guida
        else:
            widget.resize(widget.width() if widget.width() > 100 else 420, widget.height() if widget.height() > 100 else 700)
        iface.messageBar().clearWidgets()
        QCoreApplication.processEvents()
        widget.grab().save(os.path.join(OUT, name + '.png'))

    if os.environ.get('W2Q_LANG'):
        from qgis.core import QgsSettings
        QgsSettings().setValue('webodm2qgis_tools/language', os.environ['W2Q_LANG'])
    plugin = plug_mod.WebODM2QGISPlugin(iface)
    plugin.initGui()
    ok('initGui eseguito')
    win = iface.mainWindow()
    win.resize(1500, 900)
    win.show()

    # menu e barra
    menus = [a.text() for a in win.menuBar().actions()]
    if any('WebODM' in t for t in menus):
        ok('menu WebODM nella barra dei menu')
    else:
        fail('menu WebODM mancante: %s' % menus)
    names = [a.objectName() for a in plugin.toolbar.actions()]
    if len(names) >= 8:
        ok('barra con %d azioni' % len(names))
    else:
        fail('barra incompleta: %s' % names)
    if plugin.act_ortho.isEnabled():
        fail('Carica ortofoto abilitato senza task')
    else:
        ok('azioni dipendenti dal task disabilitate prima della scelta')

    # dialoghi: si costruiscono e si fotografano
    from webodm2qgis_tools.ui.server_dialog import ServerDialog
    from webodm2qgis_tools.ui.session_dialog import SessionDialog
    d = ServerDialog(plugin.ctl, win)
    d._local()
    d.url.setText('http://odm.example.org')
    shot(d, 'dlg_server')
    if 'HTTPS' in d.note.text():
        ok('avviso http non locale')
    else:
        fail('manca avviso http remoto')
    sd = SessionDialog('Chiesa 2026-10-11', os.path.join(OUT, 'sessioni'), win)
    shot(sd, 'dlg_sessione')
    if sd.buttons.button(sd.buttons.StandardButton.Ok).isEnabled():
        ok('dialogo sessione valido')
    else:
        fail('dialogo sessione non valido')

    # collegamento
    ctl = plugin.ctl

    class Hooks(ctl_mod.UiHooks):
        def __init__(self):
            self.shown = []
            self.msgs = []

        def ask_session(self, name, folder):
            return sess_mod.Session('Rilievo chiesa', os.path.join(OUT, 'sessioni'))

        def message(self, level, text):
            self.msgs.append((level, text))

        def open_file(self, path):
            self.shown.append(path)

        def show_shot(self, layer, product):
            self.shown.append(('shot', product.key))
            v = ShotViewer(layer, product, win)
            v.show()
            wait(lambda: False, 0.01) if False else None
            self.viewer = v
    hooks = Hooks()
    ctl.ui = hooks
    ctl.connect_server(Server('prova', server.url, 'admin'), 'admin')
    wait(lambda: ctl.projects)
    ok('collegato, %d progetti' % len(ctl.projects))
    plugin.dock.show()
    wait(lambda: plugin.dock.project.count() > 0)
    plugin.dock.project.setCurrentIndex(0)
    plugin.dock._project_activated(0)
    wait(lambda: len(ctl.tasks) == 3)
    plugin.dock.task.setCurrentIndex(0)
    ctl.select_task(T1)
    wait(lambda: ctl.task is not None and ctl.task.id == T1 and ctl.products)
    wait(lambda: plugin.dock.tree.topLevelItemCount() > 0)
    ok('albero prodotti: %d gruppi' % plugin.dock.tree.topLevelItemCount())
    if plugin.act_ortho.isEnabled() and plugin.act_photos.isEnabled() and plugin.act_shots.isEnabled():
        ok('azioni abilitate dopo la scelta del task')
    else:
        fail('azioni non abilitate dopo la scelta del task')
    shot(plugin.dock, 'dock_prodotti')

    # picker
    from webodm2qgis_tools.ui.task_picker import TaskPicker
    pk = TaskPicker(ctl, win)
    pk.show()
    wait(lambda: pk.tree.topLevelItemCount() >= 1)
    pk.tree.setCurrentItem(pk.tree.topLevelItem(0))
    wait(lambda: False if False else True)
    shot(pk, 'dlg_picker')
    ok('picker: %d task' % pk.tree.topLevelItemCount())
    pk.reject()

    # caricamento con la UI vera dell'azione
    plugin.quick(('orthophoto.tif',))
    wait(lambda: not ctl._working and not ctl._downloads)
    plugin.quick(('shots.geojson',))
    wait(lambda: not ctl._working and not ctl._downloads)
    root = QgsProject.instance().layerTreeRoot()
    grp = root.findGroup('Rilievo chiesa')
    if grp and len(grp.findLayers()) == 2:
        ok('gruppo "Rilievo chiesa" con ortofoto e foto')
    else:
        fail('gruppo sessione non corretto: %s' % (grp and len(grp.findLayers())))
    iface.mapCanvas().setExtent(iface.mapCanvas().fullExtent())
    iface.mapCanvas().refresh()

    # strumento foto: clic simulato
    from webodm2qgis_tools.ui.photo_tool import nearest_photo
    from webodm2qgis_tools.loaders import shots_points
    pl = next(n.layer() for n in grp.findLayers() if shots_points.is_photos_layer(n.layer()))
    f = next(iter(pl.getFeatures()))
    pt = f.geometry().asPoint()
    from qgis.core import QgsCoordinateTransform, QgsProject as P
    ct = QgsCoordinateTransform(pl.crs(), iface.mapCanvas().mapSettings().destinationCrs(), P.instance())
    iface.mapCanvas().zoomToFeatureIds(pl, [f.id()])
    wait(lambda: False if False else True)
    hit = nearest_photo(iface.mapCanvas(), ct.transform(pt))
    if hit and hit[1].id() == f.id():
        ok('strumento Foto trova il punto cliccato')
    else:
        fail('strumento Foto non trova il punto')
    plugin.act_phototool.trigger()
    ctl.show_photo(pl.id(), f.id())
    wait(lambda: plugin.photo_panel.thumb.pixmap() is not None and not plugin.photo_panel.thumb.pixmap().isNull(), 10)
    ok('pannello Foto con miniatura')
    shot(plugin.photo_panel, 'pannello_foto')
    ctl.open_original(pl.id(), f.id())
    wait(lambda: any(isinstance(x, str) for x in hooks.shown))
    ok('originale aperto: %s' % [x for x in hooks.shown if isinstance(x, str)][-1])

    # scatti
    plugin.show_shots()
    wait(lambda: plugin.dock.shots.list.count() == 1)
    shot(plugin.dock, 'dock_scatti')
    ok('galleria scatti: 1')
    ctl.load_products([p for p in ctl.products if p.kind == 'shot'])
    wait(lambda: not ctl._working and not ctl._downloads)
    wait(lambda: any(isinstance(x, tuple) for x in hooks.shown))
    shot(hooks.viewer, 'visualizzatore_scatto')
    ok('prospetto aperto nella mappa dedicata')

    # posizionamento sul canvas: interruttore + punto catturato + applica
    sp = plugin.dock.shots
    sp.list.setCurrentRow(0)
    if sp.place_btn.isChecked():
        fail('modalita posizionamento accesa all avvio')
    sp.place_btn.setChecked(True)
    if iface.mapCanvas().mapTool() is sp.tool:
        ok('modalita posizionamento accesa: lo strumento e attivo sul canvas')
    else:
        fail('strumento di posizionamento non attivo')
    sp.tool.pointPicked.emit(700000.0, 4100000.0)
    if abs(sp.px.value() - 700000.0) < 1e-6 and abs(sp.py.value() - 4100000.0) < 1e-6 and sp.apply_btn.isEnabled():
        ok('coordinate catturate nei campi X/Y, "Posiziona qui" abilitato')
    else:
        fail('coordinate non catturate: %s %s' % (sp.px.value(), sp.py.value()))
    shot(plugin.dock, 'dock_posiziona')
    n0 = len(QgsProject.instance().mapLayers())
    sp.apply_btn.click()
    if len(QgsProject.instance().mapLayers()) == n0 + 1:
        ok('scatto posizionato dal pulsante')
    else:
        fail('posizionamento non eseguito')
    sp.place_btn.setChecked(False)
    if iface.mapCanvas().mapTool() is not sp.tool:
        ok('modalita spenta: strumento rilasciato')
    else:
        fail('strumento ancora attivo dopo lo spegnimento')

    # visualizzatore web
    # (la vista web non si crea qui: in 'offscreen' non c'e' GPU e QtWebEngine manda in crash la chiusura)
    from webodm2qgis_tools.ui import web_viewer
    u = plugin.viewer.url()
    if u and u.endswith('/3d/project/%d/task/%s/' % (PID, T1)) or u and '/3d/project/' in u:
        ok('URL del visualizzatore 3D: %s' % u)
    else:
        fail('URL del visualizzatore errato: %s' % u)
    if os.environ.get('W2Q_NO_WEB'):
        ok('import di QtWebEngine saltato (W2Q_NO_WEB)')
    else:
        ok('visualizzatore web: %s' % ('QtWebEngine importabile' if web_viewer.webengine() else 'QtWebEngine NON disponibile (ripiego sul browser)'))

    # schermate per la documentazione: avviso CRS e Informazioni
    from webodm2qgis_tools.core import crs_guard
    from webodm2qgis_tools.core.models import CrsInfo
    from webodm2qgis_tools.ui.crs_dialog import CrsDialog
    from webodm2qgis_tools.ui.about_dialog import AboutDialog
    ctl.select_task(sample_T2)
    wait(lambda: ctl.task is not None and ctl.task.id == sample_T2 and ctl.products)
    op = next(p for p in ctl.products if p.key == 'orthophoto.tif')
    al = crs_guard.check(op, ctl.task, CrsInfo('EPSG:32632', True, False, 'WGS 84 / UTM zone 32N'),
                         CrsInfo('EPSG:25832', True, False, 'ETRS89 / UTM zone 32N'), True)
    from qgis.core import QgsCoordinateReferenceSystem as _C
    cd = CrsDialog(op, al, _C('EPSG:32632'), _C('EPSG:25832'), False, win)
    shot(cd, 'dlg_crs')
    ab = AboutDialog(plug_mod.VERSION, win)
    shot(ab, 'dlg_about')
    ctl.select_task(T1)
    wait(lambda: ctl.task is not None and ctl.task.id == T1 and ctl.products)
    # verifica CRS progetto
    shot(win, 'finestra_qgis')

    # progetto salvato e riaperto
    prj = os.path.join(OUT, 'prova.qgz')
    QgsProject.instance().write(prj)
    ctl.selection = ctl_mod.Selection()
    QgsProject.instance().read(prj)
    wait(lambda: ctl.session.valid())
    if ctl.session.name == 'Rilievo chiesa' and ctl.selection.task_id == T1:
        ok('sessione e task ripristinati riaprendo il progetto')
    else:
        fail('sessione non ripristinata: %s' % ctl.selection)
    if hooks.msgs:
        REPORT['messaggi'] = hooks.msgs

    plugin.unload()
    ok('unload pulito')


try:
    main()
except Exception:
    fail('ECCEZIONE:\n' + traceback.format_exc())
finally:
    try:
        from sample_data import server
        server.stop()
    except Exception:
        pass
    finish()
