"""Finto server WebODM per i test: stesse rotte (JWT, progetti, task, download con Range, immagini, plugin)."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = 'tok-di-prova'
PID = 7


class FakeWebODM:
    def __init__(self, tasks, files, images=(), plugin=True, ortho=None, export=None, transform=None,
                 georef=None, user='admin', password='admin'):
        """tasks: lista di dict (come l'API). files: {(task_id, nome): bytes} per download/ e assets/.
        images: {nome: bytes} foto originali presenti. ortho/export: risposte del plugin per task."""
        self.tasks, self.files, self.images = tasks, files, dict(images)
        self.plugin, self.ortho, self.export, self.transform = plugin, ortho or {}, export or {}, transform or {}
        self.georef = georef or {}
        self.user, self.password = user, password
        self.log = []                   # (metodo, percorso, Range)
        self.lock = threading.Lock()
        outer = self

        class H(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *a):
                pass

            def _send(self, code, body=b'', ctype='application/json', extra=None):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers.get('Content-Length') or 0)
                body = self.rfile.read(n)
                with outer.lock:
                    outer.log.append(('POST', self.path, None))
                if self.path.rstrip('/') == '/api/token-auth':
                    try:
                        d = json.loads(body)
                    except ValueError:
                        return self._send(400, {'error': 'x'})
                    if d.get('username') == outer.user and d.get('password') == outer.password:
                        return self._send(200, {'token': TOKEN})
                    return self._send(400, {'non_field_errors': ['Unable to log in']})
                self._send(404, {'detail': 'x'})

            def do_GET(self):
                path = self.path.split('?')[0]
                rng = self.headers.get('Range')
                with outer.lock:
                    outer.log.append(('GET', self.path, rng))
                if self.headers.get('Authorization') != 'JWT ' + TOKEN:
                    return self._send(401, {'detail': 'auth'})
                if path == '/api/projects/':
                    return self._send(200, [{'id': PID, 'name': 'Rilievo test', 'description': '',
                                             'tasks': [t['id'] for t in outer.tasks]}])
                m = re.match(r'^/api/projects/(\d+)/tasks/$', path)
                if m:
                    return self._send(200, outer.tasks)
                m = re.match(r'^/api/projects/(\d+)/tasks/([0-9a-f-]+)/$', path)
                if m:
                    t = next((t for t in outer.tasks if t['id'] == m.group(2)), None)
                    return self._send(200, t) if t else self._send(404, {'detail': 'nf'})
                m = re.match(r'^/api/projects/\d+/tasks/([0-9a-f-]+)/orthophoto/tiles\.json$', path)
                if m:
                    return self._send(200, {'maxzoom': 20})
                m = re.match(r'^/api/projects/\d+/tasks/([0-9a-f-]+)/images/(download|thumbnail)/(.+)$', path)
                if m:
                    data = outer.images.get(m.group(3))
                    return self._file(data)
                m = re.match(r'^/api/projects/\d+/tasks/([0-9a-f-]+)/(?:download|assets)/(.+)$', path)
                if m:
                    data = outer.files.get((m.group(1), m.group(2)))
                    return self._file(data, rng)
                m = re.match(r'^/api/plugins/webodm-model-tools/task/([0-9a-f-]+)/(export|ortho|transform|georef)$', path)
                if m:
                    if not outer.plugin:
                        return self._send(404, {'detail': 'nf'})
                    tid, what = m.groups()
                    store = {'export': outer.export, 'ortho': outer.ortho, 'transform': outer.transform,
                             'georef': outer.georef}[what]
                    default = {'export': {'state': 'idle', 'files': []}, 'ortho': {'state': 'idle', 'results': []},
                               'transform': {'transform': None}, 'georef': {'georef': None}}[what]
                    return self._send(200, store.get(tid, default))
                self._send(404, {'detail': 'nf'})

            def _file(self, data, rng=None):
                if data is None:
                    return self._send(404, {'detail': 'nf'})
                if rng:
                    m = re.match(r'bytes=(\d+)-', rng)
                    start = int(m.group(1)) if m else 0
                    if start >= len(data):
                        return self._send(416, b'', 'application/octet-stream')
                    chunk = data[start:]
                    return self._send(206, chunk, 'application/octet-stream',
                                      {'Content-Range': 'bytes %d-%d/%d' % (start, len(data) - 1, len(data))})
                self._send(200, data, 'application/octet-stream')

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.url = 'http://127.0.0.1:%d' % self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def count(self, needle):
        with self.lock:
            return sum(1 for _m, p, _r in self.log if needle in p)

    def ranges(self):
        with self.lock:
            return [r for _m, _p, r in self.log if r]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
