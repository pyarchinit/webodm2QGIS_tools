"""Ogni testo T('...') del plugin ha la traduzione inglese e gli stessi segnaposto.
    python tests/test_i18n.py            controlla
    python tests/test_i18n.py --missing  stampa le righe da aggiungere a i18n_en.py"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(os.path.dirname(HERE), 'webodm2qgis_tools')
sys.path.insert(0, os.path.dirname(HERE))

from webodm2qgis_tools.i18n_en import EN                     # noqa: E402
from webodm2qgis_tools import i18n                           # noqa: E402
from webodm2qgis_tools.core import catalog                   # noqa: E402

PLACE = re.compile(r'\{(\w+)(?::[^}]*)?\}')


def keys_in_code():
    found = {}
    for d, _dirs, files in os.walk(PKG):
        for f in files:
            if not f.endswith('.py') or f == 'i18n_en.py':
                continue
            path = os.path.join(d, f)
            tree = ast.parse(open(path, encoding='utf-8').read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'T' and node.args:
                    a = node.args[0]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        found[a.value] = '%s:%d' % (f, node.lineno)
                    elif isinstance(a, ast.BinOp) or isinstance(a, ast.JoinedStr):
                        pass
                    elif isinstance(a, ast.Name) and f == 'catalog.py':
                        pass
    for label, _g, _k in catalog.ASSETS.values():
        found[label] = 'catalog.ASSETS'
    for n in ('georeferenced_model.laz', 'scaled_model.laz'):
        found[catalog.plugin_export_label(n)] = 'catalog.plugin_export_label'
    return found


def main():
    found = keys_in_code()
    missing = sorted(k for k in found if k not in EN)
    bad = []
    for k, v in EN.items():
        if set(PLACE.findall(k)) != set(PLACE.findall(v)):
            bad.append(k)
    unused = sorted(k for k in EN if k not in found)
    lang_fail = []
    for code, tab in i18n.tables().items():
        for k in found:
            if k not in tab:
                lang_fail.append('%s: manca %r' % (code, k))
            elif set(PLACE.findall(k)) != set(PLACE.findall(tab[k])):
                lang_fail.append('%s: segnaposto diversi in %r -> %r' % (code, k, tab[k]))
            elif k.count('<b>') != tab[k].count('<b>'):
                lang_fail.append('%s: tag HTML diversi in %r' % (code, k))

    if '--missing' in sys.argv:
        for k in missing:
            print('    %r: %r,   # %s' % (k, '', found[k]))
        return 0
    for k in missing:
        print('FAIL senza traduzione inglese (%s): %r' % (found[k], k))
    for k in bad:
        print('FAIL segnaposto diversi tra italiano e inglese: %r' % k)
    for k in unused[:20]:
        print('nota: traduzione non piu\' usata: %r' % k)
    for m in lang_fail[:40]:
        print('FAIL', m)
    ok = not missing and not bad and not lang_fail
    print('test_i18n: %s (%d testi, %d tradotti)' % ('tutto ok' if ok else 'FALLITO', len(found), len(found) - len(missing)) + ' - lingue: en + ' + ', '.join(i18n.tables()))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
