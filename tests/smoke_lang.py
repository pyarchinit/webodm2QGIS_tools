"""Nel QGIS 4 vero: avvia il plugin in ognuna delle sei lingue, raccoglie TUTTI i testi visibili (menu, barra, pannelli,
tooltip, finestre) e controlla che cambino davvero. Scrive W2Q_OUT/lang_report.json.
    python qgis_dev.py lang"""
import json
import os
import re
import sys
import traceback

ROOT = os.environ['W2Q_ROOT']
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tests'))
OUT = os.environ['W2Q_OUT']
os.makedirs(OUT, exist_ok=True)
REPORT = {'fail': [], 'ok': [], 'texts': {}, 'same_as_italian': {}}


def finish():
    json.dump(REPORT, open(os.path.join(OUT, 'lang_report.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    from qgis.core import QgsApplication, QgsProject
    from qgis.PyQt.QtCore import QCoreApplication, QTimer
    try:
        QgsProject.instance().clear()
        QCoreApplication.processEvents()
    except Exception:
        pass
    code = 1 if REPORT['fail'] else 0
    QTimer.singleShot(0, lambda: QgsApplication.exit(code))


def plain(t):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t or '')).strip()


def collect(root, tag):
    """Tutti i testi visibili di un widget: etichette, pulsanti, tooltip, elenchi, schede, intestazioni, titoli."""
    from qgis.PyQt.QtWidgets import (QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QTabWidget, QTreeWidget,
                                     QWidget)
    out = {}
    n = [0]

    def add(kind, text):
        text = plain(text)
        if text:
            n[0] += 1
            out['%s/%03d %s' % (tag, n[0], kind)] = text
    add('titolo', root.windowTitle())
    for w in [root] + root.findChildren(QWidget):
        if isinstance(w, QLabel):
            add('etichetta', w.text())
        if isinstance(w, QAbstractButton):
            add('pulsante', w.text())
        if isinstance(w, QGroupBox):
            add('gruppo', w.title())
        if isinstance(w, QLineEdit):
            add('segnaposto', w.placeholderText())
        if isinstance(w, QComboBox):
            for i in range(w.count()):
                if not re.match(r'^[\d\W_]+$', w.itemText(i)):
                    add('voce-elenco', w.itemText(i))
        if isinstance(w, QTabWidget):
            for i in range(w.count()):
                add('scheda', w.tabText(i))
        if isinstance(w, QTreeWidget):
            h = w.headerItem()
            for c in range(w.columnCount()):
                add('intestazione', h.text(c))
        if w.toolTip():
            add('tooltip', w.toolTip())
    return out


def main():
    from qgis.core import QgsCoordinateReferenceSystem as C, QgsSettings
    from qgis.utils import iface
    from webodm2qgis_tools import i18n, plugin as plug_mod
    from webodm2qgis_tools.core import crs_guard
    from webodm2qgis_tools.core.models import CrsInfo, Product, Task
    from webodm2qgis_tools.ui.about_dialog import AboutDialog
    from webodm2qgis_tools.ui.crs_dialog import CrsDialog
    from webodm2qgis_tools.ui.server_dialog import ServerDialog
    from webodm2qgis_tools.ui.session_dialog import SessionDialog
    from webodm2qgis_tools.ui.task_picker import TaskPicker

    probes = {'it': 'Collega', 'en': 'Connect', 'fr': 'Connecter', 'de': 'Verbinden', 'es': 'Conectar', 'pt': 'Conectar'}
    allt = {}
    for lang in i18n.LANGS:
        QgsSettings().setValue('webodm2qgis_tools/language', lang)
        pl = plug_mod.WebODM2QGISPlugin(iface)
        pl.initGui()
        if i18n.language() != lang:
            REPORT['fail'].append('%s: lingua attiva %s' % (lang, i18n.language()))
        t = {}
        t.update(collect(pl.dock, 'pannello'))
        t.update(collect(pl.photo_panel, 'foto'))
        t.update(collect(pl.viewer, 'visualizzatore'))
        for i, a in enumerate(pl.actions):
            t['azione/%02d testo' % i] = plain(a.text())
            t['azione/%02d tooltip' % i] = plain(a.toolTip())
        t['menu/titolo'] = plain(pl.menu.title())
        win = iface.mainWindow()
        for tag, dlg in (('server', ServerDialog(pl.ctl, win)), ('sessione', SessionDialog('Nome', 'C:/x', win)),
                         ('picker', TaskPicker(pl.ctl, win)), ('info', AboutDialog('0.1.0', win))):
            t.update(collect(dlg, tag))
            dlg.deleteLater()
        tk = Task.from_json({'id': 'aaaaaaaa-1111', 'name': 'x', 'status': 40, 'available_assets': []}, 7)
        prod = Product(key='o', label='o', group='Ortofoto', kind='raster', filename='orthophoto.tif')
        al = crs_guard.check(prod, tk, CrsInfo('EPSG:32632', True, False), CrsInfo('EPSG:25832', True, False), True)
        cd = CrsDialog(prod, al, C('EPSG:32632'), C('EPSG:25832'), False, win)
        t.update(collect(cd, 'crs'))
        cd.deleteLater()
        for i, k in enumerate(('Annulla', 'Completato', 'Non collegato', 'Foto non trovata nel layer')):
            t['runtime/%d' % i] = i18n.T(k)
        if not [v for k, v in t.items() if k.startswith('pannello') and 'pulsante' in k and v == probes[lang]]:
            REPORT['fail'].append('%s: il pulsante "%s" non compare nel pannello' % (lang, probes[lang]))
        else:
            REPORT['ok'].append('%s: pulsante del pannello = "%s"' % (lang, probes[lang]))
        allt[lang] = t
        REPORT['texts'][lang] = len(t)
        pl.unload()
    it = allt['it']
    names_ok = {'WebODM', 'Zoom', 'X', 'Y', 'CRS', 'KBS', 'SCR', 'Dashboard', 'Task', 'File', 'Mesh', 'Password',
                'WebODM2QGIS-tools'}
    for lang in i18n.LANGS:
        if lang == 'it':
            continue
        same = sorted(set(v for k, v in allt[lang].items() if k in it and it[k] == v and re.search(r'[A-Za-z]{3,}', v)
                          and v not in names_ok))
        REPORT['same_as_italian'][lang] = same
        ratio = 1.0 - float(len(same)) / max(1, len(allt[lang]))
        if ratio < 0.80:
            REPORT['fail'].append('%s: solo il %.0f%% dei testi e cambiato' % (lang, 100 * ratio))
    # scelta della lingua dalla finestra Informazioni: salva e vale al riavvio del plugin
    QgsSettings().setValue('webodm2qgis_tools/language', 'auto')
    dlg = AboutDialog('0.1.0', iface.mainWindow())
    dlg.lang.setCurrentIndex(dlg.lang.findData('de'))
    dlg.accept()
    pl = plug_mod.WebODM2QGISPlugin(iface)
    pl.initGui()
    if i18n.language() == 'de' and any(v == 'Verbinden' for v in collect(pl.dock, 'p').values()):
        REPORT['ok'].append('Informazioni > Lingua > Deutsch: dopo il riavvio del plugin l interfaccia e in tedesco')
    else:
        REPORT['fail'].append('la scelta fatta in Informazioni non ha cambiato la lingua (%s)' % i18n.language())
    pl.unload()
    QgsSettings().setValue('webodm2qgis_tools/language', 'auto')
    pl = plug_mod.WebODM2QGISPlugin(iface)
    pl.initGui()
    REPORT['ok'].append('lingua automatica con QGIS in italiano -> %s' % i18n.language())
    if i18n.language() != 'it':
        REPORT['fail'].append('automatica non segue la lingua di QGIS: %s' % i18n.language())
    pl.unload()


try:
    main()
except Exception:
    REPORT['fail'].append('ECCEZIONE:\n' + traceback.format_exc())
finally:
    finish()
