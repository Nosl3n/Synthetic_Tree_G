"""Recorrido de una plataforma con LiDAR + cámara de profundidad por el bosque sintético.

La plataforma (/World/Rig) sigue un circuito cerrado entre los árboles a velocidad
de paseo. Lleva:
  - LiDAR rotatorio Ouster OS1 (128 canales, 10 Hz, 1024 columnas) a 1,8 m.
  - Cámara RGB-D con la óptica de una Intel RealSense D455 (87° x 58°, 848x480) a 1,2 m.

Cada ~0,1 s se guarda un fotograma en <out>/frames/NNNNNN.npz (escritura atómica),
que es lo que lee el visualizador en tiempo real (viewer.py). Contenido:
  lidar_xyz (N,3) mundo · lidar_xyz_sensor · lidar_intensity · lidar_label · lidar_tree
  rgb (H,W,3) · depth (H,W) float16 [m] · sem (H,W) uint8 · pose de la plataforma, LiDAR y cámara.

Uso (entorno de Isaac Sim):
    export OMNI_KIT_ACCEPT_EULA=YES
    $ISAAC_PY run_sensors.py --scene scenes/forest_v2_bosque.usd --duration 84 --out recordings/v2_bosque
    $ISAAC_PY run_sensors.py --gui --duration 0       # ventana, bucle infinito
"""
import argparse
import json
import os
import re
import time

ap = argparse.ArgumentParser()
ap.add_argument('--scene', default='scenes/forest_v2_bosque.usd')
ap.add_argument('--out', default='recordings/run0')
ap.add_argument('--duration', type=float, default=60.0, help='segundos simulados (0 = sin fin)')
ap.add_argument('--speed', type=float, default=1.0, help='m/s')
ap.add_argument('--dt', type=float, default=1 / 60, help='paso de simulación (s)')
ap.add_argument('--rate', type=float, default=10.0, help='fotogramas guardados por segundo')
ap.add_argument('--lidar-variant', default='OS1_REV6_128ch10hz1024res')
ap.add_argument('--res', type=int, nargs=2, default=[480, 848], help='alto ancho de la cámara')
ap.add_argument('--keep', type=int, default=0, help='guardar solo los últimos K fotogramas (0 = todos)')
ap.add_argument('--gui', action='store_true')
args = ap.parse_args()

from isaacsim.simulation_app import SimulationApp  # noqa: E402

app = SimulationApp({'headless': not args.gui, 'width': 1600, 'height': 900})

import numpy as np  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from isaacsim.sensors.experimental.rtx import (CameraSensor, Lidar, LidarSensor, RtxCamera,  # noqa: E402
                                               parse_generic_model_output_data, parse_object_ids,
                                               parse_stable_id_map_data)
from pxr import Gf, Usd, UsdGeom  # noqa: E402
import dressing as DR  # noqa: E402

# índices de lidar_label y sem ('leaf' queda reservada para una versión futura con hojas)
CLASSES = ['none', 'ground', 'trunk', 'branch', 'leaf', 'understory', 'deadwood', 'rock', 'other']
SEM_ID = {c: i for i, c in enumerate(CLASSES)}
# nombre de la malla -> clase (las ramitas de los brotes cuentan como rama)
TREE_RE = re.compile(r'/Trees/tree_(\d+)/|/OuterTrees/outer_(\d+)/')


def tree_of(path):
    """Índice del árbol alcanzado: 0-23 parcela, 100+ anillo exterior, -1 si no es un árbol."""
    m = TREE_RE.search(path)
    return -1 if m is None else int(m.group(1)) if m.group(1) else 100 + int(m.group(2))


def class_of(path):
    """Clase de un retorno LiDAR a partir de la ruta USD del objeto alcanzado."""
    for key, c in (('/Understory/', 5), ('/Deadwood/', 6), ('/Rocks/', 7), ('/Ground', 1)):
        if key in path:
            return c
    leaf = path.rsplit('/', 1)[-1].split('_')[0]
    return {'trunk': 2, 'branch': 3, 'twigs': 3, 'leaves': 4}.get(leaf, 8)
CAM_Q = [0.5, 0.5, -0.5, -0.5]      # wxyz: la cámara (mira a -Z) apunta a +X de la plataforma, +Y arriba
LIDAR_H, CAM_H = 1.8, 1.2
HFOV = 87.0                         # Intel RealSense D455 (profundidad)


def world_matrix(prim):
    """Matriz 4x4 local->mundo en convención columna (p_w = M @ p)."""
    m = UsdGeom.XformCache(Usd.TimeCode.Default()).GetLocalToWorldTransform(prim)
    return np.array(m, float).T


def save_atomic(path, **data):
    tmp = path + '.tmp.npz'
    np.savez_compressed(tmp, **data)
    os.replace(tmp, path)


def main():
    out = os.path.abspath(args.out)
    os.makedirs(os.path.join(out, 'frames'), exist_ok=True)
    stage_utils.open_stage(os.path.abspath(args.scene))
    stage = stage_utils.get_current_stage()
    info = json.load(open(os.path.splitext(args.scene)[0] + '_trees.json'))
    if 'path_xy' in info:                       # escena con ambientación: circuito y terreno guardados
        P = np.array(info['path_xy'])
        T = info['terrain']
    else:
        P = DR.plan_loop([[t['x'], t['y']] for t in info['trees']], info['plot'] / 2)
        T = dict(kx=[], ky=[], a=[], ph=[])
    s = DR.path_lengths(P)

    rig = UsdGeom.Xform.Define(stage, '/World/Rig')
    op_t = rig.AddTranslateOp()
    op_r = rig.AddRotateZOp()
    lidar = Lidar.create(path='/World/Rig/lidar', config='OS1', variant=args.lidar_variant,
                         aux_output_level='FULL', tick_rate=10.0, accumulate_outputs=True,
                         translations=[[0.0, 0.0, LIDAR_H]])
    lsens = LidarSensor(lidar, annotators=['generic-model-output', 'stable-id-map'])
    H, W = args.res
    cam = RtxCamera('/World/Rig/depth_cam', tick_rate=30.0, translations=[[0.15, 0.0, CAM_H]],
                    orientations=[CAM_Q])
    hap = 20.955
    focal = hap / 2 / np.tan(np.radians(HFOV / 2))
    cam.camera.set_focal_lengths(focal)
    cam.camera.set_apertures(horizontal_apertures=hap, vertical_apertures=hap * H / W)
    cam.camera.set_clipping_ranges(0.1, 80.0)
    csens = CameraSensor(cam, resolution=(H, W),
                         annotators=['rgb', 'distance_to_image_plane', 'semantic_segmentation'])
    if args.gui:
        lsens.attach_writer('draw-point-cloud', size=0.04, color=[0.1, 1.0, 0.4, 1.0])

    lidar_prim = next(p for p in Usd.PrimRange(stage.GetPrimAtPath('/World/Rig/lidar'))
                      if p.GetTypeName() == 'OmniLidar')
    cam_prim = stage.GetPrimAtPath('/World/Rig/depth_cam')
    fx = focal / hap * W
    meta = dict(classes=CLASSES, scene=os.path.abspath(args.scene), lidar=f'Ouster OS1 {args.lidar_variant}',
                lidar_height=LIDAR_H, camera='RGB-D (óptica Intel RealSense D455)', camera_height=CAM_H,
                width=W, height=H, fx=fx, fy=fx, cx=W / 2, cy=H / 2, hfov_deg=HFOV,
                speed=args.speed, rate=args.rate, path_xy=P.tolist(), trees=info['trees'], terrain=T)
    json.dump(meta, open(os.path.join(out, 'meta.json'), 'w'), indent=1)

    app_utils.play(commit=True)
    t, k, last_scan, last_save = 0.0, 0, None, -1e9
    scan = None
    id_cache = {}
    wall0 = time.time()
    while app.is_running():
        pos, yaw = DR.pose_at(P, s, args.speed * t)
        op_t.Set(Gf.Vec3d(pos[0], pos[1], float(DR.terrain_height(T, pos[0], pos[1]))))
        op_r.Set(float(np.degrees(yaw)))
        app.update()
        t += args.dt

        # LiDAR: un barrido completo por GMO; se ignoran repeticiones
        d, _ = lsens.get_data('generic-model-output')
        if d is not None and len(d):
            g = parse_generic_model_output_data(d)
            ts = int(g.frameEnd.timestampNs)
            if g.numElements and ts != last_scan:
                last_scan = ts
                az, el, r = (np.radians(np.asarray(g.x)), np.radians(np.asarray(g.y)), np.asarray(g.z))
                hit = r > 0.05
                ps = np.c_[r * np.cos(el) * np.cos(az), r * np.cos(el) * np.sin(az), r * np.sin(el)][hit]
                M = world_matrix(lidar_prim)
                pw = ps @ M[:3, :3].T + M[:3, 3]
                sm, _ = lsens.get_data('stable-id-map')
                if sm is not None and len(sm):
                    id_cache.update(parse_stable_id_map_data(sm))
                ids = np.array(parse_object_ids(np.asarray(g.objId)), dtype=object)[hit]
                paths = [id_cache.get(o, '') for o in ids]
                lab = np.array([class_of(p) for p in paths], np.uint8)
                tree = np.array([tree_of(p) for p in paths], np.int16)
                scan = dict(lidar_xyz=pw.astype(np.float32), lidar_xyz_sensor=ps.astype(np.float32),
                            lidar_intensity=np.asarray(g.scalar)[hit].astype(np.float16),
                            lidar_label=lab, lidar_tree=tree, lidar_pose=M.astype(np.float32),
                            lidar_t=np.float64(t))

        # guardado a ritmo fijo: último barrido + imagen actual
        if t - last_save >= 1 / args.rate - 1e-9 and scan is not None:
            rgb, _ = csens.get_data('rgb')
            dep, _ = csens.get_data('distance_to_image_plane')
            sem, sinfo = csens.get_data('semantic_segmentation')
            if rgb is None or dep is None or sem is None:
                continue
            rgb = rgb.numpy()[..., :3]
            dep = dep.numpy()[..., 0]
            sem = sem.numpy()[..., 0]
            lut = {int(i): v.get('class', '') for i, v in sinfo.get('idToLabels', {}).items()}
            sem_c = np.zeros_like(sem, np.uint8)
            for i, c in lut.items():
                sem_c[sem == i] = SEM_ID.get(c, 0 if c in ('BACKGROUND', '') else SEM_ID['other'])
            dep = np.where(np.isfinite(dep) & (dep < 80), dep, 0).astype(np.float16)
            save_atomic(os.path.join(out, 'frames', f'{k:06d}.npz'), **scan, rgb=rgb, depth=dep, sem=sem_c,
                        cam_pose=world_matrix(cam_prim).astype(np.float32),
                        rig_xy=pos.astype(np.float32), rig_yaw=np.float32(yaw), t=np.float64(t))
            if args.keep and k >= args.keep:
                old = os.path.join(out, 'frames', f'{k - args.keep:06d}.npz')
                if os.path.exists(old):
                    os.remove(old)
            last_save = t
            k += 1
            if k % 50 == 0:
                print(f'[{k} fotogramas] t_sim={t:.1f}s  {k / (time.time() - wall0):.1f} fps guardados  '
                      f'puntos={len(scan["lidar_xyz"])}', flush=True)
        if args.duration and t >= args.duration:
            break
    print(f'FIN: {k} fotogramas en {out}  ({time.time() - wall0:.0f} s reales)')
    app.close()


if __name__ == '__main__':
    main()
