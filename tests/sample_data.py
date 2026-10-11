"""Dati di prova: un finto WebODM con tre task (georiferito, non georiferito, in elaborazione)."""
import io
import json
import struct
import tempfile
import zipfile
import os

from osgeo import gdal, osr
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice
from qgis.PyQt.QtGui import QImage

from fake_webodm import FakeWebODM, PID

gdal.UseExceptions()
osr.UseExceptions()
TMP = tempfile.mkdtemp(prefix='w2q_data_')


def make_tif(epsg=None, w=64, h=64):
    path = os.path.join(TMP, 'src_%s.tif' % (epsg or 'nocrs'))
    ds = gdal.GetDriverByName('GTiff').Create(path, w, h, 3, gdal.GDT_Byte)
    ds.SetGeoTransform((600000.0, 1.0, 0.0, 5000000.0, 0.0, -1.0))
    if epsg:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(epsg)
        ds.SetProjection(srs.ExportToWkt())
    for b in (1, 2, 3):
        ds.GetRasterBand(b).Fill(80 * b)
    ds = None
    return open(path, 'rb').read()


def make_las(n=200):
    """LAS 1.2, formato 0, senza VLR/CRS."""
    pts = b''.join(struct.pack('<lllHBBbBH', i * 10, (i % 20) * 10, i, 100, 0, 0, 0, 0, 0)[:20] for i in range(n))
    hdr = bytearray(227)
    hdr[0:4] = b'LASF'
    hdr[24], hdr[25] = 1, 2
    struct.pack_into('<H', hdr, 94, 227)
    struct.pack_into('<I', hdr, 96, 227)
    struct.pack_into('<I', hdr, 100, 0)
    hdr[104] = 0
    struct.pack_into('<H', hdr, 105, 20)
    struct.pack_into('<I', hdr, 107, n)
    struct.pack_into('<ddd', hdr, 131, 0.01, 0.01, 0.01)
    struct.pack_into('<dddddd', hdr, 179, n * 0.1, 0.0, 0.2 * 10, 0.0, n * 0.01, 0.0)
    return bytes(hdr) + pts


def jpeg(color):
    img = QImage(32, 24, QImage.Format.Format_RGB32)
    img.fill(color)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'JPG')
    return bytes(ba)


def zip_bytes(members):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for k, v in members.items():
            z.writestr(k, v)
    return b.getvalue()


T1 = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa'    # georiferito, completo
T2 = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb'    # non georiferito
T3 = 'cccccccc-3333-4333-8333-cccccccccccc'    # in elaborazione
shots = {'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'properties': {'filename': 'IMG1.jpg', 'camera': 'c', 'width': 4000, 'height': 3000,
                                       'capture_time': 1790844232.5, 'translation': [1, 2, 30], 'rotation': [3.14159, 0, 0]},
     'geometry': {'type': 'Point', 'coordinates': [11.5, 44.5, 31.0]}},
    {'type': 'Feature', 'properties': {'filename': 'IMG2.jpg', 'rotation': [3.14159, 0, 0]},
     'geometry': {'type': 'Point', 'coordinates': [11.6, 44.5, 32.0]}},
    {'type': 'Feature', 'properties': {'filename': '../evil.jpg'}, 'geometry': {'type': 'Point', 'coordinates': [1, 1, 1]}}]}
base_assets = lambda: ['orthophoto.tif', 'dsm.tif', 'georeferenced_model.las', 'shots.geojson', 'textured_model.zip',
                       'report.pdf', 'all.zip']
tasks = [
    {'id': T1, 'name': 'Chiesa', 'status': 40, 'created_at': '2026-10-01', 'images_count': 2, 'epsg': 32632,
     'available_assets': base_assets()},
    {'id': T2, 'name': 'Ponte', 'status': 40, 'created_at': '2026-09-01', 'images_count': 2, 'epsg': None,
     'available_assets': ['orthophoto.tif', 'shots.geojson']},
    {'id': T3, 'name': 'Casa', 'status': 20, 'created_at': '2026-10-05', 'images_count': 2, 'epsg': None,
     'available_assets': []}]
ortho_base = '/api/projects/%d/tasks/%s/assets/scaling_tool/ortho/' % (PID, T1)
files = {
    (T1, 'orthophoto.tif'): make_tif(32632), (T1, 'dsm.tif'): make_tif(32633),
    (T1, 'georeferenced_model.las'): make_las(),
    (T1, 'shots.geojson'): json.dumps(shots).encode(),
    (T1, 'textured_model.zip'): zip_bytes({'odm_texturing/odm_textured_model_geo.obj': 'v 0 0 0\n', 'a.mtl': 'x'}),
    (T1, 'all.zip'): zip_bytes({'../fuori.txt': 'x'}),
    (T1, 'report.pdf'): b'%PDF-1.4 finto',
    (T1, 'scaling_tool/ortho/ortho_front.tif'): make_tif(None),
    (T1, 'scaling_tool/ortho/ortho_front.points'): b'mapX,mapY,sourceX,sourceY,enable\n',
    (T2, 'orthophoto.tif'): make_tif(32632), (T2, 'shots.geojson'): json.dumps(shots).encode(),
}
out_base = '/api/projects/%d/tasks/%s/assets/scaling_tool/out/' % (PID, T1)
files[(T1, 'scaling_tool/out/georeferenced_model.laz')] = make_las(60)
files[(T1, 'scaling_tool/out/scaled_model.laz')] = make_las(60)
export_meta = {'state': 'done', 'files': [
    {'name': 'georeferenced_model.laz', 'url': out_base + 'georeferenced_model.laz'},
    {'name': 'scaled_model.laz', 'url': out_base + 'scaled_model.laz'}]}
ortho_meta = {'results': [{'name': 'ortho_front', 'view': 'front', 'epsg': None, 'title': 'Facciata',
                           'files': [{'name': 'ortho_front.tif', 'url': ortho_base + 'ortho_front.tif'},
                                     {'name': 'ortho_front.points', 'url': ortho_base + 'ortho_front.points'}]}]}
server = FakeWebODM(tasks, files, images={'IMG1.jpg': jpeg(0xff0000ff)}, ortho={T1: ortho_meta},
                    export={T1: export_meta},
                    georef={T1: {'georef': {'epsg': 32632}, 'result': {
                        'epsg': 32632, 'matrix_abs': [[0, -2, 0, 500000], [2, 0, 0, 4000000], [0, 0, 2, 0], [0, 0, 0, 1]]}}},
                    transform={T1: {'transform': {'scale': 2.0, 'matrix': [[2, 0, 0, 0], [0, 2, 0, 0], [0, 0, 2, 0], [0, 0, 0, 1]]}}})
