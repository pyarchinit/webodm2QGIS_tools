"""Esegue uno script con il Python di QGIS 4 in un ambiente PULITO.

Serve perche' il PYTHONPATH utente (site-packages di un altro Python) e le variabili di PostgreSQL/PostGIS
(PROJ_LIB, GDAL_DATA...) fanno fallire `import qgis._core` ("DLL load failed"). Uso:
    python run_qgis.py tests/test_integration.py [argomenti]
"""
import os
import subprocess
import sys

QGIS_ROOTS = [os.environ.get('QGIS4_ROOT', ''), r'C:\Program Files\QGIS 4.2.2']
POISON = ('PYTHONPATH', 'PYTHONHOME', 'GDAL_DATA', 'GDAL_DRIVER_PATH', 'PROJ_LIB', 'PROJ_DATA', 'CURL_CA_BUNDLE',
          'POSTGIS_GDAL_ENABLED_DRIVERS', 'QGIS_PREFIX_PATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR')


def find_qgis():
    for r in QGIS_ROOTS:
        if r and os.path.isfile(os.path.join(r, 'bin', 'python-qgis.bat')):
            return r
    return None


def clean_env():
    env = dict(os.environ)
    for k in POISON:
        env.pop(k, None)
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    return env


def run(args):
    root = find_qgis()
    if root is None:
        print('QGIS 4 non trovato (imposta QGIS4_ROOT)')
        return 2
    bat = os.path.join(root, 'bin', 'python-qgis.bat')
    cmd = 'call "%s" %s' % (bat, ' '.join('"%s"' % a for a in args))
    return subprocess.call(cmd, shell=True, env=clean_env())


def run_gui(script, profile_dir, extra_env=None, timeout=240):
    """Avvia QGIS 4 vero (senza finestra visibile: piattaforma 'offscreen'), con un profilo vuoto, ed esegue
    `script` con --code. Lo script deve chiudere QGIS da solo. Restituisce il codice di uscita."""
    root = find_qgis()
    if root is None:
        print('QGIS 4 non trovato (imposta QGIS4_ROOT)')
        return 2
    env = clean_env()
    env.update(extra_env or {})
    os.makedirs(profile_dir, exist_ok=True)
    bat = os.path.join(profile_dir, 'avvia_qgis.bat')
    with open(bat, 'w') as f:
        f.write('@echo off\r\n'
                'call "%(r)s\\bin\\o4w_env.bat" >nul\r\n'
                'call "%(r)s\\bin\\qt6_env.bat" >nul\r\n'
                'path %%OSGEO4W_ROOT%%\\apps\\qgis\\bin;%%PATH%%\r\n'
                'set "QGIS_PREFIX_PATH=%%OSGEO4W_ROOT:\\=/%%/apps/qgis"\r\n'
                'set "QT_PLUGIN_PATH=%%OSGEO4W_ROOT%%\\apps\\qgis\\qtplugins;%%OSGEO4W_ROOT%%\\apps\\qt6\\plugins"\r\n'
                '"%%OSGEO4W_ROOT%%\\bin\\qgis-bin.exe" --nologo --noversioncheck --profiles-path "%(p)s" --code "%(s)s"\r\n'
                % {'r': root, 'p': profile_dir, 's': script})
    env['W2Q_ROOT'] = os.path.dirname(os.path.abspath(__file__))     # --code non definisce __file__
    proc = subprocess.Popen(['cmd', '/c', bat], env=env)
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print('QGIS non si e\' chiuso entro %d s: lo termino' % timeout)
        subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        return 3


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--gui':
        sys.exit(run_gui(os.path.abspath(sys.argv[2]), os.path.join(os.environ.get('TEMP', '.'), 'w2q_profile')))
    sys.exit(run(sys.argv[1:]))
