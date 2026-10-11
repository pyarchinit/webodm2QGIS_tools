#!/usr/bin/env python3
"""Ciclo di sviluppo del plugin QGIS 4: controlli -> nuova versione -> zip -> installa in QGIS -> backup.

    python qgis_dev.py            esegue tutto (default)
    python qgis_dev.py check      solo controlli e test, non modifica nulla
    python qgis_dev.py build      controlli + nuova versione + zip + backup, senza toccare QGIS
    python qgis_dev.py status     confronta versione sorgente / zip / installata
    python qgis_dev.py gui        prova nel QGIS 4 vero (senza finestra): schermate in tests/_gui_out
    python qgis_dev.py shots      rifa le schermate della guida (italiano e inglese) in docs/img_it e docs/img_en

Opzioni:  --no-bump  non incrementa la versione     --no-tests  salta i test (solo sintassi)

I test che usano QGIS girano con run_qgis.py (ambiente pulito: il PYTHONPATH utente e le variabili di
PostGIS rompono l'import di qgis._core). Cartella dei plugin di QGIS 4: variabile QGIS4_PLUGINS_DIR.
"""
import ast
import filecmp
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'webodm2qgis_tools'
SRC = os.path.join(HERE, NAME)
ZIP = os.path.join(HERE, NAME + '.zip')
METADATA = os.path.join(SRC, 'metadata.txt')
PLUGINS_DIR = os.environ.get('QGIS4_PLUGINS_DIR') or os.path.join(
    os.environ.get('APPDATA', ''), 'QGIS', 'QGIS4', 'profiles', 'default', 'python', 'plugins')
INSTALLED = os.path.join(PLUGINS_DIR, NAME)
SKIP_DIRS = ('__pycache__',)
PY_TARGET = (3, 12)                    # Python incluso in QGIS 4.2


def source_files():
    out = []
    for d, dirs, files in os.walk(SRC):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if not f.endswith('.pyc'):
                out.append(os.path.relpath(os.path.join(d, f), SRC).replace(os.sep, '/'))
    return sorted(out)


def read_version(path):
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                if line.startswith('version='):
                    return line.split('=', 1)[1].strip()
    except OSError:
        pass
    return None


def zip_version(path):
    try:
        with zipfile.ZipFile(path) as z:
            for line in z.read(NAME + '/metadata.txt').decode('utf-8').splitlines():
                if line.startswith('version='):
                    return line.split('=', 1)[1].strip()
    except (OSError, KeyError, zipfile.BadZipFile):
        pass
    return None


def write_zip(path):
    # zipfile e non Compress-Archive: quello di Windows scrive percorsi con "\"; QGIS vuole la cartella NAME in testa
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in source_files():
            z.write(os.path.join(SRC, rel), NAME + '/' + rel)


def check_metadata():
    text = open(METADATA, encoding='utf-8').read()
    for key in ('name', 'qgisMinimumVersion', 'supportsQt6', 'version', 'author', 'description', 'about'):
        if not re.search(r'^%s=.+' % key, text, re.M):
            raise SystemExit('metadata.txt: manca "%s"' % key)
    if not re.search(r'^supportsQt6=True', text, re.M):
        raise SystemExit('metadata.txt: supportsQt6 deve essere True (QGIS 4 non carica altrimenti il plugin)')
    if not re.search(r'^qgisMinimumVersion=4', text, re.M):
        raise SystemExit('metadata.txt: qgisMinimumVersion deve essere >= 4.0')


def check(run_tests=True):
    print('== controlli')
    for rel in source_files():
        if rel.endswith('.py'):
            with open(os.path.join(SRC, rel), encoding='utf-8') as f:
                src = f.read()
            ast.parse(src, filename=rel, feature_version=PY_TARGET)
            if re.search(r'^\s*(from|import)\s+PyQt5', src, re.M):
                raise SystemExit('%s: importa PyQt5; usa qgis.PyQt (QGIS 4 e\' Qt6)' % rel)
            if 'requests' in re.findall(r'^\s*(?:from|import)\s+(\w+)', src, re.M):
                raise SystemExit('%s: il plugin non deve dipendere da "requests"' % rel)
    print('OK  sintassi Python %d.%d, nessun PyQt5, nessuna dipendenza esterna' % PY_TARGET)
    check_metadata()
    print('OK  metadata.txt')
    for rel in ('docs/guide_it.html', 'docs/guide_en.html', 'translations.txt'):
        if not os.path.isfile(os.path.join(SRC, rel)):
            raise SystemExit('manca %s: esegui python docs/build_docs.py (guide) o rigenera le traduzioni' % rel)
    if not os.path.isfile(os.path.join(HERE, 'LICENSE')):
        raise SystemExit('manca LICENSE')
    print('OK  guide, traduzioni e licenza presenti')
    if os.path.exists(os.path.join(SRC, 'requirements.txt')):
        raise SystemExit('requirements.txt non ammesso')
    if not run_tests:
        return
    for test in ('test_core.py', 'test_i18n.py'):
        print('== tests/' + test)
        subprocess.run([sys.executable, os.path.join(HERE, 'tests', test)], check=True)
    import run_qgis
    if run_qgis.find_qgis() is None:
        print('--  QGIS 4 non trovato: test di integrazione saltato (imposta QGIS4_ROOT)')
        return
    print('== tests/test_integration.py (dentro QGIS 4)')
    if run_qgis.run([os.path.join(HERE, 'tests', 'test_integration.py')]) != 0:
        raise subprocess.CalledProcessError(1, ['test_integration.py'])


def bump():
    text = open(METADATA, encoding='utf-8').read()
    m = re.search(r'^version=(\d+)\.(\d+)\.(\d+)\s*$', text, re.M)
    new = '%s.%s.%d' % (m.group(1), m.group(2), int(m.group(3)) + 1)
    text = text[:m.start()] + 'version=' + new + text[m.end():]
    with open(METADATA, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return new


def deploy():
    """Allinea la copia installata nel profilo QGIS 4 al sorgente. Ritorna i file cambiati."""
    if not os.path.isdir(PLUGINS_DIR):
        print('--  cartella dei plugin di QGIS 4 non trovata: %s' % PLUGINS_DIR)
        return None
    wanted = source_files()
    changed = []
    for rel in wanted:
        src, dst = os.path.join(SRC, rel), os.path.join(INSTALLED, rel)
        if not os.path.isfile(dst) or not filecmp.cmp(src, dst, shallow=False):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            changed.append(rel)
    if os.path.isdir(INSTALLED):
        for d, dirs, files in os.walk(INSTALLED):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for f in files:
                rel = os.path.relpath(os.path.join(d, f), INSTALLED).replace(os.sep, '/')
                if rel not in wanted and not f.endswith('.pyc'):
                    os.remove(os.path.join(d, f))
                    changed.append(rel + ' (rimosso)')
    return changed


def status():
    src, zipped, inst = read_version(METADATA), zip_version(ZIP), read_version(os.path.join(INSTALLED, 'metadata.txt'))
    print('== versioni')
    print('sorgente    %s' % src)
    print('zip         %s' % (zipped or 'assente'))
    print('installata  %s   (%s)' % (inst or 'assente', INSTALLED))
    same = inst is not None and all(
        os.path.isfile(os.path.join(INSTALLED, r)) and filecmp.cmp(os.path.join(SRC, r), os.path.join(INSTALLED, r), shallow=False)
        for r in source_files())
    aligned = src == zipped == inst and same
    print('ALLINEATO' if aligned else 'NON ALLINEATO: esegui "python qgis_dev.py"')
    return aligned


def backup(version):
    """Zip installabile con la versione nel nome + copia datata di questa cartella, in Documenti\\copia_backup
    (cambia con SCALING_BACKUP_DIR, la stessa variabile di dev.py)."""
    dest = os.environ.get('SCALING_BACKUP_DIR') or os.path.join(os.path.dirname(os.path.dirname(HERE)), 'copia_backup')
    try:
        os.makedirs(os.path.join(dest, 'installazione'), exist_ok=True)
        zip_copy = os.path.join(dest, 'installazione', '%s_v%s.zip' % (NAME, version))
        shutil.copy2(ZIP, zip_copy)
        folder = os.path.join(dest, 'webodm2QGIS-tools_' + time.strftime('%Y%m%d_%H%M%S'))
        shutil.copytree(HERE, folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '_gui_out'))
        print('== backup zip:    ' + zip_copy)
        print('== backup codice: ' + folder)
    except OSError as e:
        print('!!  backup non riuscito: %s' % e)


def gui():
    import run_qgis
    out = os.path.join(HERE, 'tests', '_gui_out')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    code = run_qgis.run_gui(os.path.join(HERE, 'tests', 'smoke_gui.py'), os.path.join(out, 'profilo'),
                            {'W2Q_OUT': out}, timeout=300)
    rep = os.path.join(out, 'report.json')
    if os.path.isfile(rep):
        import json
        data = json.load(open(rep, encoding='utf-8'))
        for m in data['ok']:
            print('OK  ' + m)
        for m in data['fail']:
            print('FAIL ' + m)
        print('schermate in ' + out)
        return 1 if data['fail'] else 0
    print('nessun rapporto: la prova non e\' partita (codice %s)' % code)
    return 1


def shots():
    """Schermate per la guida: il test nel QGIS vero, una volta per lingua, poi copia i PNG in docs/img_<lingua>."""
    import run_qgis
    names = ('finestra_qgis', 'dlg_server', 'dlg_sessione', 'dlg_picker', 'dock_prodotti', 'dlg_crs', 'pannello_foto',
             'dock_scatti', 'visualizzatore_scatto', 'dock_posiziona', 'dlg_about')
    for lang in ('it', 'en'):
        out = os.path.join(HERE, 'tests', '_gui_out_' + lang)
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        run_qgis.run_gui(os.path.join(HERE, 'tests', 'smoke_gui.py'), os.path.join(out, 'profilo'),
                         {'W2Q_OUT': out, 'W2Q_LANG': lang}, timeout=300)
        dest = os.path.join(HERE, 'docs', 'img_' + lang)
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest)
        missing = []
        for n in names:
            src = os.path.join(out, n + '.png')
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dest, n + '.png'))
            else:
                missing.append(n)
        print('%s: %d schermate in %s%s' % (lang, len(names) - len(missing), dest,
                                            ('  (mancano: %s)' % ', '.join(missing)) if missing else ''))
        shutil.rmtree(out, ignore_errors=True)
    return 0


def main():
    sys.stdout.reconfigure(line_buffering=True)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = set(a for a in sys.argv[1:] if a.startswith('--'))
    cmd = args[0] if args else 'run'
    if cmd not in ('run', 'check', 'build', 'status', 'gui', 'shots') or flags - {'--no-bump', '--no-tests'}:
        print(__doc__)
        return 2
    if cmd == 'status':
        return 0 if status() else 1
    if cmd == 'gui':
        return gui()
    if cmd == 'shots':
        return shots()

    check(run_tests='--no-tests' not in flags)
    if cmd == 'check':
        return 0

    version = read_version(METADATA) if '--no-bump' in flags else bump()
    write_zip(ZIP)
    print('== versione %s -> %s' % (version, os.path.basename(ZIP)))
    backup(version)
    if cmd == 'build':
        return 0

    changed = deploy()
    if changed is None:
        return 0
    print('== QGIS 4 aggiornato (%d file)' % len(changed))
    for rel in changed[:30]:
        print('   ' + rel)
    print('!!  In QGIS: Plugin > Gestisci e installa plugin > Installati > attiva "WebODM2QGIS-tools".')
    print('    Se era gia\' attivo: ricaricalo con il plugin "Plugin Reloader" (gia\' installato) o riavvia QGIS.')
    status()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print('FALLITO: %s' % ' '.join(str(x) for x in e.cmd[:2]))
        print('Niente e\' stato modificato: versione, zip e QGIS sono rimasti come prima.')
        sys.exit(1)
    except SyntaxError as e:
        print('FALLITO: errore di sintassi in %s riga %s: %s' % (e.filename, e.lineno, e.msg))
        sys.exit(1)
