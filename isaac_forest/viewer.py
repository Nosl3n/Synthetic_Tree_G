"""Visualizador en tiempo real (Rerun) de los sensores del bosque sintético.

Lee los fotogramas que escribe run_sensors.py (<dir>/frames/*.npz) a medida que
aparecen y muestra:
  - 3D: barrido LiDAR actual coloreado por clase, mapa acumulado (vóxeles), árboles
        "verdad" (esqueleto QSM), trayectoria, plataforma y la cámara con su
        profundidad proyectada en 3D.
  - 2D: RGB, profundidad y segmentación semántica de la cámara.
  - Series: puntos por barrido y por clase.

Uso (entorno .venv_viz):
    .venv_viz/bin/python viewer.py recordings/run0            # en vivo (espera fotogramas nuevos)
    .venv_viz/bin/python viewer.py recordings/run0 --replay   # reproduce una grabación a velocidad real
    .venv_viz/bin/python viewer.py recordings/run0 --replay --web    # en el navegador
    .venv_viz/bin/python viewer.py recordings/run0 --replay --save demo.rrd   # archivo para la exposición
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'synth_trees'))

CLASS_COLORS = {0: ('sin dato', (0, 0, 0)), 1: ('suelo', (150, 125, 80)), 2: ('tronco', (140, 70, 20)),
                3: ('rama', (230, 160, 60)), 4: ('hoja', (40, 200, 70)), 5: ('sotobosque', (60, 210, 90)),
                6: ('madera muerta', (170, 90, 200)), 7: ('roca', (120, 130, 150)), 8: ('otro', (128, 128, 128))}


def blueprint():
    return rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial3DView(origin='world', name='Bosque 3D (LiDAR + cámara)',
                              background=(12, 14, 20)),
            rrb.Vertical(
                rrb.Spatial2DView(origin='world/camera', contents=['world/camera/rgb'], name='RGB'),
                rrb.Spatial2DView(origin='world/camera', contents=['world/camera/depth'], name='Profundidad'),
                rrb.Spatial2DView(origin='world/camera', contents=['world/camera/sem'], name='Semántica'),
                rrb.TimeSeriesView(origin='stats', name='Puntos LiDAR por barrido'),
                row_shares=[3, 3, 3, 2],
            ),
            column_shares=[3, 1.3],
        ),
        rrb.TimePanel(state='collapsed'),
    )


def terrain_z(meta, xy):
    T = meta.get('terrain') or dict(kx=[], ky=[], a=[], ph=[])
    xy = np.asarray(xy)
    z = np.zeros(len(xy))
    for kx, ky, a, ph in zip(T['kx'], T['ky'], T['a'], T['ph']):
        z += a * np.sin(kx * xy[:, 0] + ky * xy[:, 1] + ph)
    return z


def log_static(meta, work):
    rr.log('/', rr.AnnotationContext([(k, n, c) for k, (n, c) in CLASS_COLORS.items()]), static=True)
    rr.log('world', rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    path = np.array(meta['path_xy'])
    zp = terrain_z(meta, path) + 0.05
    rr.log('world/trayectoria', rr.LineStrips3D([np.c_[path, zp]], colors=[(80, 160, 255)],
                                                radii=0.05), static=True)
    # árboles "verdad": eje de cada cilindro QSM, en su posición en la parcela
    try:
        import qsm
    except ImportError:
        return
    for k, t in enumerate(meta['trees']):
        gen = 'recombine' if t['generator'] == 'G2' else 'procedural'
        f = os.path.join(work, 'syn_' + gen, t['tree'] + '.npz')
        if not os.path.exists(f):
            continue
        q = qsm.load_npz(f)
        y = np.radians(t['yaw_deg'])
        R = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
        z0 = terrain_z(meta, [[t['x'], t['y']]])[0] - 0.15
        a = (q.start - q.start[0]) @ R.T + [t['x'], t['y'], z0]
        b = (q.end - q.start[0]) @ R.T + [t['x'], t['y'], z0]
        cls = np.where(q.order == 0, 2, 3)
        rr.log(f'world/arboles_verdad/{t["tree"]}', rr.LineStrips3D(np.stack([a, b], 1), class_ids=cls,
                                                                     radii=np.maximum(q.radius, 0.01)), static=True)


class Map:
    """Mapa acumulado del LiDAR con submuestreo por vóxeles."""

    def __init__(self, voxel):
        self.v = voxel
        self.keys = set()
        self.pts, self.cls = [], []

    def add(self, p, c):
        k = np.floor(p / self.v).astype(np.int64)
        kk = (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)
        _, first = np.unique(kk, return_index=True)
        new = [i for i in first if kk[i] not in self.keys]
        self.keys.update(kk[new].tolist())
        self.pts.append(p[new])
        self.cls.append(c[new])

    def arrays(self):
        return np.concatenate(self.pts), np.concatenate(self.cls)


def log_frame(z, meta, mp, k, map_every):
    t = float(z['t'])
    rr.set_time('sim', duration=t)
    P, L = z['lidar_xyz'], z['lidar_label']
    rr.log('world/lidar/barrido', rr.Points3D(P, class_ids=L, radii=0.03))
    mp.add(P, L)
    if k % map_every == 0:
        mp_p, mp_c = mp.arrays()
        rr.log('world/lidar/mapa', rr.Points3D(mp_p, class_ids=mp_c, radii=0.04))
    M = z['lidar_pose']
    rr.log('world/plataforma', rr.Transform3D(translation=M[:3, 3], mat3x3=M[:3, :3]))
    rr.log('world/plataforma/lidar', rr.Boxes3D(half_sizes=[0.05, 0.05, 0.06], colors=[(255, 200, 0)]))
    C = z['cam_pose']
    rr.log('world/camera', rr.Transform3D(translation=C[:3, 3], mat3x3=C[:3, :3]))
    rr.log('world/camera', rr.Pinhole(focal_length=meta['fx'], width=meta['width'], height=meta['height'],
                                      camera_xyz=rr.ViewCoordinates.RUB, image_plane_distance=1.5))
    rr.log('world/camera/rgb', rr.Image(z['rgb']))
    rr.log('world/camera/depth', rr.DepthImage(z['depth'].astype(np.float32), meter=1.0,
                                               colormap='turbo', depth_range=[0.0, 40.0], point_fill_ratio=0.3))
    rr.log('world/camera/sem', rr.SegmentationImage(z['sem']))
    rr.log('stats/total', rr.Scalars(len(P)))
    for c, name in ((2, 'tronco'), (3, 'rama'), (5, 'sotobosque'), (6, 'madera_muerta'), (7, 'roca')):
        rr.log(f'stats/{name}', rr.Scalars(int((L == c).sum())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--replay', action='store_true', help='reproducir lo ya grabado (no esperar más)')
    ap.add_argument('--speed', type=float, default=1.0, help='velocidad de reproducción')
    ap.add_argument('--web', action='store_true', help='visor en el navegador en vez de ventana nativa')
    ap.add_argument('--save', help='guardar a un archivo .rrd en vez de mostrar')
    ap.add_argument('--voxel', type=float, default=0.15)
    ap.add_argument('--map-every', type=int, default=5)
    ap.add_argument('--work', default=os.path.join(HERE, '..', 'synth_trees', 'work'))
    args = ap.parse_args()

    rr.init('Synthetic_Tree_G bosque sintetico', spawn=not (args.web or args.save), default_blueprint=blueprint())
    if args.save:
        rr.save(args.save, default_blueprint=blueprint())
    elif args.web:
        rr.serve_web_viewer(connect_to=rr.serve_grpc())
    meta_f = os.path.join(args.dir, 'meta.json')
    while not os.path.exists(meta_f):
        time.sleep(0.2)
    meta = json.load(open(meta_f))
    log_static(meta, args.work)
    mp = Map(args.voxel)
    done, k = set(), 0
    wall0 = sim0 = None
    while True:
        files = [f for f in sorted(glob.glob(os.path.join(args.dir, 'frames', '*.npz')))
                 if f not in done and not f.endswith('.tmp.npz')]
        if not files:
            if args.replay:
                break
            time.sleep(0.03)
            continue
        if not args.replay:
            files = files[-3:]          # en vivo: ir siempre a lo último si el visor se atrasa
        for f in files:
            done.add(f)
            try:
                z = np.load(f)
                if args.replay and not args.save:
                    t = float(z['t'])
                    if wall0 is None:
                        wall0, sim0 = time.time(), t
                    lag = (t - sim0) / args.speed - (time.time() - wall0)
                    if lag > 0:
                        time.sleep(lag)
                log_frame(z, meta, mp, k, args.map_every)
                k += 1
            except (OSError, ValueError, KeyError, EOFError):
                done.discard(f)         # aún escribiéndose: se reintenta
    print(f'{k} fotogramas visualizados')
    if args.web:
        input('Visor web activo; Enter para salir...')


if __name__ == '__main__':
    main()
