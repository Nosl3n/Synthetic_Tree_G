"""Capturas del bosque sintético desde varias vistas (render RTX de Isaac Sim).

    $ISAAC_PY tools/screenshots.py --scene scenes/forest_v2_bosque.usd --out screenshots/v2_bosque
"""
import argparse
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument('--scene', default='scenes/forest_v2_bosque.usd')
ap.add_argument('--out', default='screenshots')
ap.add_argument('--res', type=int, nargs=2, default=[900, 1600], help='alto ancho')
ap.add_argument('--warmup', type=int, default=40, help='fotogramas para que converja la iluminación')
args = ap.parse_args()

from isaacsim.simulation_app import SimulationApp  # noqa: E402

app = SimulationApp({'headless': True})

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, Usd  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import dressing as DR  # noqa: E402


def look_at(eye, target):
    """Cuaternión wxyz de una cámara USD (mira a -Z, +Y arriba) en `eye` mirando a `target`."""
    f = np.asarray(target, float) - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0])
    r = r / np.linalg.norm(r) if np.linalg.norm(r) > 1e-6 else np.array([1.0, 0, 0])
    u = np.cross(r, f)
    q = Rotation.from_matrix(np.column_stack([r, u, -f])).as_quat()
    return [q[3], q[0], q[1], q[2]]


def main():
    os.makedirs(args.out, exist_ok=True)
    stage_utils.open_stage(os.path.abspath(args.scene))
    stage = stage_utils.get_current_stage()
    info = json.load(open(os.path.splitext(args.scene)[0] + '_trees.json'))
    trees = info['trees']
    g2 = max((t for t in trees if t['generator'] == 'G2'), key=lambda t: t['height'])
    g4 = max((t for t in trees if t['generator'] == 'G4'), key=lambda t: t['height'])
    near = min(trees, key=lambda t: np.hypot(t['x'], t['y']))

    def side(t, dist, z_eye, z_tgt):
        a = np.radians(t['yaw_deg'] + 90)
        return ([t['x'] + dist * np.cos(a), t['y'] + dist * np.sin(a), z_eye], [t['x'], t['y'], z_tgt])

    views = {
        '01_aerea': ([-48, -42, 38], [0, 0, 8], 20.0),
        '02_cenital': ([0.01, 0, 85], [0, 0, 0], 18.0),
        '03_a_pie_entre_arboles': ([-4, -16, 1.7], [6, 10, 6], 14.0),
        f'04_arbol_G2_{g2["species"]}': (*side(g2, 30, 12, g2['height'] * 0.5), 18.0),
        f'05_arbol_G4_{g4["species"]}': (*side(g4, 30, 12, g4['height'] * 0.5), 18.0),
        '06_mirando_la_copa': ([near['x'] + 4, near['y'] - 3, 1.5], [near['x'], near['y'], near['height'] * 0.75], 12.0),
        '07_lateral_bosque': ([0, -55, 14], [0, 0, 14], 22.0),
    }
    T = info.get('terrain')
    if T:
        # alturas relativas al terreno; vista extra desde el sendero de la plataforma
        lift = lambda p: [p[0], p[1], p[2] + float(DR.terrain_height(T, p[0], p[1]))]
        views = {k: (lift(e), lift(g), f) for k, (e, g, f) in views.items()}
        loop = np.array(info['path_xy'])
        i = len(loop) // 6
        e = [*loop[i], 1.6]
        g = [*(loop[i] + 8 * (loop[i + 3] - loop[i]) / np.linalg.norm(loop[i + 3] - loop[i])), 2.5]
        views['08_sendero'] = (lift(e), lift(g), 12.0)
    H, W = args.res
    cam = RtxCamera('/World/ShotCam', translations=[[0, 0, 0]], orientations=[[1, 0, 0, 0]])
    cam.camera.set_apertures(horizontal_apertures=20.955, vertical_apertures=20.955 * H / W)
    cam.camera.set_clipping_ranges(0.1, 500.0)
    sens = CameraSensor(cam, resolution=(H, W), annotators=['rgb'])
    prim = stage.GetPrimAtPath('/World/ShotCam')
    app_utils.play(commit=True)
    for name, (eye, tgt, focal) in views.items():
        q = look_at(np.asarray(eye, float), tgt)
        prim.GetAttribute('xformOp:translate').Set(Gf.Vec3d(*eye))
        orient = prim.GetAttribute('xformOp:orient')
        orient.Set(type(orient.Get())(q[0], Gf.Vec3d(*q[1:])) if orient.Get() is not None
                   else Gf.Quatd(q[0], *q[1:]))
        cam.camera.set_focal_lengths(focal)
        for _ in range(args.warmup):
            app.update()
        rgb, _ = sens.get_data('rgb')
        Image.fromarray(rgb.numpy()[..., :3]).save(os.path.join(args.out, name + '.png'))
        print('OK', name, flush=True)
    app.close()


if __name__ == '__main__':
    main()
