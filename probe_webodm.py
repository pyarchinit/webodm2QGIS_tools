#!/usr/bin/env python3
"""Prova in sola lettura le rotte che usa il plugin QGIS contro un WebODM VERO (spike della fase 0).

    python probe_webodm.py http://localhost:29800 admin [password]

Se la password manca la chiede. Non scrive nulla sul server. Stampa per ogni rotta: stato HTTP e una riga di
sintesi, e a fine corsa dice cosa non coincide con le ipotesi del plugin.
"""
import getpass
import json
import sys
import urllib.error
import urllib.request


def call(base, path, token=None, data=None, method=None, limit=None):
    req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                                 method=method)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'JWT ' + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(limit) if limit else r.read()
            return r.status, body, r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(300), e.headers
    except urllib.error.URLError as e:
        return 0, str(e).encode(), {}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    base, user = sys.argv[1].rstrip('/'), sys.argv[2]
    pw = sys.argv[3] if len(sys.argv) > 3 else getpass.getpass('Password: ')
    problems = []
    st, body, _ = call(base, '/api/token-auth/', data={'username': user, 'password': pw})
    print('POST /api/token-auth/            ->', st)
    if st != 200:
        print('login fallito: %s' % body[:200])
        return 1
    token = json.loads(body)['token']
    st, body, _ = call(base, '/api/projects/', token)
    projects = json.loads(body) if st == 200 else []
    print('GET  /api/projects/              ->', st, '(%s)' % type(projects).__name__, len(projects), 'progetti')
    if isinstance(projects, dict):
        problems.append('/api/projects/ e\' paginato: il plugin gestisce {"results": [...]} ma controlla')
    for p in (projects if isinstance(projects, list) else projects.get('results', []))[:5]:
        print('   progetto %s: %s' % (p['id'], p['name']))
        st, body, _ = call(base, '/api/projects/%s/tasks/' % p['id'], token)
        tasks = json.loads(body) if st == 200 else []
        tasks = tasks if isinstance(tasks, list) else tasks.get('results', [])
        for t in tasks[:6]:
            print('     task %s  %-24s status=%s epsg=%s foto=%s assets=%d' % (
                t['id'][:8], (t.get('name') or '')[:24], t.get('status'), t.get('epsg'), t.get('images_count'),
                len(t.get('available_assets') or [])))
            if t.get('status') != 40:
                continue
            tp = '/api/projects/%s/tasks/%s' % (p['id'], t['id'])
            for asset in ('shots.geojson',):
                if asset in (t.get('available_assets') or []):
                    st, body, _ = call(base, tp + '/download/' + asset, token)
                    try:
                        g = json.loads(body)
                        f0 = g['features'][0]
                        keys = sorted(f0['properties'])
                        print('       shots.geojson -> %d feature, proprieta: %s' % (len(g['features']), ', '.join(keys)))
                        for need in ('filename', 'translation', 'rotation'):
                            if need not in keys:
                                problems.append('shots.geojson senza "%s"' % need)
                        fn = f0['properties']['filename']
                        st, _b, h = call(base, tp + '/images/thumbnail/' + fn + '?size=64', token, limit=4)
                        print('       images/thumbnail/%s -> %s' % (fn, st))
                        st, _b, h = call(base, tp + '/images/download/' + fn, token, limit=4)
                        print('       images/download/%s  -> %s  Content-Length=%s' % (fn, st, h.get('Content-Length')))
                        if st not in (200, 404):
                            problems.append('images/download risponde %s' % st)
                    except (ValueError, KeyError, IndexError):
                        problems.append('shots.geojson non leggibile (stato %s)' % st)
            for name in ('export', 'ortho', 'transform'):
                st, body, _ = call(base, '/api/plugins/webodm-model-tools/task/%s/%s' % (t['id'], name), token)
                print('       plugin webodm-model-tools/%s -> %s' % (name, st))
            break
    print()
    print('PROBLEMI:' if problems else 'Nessuna differenza dalle ipotesi del plugin.')
    for p in problems:
        print(' -', p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
